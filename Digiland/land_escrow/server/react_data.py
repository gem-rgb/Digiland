from django import forms as django_forms
from django.contrib.messages import get_messages
from django.urls import reverse
from core.legal import KENYAN_LAND_DOCUMENTS, JOINT_KENYAN_LAND_DOCUMENTS


def build_nav(user, active=None):
    active = active or ''
    role = getattr(user, 'role', None)
    is_authenticated = getattr(user, 'is_authenticated', False)

    if not is_authenticated:
        return [
            {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'icon': 'parcels', 'active': active == 'parcel-list'},
            {'label': 'Features', 'href': '/features/', 'icon': 'security', 'active': active == 'features'},
            {'label': 'About Us', 'href': '/about/', 'icon': 'documents', 'active': active in {'about', 'content'}},
            {'label': 'Legal & Escrow', 'href': reverse('frontend:escrow_acts'), 'icon': 'legal', 'active': active in {'legal', 'joint-laws'}},
        ]

    if role == 'Buyer':
        is_joint_buyer_account = getattr(user, 'buyer_account_type', None) == 'Joint'

        nav = [
            {'label': 'Dashboard', 'href': reverse('frontend:home'), 'icon': 'dashboard', 'active': active == 'dashboard'},
            {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'icon': 'parcels', 'active': active == 'parcel-list'},
            {'label': 'Transactions', 'href': reverse('frontend:transactions'), 'icon': 'transactions', 'active': active == 'transactions'},
            {'label': 'My Commissions', 'href': reverse('frontend:buyer_dashboard'), 'icon': 'security', 'active': active in {'commission-detail', 'my-commissions'}},
            {'label': 'Legal', 'href': reverse('frontend:escrow_acts'), 'icon': 'legal', 'active': active in {'legal', 'joint-laws'}},
        ]
        if is_joint_buyer_account:
            nav.insert(3, {'label': 'My Groups', 'href': reverse('frontend:joint_groups'), 'icon': 'joint', 'active': active.startswith('joint')})
        if getattr(user, 'buyer_account_type', None) is None:
            nav.insert(3, {'label': 'Buyer Setup', 'href': reverse('frontend:buyer_account_choice'), 'icon': 'security', 'active': active == 'buyer-choice'})
        return nav

    if role == 'Seller':
        return [
            {'label': 'Dashboard', 'href': reverse('frontend:home'), 'icon': 'dashboard', 'active': active == 'dashboard'},
            {'label': 'My Parcels', 'href': reverse('frontend:parcel_list'), 'icon': 'parcels', 'active': active == 'parcel-list'},
            {'label': 'Promotions & Ads', 'href': reverse('frontend:seller_promotions'), 'icon': 'security', 'active': active == 'seller-promotions'},
            {'label': 'Transactions', 'href': reverse('frontend:transactions'), 'icon': 'transactions', 'active': active == 'transactions'},
            {'label': 'Messages', 'href': reverse('frontend:messages'), 'icon': 'documents', 'active': active == 'messages'},
            {'label': 'Legal', 'href': reverse('frontend:seller_laws'), 'icon': 'legal', 'active': active in {'legal', 'seller-laws'}},
        ]

    if role == 'Lawyer':
        return [
            {'label': 'Command Centre', 'href': reverse('frontend:agent_dashboard'), 'icon': 'dashboard', 'active': active in {'dashboard', 'lawyer-dashboard'}},
            {'label': 'Transactions', 'href': reverse('frontend:transactions'), 'icon': 'transactions', 'active': active == 'transactions'},
            {'label': 'Messages', 'href': reverse('frontend:messages'), 'icon': 'documents', 'active': active == 'messages'},
            {'label': 'Legal Library', 'href': reverse('frontend:escrow_acts'), 'icon': 'legal', 'active': active in {'legal', 'joint-laws'}},
        ]

    nav = [
        {'label': 'Command Centre', 'href': reverse('frontend:agent_dashboard'), 'icon': 'dashboard', 'active': active in {'dashboard', 'admin-dashboard', 'agent-dashboard', 'lawyer-dashboard'}},
        {'label': 'Tasks', 'href': reverse('frontend:task_management'), 'icon': 'parcels', 'active': active == 'tasks'},
        {'label': 'Parcels', 'href': reverse('frontend:parcel_list'), 'icon': 'parcels', 'active': active == 'parcel-list'},
        {'label': 'Transactions', 'href': reverse('frontend:transactions'), 'icon': 'transactions', 'active': active == 'transactions'},
        {'label': 'Escrow Release', 'href': reverse('frontend:escrow_release'), 'icon': 'security', 'active': active == 'escrow-release'},
        {'label': 'Messages', 'href': reverse('frontend:messages'), 'icon': 'documents', 'active': active == 'messages'},
    ]
    if getattr(user, 'role', '') == 'Admin':
        nav.append({'label': 'Finance', 'href': reverse('frontend:admin_finance'), 'icon': 'money', 'active': active == 'finance'})
    return nav


