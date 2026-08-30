"""
Migration bridge from legacy JointBuyerGroup models to unified Account architecture.
Preserves existing data while enabling the new Entity, Membership & Decision capabilities.
"""
import logging
from django.db import transaction
from core.models import (
    User,
    JointBuyerGroup,
    JointBuyerMember,
    Account,
    AccountMember,
    AccountAuditEvent
)

logger = logging.getLogger(__name__)


def migrate_legacy_joint_groups() -> dict:
    """
    Migrates existing JointBuyerGroup records to the unified Account & AccountMember system.
    Safe to run repeatedly (idempotent).
    """
    groups = JointBuyerGroup.objects.all()
    accounts_created = 0
    members_migrated = 0

    group_to_entity_map = {
        'Couple': 'FAMILY',
        'Chama': 'CHAMA',
        'Family': 'FAMILY',
        'Investment_Group': 'JOINT_INVESTMENT',
    }

    with transaction.atomic():
        for group in groups:
            entity_type = group_to_entity_map.get(group.group_type, 'CHAMA')

            account, created = Account.objects.get_or_create(
                id=group.id,  # Preserve UUID for smooth FK bridging
                defaults={
                    'tenant_id': group.tenant_id,
                    'account_type': 'JOINT',
                    'purpose': 'BUY',
                    'entity_type': entity_type,
                    'display_name': group.name,
                    'status': 'ACTIVE',
                    'governance_rule': 'SIMPLE_MAJORITY',
                    'created_by': group.leader,
                }
            )
            if created:
                accounts_created += 1

            # Migrate leader as Buyer Team Manager
            leader_member, _ = AccountMember.objects.get_or_create(
                account=account,
                user=group.leader,
                defaults={
                    'tenant_id': group.tenant_id,
                    'role': 'BUYER_TEAM_MANAGER',
                    'status': 'ACTIVE',
                    'full_name': (f"{group.leader.first_name} {group.leader.last_name}").strip() or group.leader.email,
                    'email': group.leader.email,
                    'phone_number': getattr(group.leader, 'phone_number', None),
                    'id_number': getattr(group.leader, 'id_number', None),
                    'kra_pin': getattr(group.leader, 'kra_pin', None),
                    'is_account_leader': True,
                    'joined_at': group.created_at,
                }
            )

            # Migrate members
            for member in group.members.all():
                if member.is_leader and member.email == group.leader.email:
                    # Update share percentage on leader
                    leader_member.share_percentage = member.share_percentage
                    leader_member.save(update_fields=['share_percentage'])
                    continue

                # Find or link existing user by email if possible
                matched_user = User.objects.filter(email=member.email).first() if member.email else None

                _, mem_created = AccountMember.objects.get_or_create(
                    id=member.id,  # Preserve member UUID
                    defaults={
                        'tenant_id': member.tenant_id,
                        'account': account,
                        'user': matched_user,
                        'role': 'BUYER_TEAM_MANAGER' if member.is_leader else 'CO_BUYER',
                        'status': 'ACTIVE',
                        'full_name': member.full_name,
                        'email': member.email,
                        'phone_number': member.phone_number,
                        'id_number': member.id_number,
                        'kra_pin': member.kra_pin,
                        'share_percentage': member.share_percentage,
                        'is_account_leader': member.is_leader,
                        'invited_by': group.leader,
                        'joined_at': member.added_at,
                    }
                )
                if mem_created:
                    members_migrated += 1

    return {
        'accounts_created': accounts_created,
        'members_migrated': members_migrated,
        'status': 'SUCCESS'
    }
