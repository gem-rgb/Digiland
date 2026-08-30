"""
Account and Resource-Level Authorization Service.
Enforces data-driven permissions across:
- Account Membership & Governance
- Property Due Diligence & Listing
- Group Decisions & Voting
- Transactions & Escrow Authorizations
- Legal Signatory Overrides
"""
from typing import Any, Optional
from django.contrib.auth import get_user_model
from core.models import Account, AccountMember, PropertyOwner, AccountDecision

User = get_user_model()


class Action:
    # Account Actions
    INVITE_MEMBER = 'INVITE_MEMBER'
    CHANGE_MEMBER_ROLE = 'CHANGE_MEMBER_ROLE'
    PROPOSE_MEMBER_REMOVAL = 'PROPOSE_MEMBER_REMOVAL'
    CHANGE_MANAGER = 'CHANGE_MANAGER'
    CLOSE_ACCOUNT = 'CLOSE_ACCOUNT'
    EDIT_ACCOUNT_PROFILE = 'EDIT_ACCOUNT_PROFILE'
    VIEW_ACCOUNT = 'VIEW_ACCOUNT'

    # Property Actions
    SAVE_PROPERTY = 'SAVE_PROPERTY'
    EXPRESS_INTEREST = 'EXPRESS_INTEREST'
    INITIATE_DUE_DILIGENCE = 'INITIATE_DUE_DILIGENCE'
    VIEW_PROPERTY_DOCS = 'VIEW_PROPERTY_DOCS'
    LIST_PROPERTY = 'LIST_PROPERTY'

    # Decision & Voting Actions
    CREATE_DECISION = 'CREATE_DECISION'
    CAST_VOTE = 'CAST_VOTE'
    CANCEL_DECISION = 'CANCEL_DECISION'
    REQUEST_DISCUSSION = 'REQUEST_DISCUSSION'

    # Transaction Actions
    INITIATE_PURCHASE = 'INITIATE_PURCHASE'
    APPROVE_PURCHASE = 'APPROVE_PURCHASE'
    INITIATE_PAYMENT = 'INITIATE_PAYMENT'
    SIGN_CONTRACT = 'SIGN_CONTRACT'
    INITIATE_SALE = 'INITIATE_SALE'
    APPROVE_SALE = 'APPROVE_SALE'


def get_account_membership(user: User, account: Account) -> Optional[AccountMember]:
    """Retrieve active AccountMember record for a given user and account."""
    if not user or not user.is_authenticated or not account:
        return None
    return AccountMember.objects.filter(
        account=account,
        user=user,
        status='ACTIVE'
    ).first()