def serialize_user(user):
    if not getattr(user, 'is_authenticated', False):
        return None

    full_name = (f"{getattr(user, 'first_name', '')} {getattr(user, 'last_name', '')}").strip() or getattr(user, 'email', '')
    return {
        'email': user.email,
        'role': getattr(user, 'role', ''),
        'buyer_account_type': getattr(user, 'buyer_account_type', None),
        'is_identity_verified': getattr(user, 'is_identity_verified', False),
        'full_name': full_name,
        'phone_number': getattr(user, 'phone_number', None),
    }


def serialize_review_user(user):
    data = serialize_user(user) or {}
    data.update({
        'id': str(user.id),
        'is_active': getattr(user, 'is_active', None),
        'id_number': getattr(user, 'id_number', None),
        'phone_number': getattr(user, 'phone_number', None),
        'kra_pin': getattr(user, 'kra_pin', None),
        'joined_at': user.date_joined.strftime('%b %d, %Y') if getattr(user, 'date_joined', None) else None,
        'role_label': getattr(user, 'role', ''),
    })
    return data


def serialize_parcel(parcel, user=None):
    is_owner = bool(user and getattr(user, 'id', None) == getattr(parcel.listed_by, 'id', None))
    is_admin = bool(user and getattr(user, 'role', None) == 'Admin')
    
    # Check for active promotion tier
    active_promo = parcel.promotions.filter(is_active=True, payment_status='Paid').first()
    promotion_tier = active_promo.tier if active_promo else None
    
    return {
        'parcel_number': str(parcel.parcel_number),
        'county': parcel.county,
        'constituency': parcel.constituency,
        'ward': parcel.ward,
        'land_size': str(parcel.land_size),
        'land_use_type': parcel.land_use_type,
        'verification_status': parcel.verification_status,
        'image_url': parcel.image.url if getattr(parcel, 'image', None) else None,
        'details_url': reverse('frontend:parcel_detail', args=[parcel.parcel_number]),
        'edit_url': reverse('frontend:parcel_edit', args=[parcel.parcel_number]) if (is_owner or is_admin) else None,
        'delete_url': reverse('frontend:parcel_delete', args=[parcel.parcel_number]) if (is_owner or is_admin) else None,
        'manage_label': 'Manage Listing' if (is_owner or is_admin) else 'View Details and Buy',
        'manage_url': reverse('frontend:parcel_detail', args=[parcel.parcel_number]),
        'status_badge': parcel.get_verification_status_display() if hasattr(parcel, 'get_verification_status_display') else parcel.verification_status,
        'promotion_tier': promotion_tier,
        'is_promoted': bool(promotion_tier),
        'asking_price': str(parcel.asking_price) if getattr(parcel, 'asking_price', None) is not None else None,
        'displayed_price': str(parcel.displayed_price) if getattr(parcel, 'displayed_price', None) is not None else None,
        'latitude': str(parcel.latitude) if parcel.latitude else None,
        'longitude': str(parcel.longitude) if parcel.longitude else None,
        'dist_to_road': parcel.dist_to_road,
        'dist_to_school': parcel.dist_to_school,
        'dist_to_hospital': parcel.dist_to_hospital,
        'dist_to_mall': parcel.dist_to_mall,
        'dist_to_industrial_zone': parcel.dist_to_industrial_zone,
        'dist_to_transport_hub': parcel.dist_to_transport_hub,
    }


def serialize_document(document):
    return {
        'id': str(document.id),
        'document_type': document.document_type,
        'document_label': document.get_document_type_display() if hasattr(document, 'get_document_type_display') else document.document_type,
        'verification_status': document.verification_status,
        'uploaded_at': document.uploaded_at.strftime('%b %d, %Y') if getattr(document, 'uploaded_at', None) else '',
        'file_url': document.file_url.url if getattr(document, 'file_url', None) else None,
    }


def serialize_transaction(tx, user=None):
    role_label = 'Buyer' if user and getattr(user, 'id', None) == getattr(tx, 'buyer_id', None) else 'Seller'
    if user and getattr(user, 'role', None) == 'Admin':
        role_label = 'Admin'
    status_tone = 'muted'
    if tx.status in {'Completed'}:
        status_tone = 'success'
    elif tx.status in {'Deposit_Paid', 'Under_Verification'}:
        status_tone = 'accent'
    elif tx.status in {'Reversed', 'Refunded', 'Disputed'}:
        status_tone = 'danger'
    elif tx.status in {'Initiated'}:
        status_tone = 'warning'

    action_label = 'View Contract'
    if tx.status == 'Completed':
        action_label = 'Archived Contract'
    elif tx.status in {'Reversed', 'Refunded', 'Disputed'}:
        action_label = 'View Details'
    elif user and getattr(user, 'id', None) == getattr(tx, 'buyer_id', None) and not tx.buyer_signature:
        action_label = 'Sign Agreement'
    elif user and getattr(user, 'id', None) == getattr(tx, 'seller_id', None) and not tx.seller_signature:
        action_label = 'Sign Agreement'
    elif user and getattr(user, 'role', None) == 'Lawyer' and not tx.lawyer_signature:
        action_label = 'Execute Sign-off'

    action_url = reverse('frontend:sign_contract', args=[tx.id])
    if action_label in {'Sign Agreement', 'Execute Sign-off'}:
        from django.core.signing import Signer
        signer = Signer()
        signing_token = signer.sign(str(tx.id))
        action_url = reverse('frontend:contract_sign_fullpage', args=[signing_token])

    return {
        'id': str(tx.id),
        'parcel_number': tx.land_parcel.parcel_number,
        'role_label': role_label,
        'amount': str(tx.agreed_price),
        'status': tx.get_status_display() if hasattr(tx, 'get_status_display') else tx.status,
        'status_tone': status_tone,
        'created_at': tx.created_at.strftime('%b %d, %Y'),
        'action_label': action_label,
        'action_url': action_url,
        'is_joint_purchase': bool(getattr(tx, 'is_joint_purchase', False)),
        'joint_label': 'Joint' if getattr(tx, 'is_joint_purchase', False) else '',
    }


