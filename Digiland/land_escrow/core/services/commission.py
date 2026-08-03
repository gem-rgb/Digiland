from django.core.exceptions import ValidationError
from django.db import transaction as db_transaction
from django.utils import timezone

from core.models import AuditLog, LandParcel, Message, PurchaseCommission, Transaction, User as CoreUser

COMMISSION_STEP_SEQUENCE = [
    'Open',
    'Accepted',
    'Documents_Review',
    'Lawyer_Verification',
    'Site_Visit_Scheduled',
    'Site_Visit_Complete',
    'Closing',
    'Completed',
    'Cancelled',
]


def resolve_agent_region(agent):
    """Resolve an agent's operating region, falling back to their latest assigned parcel."""
    county = (getattr(agent, 'agent_county', '') or '').strip() or None
    constituency = (getattr(agent, 'agent_constituency', '') or '').strip() or None
    if county and constituency:
        return county, constituency, 'profile'

    recent_parcel = (
        LandParcel.objects.filter(assigned_agent=agent)
        .order_by('-updated_at', '-created_at')
        .only('county', 'constituency')
        .first()
    )
    if recent_parcel:
        return recent_parcel.county, recent_parcel.constituency, 'parcel_proxy'

    return None, None, 'unassigned'


def find_nearby_agents(county, constituency):
    """Return verified agents operating in the requested region."""
    county = (county or '').strip()
    constituency = (constituency or '').strip()

    base = CoreUser.objects.filter(role='Agent', is_active=True, is_identity_verified=True)
    if county and constituency:
        exact = base.filter(agent_county__iexact=county, agent_constituency__iexact=constituency)
        if exact.exists():
            return exact.order_by('date_joined', 'email')

        county_match = base.filter(agent_county__iexact=county)
        if county_match.exists():
            return county_match.order_by('date_joined', 'email')

        constituency_match = base.filter(agent_constituency__iexact=constituency)
        if constituency_match.exists():
            return constituency_match.order_by('date_joined', 'email')

    return base.order_by('date_joined', 'email')


def get_default_lawyer():
    """Resolve a default lawyer account for commission review."""
    return (
        CoreUser.objects.filter(role='Lawyer', is_active=True, is_identity_verified=True)
        .order_by('date_joined', 'email')
        .first()
    )


def _send_message(sender, receiver, content, *, commission=None, transaction=None):
    if not sender or not receiver:
        return None

    linked_transaction = transaction
    if linked_transaction is None and commission and getattr(commission, 'transaction_id', None):
        linked_transaction = commission.transaction

    return Message.objects.create(
        sender=sender,
        receiver=receiver,
        transaction=linked_transaction,
        content=content,
    )


def notify_agents(commission, agents=None):
    agents = list(agents or find_nearby_agents(commission.target_county, commission.target_constituency))
    if not agents:
        agents = list(CoreUser.objects.filter(role='Agent', is_active=True, is_identity_verified=True).order_by('date_joined', 'email')[:20])

    content = (
        f"New purchase commission for parcel {commission.land_parcel.parcel_number} "
        f"in {commission.target_county}, {commission.target_constituency}. "
        "Open the job board to accept it."
    )
    for agent in agents:
        if agent.id == commission.buyer_id:
            continue
        _send_message(commission.buyer, agent, content, commission=commission)

    return agents


def create_commission(buyer, land_parcel, *, is_joint_purchase=False, joint_group=None):
    if buyer.role not in {'Buyer', 'Admin'}:
        raise ValidationError('Only buyers can commission a parcel for purchase.')
    if land_parcel.verification_status != 'Verified':
        raise ValidationError('Only verified parcels can be commissioned for purchase.')
    if not land_parcel.listed_by_id:
        raise ValidationError('This parcel is missing a seller listing and cannot be commissioned.')

    active_statuses = {'Open', 'Accepted', 'Documents_Review', 'Lawyer_Verification', 'Site_Visit_Scheduled', 'Site_Visit_Complete', 'Closing'}
    if PurchaseCommission.objects.filter(buyer=buyer, land_parcel=land_parcel, status__in=active_statuses).exists():
        raise ValidationError('You already have an active commission for this parcel.')

    with db_transaction.atomic():
        commission = PurchaseCommission.objects.create(
            tenant_id=land_parcel.tenant_id,
            buyer=buyer,
            land_parcel=land_parcel,
            is_joint_purchase=bool(is_joint_purchase),
            joint_group=joint_group,
            status='Open',
            target_county=land_parcel.county,
            target_constituency=land_parcel.constituency,
            updated_by=buyer,
        )
        notify_agents(commission)
        AuditLog.objects.create(
            user=buyer,
            action=f'Created purchase commission for parcel {land_parcel.parcel_number}',
            metadata={
                'commission_id': str(commission.id),
                'parcel_number': land_parcel.parcel_number,
                'target_county': commission.target_county,
                'target_constituency': commission.target_constituency,
            },
        )
        return commission