def can(user_or_member: Any, action: str, resource: Any = None, account: Optional[Account] = None) -> bool:
    """
    Main authorization evaluator: can(actor, action, resource, account) -> bool.
    Evaluates role permissions, custom permissions, and legal signatory requirements.
    """
    if not user_or_member:
        return False

    # Resolve User and AccountMember
    if isinstance(user_or_member, AccountMember):
        member = user_or_member
        user = member.user
        if not account:
            account = member.account
    elif isinstance(user_or_member, User):
        user = user_or_member
        if not user.is_authenticated:
            return False
        if user.is_superuser:
            return True
        if account:
            member = get_account_membership(user, account)
        else:
            member = None
    else:
        return False

    # If action is on an Account and actor is an individual with an Individual Account
    if account and account.account_type == 'INDIVIDUAL':
        if account.created_by == user:
            return True
        return False

    # If actor has no active membership in the target account
    if not member and account:
        # Check if user is the account creator
        if account.created_by == user:
            return True
        return False

    if not member:
        return False

    role = member.role
    custom_perms = member.custom_permissions or []

    # Custom permission override
    if action in custom_perms:
        return True

    # 1. ACCOUNT GOVERNANCE ACTIONS
    if action == Action.VIEW_ACCOUNT:
        return member.status == 'ACTIVE'

    if action == Action.EDIT_ACCOUNT_PROFILE:
        return role in ['BUYER_TEAM_MANAGER', 'SELLER_TEAM_MANAGER', 'PRIMARY_REPRESENTATIVE']

    if action == Action.INVITE_MEMBER:
        return role in ['BUYER_TEAM_MANAGER', 'SELLER_TEAM_MANAGER', 'PRIMARY_REPRESENTATIVE', 'AUTHORIZED_REPRESENTATIVE']

    if action == Action.CHANGE_MEMBER_ROLE:
        return role in ['BUYER_TEAM_MANAGER', 'SELLER_TEAM_MANAGER', 'PRIMARY_REPRESENTATIVE']

    if action == Action.PROPOSE_MEMBER_REMOVAL:
        # Anyone with manager or co-buyer status can propose removal, but nobody can unilaterally delete
        return role in ['BUYER_TEAM_MANAGER', 'SELLER_TEAM_MANAGER', 'CO_BUYER', 'PRIMARY_REPRESENTATIVE', 'AUTHORIZED_REPRESENTATIVE']

    if action == Action.CHANGE_MANAGER or action == Action.CLOSE_ACCOUNT:
        return role in ['BUYER_TEAM_MANAGER', 'SELLER_TEAM_MANAGER', 'CO_BUYER', 'PRIMARY_REPRESENTATIVE']

    # 2. PROPERTY ACTIONS
    if action in [Action.SAVE_PROPERTY, Action.VIEW_PROPERTY_DOCS]:
        return member.status == 'ACTIVE'

    if action in [Action.EXPRESS_INTEREST, Action.INITIATE_DUE_DILIGENCE]:
        return role in [
            'BUYER_TEAM_MANAGER', 'SELLER_TEAM_MANAGER', 'CO_BUYER',
            'PRIMARY_REPRESENTATIVE', 'AUTHORIZED_REPRESENTATIVE', 'TRANSACTION_OFFICER'
        ]

    if action == Action.LIST_PROPERTY:
        return role in ['SELLER_TEAM_MANAGER', 'PRIMARY_REPRESENTATIVE', 'AUTHORIZED_REPRESENTATIVE', 'TRANSACTION_OFFICER']

    # 3. DECISION & VOTING ACTIONS
    if action == Action.CREATE_DECISION:
        return role in [
            'BUYER_TEAM_MANAGER', 'SELLER_TEAM_MANAGER', 'CO_BUYER',
            'PRIMARY_REPRESENTATIVE', 'AUTHORIZED_REPRESENTATIVE', 'TRANSACTION_OFFICER'
        ]

    if action in [Action.CAST_VOTE, Action.REQUEST_DISCUSSION]:
        # Every active member/representative has 1 vote
        return member.status == 'ACTIVE' and role != 'VIEWER'

    if action == Action.CANCEL_DECISION:
        if isinstance(resource, AccountDecision):
            return resource.created_by == user or role in ['BUYER_TEAM_MANAGER', 'SELLER_TEAM_MANAGER', 'PRIMARY_REPRESENTATIVE']
        return role in ['BUYER_TEAM_MANAGER', 'SELLER_TEAM_MANAGER', 'PRIMARY_REPRESENTATIVE']

    # 4. TRANSACTION ACTIONS
    if action == Action.INITIATE_PURCHASE:
        return role in [
            'BUYER_TEAM_MANAGER', 'CO_BUYER', 'PRIMARY_REPRESENTATIVE',
            'AUTHORIZED_REPRESENTATIVE', 'TRANSACTION_OFFICER'
        ]

    if action == Action.APPROVE_PURCHASE:
        return role in [
            'BUYER_TEAM_MANAGER', 'CO_BUYER', 'PRIMARY_REPRESENTATIVE',
            'AUTHORIZED_REPRESENTATIVE', 'FINANCE_OFFICER'
        ]

    if action == Action.INITIATE_PAYMENT:
        return role in [
            'BUYER_TEAM_MANAGER', 'FINANCIAL_CONTRIBUTOR', 'CO_BUYER',
            'PRIMARY_REPRESENTATIVE', 'FINANCE_OFFICER'
        ]

    if action == Action.SIGN_CONTRACT:
        # Legal override check: does this user hold legal ownership rights or statutory authority?
        if resource:
            parcel = getattr(resource, 'land_parcel', None) or resource
            if hasattr(parcel, 'legal_owners'):
                # Check if legal owners are defined
                legal_owners = parcel.legal_owners.all()
                if legal_owners.exists():
                    user_is_legal_owner = legal_owners.filter(user=user, is_mandatory_signatory=True).exists()
                    if user_is_legal_owner:
                        return True
        return role in [
            'BUYER_TEAM_MANAGER', 'SELLER_TEAM_MANAGER', 'CO_BUYER',
            'PRIMARY_REPRESENTATIVE', 'AUTHORIZED_REPRESENTATIVE'
        ]

    if action in [Action.INITIATE_SALE, Action.APPROVE_SALE]:
        return role in ['SELLER_TEAM_MANAGER', 'PRIMARY_REPRESENTATIVE', 'AUTHORIZED_REPRESENTATIVE']

    return False


def verify_legal_ownership_signoffs(land_parcel, transaction=None) -> dict:
    """
    Checks if all mandatory statutory legal owners have consented to the transaction.
    Ensures that a majority vote inside Digiland never overrides registered legal property rights.
    """
    legal_owners = PropertyOwner.objects.filter(land_parcel=land_parcel)
    if not legal_owners.exists():
        return {
            'has_legal_owners_registered': False,
            'is_fully_authorized': True,
            'message': 'No external statutory ownership split registered; standard seller mandate applies.',
            'pending_owners': []
        }

    mandatory_owners = legal_owners.filter(is_mandatory_signatory=True)
    total_percentage = sum(o.ownership_percentage for o in legal_owners)
    
    pending_owners = []
    for owner in mandatory_owners:
        if owner.legal_verification_status != 'LAWYER_VERIFIED':
            pending_owners.append({
                'name': owner.full_legal_name,
                'id_number': owner.id_number_or_reg,
                'share': float(owner.ownership_percentage),
                'status': owner.legal_verification_status
            })

    is_fully_authorized = len(pending_owners) == 0

    return {
        'has_legal_owners_registered': True,
        'is_fully_authorized': is_fully_authorized,
        'total_registered_shares': float(total_percentage),
        'pending_owners': pending_owners,
        'message': 'All legal owner verifications complete.' if is_fully_authorized else f'{len(pending_owners)} mandatory legal owner(s) require lawyer verification.'
    }