COMMISSION_STEP_DEFINITIONS = [
    ('Open', 'Awaiting Agent', 'A nearby agent has not yet accepted the commission.'),
    ('Accepted', 'Agent Accepted', 'An agent has accepted responsibility for the commission.'),
    ('Documents_Review', 'Document Review', 'The accepted agent has reviewed the parcel documents.'),
    ('Lawyer_Verification', 'Lawyer Verification', 'Documents are with the lawyer for authentication.'),
    ('Site_Visit_Scheduled', 'Site Visit Scheduled', 'A site visit has been proposed and shared with the buyer.'),
    ('Site_Visit_Complete', 'Site Visit Complete', 'The on-site visit has been completed.'),
    ('Closing', 'Closing', 'The transaction has been created and payment can begin.'),
    ('Completed', 'Completed', 'Escrow closed and ownership transfer completed.'),
    ('Cancelled', 'Cancelled', 'The commission was cancelled before completion.'),
]


def _commission_status_tone(status):
    if status == 'Completed':
        return 'success'
    if status in {'Open', 'Accepted', 'Documents_Review', 'Lawyer_Verification', 'Site_Visit_Scheduled', 'Closing'}:
        return 'warning'
    if status in {'Site_Visit_Complete'}:
        return 'accent'
    if status == 'Cancelled':
        return 'danger'
    return 'muted'


def _serialize_commission_documents(parcel):
    return [
        {
            'id': str(document.id),
            'document_type': document.document_type,
            'document_label': document.get_document_type_display() if hasattr(document, 'get_document_type_display') else document.document_type,
            'verification_status': document.verification_status,
            'uploaded_at': document.uploaded_at.strftime('%b %d, %Y') if getattr(document, 'uploaded_at', None) else '',
        }
        for document in parcel.documents.all().order_by('-uploaded_at')
    ]


def _serialize_commission_steps(commission):
    status_order = {status: index for index, (status, _, _) in enumerate(COMMISSION_STEP_DEFINITIONS)}
    current_index = status_order.get(commission.status, 0)
    steps = []
    for index, (status, label, description) in enumerate(COMMISSION_STEP_DEFINITIONS):
        if commission.status == 'Cancelled' and status != 'Cancelled':
            state = 'skipped'
            completed = False
            active = False
        else:
            completed = index < current_index
            active = index == current_index and commission.status != 'Cancelled'
            state = 'complete' if completed else 'current' if active else 'upcoming'
        steps.append({
            'key': status.lower(),
            'status': status,
            'label': label,
            'description': description,
            'completed': completed,
            'active': active,
            'state': state,
        })
    return steps