def check_agent_exclusivity_lock(agent):
    """
    Server-side Exclusivity Lock:
    An agent cannot accept any new job if they hold an active, unfinalized parcel or commission assignment,
    unless the assignment has passed its 30-day expiration policy without finalization.
    """
    if getattr(agent, 'role', None) == 'Admin':
        return  # Admins exempt from lock

    active_parcel_statuses = [
        'AGENT_ASSIGNED',
        'AWAITING_SELLER_ACCESS_GRANT',
        'AGENT_VERIFYING',
        'AGENT_APPROVED',
        'BUYER_OFFER_RECEIVED',
        'LAWYER_REVIEW',
        'LAWYER_APPROVED',
    ]
    active_parcels = LandParcel.objects.filter(
        assigned_agent=agent,
        verification_status__in=active_parcel_statuses,
    )
    for p in active_parcels:
        if p.assignment_expires_at and p.assignment_expires_at < timezone.now():
            # Exclusivity lock auto-expires after 30 days of inactivity
            p.verification_status = 'AGENT_RELEASED'
            p.assigned_agent = None
            p.save(update_fields=['verification_status', 'assigned_agent', 'updated_at'])
            AuditLog.objects.create(
                user=agent,
                action=f'Exclusivity Lock expired (30-day limit) for parcel {p.parcel_number}',
                metadata={'parcel_id': str(p.id)},
            )

    # Re-evaluate active parcels after expiration check
    remaining_parcels = LandParcel.objects.filter(
        assigned_agent=agent,
        verification_status__in=active_parcel_statuses,
    )
    if remaining_parcels.exists():
        first_parcel = remaining_parcels.first()
        raise ValidationError(
            f"Exclusivity Lock: You are currently assigned to parcel {first_parcel.parcel_number}. "
            "You cannot accept a new job until your active assignment reaches finalization."
        )

    active_commission_statuses = [
        'Accepted',
        'Documents_Review',
        'Lawyer_Verification',
        'Site_Visit_Scheduled',
        'Site_Visit_Complete',
        'Closing',
    ]
    active_commissions = PurchaseCommission.objects.filter(
        accepted_by=agent,
        status__in=active_commission_statuses,
    )
    if active_commissions.exists():
        first_comm = active_commissions.first()
        raise ValidationError(
            f"Exclusivity Lock: You currently hold an active commission job for parcel {first_comm.land_parcel.parcel_number}. "
            "You must finalize your current job before accepting new assignments."
        )


def accept_parcel_verification_job(agent, parcel):
    """Allow an agent to claim an unassigned parcel verification job (Stage 2 -> Stage 3)."""
    if agent.role != 'Agent' and agent.role != 'Admin':
        raise ValidationError('Only agents can accept parcel verification jobs.')

    check_agent_exclusivity_lock(agent)

    from datetime import timedelta

    with db_transaction.atomic():
        locked_parcel = LandParcel.objects.select_for_update().get(id=parcel.id)
        if locked_parcel.verification_status not in {'AGENT_JOB_POSTED', 'AI_APPROVED', 'Pending'}:
            raise ValidationError(f'Parcel {parcel.parcel_number} is not available for job assignment.')
        if locked_parcel.assigned_agent_id and locked_parcel.assigned_agent_id != agent.id:
            raise ValidationError('This parcel verification job has already been claimed by another agent.')

        locked_parcel.assigned_agent = agent
        locked_parcel.verification_status = 'AGENT_ASSIGNED'
        locked_parcel.assignment_expires_at = timezone.now() + timedelta(days=30)
        locked_parcel.last_agent_checkin_at = timezone.now()
        locked_parcel.save(update_fields=['assigned_agent', 'verification_status', 'assignment_expires_at', 'last_agent_checkin_at', 'updated_at'])

        AuditLog.objects.create(
            user=agent,
            action=f'Claimed verification job for parcel {parcel.parcel_number}',
            metadata={'parcel_id': str(parcel.id), 'parcel_number': parcel.parcel_number, 'expires_at': locked_parcel.assignment_expires_at.isoformat()},
        )
        return locked_parcel



