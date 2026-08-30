"""
Group Decision & Voting Engine.
Handles:
- Creating formal proposals (Purchase proposals, member removal, leadership succession, account closure)
- Casting and auditing votes (1 member = 1 vote)
- Evaluating threshold rules (Simple Majority >50%, Two-Thirds >=66.7%, Unanimous 100%)
- Automated execution upon threshold achievement
- Anti-takeover protections & member removal security (revoking sessions while preserving audit logs)
"""
from typing import Dict, Any, Optional
from decimal import Decimal
from django.utils import timezone
from django.db import transaction as db_transaction
from django.contrib.auth import get_user_model
from core.models import Account, AccountMember, AccountDecision, DecisionVote, AccountAuditEvent, UserSession

User = get_user_model()


class DecisionEngine:

    @staticmethod
    def create_proposal(
        account: Account,
        creator: User,
        decision_type: str,
        title: str,
        proposal_text: str,
        proposed_amount: Optional[Decimal] = None,
        target_member: Optional[AccountMember] = None,
        land_parcel: Any = None,
        transaction_obj: Any = None,
        approval_rule: str = 'SIMPLE_MAJORITY',
        deadline: Optional[timezone.datetime] = None,
    ) -> AccountDecision:
        """Create a new formal proposal for group voting."""
        with db_transaction.atomic():
            decision = AccountDecision.objects.create(
                tenant_id=account.tenant_id,
                account=account,
                decision_type=decision_type,
                title=title,
                proposal_text=proposal_text,
                proposed_amount=proposed_amount,
                target_member=target_member,
                land_parcel=land_parcel,
                transaction=transaction_obj,
                approval_rule=approval_rule,
                status='ACTIVE',
                created_by=creator,
                deadline=deadline,
            )

            # Auto-cast the creator's YES vote
            creator_member = AccountMember.objects.filter(account=account, user=creator, status='ACTIVE').first()
            if creator_member:
                DecisionVote.objects.create(
                    decision=decision,
                    voter=creator,
                    account_member=creator_member,
                    vote='APPROVE',
                    comment='Proposal creator auto-vote'
                )

            # Audit event
            AccountAuditEvent.objects.create(
                account=account,
                actor=creator,
                action='DECISION_CREATED',
                resource_type='AccountDecision',
                resource_id=str(decision.id),
                new_state={
                    'decision_type': decision_type,
                    'title': title,
                    'approval_rule': approval_rule,
                    'proposed_amount': str(proposed_amount) if proposed_amount else None,
                }
            )

            # Evaluate immediately in case 1-person group meets threshold
            DecisionEngine.evaluate_and_execute(decision)
            decision.refresh_from_db()
            return decision

    @staticmethod
    def cast_vote(
        decision: AccountDecision,
        voter: User,
        vote_choice: str,
        comment: str = ''
    ) -> Dict[str, Any]:
        """
        Cast a vote on an active proposal.
        Strictly enforces 1 member = 1 vote.
        """
        if decision.status != 'ACTIVE':
            return {
                'success': False,
                'error': f"Voting is closed for this decision (Status: {decision.get_status_display()})"
            }

        member = AccountMember.objects.filter(account=decision.account, user=voter, status='ACTIVE').first()
        if not member:
            return {
                'success': False,
                'error': "Only active members of this account are eligible to vote."
            }

        # Prevent the target of a removal proposal from voting on their own removal if configured
        if decision.decision_type == 'MEMBER_REMOVAL' and decision.target_member and decision.target_member.user == voter:
            # Target member can submit comments/defense but their vote is not eligible
            return {
                'success': False,
                'error': "Members facing a removal proposal cannot vote on their own removal."
            }

        with db_transaction.atomic():
            vote_obj, created = DecisionVote.objects.update_or_create(
                decision=decision,
                voter=voter,
                defaults={
                    'account_member': member,
                    'vote': vote_choice,
                    'comment': comment,
                    'voted_at': timezone.now()
                }
            )

            # Audit log
            AccountAuditEvent.objects.create(
                account=decision.account,
                actor=voter,
                action='VOTE_CAST',
                resource_type='DecisionVote',
                resource_id=str(vote_obj.id),
                metadata={
                    'decision_id': str(decision.id),
                    'decision_title': decision.title,
                    'vote': vote_choice,
                    'comment': comment,
                }
            )

            # Evaluate threshold and trigger execution if met
            outcome = DecisionEngine.evaluate_and_execute(decision)

            return {
                'success': True,
                'vote': vote_choice,
                'decision_status': decision.status,
                'outcome': outcome
            }

    @staticmethod
    def evaluate_and_execute(decision: AccountDecision) -> Dict[str, Any]:
        """
        Evaluates current vote tallies against configured approval rule.
        If threshold is achieved, transitions status to APPROVED and executes action.
        """
        account = decision.account
        eligible_members = account.members.filter(status='ACTIVE')
        
        # In member removal, exclude target from denominator
        if decision.decision_type == 'MEMBER_REMOVAL' and decision.target_member:
            eligible_members = eligible_members.exclude(id=decision.target_member.id)
            
        total_eligible = eligible_members.count()
        if total_eligible == 0:
            total_eligible = 1

        approved_votes = decision.votes.filter(vote='APPROVE').count()
        rejected_votes = decision.votes.filter(vote='REJECT').count()
        rule = decision.approval_rule

        is_approved = False
        is_rejected = False

        if rule == 'SIMPLE_MAJORITY':
            # > 50% of total eligible voters
            threshold = (total_eligible / 2.0)
            if approved_votes > threshold:
                is_approved = True
            elif rejected_votes >= (total_eligible - threshold):
                is_rejected = True

        elif rule == 'TWO_THIRDS':
            # >= 66.7% of total eligible voters
            threshold = (total_eligible * 2.0) / 3.0
            if approved_votes >= threshold:
                is_approved = True
            elif (total_eligible - rejected_votes) < threshold:
                is_rejected = True

        elif rule == 'UNANIMOUS':
            # 100% of total eligible voters
            if approved_votes == total_eligible:
                is_approved = True
            elif rejected_votes > 0:
                is_rejected = True

        elif rule == 'ALL_LEGAL_OWNERS':
            # Check statutory owners
            if decision.land_parcel:
                legal_owners = decision.land_parcel.legal_owners.all()
                if legal_owners.exists():
                    owner_user_ids = set(legal_owners.filter(user__isnull=False).values_list('user_id', flat=True))
                    voted_owner_ids = set(decision.votes.filter(vote='APPROVE', voter__in=owner_user_ids).values_list('voter_id', flat=True))
                    if owner_user_ids and owner_user_ids.issubset(voted_owner_ids):
                        is_approved = True
                    elif decision.votes.filter(vote='REJECT', voter__in=owner_user_ids).exists():
                        is_rejected = True
            else:
                if approved_votes > (total_eligible / 2.0):
                    is_approved = True

        result_summary = {
            'rule': rule,
            'total_eligible': total_eligible,
            'approved_votes': approved_votes,
            'rejected_votes': rejected_votes,
            'is_approved': is_approved,
            'is_rejected': is_rejected,
        }

        if is_approved and decision.status == 'ACTIVE':
            decision.status = 'APPROVED'
            decision.closed_at = timezone.now()
            execution_details = DecisionEngine._execute_approved_decision(decision)
            decision.execution_result = execution_details
            decision.save(update_fields=['status', 'closed_at', 'execution_result', 'updated_at'])

            AccountAuditEvent.objects.create(
                account=account,
                actor=None,
                action='DECISION_APPROVED_AND_EXECUTED',
                resource_type='AccountDecision',
                resource_id=str(decision.id),
                metadata={'result': result_summary, 'execution': execution_details}
            )

        elif is_rejected and decision.status == 'ACTIVE':
            decision.status = 'REJECTED'
            decision.closed_at = timezone.now()
            decision.save(update_fields=['status', 'closed_at', 'updated_at'])

            AccountAuditEvent.objects.create(
                account=account,
                actor=None,
                action='DECISION_REJECTED',
                resource_type='AccountDecision',
                resource_id=str(decision.id),
                metadata={'result': result_summary}
            )

        return result_summary

    @staticmethod
    def _execute_approved_decision(decision: AccountDecision) -> Dict[str, Any]:
        """Executes the specific action for an approved decision."""
        account = decision.account
        details = {'executed_at': timezone.now().isoformat()}

        if decision.decision_type == 'MEMBER_REMOVAL' and decision.target_member:
            target = decision.target_member
            target.status = 'REMOVED'
            target.save(update_fields=['status', 'updated_at'])

            # Invalidate target user's active sessions for security
            if target.user:
                UserSession.objects.filter(user=target.user, is_active=True).update(is_active=False)

            details['action'] = 'MEMBER_REMOVED'
            details['removed_member_id'] = str(target.id)
            details['removed_member_name'] = target.full_name
            details['legal_ownership_notice'] = 'Note: Account removal does not alter registered title deed or statutory property rights.'

        elif decision.decision_type == 'CHANGE_MANAGER' and decision.target_member:
            new_manager = decision.target_member
            # Demote current leader(s) to co-buyer/member
            account.members.filter(is_account_leader=True).update(
                is_account_leader=False,
                role='CO_BUYER' if account.purpose == 'BUY' else 'MEMBER'
            )
            # Promote target member
            new_manager.is_account_leader = True
            new_manager.role = 'BUYER_TEAM_MANAGER' if account.purpose == 'BUY' else 'SELLER_TEAM_MANAGER'
            new_manager.save(update_fields=['is_account_leader', 'role', 'updated_at'])

            details['action'] = 'MANAGER_SUCCESSION_COMPLETED'
            details['new_manager_id'] = str(new_manager.id)
            details['new_manager_name'] = new_manager.full_name

        elif decision.decision_type == 'PURCHASE_PROPOSAL':
            details['action'] = 'PURCHASE_PROPOSAL_APPROVED'
            details['parcel_number'] = decision.land_parcel.parcel_number if decision.land_parcel else 'N/A'
            details['proposed_amount'] = str(decision.proposed_amount) if decision.proposed_amount else 'N/A'
            details['next_step'] = 'Escrow deposit authorization unlocked'

        elif decision.decision_type == 'CLOSE_ACCOUNT':
            account.status = 'CLOSED'
            account.save(update_fields=['status', 'updated_at'])
            details['action'] = 'ACCOUNT_CLOSED'

        return details