def serialize_commission(commission, user=None):
    parcel = commission.land_parcel
    parcel_summary = serialize_parcel(parcel, user)
    documents = _serialize_commission_documents(parcel)
    steps = _serialize_commission_steps(commission)
    is_buyer = bool(user and getattr(user, 'id', None) == getattr(commission, 'buyer_id', None))
    is_agent = bool(user and getattr(user, 'id', None) == getattr(commission, 'accepted_by_id', None))
    is_lawyer = bool(user and getattr(user, 'id', None) == getattr(commission, 'assigned_lawyer_id', None))
    is_admin = bool(user and getattr(user, 'role', None) == 'Admin')

    can_accept = bool(user and getattr(user, 'role', None) == 'Agent' and commission.status == 'Open')
    can_work = bool(is_agent or is_admin)
    can_review_documents = can_work and commission.status in {'Accepted', 'Documents_Review'}
    can_submit_to_lawyer = can_work and commission.documents_reviewed
    can_schedule_site_visit = can_work and commission.lawyer_verified is True
    can_complete_site_visit = can_work and commission.status == 'Site_Visit_Scheduled'
    can_close = can_work and commission.can_create_transaction
    can_review_as_lawyer = bool(user and getattr(user, 'role', None) == 'Lawyer' and (commission.assigned_lawyer_id in {None, getattr(user, 'id', None)} or is_admin))

    return {
        'id': str(commission.id),
        'status': commission.status,
        'status_label': commission.get_status_display() if hasattr(commission, 'get_status_display') else commission.status,
        'status_tone': _commission_status_tone(commission.status),
        'buyer': serialize_user(commission.buyer),
        'accepted_by': serialize_user(commission.accepted_by) if commission.accepted_by else None,
        'accepted_at': commission.accepted_at.strftime('%b %d, %Y %H:%M') if getattr(commission, 'accepted_at', None) else None,
        'assigned_lawyer': serialize_user(commission.assigned_lawyer) if commission.assigned_lawyer else None,
        'lawyer_submitted_at': commission.lawyer_submitted_at.strftime('%b %d, %Y %H:%M') if getattr(commission, 'lawyer_submitted_at', None) else None,
        'lawyer_verified': commission.lawyer_verified,
        'lawyer_verification_note': commission.lawyer_verification_note,
        'lawyer_verified_at': commission.lawyer_verified_at.strftime('%b %d, %Y %H:%M') if getattr(commission, 'lawyer_verified_at', None) else None,
        'documents_reviewed': commission.documents_reviewed,
        'documents_review_note': commission.documents_review_note,
        'documents_reviewed_at': commission.documents_reviewed_at.strftime('%b %d, %Y %H:%M') if getattr(commission, 'documents_reviewed_at', None) else None,
        'site_visit_date': commission.site_visit_date.strftime('%b %d, %Y %H:%M') if getattr(commission, 'site_visit_date', None) else None,
        'site_visit_location': commission.site_visit_location,
        'site_visit_notes': commission.site_visit_notes,
        'site_visit_complete': commission.site_visit_complete,
        'site_visit_completed_at': commission.site_visit_completed_at.strftime('%b %d, %Y %H:%M') if getattr(commission, 'site_visit_completed_at', None) else None,
        'transaction_id': str(commission.transaction_id) if commission.transaction_id else None,
        'transaction_status': commission.transaction.status if commission.transaction_id else None,
        'closed_at': commission.closed_at.strftime('%b %d, %Y %H:%M') if getattr(commission, 'closed_at', None) else None,
        'is_joint_purchase': bool(commission.is_joint_purchase),
        'joint_group': serialize_joint_group(commission.joint_group, user) if commission.joint_group else None,
        'target_county': commission.target_county,
        'target_constituency': commission.target_constituency,
        'created_at': commission.created_at.strftime('%b %d, %Y %H:%M'),
        'updated_at': commission.updated_at.strftime('%b %d, %Y %H:%M'),
        'parcel': parcel_summary,
        'documents': documents,
        'document_count': len(documents),
        'required_documents': [
            {
                'title': doc['title'],
                'key': doc['key'],
                'required': doc.get('required', False),
                'description': doc.get('description', ''),
            }
            for doc in (JOINT_KENYAN_LAND_DOCUMENTS if commission.is_joint_purchase else KENYAN_LAND_DOCUMENTS)
        ],
        'steps': steps,
        'detail_url': reverse('frontend:commission_detail', args=[commission.id]),
        'accept_url': reverse('frontend:agent_accept_job', args=[commission.id]),
        'steps_url': reverse('frontend:agent_commission_steps', args=[commission.id]),
        'step_action_base_url': reverse('frontend:agent_commission_step_action', args=[commission.id, 'documents_review']),
        'step_action_urls': {
            'documents_review': reverse('frontend:agent_commission_step_action', args=[commission.id, 'documents_review']),
            'submit_to_lawyer': reverse('frontend:agent_commission_step_action', args=[commission.id, 'submit_to_lawyer']),
            'lawyer_verdict': reverse('frontend:agent_commission_step_action', args=[commission.id, 'lawyer_verdict']),
            'schedule_site_visit': reverse('frontend:agent_commission_step_action', args=[commission.id, 'schedule_site_visit']),
            'complete_site_visit': reverse('frontend:agent_commission_step_action', args=[commission.id, 'complete_site_visit']),
            'close': reverse('frontend:agent_commission_step_action', args=[commission.id, 'close']),
        },
        'review_url': reverse('frontend:lawyer_review_commission', args=[commission.id]),
        'transaction_url': reverse('frontend:payment_onboarding', args=[commission.transaction_id]) if commission.transaction_id else None,
        'can_accept': can_accept,
        'can_work': can_work,
        'can_review_documents': can_review_documents,
        'can_submit_to_lawyer': can_submit_to_lawyer,
        'can_schedule_site_visit': can_schedule_site_visit,
        'can_complete_site_visit': can_complete_site_visit,
        'can_close': can_close,
        'can_review_as_lawyer': can_review_as_lawyer,
        'is_buyer': is_buyer,
        'is_agent': is_agent,
        'is_lawyer': is_lawyer,
        'is_admin': is_admin,
    }


def serialize_status_page(*, title, description, tone='default', icon=None, primary_action=None, secondary_action=None, extra_actions=None):
    return {
        'icon': icon,
        'tone': tone,
        'title': title,
        'description': description,
        'primary_action': primary_action,
        'secondary_action': secondary_action,
        'extra_actions': extra_actions or [],
    }