def accept_commission(agent, commission):
    if agent.role != 'Agent' or not agent.is_active or not agent.is_identity_verified:
        raise ValidationError('Only verified agents can accept commissions.')

    check_agent_exclusivity_lock(agent)

    county, constituency, source = resolve_agent_region(agent)
    matched_agents = find_nearby_agents(commission.target_county, commission.target_constituency)
    if matched_agents.filter(id=agent.id).count() == 0:
        if county and constituency:
            raise ValidationError('This commission is outside your operating region.')
        # If the agent has no region on file, allow acceptance but keep the audit trail explicit.

    with db_transaction.atomic():
        locked = PurchaseCommission.objects.select_for_update().select_related('buyer', 'land_parcel', 'accepted_by').get(id=commission.id)
        if locked.status != 'Open' or locked.accepted_by_id:
            raise ValidationError('This commission has already been accepted.')

        locked.accepted_by = agent
        locked.accepted_at = timezone.now()
        locked.status = 'Accepted'

        locked.updated_by = agent
        locked.save(update_fields=['accepted_by', 'accepted_at', 'status', 'updated_by', 'updated_at'])

        _send_message(
            agent,
            locked.buyer,
            f"Agent {agent.email} accepted your commission for parcel {locked.land_parcel.parcel_number}.",
            commission=locked,
        )
        AuditLog.objects.create(
            user=agent,
            action=f'Accepted purchase commission {locked.id}',
            metadata={
                'commission_id': str(locked.id),
                'parcel_number': locked.land_parcel.parcel_number,
                'region_source': source,
                'agent_region': {'county': county, 'constituency': constituency},
            },
        )
        return locked


def review_documents(commission, actor, note='', *, approved=True):
    if actor.role not in {'Agent', 'Admin'}:
        raise ValidationError('Only the accepted agent or an admin can review documents.')
    if actor.role == 'Agent' and commission.accepted_by_id != actor.id:
        raise ValidationError('Only the assigned agent can review this commission.')

    with db_transaction.atomic():
        locked = PurchaseCommission.objects.select_for_update().select_related('buyer', 'land_parcel', 'accepted_by').get(id=commission.id)
        locked.documents_reviewed = True
        locked.documents_review_note = note.strip()
        locked.documents_reviewed_at = timezone.now()
        locked.status = 'Documents_Review'
        locked.updated_by = actor
        locked.save(update_fields=['documents_reviewed', 'documents_review_note', 'documents_reviewed_at', 'status', 'updated_by', 'updated_at'])

        _send_message(
            actor,
            locked.buyer,
            f"Documents were reviewed for parcel {locked.land_parcel.parcel_number}. {note.strip() or 'The review is complete.'}",
            commission=locked,
        )
        AuditLog.objects.create(
            user=actor,
            action=f'Document review recorded for commission {locked.id}',
            metadata={
                'commission_id': str(locked.id),
                'approved': approved,
                'note': note,
            },
        )
        return locked


def submit_to_lawyer(commission, actor, lawyer=None, note=''):
    if actor.role not in {'Agent', 'Admin'}:
        raise ValidationError('Only the accepted agent or an admin can submit documents to a lawyer.')
    if actor.role == 'Agent' and commission.accepted_by_id != actor.id:
        raise ValidationError('Only the assigned agent can submit this commission to a lawyer.')

    lawyer = lawyer or commission.assigned_lawyer or get_default_lawyer()
    if lawyer is None:
        raise ValidationError('No lawyer account is available for verification.')

    with db_transaction.atomic():
        locked = PurchaseCommission.objects.select_for_update().select_related('buyer', 'land_parcel', 'accepted_by', 'assigned_lawyer').get(id=commission.id)
        locked.assigned_lawyer = lawyer
        locked.lawyer_submitted_at = timezone.now()
        locked.status = 'Lawyer_Verification'
        locked.updated_by = actor
        if note:
            locked.lawyer_verification_note = note.strip()
        locked.save(update_fields=['assigned_lawyer', 'lawyer_submitted_at', 'status', 'updated_by', 'lawyer_verification_note', 'updated_at'])

        _send_message(
            actor,
            lawyer,
            f"Commission {locked.land_parcel.parcel_number} has been submitted for lawyer verification.",
            commission=locked,
        )
        _send_message(
            actor,
            locked.buyer,
            f"Your commission for parcel {locked.land_parcel.parcel_number} has been forwarded to the lawyer for review.",
            commission=locked,
        )
        AuditLog.objects.create(
            user=actor,
            action=f'Submitted commission {locked.id} to lawyer {lawyer.email}',
            metadata={
                'commission_id': str(locked.id),
                'lawyer_id': str(lawyer.id),
                'note': note,
            },
        )
        return locked


def lawyer_verdict(commission, lawyer, *, verified, note=''):
    if lawyer.role not in {'Lawyer', 'Admin'} or (lawyer.role == 'Lawyer' and not lawyer.is_active):
        raise ValidationError('Only an active lawyer or admin can verify commission documents.')
    if lawyer.role == 'Lawyer' and commission.assigned_lawyer_id and commission.assigned_lawyer_id != lawyer.id:
        raise ValidationError('This commission is assigned to a different lawyer.')

    with db_transaction.atomic():
        locked = PurchaseCommission.objects.select_for_update().select_related('buyer', 'land_parcel', 'accepted_by', 'assigned_lawyer').get(id=commission.id)
        locked.lawyer_verified = bool(verified)
        locked.lawyer_verification_note = note.strip()
        locked.lawyer_verified_at = timezone.now()
        locked.status = 'Site_Visit_Scheduled' if verified else 'Lawyer_Verification'
        locked.updated_by = lawyer
        locked.save(update_fields=['lawyer_verified', 'lawyer_verification_note', 'lawyer_verified_at', 'status', 'updated_by', 'updated_at'])

        _send_message(
            lawyer,
            locked.buyer,
            f"Lawyer review for parcel {locked.land_parcel.parcel_number} is {'approved' if verified else 'rejected'}. {note.strip() or ''}".strip(),
            commission=locked,
        )
        if locked.accepted_by_id:
            _send_message(
                lawyer,
                locked.accepted_by,
                f"Lawyer review for parcel {locked.land_parcel.parcel_number} is {'approved' if verified else 'rejected'}. {note.strip() or ''}".strip(),
                commission=locked,
            )
        AuditLog.objects.create(
            user=lawyer,
            action=f'Lawyer verdict recorded for commission {locked.id}',
            metadata={
                'commission_id': str(locked.id),
                'verified': bool(verified),
                'note': note,
            },
        )
        return locked


def schedule_site_visit(commission, actor, *, visit_date, location='', notes=''):
    if actor.role not in {'Agent', 'Admin'}:
        raise ValidationError('Only the accepted agent or an admin can schedule a site visit.')
    if actor.role == 'Agent' and commission.accepted_by_id != actor.id:
        raise ValidationError('Only the assigned agent can schedule this site visit.')

    with db_transaction.atomic():
        locked = PurchaseCommission.objects.select_for_update().select_related('buyer', 'land_parcel', 'accepted_by').get(id=commission.id)
        locked.site_visit_date = visit_date
        locked.site_visit_location = location.strip()
        locked.site_visit_notes = notes.strip()
        locked.status = 'Site_Visit_Scheduled'
        locked.updated_by = actor
        locked.save(update_fields=['site_visit_date', 'site_visit_location', 'site_visit_notes', 'status', 'updated_by', 'updated_at'])

        _send_message(
            actor,
            locked.buyer,
            f"Site visit for parcel {locked.land_parcel.parcel_number} has been scheduled for {visit_date:%Y-%m-%d %H:%M}.",
            commission=locked,
        )
        AuditLog.objects.create(
            user=actor,
            action=f'Site visit scheduled for commission {locked.id}',
            metadata={
                'commission_id': str(locked.id),
                'visit_date': visit_date.isoformat(),
                'location': location,
            },
        )
        return locked


def complete_site_visit(commission, actor, notes=''):
    if actor.role not in {'Agent', 'Admin'}:
        raise ValidationError('Only the accepted agent or an admin can complete a site visit.')
    if actor.role == 'Agent' and commission.accepted_by_id != actor.id:
        raise ValidationError('Only the assigned agent can complete this site visit.')

    with db_transaction.atomic():
        locked = PurchaseCommission.objects.select_for_update().select_related('buyer', 'land_parcel', 'accepted_by').get(id=commission.id)
        locked.site_visit_complete = True
        locked.site_visit_notes = notes.strip() or locked.site_visit_notes
        locked.site_visit_completed_at = timezone.now()
        locked.status = 'Site_Visit_Complete'
        locked.updated_by = actor
        locked.save(update_fields=['site_visit_complete', 'site_visit_notes', 'site_visit_completed_at', 'status', 'updated_by', 'updated_at'])

        _send_message(
            actor,
            locked.buyer,
            f"Site visit for parcel {locked.land_parcel.parcel_number} has been completed.",
            commission=locked,
        )
        AuditLog.objects.create(
            user=actor,
            action=f'Site visit completed for commission {locked.id}',
            metadata={
                'commission_id': str(locked.id),
                'notes': notes,
            },
        )
        return locked