def serialize_contract(transaction, user, *, documents, joint_breakdown=None, sign_url, payment_url, transactions_url, csrf_token):
    joint_breakdown_data = []
    for row in joint_breakdown or []:
        member = row.get('member')
        joint_breakdown_data.append({
            'member': serialize_joint_member(member),
            'amount': str(row.get('amount', '0')),
        })

    can_checkout = bool(
        transaction.contract_agreed
        and getattr(user, 'role', None) in {'Buyer', 'Admin'}
        and transaction.status in {'Initiated', 'Under_Verification'}
    )

    return {
        'transaction_id': str(transaction.id),
        'parcel_number': transaction.land_parcel.parcel_number,
        'buyer_email': transaction.buyer.email,
        'seller_email': transaction.seller.email,
        'agreed_price': str(transaction.agreed_price),
        'contract_agreed': bool(transaction.contract_agreed),
        'transaction_status': transaction.status,
        'checkout_available': can_checkout,
        'buyer_signature_present': bool(transaction.buyer_signature),
        'seller_signature_present': bool(transaction.seller_signature),
        'lawyer_signature_present': bool(transaction.lawyer_signature),
        'lawyer_name': transaction.lawyer_name,
        'lawyer_lsk_number': transaction.lawyer_lsk_number,
        'current_user_is_lawyer': getattr(user, 'role', None) == 'Lawyer',
        'is_joint_purchase': bool(transaction.is_joint_purchase),
        'joint_group_name': transaction.joint_group.name if transaction.is_joint_purchase and transaction.joint_group else None,
        'joint_group_ownership': transaction.joint_group.get_ownership_type_display() if transaction.is_joint_purchase and transaction.joint_group else None,
        'joint_breakdown': joint_breakdown_data,
        'documents': documents,
        'current_user_role': getattr(user, 'role', ''),
        'current_user_is_buyer': getattr(user, 'id', None) == getattr(transaction, 'buyer_id', None),
        'current_user_is_seller': getattr(user, 'id', None) == getattr(transaction, 'seller_id', None),
        'current_user_is_admin': getattr(user, 'role', None) == 'Admin',
        'current_user_is_joint_leader': bool(
            transaction.is_joint_purchase
            and transaction.joint_group
            and getattr(transaction.joint_group, 'leader_id', None) == getattr(user, 'id', None)
        ),
        'sign_url': sign_url,
        'payment_url': payment_url,
        'transactions_url': transactions_url,
        'csrf_token': csrf_token,
        'signature_data_name': 'signature_data',
        'admin_dual_sign': getattr(user, 'role', None) == 'Admin',
    }