def close_commission(commission, actor):
    if actor.role not in {'Agent', 'Admin'}:
        raise ValidationError('Only the accepted agent or an admin can close a commission.')
    if actor.role == 'Agent' and commission.accepted_by_id != actor.id:
        raise ValidationError('Only the assigned agent can close this commission.')
    if not commission.can_create_transaction:
        raise ValidationError('The commission must pass document review, lawyer review, and site visit before closing.')

    with db_transaction.atomic():
        locked = PurchaseCommission.objects.select_for_update().select_related('buyer', 'land_parcel', 'accepted_by', 'assigned_lawyer', 'transaction').get(id=commission.id)
        if locked.transaction_id:
            locked.status = 'Closing'
            locked.closed_at = locked.closed_at or timezone.now()
            locked.updated_by = actor
            locked.save(update_fields=['status', 'closed_at', 'updated_by', 'updated_at'])
            return locked, locked.transaction

        transaction = Transaction.objects.create(
            tenant_id=locked.tenant_id,
            buyer=locked.buyer,
            seller=locked.land_parcel.listed_by,
            agent=locked.accepted_by,
            land_parcel=locked.land_parcel,
            agreed_price=locked.land_parcel.displayed_price,
            status='Under_Verification',
            contract_agreed=True,
            is_joint_purchase=locked.is_joint_purchase,
            joint_group=locked.joint_group,
            updated_by=actor,
        )
        locked.transaction = transaction
        locked.status = 'Closing'
        locked.closed_at = timezone.now()
        locked.updated_by = actor
        locked.save(update_fields=['transaction', 'status', 'closed_at', 'updated_by', 'updated_at'])

        _send_message(
            actor,
            locked.buyer,
            f"Commission {locked.land_parcel.parcel_number} has entered closing and payment can begin.",
            commission=locked,
            transaction=transaction,
        )
        if locked.land_parcel.listed_by_id:
            _send_message(
                actor,
                locked.land_parcel.listed_by,
                f"Commission {locked.land_parcel.parcel_number} has entered closing under legal supervision.",
                commission=locked,
                transaction=transaction,
            )
        AuditLog.objects.create(
            user=actor,
            action=f'Closed commission {locked.id} into transaction {transaction.id}',
            metadata={
                'commission_id': str(locked.id),
                'transaction_id': str(transaction.id),
            },
        )
        return locked, transaction


def advance_step(commission, step, actor, **data):
    step = (step or '').strip().lower()
    if step in {'accept', 'accepted'}:
        return accept_commission(actor, commission)
    if step in {'documents_review', 'document_review', 'review_documents'}:
        return review_documents(commission, actor, data.get('note', ''), approved=data.get('approved', True))
    if step in {'submit_to_lawyer', 'lawyer_submit'}:
        return submit_to_lawyer(commission, actor, lawyer=data.get('lawyer'), note=data.get('note', ''))
    if step in {'lawyer_verdict', 'lawyer_review'}:
        return lawyer_verdict(commission, actor, verified=data.get('verified', False), note=data.get('note', ''))
    if step in {'schedule_site_visit', 'site_visit'}:
        visit_date = data.get('visit_date')
        if visit_date is None:
            raise ValidationError('A site visit date is required.')
        return schedule_site_visit(
            commission,
            actor,
            visit_date=visit_date,
            location=data.get('location', ''),
            notes=data.get('notes', ''),
        )
    if step in {'complete_site_visit', 'site_visit_complete'}:
        return complete_site_visit(commission, actor, notes=data.get('notes', ''))
    if step in {'close', 'closing'}:
        return close_commission(commission, actor)
    if step in {'cancel', 'cancelled'}:
        with db_transaction.atomic():
            locked = PurchaseCommission.objects.select_for_update().get(id=commission.id)
            locked.status = 'Cancelled'
            locked.updated_by = actor
            locked.save(update_fields=['status', 'updated_by', 'updated_at'])
            AuditLog.objects.create(
                user=actor,
                action=f'Cancelled commission {locked.id}',
                metadata={'commission_id': str(locked.id)},
            )
            return locked
    raise ValidationError(f'Unsupported commission step: {step}')