def serialize_checkout(
    transaction,
    user,
    *,
    joint_breakdown=None,
    contributions=None,
    joint_bank_ready=False,
    joint_payment_method=None,
    paystack_enabled=False,
    process_url,
    transactions_url,
    sign_url,
    failed_url,
    csrf_token,
    phone_number='',
    escrow_bank_name=None,
    escrow_bank_account_name=None,
    escrow_bank_account_number=None,
    escrow_bank_branch=None,
):
    from core.services.service_fee import ServiceFeeService

    breakdown_data = []
    for row in joint_breakdown or []:
        member = row.get('member')
        breakdown_data.append({
            'member_name': member.full_name,
            'member_id': str(member.id),
            'share_percentage': str(member.share_percentage),
            'amount': str(row.get('amount', '0')),
            'phone_number': member.phone_number,
        })

    contribution_data = []
    for contribution in contributions or []:
        contribution_data.append({
            'member_name': contribution.member.full_name if contribution.member else 'Leader / Full Amount',
            'amount': str(contribution.amount),
            'channel': contribution.get_payment_channel_display() if hasattr(contribution, 'get_payment_channel_display') else contribution.payment_channel,
            'status': contribution.get_status_display() if hasattr(contribution, 'get_status_display') else contribution.status,
            'phone_number': contribution.phone_number,
            'bank_reference': contribution.bank_reference,
            'depositor_name': contribution.depositor_name,
        })

    group = transaction.joint_group if transaction.is_joint_purchase and transaction.joint_group else None
    fee_explanations = ServiceFeeService.get_fee_explanations()
    fee_breakdown = [
        {
            'key': 'land_price',
            'label': 'Land Price',
            'amount': str(transaction.agreed_price),
            'description': 'The negotiated purchase price for the parcel.',
            'included': True,
            'tone': 'default',
        },
        {
            'key': 'platform_service_fee',
            'label': fee_explanations['platform_service']['label'],
            'amount': str(transaction.platform_service_fee),
            'description': fee_explanations['platform_service']['what'],
            'note': fee_explanations['platform_service']['why'],
            'included': True,
            'tone': 'warning',
        },
        {
            'key': 'escrow_fee',
            'label': fee_explanations['escrow_holding']['label'],
            'amount': str(transaction.escrow_fee),
            'description': fee_explanations['escrow_holding']['what'],
            'note': fee_explanations['escrow_holding']['why'],
            'included': True,
            'tone': 'warning',
        },
        {
            'key': 'processing_fee',
            'label': fee_explanations['payment_processing']['label'],
            'amount': str(transaction.processing_fee),
            'description': fee_explanations['payment_processing']['what'],
            'note': fee_explanations['payment_processing']['why'],
            'included': True,
            'tone': 'default',
        },
        {
            'key': 'legal_verification_fee',
            'label': fee_explanations['verification']['label'],
            'amount': str(transaction.legal_verification_fee),
            'description': fee_explanations['verification']['what'],
            'note': 'Selected' if transaction.include_legal_verification else 'Optional',
            'included': bool(transaction.include_legal_verification),
            'tone': 'default',
        },
        {
            'key': 'due_diligence_fee',
            'label': fee_explanations['due_diligence']['label'],
            'amount': str(transaction.due_diligence_fee),
            'description': fee_explanations['due_diligence']['what'],
            'note': 'Selected' if transaction.include_due_diligence else 'Optional',
            'included': bool(transaction.include_due_diligence),
            'tone': 'default',
        },
        {
            'key': 'total_payable',
            'label': 'TOTAL PAYABLE',
            'amount': str(transaction.total_payable),
            'description': 'Land price plus all selected service fees.',
            'included': True,
            'tone': 'success',
        },
    ]
    return {
        'transaction_id': str(transaction.id),
        'parcel_number': transaction.land_parcel.parcel_number,
        'seller_email': transaction.seller.email,
        'buyer_email': transaction.buyer.email,
        'agreed_price': str(transaction.agreed_price),
        'land_price': str(transaction.agreed_price),
        'is_joint_purchase': bool(transaction.is_joint_purchase),
        'joint_group_name': group.name if group else None,
        'joint_group_ownership': group.get_ownership_type_display() if group else None,
        'joint_payment_method': group.get_preferred_payment_method_display() if group else None,
        'joint_bank_ready': bool(joint_bank_ready),
        'paystack_enabled': bool(paystack_enabled),
        'breakdown': breakdown_data,
        'contributions': contribution_data,
        'phone_number': phone_number,
        'csrf_token': csrf_token,
        'process_url': process_url,
        'transactions_url': transactions_url,
        'sign_url': sign_url,
        'failed_url': failed_url,
        'default_payment_method': 'joint_bank_account' if group and group.preferred_payment_method == 'Joint_Bank_Account' else 'm_pesa',
        'bank_name': group.bank_name if group else None,
        'bank_account_name': group.bank_account_name if group else None,
        'bank_account_number': group.bank_account_number if group else None,
        'bank_branch': group.bank_branch if group else None,
        'escrow_bank_name': escrow_bank_name,
        'escrow_bank_account_name': escrow_bank_account_name,
        'escrow_bank_account_number': escrow_bank_account_number,
        'escrow_bank_branch': escrow_bank_branch,
        'platform_service_fee': str(transaction.platform_service_fee),
        'escrow_fee': str(transaction.escrow_fee),
        'processing_fee': str(transaction.processing_fee),
        'legal_verification_fee': str(transaction.legal_verification_fee),
        'due_diligence_fee': str(transaction.due_diligence_fee),
        'include_legal_verification': bool(transaction.include_legal_verification),
        'include_due_diligence': bool(transaction.include_due_diligence),
        'fee_breakdown': fee_breakdown,
        'fee_explanations': fee_explanations,
        'grand_total': str(transaction.total_payable),
        'total_payable': str(transaction.total_payable),
    }


def serialize_recommendations_page(recommended, rec_type, popular_parcels, popular_county, recently_viewed, hot_deals=None, recently_viewed_similar=None, trending_in_target_area=None, people_also_viewed=None, sponsored_listings=None, user=None):
    def _serialize_parcels(parcels):
        return [serialize_parcel(parcel, user) for parcel in parcels]

    recommended_data = []
    for parcel, score in recommended or []:
        item = serialize_parcel(parcel, user)
        item['match_score'] = score
        recommended_data.append(item)

    return {
        'rec_type': rec_type,
        'recommended': recommended_data,
        'popular_county': popular_county,
        'popular_parcels': _serialize_parcels(popular_parcels or []),
        'recently_viewed': _serialize_parcels(recently_viewed or []),
        'hot_deals': _serialize_parcels(hot_deals or []),
        'recently_viewed_similar': _serialize_parcels(recently_viewed_similar or []),
        'trending_in_target_area': _serialize_parcels(trending_in_target_area or []),
        'people_also_viewed': _serialize_parcels(people_also_viewed or []),
        'sponsored_listings': _serialize_parcels(sponsored_listings or []),
    }


def serialize_prediction_result(result):
    if not result:
        return None
    if result.get('error'):
        return {'error': result['error']}

    comparisons = [
        {
            'county': comparison.get('county', ''),
            'constituency': comparison.get('constituency', ''),
            'land_use': comparison.get('land_use', ''),
            'size_acres': str(comparison.get('size_acres', '')),
            'price_per_acre': str(comparison.get('price_per_acre', '')),
        }
        for comparison in result.get('comparisons', [])
    ]

    model_accuracy = result.get('model_accuracy', '')
    try:
        model_accuracy = f"{float(model_accuracy) * 100:.1f}%"
    except (TypeError, ValueError):
        model_accuracy = str(model_accuracy)

    return {
        'county': result.get('county'),
        'land_use': result.get('land_use'),
        'size_acres': str(result.get('size_acres', '')),
        'price_per_acre': str(result.get('price_per_acre', '')),
        'total_value': str(result.get('total_value', '')),
        'confidence_low': str(result.get('confidence_low', '')),
        'confidence_high': str(result.get('confidence_high', '')),
        'model_accuracy': model_accuracy,
        'comparisons': comparisons,
    }


def serialize_law(law):
    return {
        'title': law['title'],
        'citation': law['citation'],
        'applies_to': law['applies_to'],
        'summary': law['summary'],
        'official_url': law['official_url'],
        'required': law.get('required', False),
    }


def serialize_joint_member(member):
    return {
        'id': str(member.id),
        'full_name': member.full_name,
        'share_percentage': str(member.share_percentage),
        'phone_number': member.phone_number,
        'email': member.email,
        'id_number': member.id_number,
        'kra_pin': member.kra_pin,
        'is_leader': member.is_leader,
        'has_signed': member.has_signed,
        'signature_status': 'Signed' if member.has_signed else 'Pending',
        'edit_url': reverse('frontend:edit_joint_member', args=[member.id]),
        'delete_url': reverse('frontend:delete_joint_member', args=[member.id]),
    }


def serialize_joint_member_removal_request(removal_request):
    return {
        'id': str(removal_request.id),
        'group_id': str(removal_request.group_id),
        'group_name': removal_request.group.name if removal_request.group_id else '',
        'member': serialize_joint_member(removal_request.member),
        'requested_by': serialize_user(removal_request.requested_by),
        'consent_confirmed': removal_request.consent_confirmed,
        'compensation_confirmed': removal_request.compensation_confirmed,
        'compensation_amount': str(removal_request.compensation_amount) if removal_request.compensation_amount is not None else None,
        'notes': removal_request.notes,
        'status': removal_request.status,
        'status_label': removal_request.get_status_display() if hasattr(removal_request, 'get_status_display') else removal_request.status,
        'admin_reviewed_by': serialize_user(removal_request.admin_reviewed_by) if removal_request.admin_reviewed_by else None,
        'admin_reviewed_at': removal_request.admin_reviewed_at.strftime('%b %d, %Y %H:%M') if getattr(removal_request, 'admin_reviewed_at', None) else None,
        'admin_notes': removal_request.admin_notes,
        'created_at': removal_request.created_at.strftime('%b %d, %Y %H:%M'),
        'approve_url': reverse('frontend:approve_joint_member_removal', args=[removal_request.id]),
        'reject_url': reverse('frontend:reject_joint_member_removal', args=[removal_request.id]),
    }


def serialize_joint_group(group, user=None):
    members = [serialize_joint_member(member) for member in group.members.all()]
    is_group_leader = bool(user and getattr(user, 'id', None) == getattr(group, 'leader_id', None))
    is_admin = bool(user and getattr(user, 'role', None) == 'Admin')
    can_manage = is_group_leader or is_admin
    return {
        'id': str(group.id),
        'name': group.name,
        'group_type': group.get_group_type_display(),
        'ownership_type': group.get_ownership_type_display(),
        'preferred_payment_method': group.preferred_payment_method,
        'bank_name': group.bank_name,
        'bank_account_name': group.bank_account_name,
        'bank_account_number': group.bank_account_number,
        'bank_branch': group.bank_branch,
        'total_share': str(group.total_share),
        'is_valid': group.is_valid,
        'members': members,
        'detail_url': reverse('frontend:joint_group_detail', args=[group.id]),
        'edit_url': reverse('frontend:edit_joint_group', args=[group.id]),
        'laws_url': reverse('frontend:joint_laws'),
        'add_member_url': reverse('frontend:add_joint_member', args=[group.id]) if can_manage else None,
        'transfer_leadership_url': reverse('frontend:transfer_joint_leadership', args=[group.id]) if can_manage else None,
        'can_manage': can_manage,
        'is_group_leader': is_group_leader,
        'can_view_members': True,
    }


def serialize_messages(request):
    return [{'level': message.level_tag, 'text': str(message)} for message in get_messages(request)]


def serialize_message_thread(partner, messages, user):
    return {
        'partner': serialize_user(partner),
        'latest_timestamp': messages[0].timestamp.strftime('%b %d, %Y') if messages else '',
        'count': len(messages),
        'url': reverse('frontend:message_thread_detail', args=[partner.id]),
        'messages': [
            {
                'id': str(message.id),
                'sender_email': message.sender.email,
                'content': message.content,
                'timestamp': message.timestamp.strftime('%b %d, %Y %H:%M'),
                'is_self': getattr(message.sender, 'id', None) == getattr(user, 'id', None),
            }
            for message in messages
        ],
    }


def serialize_support_ticket(ticket):
    return {
        'id': str(ticket.id),
        'subject': ticket.subject,
        'message_excerpt': ticket.message[:160] + ('...' if len(ticket.message) > 160 else ''),
        'status': ticket.status,
        'created_at': ticket.created_at.strftime('%b %d, %Y') if getattr(ticket, 'created_at', None) else '',
    }


def _field_type(bound_field):
    widget = bound_field.field.widget
    if isinstance(widget, django_forms.Textarea):
        return 'textarea'
    if isinstance(widget, django_forms.Select):
        return 'select'
    if isinstance(widget, django_forms.RadioSelect):
        return 'radio'
    if isinstance(widget, django_forms.CheckboxInput):
        return 'checkbox'
    if isinstance(widget, django_forms.ClearableFileInput):
        return 'file'
    input_type = getattr(widget, 'input_type', 'text') or 'text'
    if input_type == 'password':
        return 'password'
    if input_type == 'email':
        return 'email'
    if input_type == 'number':
        return 'number'
    if input_type == 'tel':
        return 'tel'
    if input_type == 'url':
        return 'url'
    if input_type == 'hidden':
        return 'hidden'
    return 'text'


def _serialize_bound_field(bound_field):
    field = bound_field.field
    widget = field.widget
    field_type = _field_type(bound_field)
    attrs = getattr(widget, 'attrs', {}) or {}
    value = bound_field.value()
    if value is None:
        value = ''
    if isinstance(value, (list, tuple)):
        value = ','.join(str(item) for item in value)
    value = str(value)

    options = None
    if field_type in {'select', 'radio'} and getattr(field, 'choices', None):
        options = [
            {
                'value': str(choice_value),
                'label': str(choice_label),
                'selected': str(choice_value) == value,
                'disabled': False,
            }
            for choice_value, choice_label in field.choices
        ]

    return {
        'name': bound_field.html_name,
        'label': bound_field.label or bound_field.name.replace('_', ' ').title(),
        'type': field_type,
        'value': value,
        'checked': bool(bound_field.value()) if field_type == 'checkbox' else None,
        'placeholder': attrs.get('placeholder'),
        'helpText': str(field.help_text) if field.help_text else None,
        'required': bool(field.required),
        'disabled': bool(field.disabled),
        'rows': int(attrs.get('rows', 4)) if field_type == 'textarea' else None,
        'min': attrs.get('min'),
        'max': attrs.get('max'),
        'step': attrs.get('step'),
        'accept': attrs.get('accept'),
        'options': options,
        'errors': [str(error) for error in bound_field.errors],
        'autoFocus': bool(attrs.get('autofocus')),
    }


def _serialize_hidden_field(bound_field):
    value = bound_field.value()
    return {
        'name': bound_field.html_name,
        'value': '' if value is None else str(value),
    }


def serialize_form(form, *, action, submit_label, method='post', cancel_label=None, cancel_href=None, intro=None, sections=None):
    fields = [_serialize_bound_field(bound_field) for bound_field in form.visible_fields()]
    hidden_fields = [_serialize_hidden_field(bound_field) for bound_field in form.hidden_fields()]
    data = {
        'action': action,
        'method': method,
        'enctype': 'multipart/form-data' if form.is_multipart() else 'application/x-www-form-urlencoded',
        'submitLabel': submit_label,
        'cancelLabel': cancel_label,
        'cancelHref': cancel_href,
        'intro': intro,
        'hiddenFields': hidden_fields,
        'errors': [str(error) for error in form.non_field_errors()],
    }

    if sections:
        by_name = {field['name']: field for field in fields}
        grouped = []
        used = set()
        for section in sections:
            section_fields = []
            for name in section.get('fields', []):
                if name in by_name:
                    section_fields.append(by_name[name])
                    used.add(name)
            grouped.append({
                'title': section.get('title'),
                'subtitle': section.get('subtitle'),
                'fields': section_fields,
            })
        remainder = [field for field in fields if field['name'] not in used]
        if remainder:
            grouped.append({'fields': remainder})
        data['sections'] = grouped
    else:
        data['fields'] = fields

    return data


def serialize_formset(formset, *, action, submit_label, method='post', intro=None):
    rows = []
    for index, form in enumerate(formset.forms):
        rows.append({
            'index': index,
            'fields': [_serialize_bound_field(bound_field) for bound_field in form.visible_fields()],
            'hiddenFields': [_serialize_hidden_field(bound_field) for bound_field in form.hidden_fields()],
        })

    return {
        'action': action,
        'method': method,
        'enctype': 'multipart/form-data' if formset.is_multipart() else 'application/x-www-form-urlencoded',
        'submitLabel': submit_label,
        'intro': intro,
        'managementFields': [_serialize_hidden_field(bound_field) for bound_field in formset.management_form.hidden_fields()],
        'formsetRows': rows,
        'errors': [str(error) for error in formset.non_form_errors()],
    }
