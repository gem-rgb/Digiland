from django.http import Http404
from django.core.exceptions import ValidationError
from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.middleware.csrf import get_token
from django.db import models
from django.db.models import Q
from django.utils import timezone
from django.contrib import messages as django_messages
from datetime import timedelta
from core.models import LandParcel, Transaction, PurchaseCommission, Message, SupportTicket, Document, User as CoreUser, AgentKYCApplication, AgentRating, ParcelView, UserFavorite, JointBuyerGroup, JointBuyerMember, JointPaymentContribution, JointMemberRemovalRequest, AuditLog, PopupAdCampaign, DocumentAccessGrant, LawyerPostTransactionTask
from core.legal import (
    LAND_TRANSACTION_LAWS,
    LAND_TRANSACTION_CHECKLIST,
    JOINT_LAND_TRANSACTION_LAWS,
    JOINT_LAND_TRANSACTION_CHECKLIST,
    JOINT_PAYMENT_GUIDANCE,
    KENYAN_LAND_DOCUMENTS,
    JOINT_KENYAN_LAND_DOCUMENTS,
)
from .forms import LandParcelUploadForm
from core.forms import AgentRatingForm, DocumentUploadForm, JointBuyerGroupForm, JointBuyerMemberFormSet, JointBuyerMemberForm, JointLeaderTransferForm, JointMemberRemovalRequestForm, PricePredictionForm, PopupAdCampaignForm
from .react_data import (
    build_nav,
    serialize_checkout,
    serialize_contract,
    serialize_document,
    serialize_form,
    serialize_formset,
    serialize_joint_group,
    serialize_joint_member_removal_request,
    serialize_law,
    serialize_message_thread,
    serialize_messages,
    serialize_parcel,
    serialize_prediction_result,
    serialize_recommendations_page,
    serialize_review_user,
    serialize_status_page,
    serialize_support_ticket,
    serialize_transaction,
    serialize_commission,
    serialize_user,
)
from core.services.popup_ads import build_popup_ads_payload, build_seller_promotions_dashboard, record_popup_event
from core.services.commission import (
    accept_commission,
    advance_step,
    close_commission,
    complete_site_visit,
    create_commission,
    find_nearby_agents,
    get_default_lawyer,
    lawyer_verdict,
    resolve_agent_region,
    review_documents,
    schedule_site_visit,
    submit_to_lawyer,
)
from .public_pages import PUBLIC_PAGES

def is_seller_or_agent(user):
    if not user.is_authenticated:
        return False
    # Strict Fencing: Agents must be KYC verified by Admin offline
    if user.role == 'Agent' and not user.is_identity_verified:
        return False
    return user.role in ['Seller', 'Agent', 'Admin']

def is_verified_agent_or_admin(user):
    if not user.is_authenticated:
        return False
    if user.role in ['Admin', 'Lawyer']:
        return True
    if user.role == 'Agent' and user.is_identity_verified:
        return True
    return False

STAFF_ROLES = {'Admin', 'Agent', 'Lawyer'}


def _pin_token(pin, user, parcel):
    import hashlib, hmac
    from django.conf import settings
    value = f'{user.id}:{parcel.id}:{pin.strip()}'
    return hmac.new(settings.SECRET_KEY.encode(), value.encode(), hashlib.sha256).hexdigest()


def _verify_or_set_access_pin(user, pin, parcel):
    import hmac
    if not pin or not pin.isdigit() or len(pin) != 6:
        raise ValidationError('Enter a valid 6-digit authorization PIN.')
    token = _pin_token(pin, user, parcel)
    if user.document_access_pin_hash and not hmac.compare_digest(user.document_access_pin_hash, token):
        raise ValidationError('That PIN does not match your saved document access PIN.')
    if not user.document_access_pin_hash:
        user.document_access_pin_hash = token
        user.save(update_fields=['document_access_pin_hash'])
    return token


def _active_document_grant(parcel, accessor):
    return DocumentAccessGrant.objects.filter(
        parcel=parcel, accessor=accessor, access_granted=True,
    ).order_by('-created_at').first()


def render_react_shell(request, page, title, subtitle='', status=200, **extra):
    popup_context = extra.pop('popup_context', None)
    bootstrap = {
        'page': page,
        'title': title,
        'subtitle': subtitle,
        'user': serialize_user(request.user),
        'nav': build_nav(request.user, active=page),
        'messages': serialize_messages(request),
    }
    bootstrap['csrf_token'] = get_token(request)
    if request.user.is_authenticated:
        bootstrap['logout_url'] = reverse('account_logout')
    try:
        bootstrap['popup_ads'] = build_popup_ads_payload(request, page, context=popup_context)
    except Exception:
        bootstrap['popup_ads'] = {'enabled': False, 'page': page, 'candidates': {}, 'primary': None}
    bootstrap.update(extra)
    return render(request, 'frontend/react_shell.html', {'react_bootstrap': bootstrap}, status=status)


def custom_404_view(request, exception=None):
    """Friendly, branded custom 404 error page."""
    try:
        return render_react_shell(
            request,
            '404',
            'Page Not Found - Digiland',
            'The page or resource you are looking for does not exist or has been moved.',
            status=404
        )
    except Exception:
        return render(request, '404.html', status=404)


def custom_500_view(request):
    """Diagnose and render internal server errors cleanly."""
    import sys, traceback
    from django.http import HttpResponse
    exc_type, exc_value, exc_traceback = sys.exc_info()
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_traceback)) if exc_type else "No traceback available."
    return HttpResponse(f"<h1>Server Error (500)</h1><pre style='background:#111;color:#ff6b6b;padding:1rem;border-radius:8px;'>{tb_str}</pre>", status=500, content_type="text/html")


def public_marketing_page(request, page_key):
    page = PUBLIC_PAGES.get(page_key)
    if not page:
        raise Http404(f'Unknown public page: {page_key}')

    extra = {
        'actions': page.get('actions', []),
    }
    content = page.get('content')
    if content is not None:
        extra['content'] = content
    content_key = page.get('content_key')
    if content_key:
        extra['content_key'] = content_key

    return render_react_shell(
        request,
        'content',
        page['title'],
        page['subtitle'],
        **extra,
    )


def is_joint_buyer(user):
    if not user.is_authenticated:
        return False
    if user.role == 'Admin':
        return True
    if user.role != 'Buyer':
        return False
    if getattr(user, 'buyer_account_type', None) == 'Joint':
        return True
    try:
        return user.led_joint_groups.exists()
    except Exception:
        return False


def commission_region_matches_agent(commission, agent):
    county, constituency, _ = resolve_agent_region(agent)
    if not county or not constituency:
        return False
    return (
        commission.target_county.strip().lower() == county.strip().lower()
        and commission.target_constituency.strip().lower() == constituency.strip().lower()
    )


def can_view_commission(user, commission):
    if not getattr(user, 'is_authenticated', False):
        return False
    if getattr(user, 'role', None) == 'Admin':
        return True
    if getattr(user, 'id', None) in {getattr(commission, 'buyer_id', None), getattr(commission, 'accepted_by_id', None), getattr(commission, 'assigned_lawyer_id', None)}:
        return True
    if getattr(user, 'role', None) == 'Agent':
        if commission.status == 'Open':
            return commission_region_matches_agent(commission, user)
        return getattr(commission, 'accepted_by_id', None) == getattr(user, 'id', None)
    if getattr(user, 'role', None) == 'Lawyer':
        return getattr(user, 'role', None) == 'Admin' or getattr(commission, 'assigned_lawyer_id', None) == getattr(user, 'id', None)
    return False

def home(request):
    from django.db.models import Q
    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    public_buyer_statuses = ['AGENT_APPROVED', 'Verified', 'BUYER_OFFER_RECEIVED', 'LAWYER_REVIEW', 'LAWYER_APPROVED', 'PURCHASE_FINALIZED', 'Completed']
    try:
        parcels_qs = LandParcel.objects.filter(verification_status__in=public_buyer_statuses).exclude(transactions__status__in=active_tx_statuses).order_by('-ardhisasa_last_synced')[:5]
        parcels = list(parcels_qs)
    except Exception as exc:
        import logging
        logging.getLogger(__name__).warning("Home parcel query fallback triggered: %s", exc)
        try:
            from django.core.management import call_command
            call_command("migrate", interactive=False, verbosity=0)
            parcels_qs = LandParcel.objects.filter(verification_status__in=public_buyer_statuses).exclude(transactions__status__in=active_tx_statuses).order_by('-ardhisasa_last_synced')[:5]
            parcels = list(parcels_qs)
        except Exception:
            parcels = []

    
    transactions = None
    if request.user.is_authenticated:
        if request.user.role == 'Admin':
            transactions = Transaction.objects.all().order_by('-created_at')[:5]
        else:
            transactions = Transaction.objects.filter(Q(buyer=request.user) | Q(seller=request.user)).distinct().order_by('-created_at')[:5]
    
    if request.user.is_authenticated:
        if request.user.role == 'Seller':
            try:
                seller_parcels = LandParcel.objects.filter(listed_by=request.user).order_by('-updated_at')
                recent_parcels = [serialize_parcel(parcel, request.user) for parcel in seller_parcels]
            except Exception:
                recent_parcels = []
        else:
            recent_parcels = [serialize_parcel(parcel, request.user) for parcel in parcels]
        recent_transactions = [serialize_transaction(tx, request.user) for tx in transactions] if transactions else []
        buyer_commissions = []
        active_buyer_commissions = PurchaseCommission.objects.none()

        if request.user.role == 'Buyer':
            buyer_commissions_qs = PurchaseCommission.objects.filter(
                buyer=request.user,
            ).select_related('buyer', 'land_parcel', 'accepted_by', 'assigned_lawyer', 'transaction').order_by('-created_at')
            active_buyer_commissions = buyer_commissions_qs.filter(
                status__in=['Open', 'Accepted', 'Documents_Review', 'Lawyer_Verification', 'Site_Visit_Scheduled', 'Site_Visit_Complete', 'Closing']
            )
            buyer_commissions = [serialize_commission(commission, request.user) for commission in buyer_commissions_qs[:5]]

        # Build role-specific stats
        if request.user.role == 'Seller':
            from django.db.models import Sum, Avg
            completed_tx = Transaction.objects.filter(seller=request.user, status='Completed')
            escrow_tx = Transaction.objects.filter(seller=request.user, status__in=['Deposit_Paid', 'Under_Verification', 'Verification_Hiatus'])
            total_received = completed_tx.aggregate(total=Sum('agreed_price'))['total'] or 0
            in_escrow = escrow_tx.aggregate(total=Sum('agreed_price'))['total'] or 0
            # Simple rating: average of ratings given by buyers on transactions with this seller
            seller_rating = AgentRating.objects.filter(agent=request.user).aggregate(avg=Avg('rating'))['avg']
            rating_display = f"{seller_rating:.1f} / 5.0" if seller_rating else 'No ratings yet'
            stats = [
                {'label': 'Listed parcels', 'value': str(LandParcel.objects.filter(listed_by=request.user).count()), 'tone': 'success'},
                {'label': 'Seller rating', 'value': rating_display, 'tone': 'accent'},
                {'label': 'Payments received', 'value': f'KES {total_received:,.0f}', 'tone': 'success'},
                {'label': 'In escrow', 'value': f'KES {in_escrow:,.0f}', 'tone': 'warning'},
            ]
        elif request.user.role == 'Buyer':
            stats = [
                {'label': 'Verified parcels', 'value': str(len(recent_parcels)), 'tone': 'success'},
                {'label': 'Recent transactions', 'value': str(len(recent_transactions)), 'tone': 'accent'},
                {'label': 'Active commissions', 'value': str(active_buyer_commissions.count()), 'tone': 'warning'},
                {'label': 'Account type', 'value': getattr(request.user, 'buyer_account_type', None) or request.user.role, 'tone': 'default'},
            ]
        else:
            stats = [
                {'label': 'Verified parcels', 'value': str(len(recent_parcels)), 'tone': 'success'},
                {'label': 'Recent transactions', 'value': str(len(recent_transactions)), 'tone': 'accent'},
                {'label': 'Account type', 'value': getattr(request.user, 'buyer_account_type', None) or request.user.role, 'tone': 'warning'},
                {'label': 'Status', 'value': 'Signed in', 'tone': 'default'},
            ]

        # Build role-specific actions
        if request.user.role == 'Seller':
            dashboard_actions = [
                {'label': 'List new parcel', 'href': reverse('frontend:parcel_upload'), 'tone': 'default'},
                {'label': 'My parcels', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
                {'label': 'Withdraw funds', 'href': reverse('frontend:seller_withdraw'), 'tone': 'secondary'},
                {'label': 'Messages', 'href': reverse('frontend:messages'), 'tone': 'secondary'},
            ]
        elif request.user.role == 'Buyer':
            dashboard_actions = [
                {'label': 'Browse parcels', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
                {'label': 'Open transactions', 'href': reverse('frontend:transactions'), 'tone': 'secondary'},
            ]
        else:
            dashboard_actions = [
                {'label': 'Browse parcels', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
                {'label': 'Open transactions', 'href': reverse('frontend:transactions'), 'tone': 'secondary'},
            ]
        if request.user.role == 'Buyer' and not getattr(request.user, 'buyer_account_type', None):
            dashboard_actions.insert(0, {'label': 'Buyer setup', 'href': reverse('frontend:buyer_account_choice'), 'tone': 'outline'})

        dashboard_title = {
            'Buyer': 'Buyer Dashboard - Digiland',
            'Seller': 'Seller Dashboard - Digiland',
        }.get(request.user.role, 'Workspace - Digiland')

        return render_react_shell(
            request,
            'dashboard',
            dashboard_title,
            'Unified workspace for parcels, contracts, and escrow activity.',
            parcels=recent_parcels,
            transactions=recent_transactions,
            commissions=buyer_commissions,
            stats=stats,
            actions=dashboard_actions,
        )
    context = {
        'parcels': parcels,
        'transactions': transactions
    }
    return render_react_shell(
        request,
        'landing',
        'Digiland - Secure Land Escrow',
        'Secure land listings, verified contracts, and joint purchase support.',
        parcels=[serialize_parcel(parcel) for parcel in parcels],
        stats=[
            {'label': 'Verified parcels', 'value': str(len(parcels)), 'tone': 'success'},
            {'label': 'Active transactions', 'value': str(transactions.count() if transactions else 0), 'tone': 'accent'},
            {'label': 'Joint-ready', 'value': 'Yes', 'tone': 'warning'},
            {'label': 'Status', 'value': 'Live', 'tone': 'default'},
        ],
    )

def features(request):
    return render_react_shell(
        request,
        'features',
        'Digiland Features & Architecture',
        'Explore the 10 core capabilities powering autonomous land escrow in Kenya.',
    )

def agent_signup_complete(request):
    """
    Post-signup landing point for Agent users.
    Allauth redirects here immediately after a new agent account is created.
    We log the user out so they cannot browse as an authenticated session,
    then send them to the Staff Login portal with an informational banner.
    """
    from django.contrib.auth import logout
    if request.user.is_authenticated:
        logout(request)
    request.session['agent_signup_success'] = True
    return redirect(reverse('frontend:staff_login'))


@login_required
def buyer_account_choice(request):
    """Buyer onboarding screen for choosing individual versus joint account mode."""
    from django.middleware.csrf import get_token
    if request.user.role != 'Buyer':
        return redirect('frontend:home')

    if request.user.buyer_account_type == 'Joint':
        return redirect('frontend:joint_groups')
    if request.user.buyer_account_type == 'Individual':
        from django.contrib import messages
        messages.info(
            request,
            'Your buyer account is set to Individual. To switch to Joint ownership, request an admin account upgrade.',
        )
        return redirect('frontend:parcel_list')

    if request.method == 'POST':
        account_type = (request.POST.get('account_type') or '').strip()
        if account_type not in {'Individual', 'Joint'}:
            from django.contrib import messages
            messages.error(request, 'Please choose either an individual or joint buyer account.')
            return redirect('frontend:buyer_account_choice')

        request.user.buyer_account_type = account_type
        request.user.save(update_fields=['buyer_account_type'])

        from django.contrib import messages
        if account_type == 'Joint':
            messages.success(request, 'Joint buyer account selected. Set up your group next.')
            return redirect('frontend:create_joint_group')

        messages.success(request, 'Individual buyer account selected. You can now browse the marketplace.')
        return redirect('frontend:parcel_list')

    return render_react_shell(
        request,
        'buyer-choice',
        'Buyer setup',
        'Choose the account mode that matches how you want to buy land.',
        form={'action': reverse('frontend:buyer_account_choice'), 'csrf_token': get_token(request), 'method': 'post'},
        actions=[
            {'label': 'Open joint laws', 'href': reverse('frontend:joint_laws'), 'tone': 'outline'},
            {'label': 'View marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'secondary'},
        ],
        laws=LAND_TRANSACTION_LAWS,
    )


def legal_requirements(request):
    """Public reference page for the land sale laws and compliance checklist."""
    actions = []
    if not request.user.is_authenticated:
        actions = [
            {'label': 'Joint laws', 'href': reverse('frontend:joint_laws'), 'tone': 'outline'},
            {'label': 'Buyer setup', 'href': reverse('frontend:buyer_account_choice'), 'tone': 'secondary'},
        ]
    elif request.user.role == 'Buyer' and not getattr(request.user, 'buyer_account_type', None):
        actions = [
            {'label': 'Joint laws', 'href': reverse('frontend:joint_laws'), 'tone': 'outline'},
            {'label': 'Buyer setup', 'href': reverse('frontend:buyer_account_choice'), 'tone': 'secondary'},
        ]
    else:
        actions = [
            {'label': 'Joint laws', 'href': reverse('frontend:joint_laws'), 'tone': 'outline'},
            {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'secondary'},
        ]

    return render_react_shell(
        request,
        'legal',
        'Kenyan land laws',
        'The statutory checklist that applies to a standard land purchase.',
        laws=[serialize_law(law) for law in LAND_TRANSACTION_LAWS],
        checklist=LAND_TRANSACTION_CHECKLIST,
        actions=actions,
    )

@login_required
def seller_legal_requirements(request):
    """Reference page for sellers outlining their specific obligations."""
    if request.user.role != 'Seller':
        return redirect('frontend:home')
        
    from core.legal import SELLER_TRANSACTION_LAWS, SELLER_TRANSACTION_CHECKLIST
    return render_react_shell(
        request,
        'legal',
        'Seller legal obligations',
        'Your responsibilities and legal requirements when selling land under Kenyan law.',
        laws=[serialize_law(law) for law in SELLER_TRANSACTION_LAWS],
        checklist=SELLER_TRANSACTION_CHECKLIST,
        actions=[
            {'label': 'My Parcels', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
        ],
    )


def joint_legal_requirements(request):
    """Joint-buyer reference page for co-ownership, group purchase, and payment guidance."""
    from core.models import PlatformLegalDocument
    doc = PlatformLegalDocument.objects.filter(title='Joint Purchase Laws').first()
    document_content = doc.content if doc else None
    
    user = request.user
    actions = []
    if user.is_authenticated and user.role == 'Buyer':
        if getattr(user, 'buyer_account_type', None) == 'Joint':
            actions = [
                {'label': 'My groups', 'href': reverse('frontend:joint_groups'), 'tone': 'outline'},
                {'label': 'Create joint group', 'href': reverse('frontend:create_joint_group'), 'tone': 'secondary'},
            ]
        elif getattr(user, 'buyer_account_type', None) == 'Individual':
            actions = [
                {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
                {'label': 'Contact support for joint upgrade', 'href': reverse('frontend:support'), 'tone': 'secondary'},
            ]
        else:
            actions = [
                {'label': 'Buyer setup', 'href': reverse('frontend:buyer_account_choice'), 'tone': 'outline'},
                {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'secondary'},
            ]
    elif user.is_authenticated and user.role == 'Seller':
        actions = [
            {'label': 'My parcels', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
        ]
    elif user.is_authenticated and user.role in {'Agent', 'Admin'}:
        actions = [
            {'label': 'Command Centre', 'href': reverse('frontend:agent_dashboard'), 'tone': 'outline'},
        ]
    else:
        actions = [
            {'label': 'Buyer setup', 'href': reverse('frontend:buyer_account_choice'), 'tone': 'outline'},
            {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'secondary'},
        ]

    return render_react_shell(
        request,
        'joint-laws',
        'Joint purchase laws',
        'Kenyan co-ownership rules for group purchases and shared payment setups.',
        laws=[serialize_law(law) for law in JOINT_LAND_TRANSACTION_LAWS],
        checklist=JOINT_LAND_TRANSACTION_CHECKLIST,
        payment_guidance=JOINT_PAYMENT_GUIDANCE,
        document_content=document_content,
        actions=actions,
    )


def logout_to_staff_login(request):
    """Log the current user out and redirect straight to the staff login portal."""
    from django.contrib.auth import logout
    if request.method == 'POST':
        logout(request)
        return redirect(reverse('frontend:staff_login'))
    return redirect(reverse('frontend:agent_onboarding'))

def staff_login(request):
    """Hidden staff-only login portal for Admin and Agent roles."""
    from django.contrib.auth import authenticate, login as auth_login

    # Consume the "blocked from public login" session flag set by the adapter
    error = None
    if request.session.pop('staff_blocked', False):
        error = 'Staff accounts must authenticate through this portal only.'

    if request.user.is_authenticated:
        if request.user.role in STAFF_ROLES:
            return redirect('frontend:home')
        return redirect('frontend:parcel_list')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, email=email, password=password)

        if user is None:
            error = 'Invalid credentials. Please try again.'
        elif getattr(user, 'role', None) == 'Admin' or getattr(user, 'is_superuser', False):
            from core.auth_services import AuditService
            AuditService.log_event("ADMIN_LOGIN_BLOCKED_ON_STAFF_PORTAL", user=user, ip_address=request.META.get('REMOTE_ADDR', ''))
            error = 'Administrative accounts cannot log in via the Staff Portal. Please access the dedicated Administrative Control Plane.'
        elif getattr(user, 'role', None) != 'Agent':
            error = 'This portal is restricted to licensed Agent accounts only.'
        elif not user.is_active:
            error = 'Your account has been deactivated. Contact the system administrator.'
        else:
            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            if not user.is_identity_verified:
                # Check if KYC docs have already been submitted
                try:
                    if user.kyc_application.kyc_submitted:
                        return redirect('frontend:agent_onboarding')
                except Exception:
                    pass
                return redirect('frontend:ai_kyc')
            return redirect('frontend:agent_dashboard')

    # Consume the "just signed up" session flag set by agent_signup_complete
    signup_success = request.session.pop('agent_signup_success', False)

    return render(request, 'frontend/staff_login.html', {
        'error': error,
        'signup_success': signup_success,
    })

def parcel_list(request):
    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    search_query = (request.GET.get('q') or '').strip()
    land_type = (request.GET.get('type') or '').strip()
    price_filter = (request.GET.get('price') or '').strip()
    min_price = request.GET.get('min_price')
    max_price = request.GET.get('max_price')
    if request.user.is_authenticated and request.user.role == 'Seller':
        parcels = LandParcel.objects.filter(listed_by=request.user).order_by('-ardhisasa_last_synced')
    elif request.user.is_authenticated and request.user.role in ['Agent', 'Admin']:
        parcels = LandParcel.objects.filter(Q(assigned_agent=request.user) | Q(verification_status='Verified')).exclude(transactions__status__in=active_tx_statuses).distinct().order_by('-ardhisasa_last_synced')
    else:
        parcels = LandParcel.objects.filter(verification_status='Verified').exclude(transactions__status__in=active_tx_statuses).order_by('-ardhisasa_last_synced')
    if search_query:
        parcels = parcels.filter(Q(county__icontains=search_query) | Q(constituency__icontains=search_query) | Q(ward__icontains=search_query) | Q(parcel_number__icontains=search_query))
    if land_type:
        parcels = parcels.filter(land_use_type__iexact=land_type)
    try:
        if price_filter == 'under_1m':
            max_price = 1000000
        elif price_filter == '1m_5m':
            min_price, max_price = 1000000, 5000000
        elif price_filter == '5m_20m':
            min_price, max_price = 5000000, 20000000
        elif price_filter == '20m_plus':
            min_price = 20000000
        elif price_filter and '-' in price_filter:
            min_price, max_price = [part.strip() for part in price_filter.split('-', 1)]

        if min_price is not None and min_price != '':
            parcels = parcels.filter(asking_price__gte=float(min_price))
        if max_price is not None and max_price != '':
            parcels = parcels.filter(asking_price__lte=float(max_price))
    except (TypeError, ValueError):
        pass
    actions = []
    if request.user.is_authenticated and request.user.role == 'Seller':
        actions = [{'label': 'List new parcel', 'href': reverse('frontend:parcel_upload'), 'tone': 'default'}, {'label': 'Legal checklist', 'href': reverse('frontend:seller_laws'), 'tone': 'outline'}]
    elif request.user.is_authenticated and request.user.role == 'Buyer':
        actions = [{'label': 'Legal checklist', 'href': reverse('frontend:escrow_acts'), 'tone': 'outline'}, {'label': 'Joint laws', 'href': reverse('frontend:joint_laws'), 'tone': 'secondary'}]
    else:
        actions = [{'label': 'Legal checklist', 'href': reverse('frontend:escrow_acts'), 'tone': 'outline'}, {'label': 'Joint laws', 'href': reverse('frontend:joint_laws'), 'tone': 'secondary'}]
    return render_react_shell(
        request, 'parcel-list', 'Marketplace',
        'Verified parcels available for purchase or management.',
        parcels=[serialize_parcel(parcel, request.user) for parcel in parcels],
        actions=actions,
        search_query=search_query,
        land_type=land_type,
        price_filter=price_filter,
        search_active=bool(search_query or (land_type and land_type != 'all') or (price_filter and price_filter != 'all') or min_price or max_price)
    )
@login_required
def agent_kyc(request):
    """KYC document submission for newly registered Agent users."""
    from core.models import AgentKYCApplication
    from core.forms import AgentKYCForm

    if request.user.role != 'Agent':
        return redirect('frontend:home')
    # Already verified — go straight to dashboard
    if request.user.is_identity_verified:
        return redirect('frontend:agent_dashboard')
    # Already submitted — wait on the onboarding holding page
    try:
        app = request.user.kyc_application
        if app.kyc_submitted:
            return redirect('frontend:agent_onboarding')
    except AgentKYCApplication.DoesNotExist:
        app = None

    if request.method == 'POST':
        form = AgentKYCForm(request.POST, request.FILES, instance=app)
        if form.is_valid():
            kyc = form.save(commit=False)
            kyc.agent = request.user
            kyc.kyc_submitted = True
            kyc.save()
            return redirect('frontend:agent_onboarding')
    else:
        form = AgentKYCForm(instance=app)

    return render_react_shell(
        request,
        'agent-kyc',
        'KYC Verification - Digiland',
        'Complete your verification file so an administrator can review your application.',
        form=serialize_form(
            form,
            action=reverse('frontend:agent_kyc'),
            submit_label='Submit KYC Application',
            intro='Accepted formats include PDF, JPG, and PNG. Keep each file under 5 MB.',
            sections=[
                {'title': 'Identity and tax information', 'fields': ['kra_pin', 'id_number']},
                {'title': 'Supporting documents', 'fields': ['id_photo', 'resume', 'certificate_of_good_conduct', 'practicing_certificate']},
            ],
        ),
    )


@login_required
def agent_onboarding(request):
    if request.user.role != 'Agent':
        return redirect('frontend:home')
    # Pass the approval state to the template
    # - approved=True  → shows "Use Staff Login" message
    # - approved=False → shows "Awaiting admin review" spinner
    return render_react_shell(
        request,
        'content',
        'Agent onboarding - Digiland',
        'Track your approval status and next steps.',
        content={
            'hero': {
                'kicker': 'Agent onboarding',
                'title': 'Your verification status',
                'subtitle': 'Approved agents can continue to the staff portal. Pending applications remain under review.',
                'badge': 'Workflow status',
            },
            'sections': [
                {
                    'title': 'Current status',
                    'body': 'Approved' if request.user.is_identity_verified else 'Pending review',
                },
                {
                    'title': 'Next step',
                    'body': 'If approved, sign in through the staff portal to continue. If pending, wait for an administrator review.',
                },
            ],
        },
        actions=[
            {'label': 'Staff login', 'href': reverse('frontend:staff_login'), 'tone': 'default'},
            {'label': 'Support', 'href': reverse('frontend:support'), 'tone': 'outline'},
        ],
    )

@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_dashboard(request):
    """Agent Command Centre with role-based restrictions."""
    from core.models import User as CoreUser
    from django.db.models import Q

    # Base context for all staff roles
    context = {
        'unread_count': Message.objects.filter(receiver=request.user, is_read=False).count(),
    }

    if request.user.role == 'Admin':
        # Admin gets full command centre access
        return render_admin_dashboard(request, context)
    elif request.user.role == 'Lawyer':
        # Lawyer gets legal reviews dashboard
        return render_lawyer_dashboard(request, context)
    else:
        # Agent gets restricted dashboard
        return render_agent_dashboard(request, context)

def render_lawyer_dashboard(request, context):
    """Render lawyer-specific command centre."""
    pending_transactions = Transaction.objects.filter(
        status='Under_Verification'
    ).select_related('buyer', 'seller', 'land_parcel').order_by('created_at')

    completed_transactions = Transaction.objects.filter(
        status__in=['Completed', 'Disputed', 'Refunded', 'Reversed'],
        lawyer_signature__isnull=False
    ).select_related('buyer', 'seller', 'land_parcel').order_by('-updated_at')[:30]

    commission_reviews_qs = PurchaseCommission.objects.filter(
        status='Lawyer_Verification',
        assigned_lawyer=request.user,
    ).select_related('buyer', 'land_parcel', 'accepted_by', 'assigned_lawyer').order_by('created_at')

    commission_reviews = [serialize_commission(commission, request.user) for commission in commission_reviews_qs[:10]]

    context.update({
        'pending_transactions': pending_transactions,
        'completed_transactions': completed_transactions,
        'commission_reviews': commission_reviews,
    })

    recent_transactions = [serialize_transaction(tx, request.user) for tx in pending_transactions[:10]]

    return render_react_shell(
        request,
        'lawyer-dashboard',
        'Lawyer Command Centre',
        'Review land transfer agreements, verify advocate status, and execute cryptographic sign-offs.',
        transactions=recent_transactions,
        commission_reviews=commission_reviews,
        stats=[
            {'label': 'Pending reviews', 'value': str(pending_transactions.count()), 'tone': 'warning'},
            {'label': 'Commission reviews', 'value': str(len(commission_reviews)), 'tone': 'accent'},
            {'label': 'Completed reviews', 'value': str(completed_transactions.count()), 'tone': 'success'},
            {'label': 'LSK Status', 'value': 'Verified Advocate', 'tone': 'success'},
        ],
        actions=[
            {'label': 'Legal Library', 'href': reverse('frontend:escrow_acts'), 'tone': 'outline'},
            {'label': 'Messages', 'href': reverse('frontend:messages'), 'tone': 'secondary'},
        ],
    )

def render_admin_dashboard(request, context):
    """Render full admin command centre."""
    from core.models import User as CoreUser
    from django.db.models import Q

    # Admin can see all pending parcels and transactions
    pending_parcels = LandParcel.objects.filter(verification_status='Pending').order_by('-ardhisasa_last_synced')
    completed_parcels = LandParcel.objects.filter(
        verification_status__in=['Verified', 'Fraudulent']
    ).order_by('-ardhisasa_last_synced')[:30]
    pending_transactions = Transaction.objects.filter(
        contract_agreed=True,
        status__in=['Deposit_Paid', 'Under_Verification']
    ).order_by('created_at')
    pending_agents = CoreUser.objects.filter(role='Agent', is_identity_verified=False, is_active=True).order_by('date_joined')
    verified_agents = CoreUser.objects.filter(role='Agent', is_identity_verified=True, is_active=True).order_by('email')
    individual_buyers = CoreUser.objects.filter(role='Buyer', buyer_account_type='Individual', is_active=True).order_by('email')[:50]

    context.update({
        'pending_parcels': pending_parcels,
        'completed_parcels': completed_parcels,
        'pending_transactions': pending_transactions,
        'pending_agents': pending_agents,
        'verified_agents': verified_agents,
        'individual_buyers': individual_buyers,
        'pending_users': None,  # Admins don't need user approval section
    })
    recent_transactions = [serialize_transaction(tx, request.user) for tx in pending_transactions[:10]]

    # Serialize pending agents with KYC details for the admin approval section
    pending_agent_data = []
    for agent in pending_agents:
        agent_data = serialize_review_user(agent)
        kyc = getattr(agent, 'kyc_application', None)
        agent_data['kyc'] = {
            'submitted': bool(kyc and kyc.kyc_submitted),
            'status': kyc.status if kyc else 'Not Submitted',
            'resume_url': kyc.resume.url if (kyc and kyc.resume) else None,
            'id_photo_url': kyc.id_photo.url if (kyc and kyc.id_photo) else None,
            'certificate_url': kyc.certificate_of_good_conduct.url if (kyc and kyc.certificate_of_good_conduct) else None,
            'practicing_cert_url': kyc.practicing_certificate.url if (kyc and kyc.practicing_certificate) else None,
        } if kyc else {'submitted': False, 'status': 'Not Submitted'}
        agent_data['approve_url'] = reverse('frontend:approve_agent', args=[agent.id])
        agent_data['reject_url'] = reverse('frontend:reject_agent', args=[agent.id])
        pending_agent_data.append(agent_data)

    individual_buyer_data = []
    for buyer in individual_buyers:
        buyer_data = serialize_review_user(buyer)
        buyer_data['promote_to_joint_url'] = reverse('frontend:admin_promote_buyer_to_joint', args=[buyer.id])
        individual_buyer_data.append(buyer_data)

    return render_react_shell(
        request,
        'admin-dashboard',
        'Command Centre',
        'Full system access for approvals, assignments, transactions, and messaging.',
        transactions=recent_transactions,
        pending_agent_applications=pending_agent_data,
        individual_buyers=individual_buyer_data,
        stats=[
            {'label': 'Pending parcels', 'value': str(pending_parcels.count()), 'tone': 'warning'},
            {'label': 'Pending transactions', 'value': str(pending_transactions.count()), 'tone': 'accent'},
            {'label': 'Pending agents', 'value': str(pending_agents.count()), 'tone': 'danger'},
            {'label': 'Verified agents', 'value': str(verified_agents.count()), 'tone': 'success'},
        ],
        actions=[
            {'label': 'Task management', 'href': reverse('frontend:task_management'), 'tone': 'outline'},
            {'label': 'Agent approvals', 'href': reverse('frontend:agent_approvals'), 'tone': 'outline'},
            {'label': 'System admin', 'href': '/admin/', 'tone': 'secondary', 'external': True},
        ],
    )


@login_required
@user_passes_test(lambda u: u.is_authenticated and getattr(u, 'role', None) == 'Admin', login_url='/')
def admin_promote_buyer_to_joint(request, user_id):
    """Admin action to promote an Individual Buyer account to Joint mode."""
    if request.method != 'POST':
        return redirect('frontend:agent_dashboard')

    from django.contrib import messages
    buyer = get_object_or_404(CoreUser, id=user_id, role='Buyer')
    previous_type = buyer.buyer_account_type or 'Unset'
    buyer.buyer_account_type = 'Joint'
    buyer.save(update_fields=['buyer_account_type'])

    messages.success(
        request,
        f'{buyer.email} upgraded from {previous_type} to Joint buyer account. They can now create and manage joint groups.',
    )
    return redirect('frontend:agent_dashboard')


@login_required
@user_passes_test(lambda u: u.is_authenticated and getattr(u, 'role', None) == 'Admin', login_url='/')
def temp_approve_agent(request, email):
    """Admin-only view to approve an agent. Requires authenticated Admin user.

    SECURITY: Previously unauthenticated — now restricted to Admin role only.
    This endpoint should still be removed before full production launch.
    """
    try:
        agent = CoreUser.objects.get(email=email, role='Agent')
        
        # Create KYC application if it doesn't exist
        kyc_app, created = AgentKYCApplication.objects.get_or_create(
            agent=agent,
            defaults={
                'kra_pin': 'TEST_PIN',
                'id_number': 'TEST_ID',
                'kyc_submitted': True,
                'status': 'Approved'
            }
        )
        
        # Approve the agent
        agent.is_identity_verified = True
        agent.is_active = True
        agent.save()
        
        return render_react_shell(
            request,
            'content',
            'Temporary approval - Digiland',
            'Testing-only approval response.',
            content={
                'hero': {
                    'kicker': 'Temporary approval',
                    'title': 'Agent approved for testing',
                    'subtitle': agent.email,
                    'badge': 'Success',
                },
                'sections': [
                    {
                        'title': 'Result',
                        'body': 'The account is active and identity verified.',
                    },
                ],
            },
        )
    except CoreUser.DoesNotExist:
        return render_react_shell(
            request,
            'content',
            'Temporary approval - Digiland',
            'Testing-only approval response.',
            content={
                'hero': {
                    'kicker': 'Temporary approval',
                    'title': 'No agent found',
                    'subtitle': f'No agent found with email: {email}',
                    'badge': 'Error',
                },
                'sections': [
                    {
                        'title': 'Result',
                        'body': 'The lookup did not find a matching staff account.',
                    },
                ],
            },
        )
    except Exception as e:
        return render_react_shell(
            request,
            'content',
            'Temporary approval - Digiland',
            'Testing-only approval response.',
            content={
                'hero': {
                    'kicker': 'Temporary approval',
                    'title': 'Unexpected error',
                    'subtitle': str(e),
                    'badge': 'Error',
                },
                'sections': [
                    {
                        'title': 'Result',
                        'body': 'The approval action could not be completed.',
                    },
                ],
            },
        )


def render_agent_dashboard(request, context):
    """Render restricted agent dashboard."""
    from core.models import User as CoreUser
    from django.db.models import Q

    county, constituency, region_source = resolve_agent_region(request.user)

    # Agents can only see their assigned parcels and completed tasks
    pending_parcels = LandParcel.objects.filter(
        assigned_agent=request.user, verification_status='Pending'
    ).order_by('-ardhisasa_last_synced')
    completed_parcels = LandParcel.objects.filter(
        assigned_agent=request.user, verification_status__in=['Verified', 'Fraudulent']
    ).order_by('-ardhisasa_last_synced')[:30]

    # Open commissions within the agent's operating region
    open_commissions_qs = PurchaseCommission.objects.filter(status='Open').select_related(
        'buyer', 'land_parcel', 'accepted_by', 'assigned_lawyer'
    ).order_by('-created_at')
    if county and constituency:
        region_commissions = open_commissions_qs.filter(
            target_county__iexact=county,
            target_constituency__iexact=constituency,
        )
        if region_commissions.exists():
            open_commissions_qs = region_commissions
        else:
            county_matches = open_commissions_qs.filter(target_county__iexact=county)
            if county_matches.exists():
                open_commissions_qs = county_matches

    active_commissions_qs = PurchaseCommission.objects.filter(
        accepted_by=request.user,
        status__in=['Accepted', 'Documents_Review', 'Lawyer_Verification', 'Site_Visit_Scheduled', 'Site_Visit_Complete', 'Closing'],
    ).select_related('buyer', 'land_parcel', 'accepted_by', 'assigned_lawyer').order_by('-updated_at')

    # Agents can see transactions they're involved in or assigned parcels
    pending_transactions = Transaction.objects.filter(
        contract_agreed=True,
        status__in=['Deposit_Paid', 'Under_Verification']
    ).filter(
        Q(land_parcel__assigned_agent=request.user) |
        Q(buyer=request.user) |
        Q(seller=request.user)
    ).distinct().order_by('created_at')

    # Agents can approve Buyers/Sellers (NOT Admin/Agent accounts)
    pending_users = CoreUser.objects.filter(
        role__in=['Buyer', 'Seller'], is_identity_verified=False, is_active=True
    ).order_by('date_joined')

    # Update context while preserving existing values like unread_count
    context.update({
        'pending_parcels': pending_parcels,
        'completed_parcels': completed_parcels,
        'pending_transactions': pending_transactions,
        'pending_agents': None,  # Agents cannot see other agents
        'pending_users': pending_users,
        'open_commissions': open_commissions_qs[:6],
        'active_commissions': active_commissions_qs[:6],
        'region_source': region_source,
    })
    recent_parcels = [serialize_parcel(parcel, request.user) for parcel in pending_parcels[:6]]
    recent_transactions = [serialize_transaction(tx, request.user) for tx in pending_transactions[:6]]
    recent_open_commissions = [serialize_commission(commission, request.user) for commission in open_commissions_qs[:6]]
    recent_active_commissions = [serialize_commission(commission, request.user) for commission in active_commissions_qs[:6]]
    return render_react_shell(
        request,
        'agent-dashboard',
        'Command Centre',
        'Your assigned pipeline for parcel verification, commission routing, and escrow support.',
        parcels=recent_parcels,
        transactions=recent_transactions,
        commissions=recent_open_commissions,
        active_commissions=recent_active_commissions,
        stats=[
            {'label': 'Pending parcels', 'value': str(pending_parcels.count()), 'tone': 'warning'},
            {'label': 'Available jobs', 'value': str(open_commissions_qs.count()), 'tone': 'accent'},
            {'label': 'Active commissions', 'value': str(active_commissions_qs.count()), 'tone': 'success'},
            {'label': 'Completed parcels', 'value': str(completed_parcels.count()), 'tone': 'success'},
        ],
        actions=[
            {'label': 'Task management', 'href': reverse('frontend:task_management'), 'tone': 'outline'},
            {'label': 'Job Board', 'href': reverse('frontend:agent_job_board'), 'tone': 'secondary'},
            {'label': 'User approvals', 'href': reverse('frontend:agent_approvals'), 'tone': 'secondary'},
            {'label': 'Withdraw earnings', 'href': reverse('frontend:agent_withdraw'), 'tone': 'primary'},
        ],
    )



@login_required
def commission_detail(request, commission_id):
    commission = get_object_or_404(
        PurchaseCommission.objects.select_related(
            'buyer', 'land_parcel', 'land_parcel__listed_by', 'accepted_by', 'assigned_lawyer', 'transaction'
        ),
        id=commission_id,
    )

    if not can_view_commission(request.user, commission):
        return redirect('frontend:transactions')

    actions = []
    if request.user.role == 'Buyer':
        actions.append({'label': 'Back to parcel', 'href': reverse('frontend:parcel_detail', args=[commission.land_parcel.parcel_number]), 'tone': 'outline'})
        if commission.transaction_id:
            actions.append({'label': 'Continue to payment', 'href': reverse('frontend:payment_onboarding', args=[commission.transaction_id]), 'tone': 'default'})
    elif request.user.role == 'Agent':
        actions.append({'label': 'Job Board', 'href': reverse('frontend:agent_job_board'), 'tone': 'secondary'})
        if commission.accepted_by_id == request.user.id:
            actions.append({'label': 'Work steps', 'href': reverse('frontend:agent_commission_steps', args=[commission.id]), 'tone': 'default'})
    elif request.user.role == 'Lawyer':
        actions.append({'label': 'Command Centre', 'href': reverse('frontend:home'), 'tone': 'secondary'})
    else:
        actions.append({'label': 'Transactions', 'href': reverse('frontend:transactions'), 'tone': 'outline'})

    return render_react_shell(
        request,
        'commission-detail',
        f'Commission - {commission.land_parcel.parcel_number}',
        f'{commission.target_county}, {commission.target_constituency}',
        commission_detail=serialize_commission(commission, request.user),
        actions=actions,
    )


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_job_board(request):
    county, constituency, region_source = resolve_agent_region(request.user)
    open_commissions_qs = PurchaseCommission.objects.filter(status='Open').select_related(
        'buyer', 'land_parcel', 'accepted_by', 'assigned_lawyer'
    ).order_by('-created_at')

    if request.user.role == 'Agent':
        if county and constituency:
            region_commissions = open_commissions_qs.filter(
                target_county__iexact=county,
                target_constituency__iexact=constituency,
            )
            if region_commissions.exists():
                open_commissions_qs = region_commissions
            else:
                county_matches = open_commissions_qs.filter(target_county__iexact=county)
                if county_matches.exists():
                    open_commissions_qs = county_matches

    open_commissions = [serialize_commission(commission, request.user) for commission in open_commissions_qs[:24]]

    return render_react_shell(
        request,
        'agent-job-board',
        'Commission Job Board',
        'Open purchase commissions matched to your operating region.',
        agent_job_board={
            'region_county': county,
            'region_constituency': constituency,
            'region_source': region_source,
            'open_count': open_commissions_qs.count(),
            'commissions': open_commissions,
        },
        stats=[
            {'label': 'Open jobs', 'value': str(open_commissions_qs.count()), 'tone': 'accent'},
            {'label': 'Region', 'value': f"{county or 'Unassigned'} / {constituency or 'Unassigned'}", 'tone': 'warning'},
            {'label': 'Your dashboard', 'value': 'Agent workspace', 'tone': 'success'},
        ],
        actions=[
            {'label': 'Back to dashboard', 'href': reverse('frontend:agent_dashboard'), 'tone': 'outline'},
            {'label': 'Command Centre', 'href': reverse('frontend:agent_dashboard'), 'tone': 'secondary'},
        ],
    )


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_accept_job(request, commission_id):
    if request.method != 'POST':
        return redirect('frontend:agent_job_board')

    commission = get_object_or_404(
        PurchaseCommission.objects.select_related('buyer', 'land_parcel', 'accepted_by', 'assigned_lawyer'),
        id=commission_id,
    )

    if request.user.role != 'Agent' and request.user.role != 'Admin':
        return redirect('frontend:agent_job_board')

    from django.contrib import messages as django_messages
    try:
        accept_commission(request.user, commission)
        django_messages.success(request, f'You accepted commission {commission.land_parcel.parcel_number}.')
        return redirect('frontend:agent_commission_steps', commission_id=commission.id)
    except ValidationError as exc:
        django_messages.error(request, str(exc))
        return redirect('frontend:agent_job_board')


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_commission_steps(request, commission_id):
    commission = get_object_or_404(
        PurchaseCommission.objects.select_related(
            'buyer', 'land_parcel', 'land_parcel__listed_by', 'accepted_by', 'assigned_lawyer', 'transaction'
        ),
        id=commission_id,
    )

    if not can_view_commission(request.user, commission):
        return redirect('frontend:commission_detail', commission_id=commission.id)

    commission_data = serialize_commission(commission, request.user)
    actions = [{'label': 'Back to commission', 'href': reverse('frontend:commission_detail', args=[commission.id]), 'tone': 'outline'}]
    if request.user.role == 'Agent' and commission.accepted_by_id != request.user.id and request.user.role != 'Admin':
        actions = [{'label': 'Job Board', 'href': reverse('frontend:agent_job_board'), 'tone': 'outline'}]
    elif commission.transaction_id:
        actions.append({'label': 'Continue to payment', 'href': reverse('frontend:payment_onboarding', args=[commission.transaction_id]), 'tone': 'default'})

    return render_react_shell(
        request,
        'agent-commission-steps',
        f"Commission steps - {commission.land_parcel.parcel_number}",
        'Move through document review, lawyer verification, site visit, and closing.',
        commission_steps=commission_data,
        commission_detail=commission_data,
        actions=actions,
    )


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_commission_step_action(request, commission_id, step):
    if request.method != 'POST':
        return redirect('frontend:agent_commission_steps', commission_id=commission_id)

    commission = get_object_or_404(
        PurchaseCommission.objects.select_related(
            'buyer', 'land_parcel', 'land_parcel__listed_by', 'accepted_by', 'assigned_lawyer', 'transaction'
        ),
        id=commission_id,
    )

    if not can_view_commission(request.user, commission):
        return redirect('frontend:commission_detail', commission_id=commission.id)

    agent_steps = {'documents_review', 'submit_to_lawyer', 'schedule_site_visit', 'complete_site_visit', 'close'}
    lawyer_steps = {'lawyer_verdict'}
    if step in agent_steps:
        if request.user.role not in {'Agent', 'Admin'}:
            raise ValidationError('Only the assigned agent can advance this commission step.')
        if request.user.role == 'Agent' and commission.accepted_by_id not in {None, request.user.id}:
            raise ValidationError('Only the accepted agent can advance this commission step.')
    elif step in lawyer_steps:
        if request.user.role not in {'Lawyer', 'Admin'}:
            raise ValidationError('Only the assigned lawyer can update this step.')
        if request.user.role == 'Lawyer' and commission.assigned_lawyer_id not in {None, request.user.id}:
            raise ValidationError('Only the assigned lawyer can update this commission.')
    else:
        raise ValidationError('Unsupported commission step.')

    from django.contrib import messages as django_messages
    from django.utils import timezone
    from django.utils.dateparse import parse_datetime

    try:
        if step == 'documents_review':
            note = (request.POST.get('note') or '').strip()
            approved = (request.POST.get('approved') or 'true').strip().lower() not in {'false', '0', 'no'}
            review_documents(commission, request.user, note=note, approved=approved)
        elif step == 'submit_to_lawyer':
            note = (request.POST.get('note') or '').strip()
            lawyer_id = (request.POST.get('lawyer_id') or '').strip()
            lawyer = None
            if lawyer_id:
                lawyer = get_object_or_404(CoreUser, id=lawyer_id, role='Lawyer')
            elif commission.assigned_lawyer_id:
                lawyer = commission.assigned_lawyer
            else:
                lawyer = get_default_lawyer()
            submit_to_lawyer(commission, request.user, lawyer=lawyer, note=note)
        elif step == 'lawyer_verdict':
            verified = (request.POST.get('verified') or 'true').strip().lower() not in {'false', '0', 'no'}
            note = (request.POST.get('note') or '').strip()
            lawyer_verdict(commission, request.user, verified=verified, note=note)
        elif step == 'schedule_site_visit':
            visit_date_raw = (request.POST.get('visit_date') or request.POST.get('site_visit_date') or '').strip()
            visit_date = parse_datetime(visit_date_raw)
            if visit_date is None:
                raise ValidationError('Enter a valid site visit date and time.')
            if timezone.is_naive(visit_date):
                visit_date = timezone.make_aware(visit_date, timezone.get_current_timezone())
            location = (request.POST.get('location') or request.POST.get('site_visit_location') or '').strip()
            notes = (request.POST.get('notes') or '').strip()
            schedule_site_visit(commission, request.user, visit_date=visit_date, location=location, notes=notes)
        elif step == 'complete_site_visit':
            notes = (request.POST.get('notes') or '').strip()
            complete_site_visit(commission, request.user, notes=notes)
        elif step == 'close':
            locked_commission, transaction = close_commission(commission, request.user)
            django_messages.success(request, f'Commission {locked_commission.land_parcel.parcel_number} is now in closing.')
            return redirect('frontend:payment_onboarding', transaction_id=transaction.id)

        django_messages.success(request, f'Updated commission step: {step.replace("_", " ")}.')
        return redirect('frontend:agent_commission_steps', commission_id=commission.id)
    except ValidationError as exc:
        django_messages.error(request, str(exc))
        return redirect('frontend:agent_commission_steps', commission_id=commission.id)


@login_required
@user_passes_test(lambda u: u.is_authenticated and getattr(u, 'role', None) in {'Lawyer', 'Admin'}, login_url='/')
def lawyer_review_commission(request, commission_id):
    commission = get_object_or_404(
        PurchaseCommission.objects.select_related('buyer', 'land_parcel', 'accepted_by', 'assigned_lawyer', 'transaction'),
        id=commission_id,
    )

    if not can_view_commission(request.user, commission):
        return redirect('frontend:home')

    if request.method != 'POST':
        return redirect('frontend:commission_detail', commission_id=commission.id)

    from django.contrib import messages as django_messages
    if request.user.role != 'Admin':
        grant = _active_document_grant(commission.land_parcel, request.user)
        if not grant or not grant.is_valid():
            django_messages.error(request, 'Dual-signature document access is required before lawyer review.')
            return redirect('frontend:commission_detail', commission_id=commission.id)
    try:
        verified = (request.POST.get('verified') or 'true').strip().lower() not in {'false', '0', 'no'}
        note = (request.POST.get('note') or '').strip()
        lawyer_verdict(commission, request.user, verified=verified, note=note)
        django_messages.success(request, f'Lawyer review saved for {commission.land_parcel.parcel_number}.')
    except ValidationError as exc:
        django_messages.error(request, str(exc))

    return redirect('frontend:commission_detail', commission_id=commission.id)

@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def task_management(request):
    """Dedicated task management page: assign/reassign/unassign parcels + view allocated/completed."""
    from core.models import User as CoreUser
    from core.services.task_assignment import TaskAssignmentScorer

    if request.user.role != 'Admin':
        # Agents see their own pipeline view
        pending_parcels = LandParcel.objects.filter(
            assigned_agent=request.user, verification_status='Pending'
        ).order_by('-ardhisasa_last_synced')
        completed_parcels = LandParcel.objects.filter(
            assigned_agent=request.user, verification_status__in=['Verified', 'Fraudulent']
        ).order_by('-ardhisasa_last_synced')[:30]
        return render_react_shell(
            request,
            'task-management',
            'Command Centre',
            'Your assigned pipeline for parcel verification and escrow support.',
            task_board={
                'pending_parcels': [serialize_parcel(parcel, request.user) for parcel in pending_parcels],
                'completed_parcels': [serialize_parcel(parcel, request.user) for parcel in completed_parcels],
                'pending_transactions': [],
                'pending_users': [],
                'pending_agents': [],
                'verified_agents': [],
            },
        )

    # Admin view with intelligent recommendations
    all_pending_parcels = LandParcel.objects.filter(
        verification_status='Pending'
    ).select_related('assigned_agent', 'listed_by').order_by('-ardhisasa_last_synced')

    unassigned_parcels = [p for p in all_pending_parcels if not p.assigned_agent]

    verified_agents = CoreUser.objects.filter(
        role='Agent', is_identity_verified=True, is_active=True
    ).order_by('email')

    completed_parcels = LandParcel.objects.filter(
        verification_status__in=['Verified', 'Fraudulent']
    ).select_related('assigned_agent', 'listed_by').order_by('-ardhisasa_last_synced')[:50]

    # Generate agent recommendations with scoring
    scorer = TaskAssignmentScorer()
    agent_recommendations = []
    
    for agent in verified_agents:
        score, details = scorer.get_agent_score(agent)
        agent_recommendations.append({
            'agent_id': str(agent.id),
            'agent_email': agent.email,
            'score': float(score),
            'is_new': details.get('is_new', False),
            'rating': details.get('rating', {}),
            'completion': details.get('completion', {}),
            'usage': details.get('usage', {}),
        })
    
    # Sort by score
    agent_recommendations.sort(key=lambda x: x['score'], reverse=True)

    return render_react_shell(
        request,
        'task-management',
        'Command Centre',
        'Full system access for approvals, assignments, and parcel review.',
        task_board={
            'pending_parcels': [serialize_parcel(parcel, request.user) for parcel in all_pending_parcels],
            'completed_parcels': [serialize_parcel(parcel, request.user) for parcel in completed_parcels],
            'pending_transactions': [serialize_transaction(tx, request.user) for tx in Transaction.objects.filter(contract_agreed=True, status__in=['Deposit_Paid', 'Under_Verification']).order_by('created_at')[:20]],
            'pending_users': [serialize_review_user(user) for user in CoreUser.objects.filter(role__in=['Buyer', 'Seller'], is_identity_verified=False, is_active=True).order_by('date_joined')],
            'pending_agents': [serialize_review_user(user) for user in CoreUser.objects.filter(role='Agent', is_identity_verified=False, is_active=True).order_by('date_joined')],
            'verified_agents': [serialize_review_user(user) for user in verified_agents],
            'agent_recommendations': agent_recommendations,
            'unassigned_count': len(unassigned_parcels),
        },
    )


@login_required
def request_document_access(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    if request.user.id != parcel.listed_by_id and request.user.role != 'Admin':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
    if request.method == 'POST':
        try:
            pin = request.POST.get('pin', '').strip()
            channel = request.POST.get('channel', 'inhouse').strip().lower()
            token = _verify_or_set_access_pin(request.user, pin, parcel)

            commission = parcel.commissions.exclude(accepted_by__isnull=True).order_by('-updated_at').first()
            accessor = (commission.assigned_lawyer or commission.accepted_by or parcel.assigned_agent) if commission else parcel.assigned_agent

            if not accessor:
                raise ValidationError('No assigned reviewer (agent or lawyer) is available for this parcel yet.')

            grant, _ = DocumentAccessGrant.objects.update_or_create(
                parcel=parcel,
                accessor=accessor,
                access_granted=False,
                defaults={'commission': commission, 'seller_auth_token': token, 'seller_signed_at': timezone.now()}
            )

            # Advance parcel pipeline state to AGENT_VERIFYING
            if parcel.verification_status in {'AGENT_ASSIGNED', 'AWAITING_SELLER_ACCESS_GRANT', 'AI_APPROVED'}:
                parcel.verification_status = 'AGENT_VERIFYING'
                parcel.save(update_fields=['verification_status', 'updated_at'])

            # Send in-house secure message with access PIN
            content = f"SECURITY NOTICE: Seller {request.user.email} has granted document access authorization for parcel {parcel.parcel_number}. Use PIN code '{pin}' to complete verification."
            inhouse_msg_success = True
            try:
                Message.objects.create(
                    sender=request.user,
                    receiver=accessor,
                    content=content,
                )
            except Exception as exc:
                logger.warning("Failed to deliver in-house security message: %s", exc)
                inhouse_msg_success = False

            # WhatsApp / SMS Fallback if requested or if in-house messaging failed
            if channel == 'whatsapp' or not inhouse_msg_success:
                try:
                    from external_services.adapters.sms import AfricasTalkingAdapter
                    sms_adapter = AfricasTalkingAdapter()
                    phone = getattr(accessor, 'phone_number', '') or '+254700000000'
                    sms_adapter.send_sms(
                        recipients=[phone],
                        message=f"Digiland Security Code for Parcel {parcel.parcel_number}: {pin}. Enter code to confirm document access."
                    )
                    django_messages.info(request, f"Security code fallback dispatched to agent phone/WhatsApp ({phone}).")
                except Exception as sms_exc:
                    logger.warning("Failed to send WhatsApp/SMS security code fallback: %s", sms_exc)

            AuditLog.objects.create(
                user=request.user,
                action=f"Granted document access PIN for parcel {parcel.parcel_number}",
                metadata={'parcel_id': str(parcel.id), 'accessor_id': str(accessor.id), 'channel': channel},
            )
            django_messages.success(request, 'Seller authorization PIN recorded and dispatched securely to assigned reviewer.')
        except ValidationError as exc:
            django_messages.error(request, str(exc))
    return redirect('frontend:parcel_detail', parcel_number=parcel_number)


@login_required
def confirm_document_access(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    if request.user.role not in {'Agent', 'Lawyer', 'Admin'}:
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
    if request.method == 'POST':
        try:
            commission = parcel.commissions.filter(assigned_lawyer=request.user).first() if request.user.role == 'Lawyer' else parcel.commissions.filter(accepted_by=request.user).first()
            grant = DocumentAccessGrant.objects.filter(parcel=parcel, accessor=request.user, access_granted=False).order_by('-created_at').first()
            if not grant or not grant.seller_auth_token:
                raise ValidationError('The seller must authorize this parcel first.')
            grant.accessor_auth_token = _verify_or_set_access_pin(request.user, request.POST.get('pin', '').strip(), parcel)
            grant.accessor_signed_at = timezone.now()
            grant.commission = commission or grant.commission
            grant.access_granted = True
            grant.expires_at = timezone.now() + timedelta(hours=24)
            grant.save()
            django_messages.success(request, 'Dual-signature document access granted for 24 hours.')
        except ValidationError as exc:
            django_messages.error(request, str(exc))
    return redirect('frontend:parcel_detail', parcel_number=parcel_number)


@login_required
def lawyer_post_transaction_checklist(request, transaction_id):
    transaction = get_object_or_404(Transaction.objects.select_related('land_parcel'), id=transaction_id)
    commission = transaction.land_parcel.commissions.filter(assigned_lawyer=request.user).first()
    if request.user.role not in {'Lawyer', 'Admin'} or (request.user.role == 'Lawyer' and not commission):
        return redirect('frontend:home')
    lawyer = request.user if request.user.role == 'Lawyer' else (transaction.land_parcel.commissions.filter(assigned_lawyer__isnull=False).first().assigned_lawyer if transaction.land_parcel.commissions.filter(assigned_lawyer__isnull=False).exists() else None)
    for key, label in LawyerPostTransactionTask.TASK_CHOICES:
        LawyerPostTransactionTask.objects.get_or_create(transaction=transaction, task_key=key, defaults={'lawyer': lawyer})
    if request.method == 'POST':
        task = get_object_or_404(LawyerPostTransactionTask, transaction=transaction, task_key=request.POST.get('task_key'))
        task.completed = request.POST.get('completed') == 'on'
        task.completed_at = timezone.now() if task.completed else None
        task.notes = request.POST.get('notes', '').strip()
        task.evidence_url = request.POST.get('evidence_url', '').strip()
        task.save()
        return redirect('frontend:lawyer_post_transaction_checklist', transaction_id=transaction.id)
    tasks = LawyerPostTransactionTask.objects.filter(transaction=transaction)
    return render_react_shell(request, 'lawyer-checklist', 'Post-transaction legal checklist', 'Track registry and title-transfer duties after signing.', post_transaction_tasks=[{'key': t.task_key, 'label': t.get_task_key_display(), 'completed': t.completed, 'notes': t.notes, 'evidence_url': t.evidence_url} for t in tasks], transaction_id=str(transaction.id))

@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_verify_parcel(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    if request.method == 'POST':
        action = request.POST.get('verify_action') or request.POST.get('action')
        if action == 'verify':
            if request.user.role != 'Admin':
                grant = _active_document_grant(parcel, request.user)
                if not grant or not grant.is_valid():
                    django_messages.error(request, 'Dual-signature document access is required before verification.')
                    return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)
            parcel.verification_status = 'AGENT_APPROVED'
            parcel.save(update_fields=['verification_status', 'updated_at'])

            AuditLog.objects.create(
                user=request.user,
                action=f"Agent {request.user.email} approved parcel {parcel.parcel_number} (Stage 4 passed)",
                metadata={'parcel_id': str(parcel.id), 'status': 'AGENT_APPROVED'},
            )
            django_messages.success(request, f'Parcel {parcel.parcel_number} successfully verified by agent! Listing is now unlocked for buyers on the marketplace.')
            return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)

        elif action == 'reject':
            seller = parcel.listed_by
            parcel_label = parcel.parcel_number

            if seller:
                rejection_message = (
                    f"DIGILAND PLATFORM NOTICE — Parcel {parcel_label} Escalated for Admin Review\n\n"
                    f"Dear {seller.email},\n\n"
                    f"Your listing for parcel {parcel_label} was reviewed by assigned agent {request.user.email} "
                    f"and failed Stage 4 manual verification.\n\n"
                    f"Status: ADMIN_ESCALATED. This parcel has been escalated directly to Digiland Platform Administrators for secondary review.\n\n"
                    f"— Digiland Escrow Platform"
                )
                Message.objects.create(
                    sender=request.user,
                    receiver=seller,
                    content=rejection_message,
                )

            parcel.verification_status = 'ADMIN_ESCALATED'
            parcel.save(update_fields=['verification_status', 'updated_at'])

            AuditLog.objects.create(
                user=request.user,
                action=f"Agent {request.user.email} rejected parcel {parcel_label} (Escalated to Admin)",
                metadata={'parcel_id': str(parcel.id), 'status': 'ADMIN_ESCALATED'},
            )
            django_messages.warning(request, f'Parcel {parcel_label} verification rejected and escalated to Admin for review.')
            return redirect('frontend:agent_dashboard')

    return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_submit_checkin(request, parcel_number):
    """Allows an assigned agent to log a weekly check-in progress update with Admin."""
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    if request.user != parcel.assigned_agent and request.user.role != 'Admin':
        django_messages.error(request, 'Only the assigned agent can submit progress check-ins.')
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)

    if request.method == 'POST':
        note_text = request.POST.get('checkin_note', '').strip()
        if not note_text:
            django_messages.error(request, 'Please provide progress details for your check-in.')
            return redirect('frontend:parcel_detail', parcel_number=parcel_number)

        notes_log = parcel.agent_checkin_notes or []
        notes_log.append({
            'agent_email': request.user.email,
            'timestamp': timezone.now().isoformat(),
            'note': note_text,
        })

        parcel.agent_checkin_notes = notes_log
        parcel.last_agent_checkin_at = timezone.now()
        parcel.save(update_fields=['agent_checkin_notes', 'last_agent_checkin_at', 'updated_at'])

        AuditLog.objects.create(
            user=request.user,
            action=f"Agent weekly check-in logged for parcel {parcel.parcel_number}",
            metadata={'parcel_id': str(parcel.id), 'note': note_text},
        )
        django_messages.success(request, 'Weekly agent progress check-in recorded successfully.')

    return redirect('frontend:parcel_detail', parcel_number=parcel_number)


@login_required
def admin_extend_job_posting(request, parcel_number):
    """Admin-only: extend the job board posting duration for a parcel."""
    if request.user.role != 'Admin':
        django_messages.error(request, 'Only administrators can extend job posting time.')
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)

    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    if request.method == 'POST':
        extra_days = int(request.POST.get('extra_days', 7))
        base_time = parcel.job_expires_at if (parcel.job_expires_at and parcel.job_expires_at > timezone.now()) else timezone.now()
        parcel.job_expires_at = base_time + timedelta(days=extra_days)
        if parcel.verification_status not in {'AGENT_JOB_POSTED', 'AI_APPROVED'}:
            parcel.verification_status = 'AGENT_JOB_POSTED'

        parcel.save(update_fields=['job_expires_at', 'verification_status', 'updated_at'])

        AuditLog.objects.create(
            user=request.user,
            action=f"Admin extended job posting for parcel {parcel.parcel_number} by {extra_days} days",
            metadata={'parcel_id': str(parcel.id), 'new_expiry': parcel.job_expires_at.isoformat()},
        )
        django_messages.success(request, f'Job posting for parcel {parcel.parcel_number} extended by {extra_days} days.')

    return redirect('frontend:parcel_detail', parcel_number=parcel_number)


@login_required
def approve_agent(request, user_id):
    """Admin-only: approve an Agent's KYC application."""
    from core.models import User as CoreUser
    from django.contrib import messages
    from core.utils import send_agent_approval_email

    if request.user.role != 'Admin':
        return redirect('frontend:agent_dashboard')
    if request.method != 'POST':
        return redirect('frontend:agent_dashboard')

    agent = get_object_or_404(CoreUser, id=user_id, role='Agent', is_identity_verified=False)

    # KYC docs must be submitted before approval
    kyc_submitted = hasattr(agent, 'kyc_application') and agent.kyc_application.kyc_submitted
    if not kyc_submitted:
        messages.error(request, 'Cannot approve agent - KYC documents not submitted yet.')
        return redirect('frontend:agent_dashboard')

    # Approve the agent
    agent.is_identity_verified = True
    agent.is_active = True
    agent.save()
    
    # Update KYC application status
    if hasattr(agent, 'kyc_application'):
        agent.kyc_application.status = 'Approved'
        agent.kyc_application.save()

    # Send approval email
    email_sent, email_message = send_agent_approval_email(agent)
    if email_sent:
        messages.success(request, f'Agent {agent.email} approved successfully! Approval email sent.')
    else:
        messages.warning(request, f'Agent {agent.email} approved but email failed: {email_message}')
    
    return redirect('frontend:agent_dashboard')


@login_required
def reject_agent(request, user_id):
    """Admin-only: reject an Agent's KYC application and deactivate their account."""
    from core.models import User as CoreUser
    from django.contrib import messages
    from core.utils import send_agent_rejection_email

    if request.user.role != 'Admin':
        return redirect('frontend:agent_dashboard')
    if request.method != 'POST':
        return redirect('frontend:agent_dashboard')

    agent = get_object_or_404(CoreUser, id=user_id, role='Agent')
    agent.is_active = False
    agent.is_identity_verified = False
    agent.save()
    
    # Update KYC application status if it exists
    if hasattr(agent, 'kyc_application'):
        agent.kyc_application.status = 'Rejected'
        agent.kyc_application.save()
    
    # Send rejection email
    email_sent, email_message = send_agent_rejection_email(agent)
    if email_sent:
        messages.warning(request, f'Agent {agent.email} has been rejected and their account deactivated. Rejection email sent.')
    else:
        messages.warning(request, f'Agent {agent.email} rejected but email failed: {email_message}')
    
    return redirect('frontend:agent_dashboard')


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_approvals(request):
    """Agent/Admin: central approvals hub showing all pending items."""
    from core.models import User as CoreUser
    from django.db.models import Q

    context = {}

    # Pending user identity approvals (Buyers/Sellers only — not Admin/Agent)
    context['pending_users'] = CoreUser.objects.filter(
        role__in=['Buyer', 'Seller'], is_identity_verified=False, is_active=True
    ).order_by('date_joined')

    if request.user.role == 'Admin':
        # Admin sees all pending parcels
        context['pending_parcels'] = LandParcel.objects.filter(
            verification_status='Pending'
        ).select_related('assigned_agent', 'listed_by').order_by('-ardhisasa_last_synced')
        # Admin sees all pending transactions
        context['pending_transactions'] = Transaction.objects.filter(
            contract_agreed=True,
            status__in=['Deposit_Paid', 'Under_Verification']
        ).order_by('created_at')
        context['pending_joint_removals'] = JointMemberRemovalRequest.objects.filter(
            status='Pending_Admin_Review'
        ).select_related('group', 'member', 'requested_by').order_by('created_at')
    else:
        # Agent sees only their assigned parcels
        context['pending_parcels'] = LandParcel.objects.filter(
            assigned_agent=request.user, verification_status='Pending'
        ).select_related('listed_by').order_by('-ardhisasa_last_synced')
        # Agent sees transactions for their assigned parcels
        context['pending_transactions'] = Transaction.objects.filter(
            contract_agreed=True,
            status__in=['Deposit_Paid', 'Under_Verification']
        ).filter(
            Q(land_parcel__assigned_agent=request.user) |
            Q(buyer=request.user) |
            Q(seller=request.user)
        ).distinct().order_by('created_at')
        context['pending_joint_removals'] = []

    return render_react_shell(
        request,
        'approvals',
        'Approvals',
        'Central approvals hub for users, parcels, and transactions.',
        approvals_page={
            'pending_users': [serialize_review_user(user) for user in context['pending_users']],
            'pending_parcels': [serialize_parcel(parcel, request.user) for parcel in context['pending_parcels']],
            'pending_transactions': [serialize_transaction(tx, request.user) for tx in context['pending_transactions']],
            'pending_joint_removals': [serialize_joint_member_removal_request(removal) for removal in context['pending_joint_removals']],
        },
    )


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_user_review(request, user_id):
    """Agent/Admin: detailed review page for a specific user's identity."""
    from core.models import User as CoreUser

    reviewed_user = get_object_or_404(CoreUser, id=user_id)

    # Security: agents can only review Buyers/Sellers
    if reviewed_user.role in ['Admin', 'Agent', 'Lawyer']:
        from django.contrib import messages
        messages.error(request, 'You cannot review Admin, Agent or Lawyer accounts.')
        return redirect('frontend:agent_approvals')

    context = {
        'reviewed_user': reviewed_user,
    }

    # Fetch user's parcels (if Seller)
    if reviewed_user.role == 'Seller':
        context['user_parcels'] = LandParcel.objects.filter(
            listed_by=reviewed_user
        ).order_by('-ardhisasa_last_synced')

    # Fetch user's transactions (if Buyer)
    if reviewed_user.role == 'Buyer':
        context['user_transactions'] = Transaction.objects.filter(
            buyer=reviewed_user
        ).order_by('-created_at')

    return render_react_shell(
        request,
        'user-review',
        reviewed_user.email,
        'Detailed review for the selected account.',
        user_review={
            'reviewed_user': serialize_review_user(reviewed_user),
            'user_parcels': [serialize_parcel(parcel, request.user) for parcel in context.get('user_parcels', [])],
            'user_transactions': [serialize_transaction(tx, request.user) for tx in context.get('user_transactions', [])],
        },
    )


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_approve_user(request, user_id):
    """Agent/Admin: approve identity of a Buyer or Seller user (NOT Admin / Agent accounts)."""
    from core.models import User as CoreUser
    from django.contrib import messages

    if request.method != 'POST':
        return redirect('frontend:agent_approvals')

    user = get_object_or_404(CoreUser, id=user_id)

    # Hard security fence — agents cannot elevate Admin, Agent or Lawyer accounts
    if user.role in ['Admin', 'Agent', 'Lawyer']:
        messages.error(request, 'Permission denied: you cannot approve Admin, Agent or Lawyer accounts through this portal.')
        return redirect('frontend:agent_approvals')

    user.is_identity_verified = True
    user.is_active = True
    user.save()
    messages.success(request, f'{user.role} account {user.email} has been verified and approved.')
    return redirect('frontend:agent_approvals')



@login_required
def assign_task(request):
    """Admin-only: assign or reassign a verified agent to a specific pending parcel."""
    from core.models import User as CoreUser
    from django.contrib import messages
    from core.utils import send_task_assignment_email

    if request.user.role != 'Admin':
        return redirect('frontend:agent_dashboard')
    if request.method != 'POST':
        return redirect('frontend:agent_dashboard')

    parcel_number = request.POST.get('parcel_number', '').strip()
    agent_id = request.POST.get('agent_id', '').strip()
    try:
        parcel = LandParcel.objects.get(parcel_number=parcel_number)
        agent = CoreUser.objects.get(id=agent_id, role='Agent', is_identity_verified=True)
        old_agent = parcel.assigned_agent
        parcel.assigned_agent = agent
        parcel.save(update_fields=['assigned_agent'])
        
        # Send task assignment email
        email_sent, email_message = send_task_assignment_email(agent, parcel)
        
        if old_agent and old_agent != agent:
            messages.success(request, f'Parcel {parcel_number} reassigned from {old_agent.email} to {agent.email}. {"Email sent." if email_sent else f"Email failed: {email_message}"}')
        else:
            messages.success(request, f'Parcel {parcel_number} assigned to {agent.email}. {"Email sent." if email_sent else f"Email failed: {email_message}"}')
            
    except LandParcel.DoesNotExist:
        messages.error(request, f'Parcel {parcel_number} not found.')
    except CoreUser.DoesNotExist:
        messages.error(request, 'Selected agent is not valid or not verified.')
    return redirect('frontend:agent_dashboard')


@login_required
def unassign_task(request, parcel_number):
    """Admin-only: remove an agent assignment from a parcel (snatch back)."""
    from django.contrib import messages

    if request.user.role != 'Admin':
        return redirect('frontend:agent_dashboard')
    if request.method != 'POST':
        return redirect('frontend:agent_dashboard')

    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    old_agent = parcel.assigned_agent
    if old_agent:
        parcel.assigned_agent = None
        parcel.save(update_fields=['assigned_agent'])
        messages.warning(request, f'Parcel {parcel_number} has been unassigned from {old_agent.email}.')
    else:
        messages.info(request, f'Parcel {parcel_number} was not assigned to anyone.')
    return redirect('frontend:agent_dashboard')


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_finalize_transaction(request, transaction_id):
    """Release payment from escrow. Agents can only release after deadline; Admin can override."""
    from django.contrib import messages as django_messages
    from django.utils import timezone

    transaction = get_object_or_404(Transaction, id=transaction_id)

    if request.user.role not in ['Admin', 'Agent']:
        return redirect('frontend:home')

    if request.method != 'POST':
        return redirect('frontend:escrow_release')

    if not transaction.contract_agreed:
        django_messages.error(request, 'Contract has not been signed by both parties yet.')
        return redirect('frontend:escrow_release')

    # Only Admin can override the deadline check
    if request.user.role == 'Agent':
        if transaction.buyer_validation_deadline and transaction.buyer_validation_deadline > timezone.now():
            django_messages.error(request, f'Cannot release yet. The escrow verification period ends on {transaction.buyer_validation_deadline.strftime("%b %d, %Y %H:%M")}.')
            return redirect('frontend:escrow_release')

    transaction.status = 'Completed'
    transaction.save()

    AuditLog.objects.create(
        user=request.user,
        action=f"Escrow released for transaction {transaction.id}",
        metadata={
            'transaction_id': str(transaction.id),
            'released_by': request.user.email,
            'role': request.user.role,
            'parcel': transaction.land_parcel.parcel_number,
            'amount': float(transaction.agreed_price),
        }
    )

    django_messages.success(request, f'Payment of KES {transaction.agreed_price:,.0f} for parcel {transaction.land_parcel.parcel_number} has been released from escrow.')
    return redirect('frontend:escrow_release')


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def escrow_release(request):
    """Dedicated page for agents/admins to manage escrow releases."""
    from django.utils import timezone

    # Transactions eligible for release: Deposit_Paid, Under_Verification, Verification_Hiatus
    # where contract is signed
    eligible_statuses = ['Deposit_Paid', 'Under_Verification', 'Verification_Hiatus']
    if request.user.role == 'Agent':
        # Agents only see transactions on parcels they are assigned to
        eligible_tx = Transaction.objects.filter(
            land_parcel__assigned_agent=request.user,
            status__in=eligible_statuses,
        ).select_related('buyer', 'seller', 'land_parcel').order_by('-created_at')
    else:
        # Admin sees all
        eligible_tx = Transaction.objects.filter(
            status__in=eligible_statuses,
        ).select_related('buyer', 'seller', 'land_parcel').order_by('-created_at')

    now = timezone.now()
    is_admin = request.user.role == 'Admin'

    transactions_data = []
    for tx in eligible_tx:
        deadline_passed = tx.buyer_validation_deadline and tx.buyer_validation_deadline < now
        can_release = is_admin or (tx.contract_agreed and deadline_passed)
        days_remaining = tx.days_remaining_for_verification

        transactions_data.append({
            'id': str(tx.id),
            'parcel_number': tx.land_parcel.parcel_number,
            'buyer_email': tx.buyer.email,
            'seller_email': tx.seller.email,
            'amount': str(tx.agreed_price),
            'status': tx.get_status_display() if hasattr(tx, 'get_status_display') else tx.status,
            'contract_signed': tx.contract_agreed,
            'buyer_signature': bool(tx.buyer_signature),
            'seller_signature': bool(tx.seller_signature),
            'deadline': tx.buyer_validation_deadline.strftime('%b %d, %Y %H:%M') if tx.buyer_validation_deadline else 'Not set',
            'deadline_passed': deadline_passed,
            'days_remaining': days_remaining,
            'can_release': can_release,
            'release_url': reverse('frontend:agent_finalize_transaction', args=[tx.id]),
            'created_at': tx.created_at.strftime('%b %d, %Y'),
        })

    return render_react_shell(
        request,
        'escrow-release',
        'Escrow Release',
        'Review and release payments from escrow once the verification period has elapsed.',
        escrow_transactions=transactions_data,
        is_admin=is_admin,
        actions=[
            {'label': 'Command Centre', 'href': reverse('frontend:agent_dashboard'), 'tone': 'outline'},
            {'label': 'Tasks', 'href': reverse('frontend:task_management'), 'tone': 'secondary'},
        ],
    )

@login_required
@user_passes_test(is_seller_or_agent, login_url='/accounts/login/', redirect_field_name=None)
def parcel_upload(request):
    if request.method == 'POST':
        form = LandParcelUploadForm(request.POST, request.FILES)
        if form.is_valid():
            parcel = form.save(commit=False)
            parcel.verification_status = 'Awaiting_Documents' # Compliance Lock
            parcel.listed_by = request.user
            parcel.save()
            return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)
    else:
        form = LandParcelUploadForm()
    return render_react_shell(
        request,
        'form',
        'Register a land parcel',
        'Provide parcel details for compliance checks and listing verification.',
        form=serialize_form(
            form,
            action=reverse('frontend:parcel_upload'),
            submit_label='Submit for verification',
            intro='Our system cross-references submitted details against registry records during review.',
        ),
        actions=[{'label': 'Back to marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'}],
    )

@login_required
def upload_parcel_document(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    
    if request.user != parcel.listed_by and request.user.role != 'Admin':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            doc = form.save(commit=False)
            doc.uploaded_by = request.user
            doc.land_parcel = parcel
            doc.save()
            
            # Check compliance to release lock
            has_title = parcel.documents.filter(document_type='Title_Deed').exists()
            has_id = parcel.documents.filter(document_type='ID_Card').exists()
            has_photo = parcel.documents.filter(document_type='Passport_Photo').exists()
            has_spouse_consent = parcel.documents.filter(document_type='Spousal_Consent').exists()
            
            if parcel.verification_status == 'Awaiting_Documents' and has_title and has_id and has_photo and has_spouse_consent and parcel.image:
                parcel.verification_status = 'Pending'
                parcel.save()
                
                # AI Task Auto-Assignment Trigger
                from core.services.task_assignment import TaskAssignmentScorer
                TaskAssignmentScorer().auto_assign_parcel(parcel)
                
            return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)
    else:
        form = DocumentUploadForm()
        
    return render_react_shell(
        request,
        'form',
        f'Upload document - {parcel.parcel_number}',
        'Attach compliance documents for the selected parcel.',
        form=serialize_form(
            form,
            action=reverse('frontend:upload_document', args=[parcel.parcel_number]),
            submit_label='Upload document',
            intro=f'Parcel: {parcel.parcel_number}. Accepted document types help unlock verification.',
        ),
        actions=[{'label': 'Back to parcel', 'href': reverse('frontend:parcel_detail', args=[parcel.parcel_number]), 'tone': 'outline'}],
    )

@login_required
def moderate_document(request, parcel_number, document_id):
    if request.method != 'POST':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
    
    if request.user.role not in ['Admin', 'Agent']:
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    doc = get_object_or_404(Document, id=document_id, land_parcel__parcel_number=parcel_number)
    action = request.POST.get('moderation_action')
    
    if action == 'approve':
        doc.verification_status = 'Match'
    elif action == 'reject':
        doc.verification_status = 'Mismatch'
        
    doc.save()
    return redirect('frontend:parcel_detail', parcel_number=parcel_number)

@login_required
def delete_document(request, parcel_number, document_id):
    if request.method != 'POST':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    
    if request.user != parcel.listed_by and request.user.role != 'Admin':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    doc = get_object_or_404(Document, id=document_id, land_parcel=parcel)
    doc.delete()
    
    # Check compliance to re-evaluate status
    has_title = parcel.documents.filter(document_type='Title_Deed').exists()
    has_id = parcel.documents.filter(document_type='ID_Card').exists()
    has_photo = parcel.documents.filter(document_type='Passport_Photo').exists()
    has_spouse_consent = parcel.documents.filter(document_type='Spousal_Consent').exists()
    
    if parcel.verification_status != 'Awaiting_Documents' and not (has_title and has_id and has_photo and has_spouse_consent and parcel.image):
        parcel.verification_status = 'Awaiting_Documents'
        parcel.save()
        
    return redirect('frontend:parcel_detail', parcel_number=parcel_number)

@login_required
def parcel_edit(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    
    if request.user != parcel.listed_by and request.user.role != 'Admin':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    if request.method == 'POST':
        form = LandParcelUploadForm(request.POST, request.FILES, instance=parcel)
        if form.is_valid():
            form.save()
            if parcel.verification_status != 'Pending':
                parcel.verification_status = 'Pending'
                parcel.save()
            return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)
    else:
        form = LandParcelUploadForm(instance=parcel)
        
    return render_react_shell(
        request,
        'form',
        f'Edit parcel - {parcel.parcel_number}',
        'Update parcel details.',
        form=serialize_form(
            form,
            action=reverse('frontend:parcel_edit', args=[parcel.parcel_number]),
            submit_label='Save changes',
            cancel_label='Cancel',
            cancel_href=reverse('frontend:parcel_detail', args=[parcel.parcel_number]),
            intro='Editing parcel details will reset the verification status to Pending.',
        ),
    )

@login_required
def parcel_delete(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    
    # Seller or Admin can delete, but only if there are no active transactions
    if request.user != parcel.listed_by and request.user.role != 'Admin':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    if parcel.transactions.exclude(status__in=['Refunded', 'Reversed', 'Disputed']).exists():
        # Cannot delete parcel involved in active transactions
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    if request.method == 'POST':
        parcel.delete()
        return redirect('frontend:parcel_list')

    return render_react_shell(
        request,
        'form',
        f'Delete parcel - {parcel.parcel_number}',
        'Permanent deletion requires confirmation.',
        form={
            'action': reverse('frontend:parcel_delete', args=[parcel.parcel_number]),
            'method': 'post',
            'enctype': 'application/x-www-form-urlencoded',
            'submitLabel': 'Delete parcel',
            'cancelLabel': 'Cancel',
            'cancelHref': reverse('frontend:parcel_detail', args=[parcel.parcel_number]),
            'intro': f'You are about to permanently delete {parcel.parcel_number}. This action cannot be undone.',
            'fields': [],
            'hiddenFields': [],
            'errors': [],
        },
    )

@login_required
def initiate_escrow(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)

    from django.contrib import messages as django_messages

    # Security: Only Buyers can commission a purchase, Admins can force create for testing.
    if request.user.role not in ['Buyer', 'Admin']:
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)

    if parcel.verification_status != 'Verified':
        django_messages.error(request, 'Only verified parcels can be commissioned for purchase.')
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)

    if request.method == 'POST':
        joint_group = None
        is_joint_purchase = False
        purchase_mode = (request.POST.get('purchase_mode') or '').strip().lower()
        joint_group_id = (request.POST.get('joint_group_id') or '').strip()

        if purchase_mode == 'joint' or joint_group_id:
            if request.user.role != 'Buyer':
                django_messages.error(request, 'Joint commissions are only available for buyer accounts.')
                return redirect('frontend:parcel_detail', parcel_number=parcel_number)
            if not is_joint_buyer(request.user):
                django_messages.error(request, 'Joint commissions require a joint buyer account. Choose the joint option after signup first.')
                return redirect('frontend:buyer_account_choice')
            is_joint_purchase = True
            if joint_group_id:
                joint_group = get_object_or_404(JointBuyerGroup, id=joint_group_id, leader=request.user)
                if not joint_group.is_valid:
                    django_messages.error(request, 'This joint group is not valid. Ensure it has at least 2 members and shares total 100%.')
                    return redirect('frontend:parcel_detail', parcel_number=parcel_number)
            if getattr(request.user, 'buyer_account_type', None) != 'Joint':
                request.user.buyer_account_type = 'Joint'
                request.user.save(update_fields=['buyer_account_type'])

        try:
            commission = create_commission(
                request.user,
                parcel,
                is_joint_purchase=is_joint_purchase,
                joint_group=joint_group,
            )
            django_messages.success(request, f'Commission created for parcel {parcel.parcel_number}. Nearby agents have been notified.')
            return redirect('frontend:commission_detail', commission_id=commission.id)
        except ValidationError as exc:
            existing = PurchaseCommission.objects.filter(
                buyer=request.user,
                land_parcel=parcel,
                status__in=['Open', 'Accepted', 'Documents_Review', 'Lawyer_Verification', 'Site_Visit_Scheduled', 'Site_Visit_Complete', 'Closing'],
            ).order_by('-created_at').first()
            if existing:
                django_messages.info(request, 'An active commission for this parcel already exists. Opening it now.')
                return redirect('frontend:commission_detail', commission_id=existing.id)
            django_messages.error(request, str(exc))

    return redirect('frontend:parcel_detail', parcel_number=parcel_number)


def _active_document_grant(parcel, user):
    """Find active dual-signature access grant for a given parcel and accessor (Lawyer or Agent)."""
    return DocumentAccessGrant.objects.filter(
        parcel=parcel,
        accessor=user,
        access_granted=True,
        expires_at__gt=timezone.now()
    ).first()


@login_required
def request_document_access(request, parcel_number):
    """
    Seller initiates or approves a dual-signature document access authorization for a parcel.
    Stores seller's cryptographic signature / authorization token.
    """
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    if request.user.role != 'Admin' and request.user.id != parcel.listed_by_id:
        django_messages.error(request, 'Only the parcel seller or an admin can authorize document access.')
        return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)

    if request.method == 'POST':
        pin = (request.POST.get('seller_pin') or request.POST.get('auth_code') or '').strip()
        if not pin:
            django_messages.error(request, 'Please provide a seller authorization PIN or code.')
            return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)

        import hashlib
        seller_sig = hashlib.sha256(f"{parcel.id}:{request.user.id}:{pin}:{timezone.now().date()}".encode()).hexdigest()

        grant, created = DocumentAccessGrant.objects.get_or_create(
            parcel=parcel,
            seller=request.user,
            access_granted=False,
            defaults={'created_at': timezone.now()}
        )
        grant.seller_auth_signature = seller_sig
        grant.seller_signed_at = timezone.now()
        grant.save()

        django_messages.success(request, 'Seller document authorization recorded. The assigned advocate or agent can now confirm access.')
    return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)


@login_required
def confirm_document_access(request, parcel_number):
    """
    Assigned Lawyer or Agent provides their authorization signature / PIN to complete dual-signature access.
    Unlocks land documents for 24 hours.
    """
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    if request.user.role not in {'Lawyer', 'Agent', 'Admin'}:
        django_messages.error(request, 'Only advocates, agents, or admins can request document access.')
        return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)

    if request.method == 'POST':
        pin = (request.POST.get('accessor_pin') or request.POST.get('auth_code') or '').strip()
        if not pin:
            django_messages.error(request, 'Please enter your authorization PIN or credential code.')
            return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)

        import hashlib
        accessor_sig = hashlib.sha256(f"{parcel.id}:{request.user.id}:{pin}:{timezone.now().date()}".encode()).hexdigest()

        grant = DocumentAccessGrant.objects.filter(
            parcel=parcel,
            seller_auth_signature__isnull=False,
            access_granted=False
        ).first()

        if not grant:
            grant = DocumentAccessGrant.objects.create(
                parcel=parcel,
                seller=parcel.listed_by,
                accessor=request.user,
                accessor_auth_signature=accessor_sig,
                accessor_signed_at=timezone.now(),
                access_granted=False
            )
            django_messages.info(request, 'Your access request and signature have been recorded. Waiting for seller authorization signature.')
            return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)

        grant.accessor = request.user
        grant.accessor_auth_signature = accessor_sig
        grant.accessor_signed_at = timezone.now()
        grant.access_granted = True
        grant.granted_at = timezone.now()
        grant.expires_at = timezone.now() + timedelta(hours=24)
        grant.save()

        django_messages.success(request, 'Dual-signature authorization verified! Land documents unlocked for 24 hours.')
    return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)


@login_required
def parcel_detail(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)

    # Track page view for the recommendation engine (Buyers only, max 1 per 5 minutes)
    if request.user.role == 'Buyer':
        from django.utils import timezone
        from datetime import timedelta
        recent_cutoff = timezone.now() - timedelta(minutes=5)
        already_viewed = ParcelView.objects.filter(
            user=request.user, parcel=parcel, viewed_at__gte=recent_cutoff
        ).exists()
        if not already_viewed:
            ParcelView.objects.create(user=request.user, parcel=parcel)

    # Check if user has favorited this parcel
    is_favorited = False
    if request.user.is_authenticated:
        is_favorited = UserFavorite.objects.filter(user=request.user, parcel=parcel).exists()

    # Get AI price estimate (Disabled for initial rollout)
    ai_price = None

    joint_groups = []
    can_use_joint_purchase = False
    if request.user.is_authenticated and request.user.role == 'Buyer':
        joint_groups = JointBuyerGroup.objects.filter(leader=request.user).prefetch_related('members')
        can_use_joint_purchase = is_joint_buyer(request.user)

    can_view_documents = False
    active_grant = None
    if request.user.is_authenticated:
        if request.user.role == 'Admin' or request.user.id == parcel.listed_by_id:
            can_view_documents = True
        elif request.user.role in {'Agent', 'Lawyer'}:
            active_grant = _active_document_grant(parcel, request.user)
            can_view_documents = bool(active_grant and active_grant.is_valid())
        elif request.user.role == 'Buyer' and parcel.transactions.filter(buyer=request.user, status='Completed').exists():
            can_view_documents = True

    parcel_data = {
        'parcel_number': str(parcel.parcel_number),
        'image_url': parcel.image.url if getattr(parcel, 'image', None) else None,
        'land_use_type': parcel.land_use_type,
        'county': parcel.county,
        'constituency': parcel.constituency,
        'ward': parcel.ward,
        'land_size': str(parcel.land_size),
        'registered_owner_id_masked': f"***{parcel.registered_owner_id[3:]}" if parcel.registered_owner_id else 'N/A',
        'verification_status': parcel.verification_status,
        'latitude': str(parcel.latitude) if parcel.latitude is not None else None,
        'longitude': str(parcel.longitude) if parcel.longitude is not None else None,
        'google_maps_url': f'https://www.google.com/maps/search/?api=1&query={parcel.latitude},{parcel.longitude}' if parcel.latitude is not None and parcel.longitude is not None else None,
        'displayed_price': str(parcel.displayed_price),
        'is_favorited': is_favorited,
        'ai_price': None if not ai_price else {
            'total_value': str(ai_price.get('total_value', '')),
            'price_per_acre': str(ai_price.get('price_per_acre', '')),
            'confidence_low': str(ai_price.get('confidence_low', '')),
            'confidence_high': str(ai_price.get('confidence_high', '')),
        },
        'access_locked': bool(request.user.is_authenticated and request.user.role in {'Agent', 'Lawyer'} and not can_view_documents),
        'request_access_url': reverse('frontend:request_document_access', args=[parcel.parcel_number]) if request.user.is_authenticated and request.user.id == parcel.listed_by_id else None,
        'confirm_access_url': reverse('frontend:confirm_document_access', args=[parcel.parcel_number]) if request.user.is_authenticated and request.user.role in {'Agent', 'Lawyer'} else None,
        'documents': [
            {
                **serialize_document(doc),
                'moderate_url': reverse('frontend:moderate_document', args=[parcel.parcel_number, doc.id]) if request.user.is_authenticated and request.user.role in ['Admin', 'Agent', 'Lawyer'] else None,
                'delete_url': reverse('frontend:delete_document', args=[parcel.parcel_number, doc.id]) if request.user.is_authenticated and (request.user.role == 'Admin' or request.user.id == parcel.listed_by_id) else None,
            }
            for doc in parcel.documents.all()
        ] if can_view_documents else [],
        'can_edit': bool(request.user.is_authenticated and (request.user.role == 'Admin' or request.user.id == parcel.listed_by_id)),
        'edit_url': reverse('frontend:parcel_edit', args=[parcel.parcel_number]) if request.user.is_authenticated and (request.user.role == 'Admin' or request.user.id == parcel.listed_by_id) else None,
        'delete_url': reverse('frontend:parcel_delete', args=[parcel.parcel_number]) if request.user.is_authenticated and (request.user.role == 'Admin' or request.user.id == parcel.listed_by_id) else None,
        'can_upload_document': bool(request.user.is_authenticated and (request.user.role == 'Admin' or request.user.id == parcel.listed_by_id)),
        'can_initiate_escrow': bool(request.user.is_authenticated and request.user.role in ['Buyer', 'Admin'] and parcel.verification_status == 'Verified'),
        'can_use_joint_purchase': can_use_joint_purchase,
        'assigned_agent_email': parcel.assigned_agent.email if parcel.assigned_agent else None,
        'joint_groups': [serialize_joint_group(group) for group in joint_groups] if joint_groups else [],
        'purchase_modes': [
            {'value': 'individual', 'label': 'Individual purchase', 'selected': True},
            {'value': 'joint', 'label': 'Joint group purchase', 'selected': False},
        ],
        'initiate_escrow_url': reverse('frontend:initiate_escrow', args=[parcel.parcel_number]),
        'upload_document_url': reverse('frontend:upload_document', args=[parcel.parcel_number]) if request.user.is_authenticated and (request.user.role == 'Admin' or request.user.id == parcel.listed_by_id) and parcel.verification_status != 'Verified' else None,
        'edit_url': reverse('frontend:parcel_edit', args=[parcel.parcel_number]) if request.user.is_authenticated and (request.user.role == 'Admin' or request.user.id == parcel.listed_by_id) else None,
        'delete_url': reverse('frontend:parcel_delete', args=[parcel.parcel_number]) if request.user.is_authenticated and (request.user.role == 'Admin' or request.user.id == parcel.listed_by_id) else None,
        'toggle_favorite_url': reverse('frontend:toggle_favorite', args=[parcel.parcel_number]) if request.user.is_authenticated else None,
        'agent_verify_url': reverse('frontend:agent_verify_parcel', args=[parcel.parcel_number]) if request.user.is_authenticated and request.user.role in ['Admin', 'Agent', 'Lawyer'] else None,
    }

    return render_react_shell(
        request,
        'parcel-detail',
        f'Parcel details - {parcel.parcel_number}',
        'Review parcel information, documents, and next workflow actions.',
        parcel_detail=parcel_data,
        popup_context={
            'parcel': parcel,
            'county': parcel.county,
            'constituency': parcel.constituency,
            'ward': parcel.ward,
            'placement': 'parcel-detail',
        },
        actions=[{'label': 'Back to marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'}],
    )

@login_required
def user_transactions(request):
    if request.user.role in ['Admin', 'Lawyer']:
        transactions = Transaction.objects.all().order_by('-created_at')
    else:
        transactions = (
            Transaction.objects.filter(buyer=request.user) |
            Transaction.objects.filter(seller=request.user)
        ).order_by('-created_at')
    return render_react_shell(
        request,
        'transactions',
        'My transactions',
        'Track every active and completed land purchase or sale in your escrow pipeline.',
        transactions=[serialize_transaction(tx, request.user) for tx in transactions],
        actions=[
            {'label': 'Browse parcels', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
            {'label': 'Legal checklist', 'href': reverse('frontend:seller_laws') if request.user.role == 'Seller' else reverse('frontend:escrow_acts'), 'tone': 'secondary'},
        ],
    )

@login_required
def messages_list(request):
    from django.db.models import Q
    from django.middleware.csrf import get_token
    from core.models import User as CoreUser
    current_user = request.user

    try:
        all_msgs = Message.objects.filter(
            Q(sender=current_user) | Q(receiver=current_user)
        ).select_related('sender', 'receiver').order_by('-timestamp')
    except Exception:
        all_msgs = []

    # Aggregate into threads keyed by counterparty
    threads = {}
    for msg in all_msgs:
        partner = msg.sender if msg.receiver == current_user else msg.receiver
        if partner:
            if partner not in threads:
                threads[partner] = []
            threads[partner].append(msg)

    # Determine who this user is ALLOWED to compose to
    # Rule: Buyers & Sellers can ONLY contact Admins/Agents
    # Rule: Admins/Agents can contact anyone
    try:
        if current_user.role in ['Buyer', 'Seller']:
            allowed_recipients = CoreUser.objects.filter(
                role__in=['Admin', 'Agent', 'Lawyer']
            ).exclude(id=current_user.id)
        else:  # Admin / Agent
            allowed_recipients = CoreUser.objects.exclude(id=current_user.id)
        serialized_recipients = [serialize_user(recipient) for recipient in allowed_recipients]
    except Exception:
        serialized_recipients = []

    context = {
        'allowed_recipients': serialized_recipients,
        'msg_error': request.session.pop('msg_error', None),
    }

    if current_user.role == 'Buyer':
        context['header'] = 'My Inbox'
        context['threads'] = [
            serialize_message_thread(partner, msgs, current_user)
            for partner, msgs in threads.items()
            if partner and getattr(partner, 'role', '') in ['Admin', 'Agent', 'Lawyer']
        ]
        context['mode'] = 'single'
    elif current_user.role == 'Seller':
        context['header'] = 'My Inbox'
        context['threads'] = [
            serialize_message_thread(partner, msgs, current_user)
            for partner, msgs in threads.items()
            if partner and getattr(partner, 'role', '') in ['Admin', 'Agent', 'Lawyer']
        ]
        context['mode'] = 'single'
    else:  # Admin / Agent
        context['header'] = 'Platform Communications'
        context['buyer_threads'] = [
            serialize_message_thread(partner, msgs, current_user)
            for partner, msgs in threads.items()
            if partner and getattr(partner, 'role', '') == 'Buyer'
        ]
        context['seller_threads'] = [
            serialize_message_thread(partner, msgs, current_user)
            for partner, msgs in threads.items()
            if partner and getattr(partner, 'role', '') == 'Seller'
        ]
        context['mode'] = 'dual'

    return render_react_shell(
        request,
        'messages',
        'Messages',
        context['header'],
        messages_page={
            'allowed_recipients': context['allowed_recipients'],
            'msg_error': context['msg_error'],
            'header': context['header'],
            'threads': context.get('threads', []),
            'buyer_threads': context.get('buyer_threads', []),
            'seller_threads': context.get('seller_threads', []),
            'mode': context.get('mode', 'single'),
            'compose_action': reverse('frontend:send_message'),
            'csrf_token': get_token(request),
        },
    )


@login_required
def message_thread_detail(request, partner_id):
    from django.db.models import Q
    from django.shortcuts import get_object_or_404
    from django.middleware.csrf import get_token
    from core.models import User as CoreUser
    from django.http import JsonResponse

    user = request.user
    partner = get_object_or_404(CoreUser, id=partner_id)

    # Fetch messages
    messages = Message.objects.filter(
        Q(sender=user, receiver=partner) | Q(sender=partner, receiver=user)
    ).order_by('-timestamp')

    # Mark as read
    Message.objects.filter(sender=partner, receiver=user, is_read=False).update(is_read=True)

    thread_data = serialize_message_thread(partner, messages, user) if messages else {
        'partner': serialize_user(partner),
        'latest_timestamp': '',
        'count': 0,
        'url': reverse('frontend:message_thread_detail', args=[partner.id]),
        'messages': []
    }

    if request.headers.get('accept') == 'application/json' or request.headers.get('x-requested-with') == 'XMLHttpRequest':
        return JsonResponse({
            'status': 'ok',
            'thread': thread_data,
        })

    return render_react_shell(
        request,
        'message-thread',
        f'Conversation with {partner.email}',
        'Secure messaging thread.',
        message_thread={
            'thread': thread_data,
            'compose_action': reverse('frontend:send_message'),
            'clear_action': reverse('frontend:clear_message_thread', args=[partner.id]) if user.role == 'Admin' else None,
            'csrf_token': get_token(request),
        }
    )

@login_required
def clear_message_thread(request, partner_id):
    from django.db.models import Q
    from django.contrib import messages as django_messages

    if request.user.role != 'Admin':
        return redirect('frontend:messages')
        
    if request.method == 'POST':
        Message.objects.filter(
            Q(sender=request.user, receiver_id=partner_id) | 
            Q(sender_id=partner_id, receiver=request.user)
        ).delete()
        django_messages.success(request, "Thread successfully cleared.")
        
    return redirect('frontend:messages')

@login_required
def send_message(request):
    from core.models import User as CoreUser
    from django.http import JsonResponse
    if request.method != 'POST':
        return redirect('frontend:messages')

    sender = request.user
    
    # Support JSON or Form Data
    if request.content_type == 'application/json':
        import json
        try:
            payload = json.loads(request.body)
        except Exception:
            payload = {}
        content = payload.get('content', '').strip()
        receiver_id = payload.get('receiver_id', '').strip()
        receiver_email = payload.get('receiver_email', '').strip()
        recipient_type = payload.get('recipient_type', 'single').strip()
    else:
        content = request.POST.get('content', '').strip()
        receiver_id = request.POST.get('receiver_id', '').strip()
        receiver_email = request.POST.get('receiver_email', '').strip()
        recipient_type = request.POST.get('recipient_type', 'single').strip()

    is_ajax = request.headers.get('accept') == 'application/json' or request.headers.get('x-requested-with') == 'XMLHttpRequest' or request.content_type == 'application/json'

    if not content:
        if is_ajax:
            return JsonResponse({'error': 'Message content cannot be empty'}, status=400)
        return redirect('frontend:messages')

    if sender.role in ['Admin', 'Agent'] and recipient_type != 'single':
        recipients = []
        if recipient_type == 'all':
            recipients = CoreUser.objects.exclude(id=sender.id)
        elif recipient_type == 'buyers':
            recipients = CoreUser.objects.filter(role='Buyer').exclude(id=sender.id)
        elif recipient_type == 'sellers':
            recipients = CoreUser.objects.filter(role='Seller').exclude(id=sender.id)
        elif recipient_type == 'agents':
            recipients = CoreUser.objects.filter(role='Agent').exclude(id=sender.id)
        
        for user in recipients:
            Message.objects.create(sender=sender, receiver=user, content=content)
        
        if is_ajax:
            return JsonResponse({'status': 'ok', 'count': len(recipients), 'type': recipient_type})
        from django.contrib import messages
        messages.success(request, f'Message sent to {len(recipients)} {recipient_type}.')
        return redirect('frontend:messages')

    receiver = None
    if receiver_id:
        try:
            receiver = CoreUser.objects.get(id=receiver_id)
        except CoreUser.DoesNotExist:
            pass
    elif receiver_email:
        try:
            receiver = CoreUser.objects.get(email__iexact=receiver_email)
        except CoreUser.DoesNotExist:
            if is_ajax:
                return JsonResponse({'error': f'No account found with email: {receiver_email}'}, status=404)
            request.session['msg_error'] = f'No account found with email: {receiver_email}'
            return redirect('frontend:messages')

    if not receiver:
        if is_ajax:
            return JsonResponse({'error': 'Recipient not specified or not found'}, status=404)
        return redirect('frontend:messages')

    # Strict mediation: Buyers and Sellers CANNOT message each other directly unless part of an active transaction
    if sender.role in ['Buyer', 'Seller'] and receiver.role in ['Buyer', 'Seller']:
        from django.db.models import Q
        # Check if they share a transaction
        has_shared_tx = Transaction.objects.filter(
            (Q(buyer=sender, seller=receiver) | Q(buyer=receiver, seller=sender))
        ).exists()
        if not has_shared_tx:
            if is_ajax:
                return JsonResponse({'error': 'Direct buyer-seller messaging is restricted to active transactions.'}, status=403)
            request.session['msg_error'] = 'Direct buyer-seller messaging is restricted to active transactions.'
            return redirect('frontend:messages')

    msg = Message.objects.create(sender=sender, receiver=receiver, content=content)
    
    if is_ajax:
        return JsonResponse({
            'status': 'ok',
            'message': {
                'id': str(msg.id),
                'sender_email': msg.sender.email,
                'content': msg.content,
                'timestamp': msg.timestamp.strftime('%b %d, %Y %H:%M'),
                'is_self': True,
            },
            'partner': serialize_user(receiver),
        })

    return redirect('frontend:messages')

@login_required
def support_tickets(request):
    if request.method == 'POST':
        subject = request.POST.get('subject', '').strip()
        message = request.POST.get('message', '').strip()
        if subject and message:
            SupportTicket.objects.create(user=request.user, subject=subject, message=message)
            from django.contrib import messages
            messages.success(request, 'Support ticket created successfully.')
            return redirect('frontend:support')

    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    return render_react_shell(
        request,
        'support',
        'Support',
        'Open and review support requests related to disputes, verification issues, or account access.',
        support_page={
            'tickets': [serialize_support_ticket(ticket) for ticket in tickets],
            'create_action': reverse('frontend:support'),
            'csrf_token': get_token(request),
        },
        actions=[{'label': 'Open new ticket', 'href': '#', 'tone': 'outline'}],
    )


def initialize_lawyer_post_transaction_tasks(transaction, lawyer=None):
    """
    Initializes the mandatory 7 Kenyan post-signing conveyancing tasks for a transaction.
    """
    lawyer_obj = lawyer or transaction.agent or transaction.seller
    for key, name in LawyerPostTransactionTask.TASK_CHOICES:
        LawyerPostTransactionTask.objects.get_or_create(
            transaction=transaction,
            task_key=key,
            defaults={
                'lawyer': lawyer_obj if getattr(lawyer_obj, 'role', None) == 'Lawyer' else None,
                'completed': False
            }
        )



@login_required
def lawyer_post_transaction_tasks(request, transaction_id):
    """
    View for Lawyer/Parties to manage and check off post-contract-execution conveyancing tasks.
    """
    transaction = get_object_or_404(Transaction, id=transaction_id)
    if request.user.role not in {'Lawyer', 'Admin'} and request.user not in [transaction.buyer, transaction.seller]:
        django_messages.error(request, 'Access restricted to involved parties and advocates.')
        return redirect('frontend:transactions')

    # Ensure tasks are initialized
    initialize_lawyer_post_transaction_tasks(transaction, request.user if request.user.role == 'Lawyer' else None)

    if request.method == 'POST' and request.user.role in {'Lawyer', 'Admin'}:
        task_key = request.POST.get('task_key')
        is_completed = request.POST.get('completed') == 'true' or request.POST.get('action') == 'complete'
        evidence = (request.POST.get('evidence_url') or '').strip()
        notes = (request.POST.get('notes') or '').strip()

        task = LawyerPostTransactionTask.objects.filter(transaction=transaction, task_key=task_key).first()
        if task:
            task.completed = is_completed
            task.completed_at = timezone.now() if is_completed else None
            if evidence:
                task.evidence_url = evidence
            if notes:
                task.notes = notes
            if request.user.role == 'Lawyer':
                task.lawyer = request.user
            task.save()
            django_messages.success(request, f'Conveyancing task "{task.get_task_key_display()}" updated.')
        return redirect('frontend:lawyer_post_transaction_tasks', transaction_id=transaction.id)

    tasks_qs = LawyerPostTransactionTask.objects.filter(transaction=transaction).order_by('task_key')
    task_list = [
        {
            'id': str(t.id),
            'task_key': t.task_key,
            'task_name': t.get_task_key_display(),
            'is_completed': t.completed,
            'completed_at': t.completed_at.strftime('%b %d, %Y %H:%M') if t.completed_at else None,
            'notes': t.notes or '',
            'evidence_url': t.evidence_url or '',
            'lawyer_email': t.lawyer.email if t.lawyer else 'Pending Assignment',
        }
        for t in tasks_qs
    ]

    return render_react_shell(
        request,
        'lawyer-tasks',
        'Post-Signing Conveyancing Tasks',
        f'Property: {transaction.land_parcel.parcel_number}',
        transaction_id=str(transaction.id),
        parcel_number=transaction.land_parcel.parcel_number,
        tasks=task_list,
        completed_count=sum(1 for t in task_list if t.get('is_completed')),
        total_count=len(task_list),
        can_edit=bool(request.user.role in {'Lawyer', 'Admin'}),
        actions=[
            {'label': 'Back to contract', 'href': reverse('frontend:sign_contract', args=[transaction.id]), 'tone': 'outline'},
            {'label': 'Transactions', 'href': reverse('frontend:transactions'), 'tone': 'secondary'},
        ]
    )


def lawyer_post_transaction_checklist(request, transaction_id):
    """Alias route for post-transaction conveyancing tasks."""
    return lawyer_post_transaction_tasks(request, transaction_id)


@login_required
def sign_contract(request, transaction_id):
    transaction = get_object_or_404(
        Transaction.objects.select_related('buyer', 'seller', 'land_parcel', 'joint_group').prefetch_related('joint_group__members'),
        id=transaction_id,
    )
    
    # Security: Only involved parties (buyer, seller), Admin, or Lawyer can access
    if request.user not in [transaction.buyer, transaction.seller] and request.user.role not in ['Admin', 'Lawyer']:
        return redirect('frontend:transactions')

    from django.core.signing import Signer
    signer = Signer()
    signing_token = signer.sign(str(transaction.id))
    fullpage_url = reverse('frontend:contract_sign_fullpage', args=[signing_token])

    if request.method == 'GET' and request.user.role in {'Buyer', 'Seller', 'Lawyer'} and not transaction.contract_agreed:
        return redirect(fullpage_url)
        
    if request.method == 'POST':
        # Lawyer Sign-off handling
        if request.user.role == 'Lawyer':
            lawyer_sig = request.POST.get('lawyer_signature_data')
            lawyer_name = request.POST.get('lawyer_name')
            lawyer_lsk_number = request.POST.get('lawyer_lsk_number')

            if not lawyer_sig or not lawyer_name or not lawyer_lsk_number:
                from django.contrib import messages
                messages.error(request, 'Please complete all verification fields and capture your signature.')
                return redirect(fullpage_url)

            transaction.lawyer_signature = lawyer_sig
            transaction.lawyer_name = lawyer_name
            transaction.lawyer_lsk_number = lawyer_lsk_number
            from django.utils import timezone
            transaction.lawyer_signed_at = timezone.now()

            # Set contract_agreed = True only if ALL signatures (buyer, seller, lawyer) are present
            if transaction.buyer_signature and transaction.seller_signature:
                if transaction.is_joint_purchase and transaction.joint_group:
                    if transaction.joint_group.all_signed:
                        transaction.contract_agreed = True
                else:
                    transaction.contract_agreed = True
                if transaction.contract_agreed and transaction.status == 'Initiated':
                    transaction.status = 'Under_Verification'

            transaction.save()
            initialize_lawyer_post_transaction_tasks(transaction, request.user)
            from django.contrib import messages
            messages.success(request, 'Advocate contract signature recorded and post-signing conveyancing checklist initialized.')
            return redirect('frontend:sign_contract', transaction_id=transaction.id)

        # Admin-only dual signing capability
        if request.user.role == 'Admin' and request.POST.get('admin_dual_sign'):
            from django.contrib import messages
            buyer_sig = request.POST.get('buyer_signature_data')
            seller_sig = request.POST.get('seller_signature_data')

            if not buyer_sig and not seller_sig:
                messages.error(request, 'Capture at least one signature before executing dual sign.')
                return redirect('frontend:sign_contract', transaction_id=transaction.id)
            
            if buyer_sig:
                transaction.buyer_signature = buyer_sig
            if seller_sig:
                transaction.seller_signature = seller_sig

            if transaction.buyer_signature and transaction.seller_signature and transaction.lawyer_signature:
                transaction.contract_agreed = True
                if transaction.status == 'Initiated':
                    transaction.status = 'Under_Verification'
                
            transaction.save()
            if transaction.contract_agreed and request.user.role == 'Admin' and transaction.status in {'Initiated', 'Under_Verification'}:
                return redirect('frontend:payment_checkout', transaction_id=transaction.id)
            if transaction.contract_agreed and request.user == transaction.buyer and transaction.status in {'Initiated', 'Under_Verification'}:
                return redirect('frontend:payment_checkout', transaction_id=transaction.id)
            return redirect('frontend:sign_contract', transaction_id=transaction.id)

        # Joint signing (leader captures co-buyer signatures)
        if transaction.is_joint_purchase and transaction.joint_group:
            joint_member_id = (request.POST.get('joint_member_id') or '').strip()
            joint_sig = request.POST.get('joint_signature_data')
            if joint_member_id and joint_sig:
                if request.user != transaction.buyer and request.user.role != 'Admin':
                    return redirect('frontend:sign_contract', transaction_id=transaction.id)
                member = get_object_or_404(JointBuyerMember, id=joint_member_id, group=transaction.joint_group)
                member.signature = joint_sig
                member.has_signed = True
                member.save(update_fields=['signature', 'has_signed'])

                # Update contract agreed flag if all required signatures exist
                if transaction.buyer_signature and transaction.seller_signature and transaction.lawyer_signature and transaction.joint_group.all_signed:
                    transaction.contract_agreed = True
                    if transaction.status == 'Initiated':
                        transaction.status = 'Under_Verification'
                    transaction.save(update_fields=['contract_agreed', 'status'])
                if transaction.contract_agreed and request.user == transaction.buyer and transaction.status in {'Initiated', 'Under_Verification'}:
                    return redirect('frontend:payment_checkout', transaction_id=transaction.id)
                return redirect('frontend:sign_contract', transaction_id=transaction.id)

        # Regular signing - Agents cannot sign for others
        signature_data = request.POST.get('signature_data')
        signature_role = request.POST.get('signature_role') # Only sent by Admins
        
        if signature_data:
            # Agents can only sign if they are the actual buyer/seller
            if request.user.role == 'Agent':
                signing_as_buyer = request.user == transaction.buyer
                signing_as_seller = request.user == transaction.seller
            else:
                signing_as_buyer = (request.user == transaction.buyer) or (request.user.role == 'Admin' and signature_role == 'buyer')
                signing_as_seller = (request.user == transaction.seller) or (request.user.role == 'Admin' and signature_role == 'seller')
            
            if signing_as_buyer:
                transaction.buyer_signature = signature_data
            elif signing_as_seller:
                transaction.seller_signature = signature_data
            
            if transaction.buyer_signature and transaction.seller_signature and transaction.lawyer_signature:
                if transaction.is_joint_purchase and transaction.joint_group:
                    if transaction.joint_group.all_signed:
                        transaction.contract_agreed = True
                else:
                    transaction.contract_agreed = True
                if transaction.contract_agreed and transaction.status == 'Initiated':
                    transaction.status = 'Under_Verification'
                
            transaction.save()
            if transaction.contract_agreed and request.user == transaction.buyer and transaction.status in {'Initiated', 'Under_Verification'}:
                return redirect('frontend:payment_checkout', transaction_id=transaction.id)
            return redirect('frontend:sign_contract', transaction_id=transaction.id)
            
    joint_breakdown = []
    if transaction.is_joint_purchase and transaction.joint_group:
        from decimal import Decimal, ROUND_HALF_UP
        total = transaction.agreed_price
        for m in transaction.joint_group.members.all():
            amt = (total * (m.share_percentage / Decimal('100'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            joint_breakdown.append({'member': m, 'amount': amt})

    from django.middleware.csrf import get_token

    # Admin users see no legal restrictions (override/failover mode)
    # Regular users see legal requirements for their reference
    if request.user.role == 'Admin':
        contract_documents = []
    elif transaction.is_joint_purchase:
        contract_documents = JOINT_KENYAN_LAND_DOCUMENTS
    else:
        contract_documents = KENYAN_LAND_DOCUMENTS

    # Fetch admin-editable platform terms for the contract page
    from core.models import PlatformLegalDocument
    platform_terms_doc = PlatformLegalDocument.objects.filter(title='Joint Purchase Laws').first() if transaction.is_joint_purchase else None

    return render_react_shell(
        request,
        'contract',
        'Kenyan Land Transfer Agreement',
        f'Property: {transaction.land_parcel.parcel_number}',
        contract=serialize_contract(
            transaction,
            request.user,
            documents=contract_documents,
            joint_breakdown=joint_breakdown,
            sign_url=reverse('frontend:sign_contract', args=[transaction.id]),
            payment_url=reverse('frontend:payment_checkout', args=[transaction.id]),
            transactions_url=reverse('frontend:transactions'),
            csrf_token=get_token(request),
        ),
        document_content=platform_terms_doc.content if platform_terms_doc else None,
        require_signature=True,
        fullpage_sign_url=fullpage_url,
    )

@login_required
def payment_onboarding(request, transaction_id):
    transaction = get_object_or_404(Transaction.objects.select_related('buyer', 'seller', 'land_parcel', 'joint_group'), id=transaction_id)
    
    # Security: Only the Buyer can pay (or Admin verifying)
    if (request.user != transaction.buyer and request.user.role != 'Admin'):
        return redirect('frontend:transactions')
        
    if transaction.status not in {'Initiated', 'Under_Verification'}:
        return redirect('frontend:transactions')

    if not transaction.contract_agreed:
        return redirect('frontend:sign_contract', transaction_id=transaction.id)

    return render_react_shell(
        request,
        'status',
        'Contract signed',
        'Review the next step and continue to the escrow checkout when you are ready.',
        status=serialize_status_page(
            icon='wallet',
            tone='warning',
            title='Contract signed',
            description=f'Payment can now be initiated for parcel {transaction.land_parcel.parcel_number}. Continue to checkout to choose M-Pesa STK, KCB bank transfer, or Paystack.',
            primary_action={'label': 'Continue to checkout', 'href': reverse('frontend:payment_checkout', args=[transaction.id]), 'tone': 'default'},
            secondary_action={'label': 'Back to transactions', 'href': reverse('frontend:transactions'), 'tone': 'outline'},
        ),
    )

@login_required
def payment_checkout(request, transaction_id):
    transaction = get_object_or_404(
        Transaction.objects.select_related('buyer', 'seller', 'land_parcel', 'joint_group').prefetch_related('joint_group__members'),
        id=transaction_id,
    )
    
    if (request.user != transaction.buyer and request.user.role != 'Admin'):
        return redirect('frontend:transactions')
        
    if transaction.status not in {'Initiated', 'Under_Verification'}:
        return redirect('frontend:transactions')

    if not transaction.contract_agreed:
        return redirect('frontend:sign_contract', transaction_id=transaction.id)

    # Calculate detailed transaction fees
    from core.services.payment import calculate_checkout_fees
    from core.services.service_fee import ServiceFeeService

    include_verification = (
        request.GET.get('include_verification') == 'true'
        or request.GET.get('include_legal') == 'true'
    )
    include_due_diligence = request.GET.get('include_due_diligence') == 'true'
    
    fees = calculate_checkout_fees(transaction.agreed_price, include_verification, include_due_diligence)
    
    transaction.platform_service_fee = fees['platform_service_fee']
    transaction.escrow_fee = fees['escrow_fee']
    transaction.processing_fee = fees['processing_fee']
    transaction.legal_verification_fee = fees['legal_verification_fee']
    transaction.due_diligence_fee = fees['due_diligence_fee']
    transaction.include_legal_verification = include_verification
    transaction.include_due_diligence = include_due_diligence
    transaction.total_payable = fees['total_payable']
    transaction.save(update_fields=[
        'platform_service_fee', 'escrow_fee', 'processing_fee',
        'legal_verification_fee', 'due_diligence_fee',
        'include_legal_verification', 'include_due_diligence', 'total_payable'
    ])
    ServiceFeeService.record_fees_on_transaction(
        transaction,
        include_verification=include_verification,
        include_due_diligence=include_due_diligence,
        fees_data=fees,
    )

    joint_breakdown = None
    contributions = None
    joint_bank_ready = False
    joint_payment_method = None
    if transaction.is_joint_purchase and transaction.joint_group:
        from decimal import Decimal, ROUND_HALF_UP
        total = transaction.total_payable
        joint_breakdown = []
        for m in transaction.joint_group.members.all():
            amt = (total * (m.share_percentage / Decimal('100'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            joint_breakdown.append({'member': m, 'amount': amt})
        contributions = JointPaymentContribution.objects.filter(transaction=transaction).select_related('member')
        joint_group = transaction.joint_group
        joint_payment_method = joint_group.preferred_payment_method
        joint_bank_ready = bool(
            joint_group.bank_name and joint_group.bank_account_name and joint_group.bank_account_number
        )

    from django.conf import settings
    escrow_bank_name = 'KCB Bank Kenya'
    escrow_bank_account_name = 'Digiland Escrow'
    escrow_bank_account_number = getattr(settings, 'KCB_PLATFORM_ACCOUNT', 'DIGILAND-ESCROW-001')
    escrow_bank_branch = 'Nairobi'
    paystack_enabled = bool(getattr(settings, 'PAYSTACK_SECRET_KEY', ''))

    from django.middleware.csrf import get_token

    return render_react_shell(
        request,
        'checkout-fullpage',
        'Escrow checkout',
        'Complete payment using M-Pesa, KCB bank transfer, Paystack, or the shared joint bank account.',
        checkout=serialize_checkout(
            transaction,
            request.user,
            joint_breakdown=joint_breakdown,
            contributions=contributions,
            joint_bank_ready=joint_bank_ready,
            joint_payment_method=joint_payment_method,
            process_url=reverse('frontend:process_payment', args=[transaction.id]),
            transactions_url=reverse('frontend:transactions'),
            sign_url=reverse('frontend:sign_contract', args=[transaction.id]),
            failed_url=reverse('frontend:transaction_failed', args=[transaction.id]),
            csrf_token=get_token(request),
            phone_number=getattr(request.user, 'phone_number', '') or '',
            paystack_enabled=paystack_enabled,
            escrow_bank_name=escrow_bank_name,
            escrow_bank_account_name=escrow_bank_account_name,
            escrow_bank_account_number=escrow_bank_account_number,
            escrow_bank_branch=escrow_bank_branch,
        ),
        fullpage_mode=True,
        back_url=reverse('frontend:transactions'),
    )

@login_required
def process_payment(request, transaction_id):
    return _process_payment(request, transaction_id)


def _process_payment(request, transaction_id):
    return _process_payment_v2(request, transaction_id)

    from django.http import JsonResponse
    from core.services.payment import mpesa_stk_push
    import logging
    logger = logging.getLogger(__name__)
    
    transaction = get_object_or_404(Transaction, id=transaction_id)
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not transaction.contract_agreed:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'The contract must be signed before payment can begin.'})
        return redirect('frontend:sign_contract', transaction_id=transaction.id)
    
    if request.method == 'POST' and (request.user == transaction.buyer or request.user.role == 'Admin'):
        if transaction.status == 'Under_Verification' and transaction.contract_agreed:
            payment_method = (request.POST.get('payment_method') or '').strip()
            if not payment_method:
                if transaction.is_joint_purchase and transaction.joint_group and transaction.joint_group.preferred_payment_method == 'Joint_Bank_Account':
                    payment_method = 'joint_bank_account'
                else:
                    payment_method = 'm_pesa'

            if payment_method == 'joint_bank_account':
                if not transaction.is_joint_purchase or not transaction.joint_group:
                    if is_ajax:
                        return JsonResponse({'status': 'error', 'message': 'Joint bank checkout is only available for joint purchases.'})
                    return redirect('frontend:payment_checkout', transaction_id=transaction.id)

                group = transaction.joint_group
                if not (group.bank_name and group.bank_account_name and group.bank_account_number):
                    if is_ajax:
                        return JsonResponse({'status': 'error', 'message': 'The joint bank account has not been configured yet.'})
                    from django.contrib import messages
                    messages.error(request, 'The joint bank account has not been configured yet.')
                    return redirect('frontend:payment_checkout', transaction_id=transaction.id)

                bank_reference = (request.POST.get('bank_reference') or '').strip()
                depositor_name = (request.POST.get('depositor_name') or '').strip()
                if not depositor_name:
                    depositor_name = getattr(request.user, 'get_full_name', lambda: '')() or request.user.email

                if not bank_reference:
                    if is_ajax:
                        return JsonResponse({'status': 'error', 'message': 'Please enter the bank transfer reference number.'})
                    return redirect('frontend:payment_checkout', transaction_id=transaction.id)

                amount_decimal = transaction.agreed_price
                contribution = JointPaymentContribution.objects.create(
                    transaction=transaction,
                    member=None,
                    amount=amount_decimal,
                    payment_channel='Bank_Transfer',
                    phone_number=None,
                    status='Bank_Submitted',
                    bank_reference=bank_reference,
                    depositor_name=depositor_name,
                    bank_name=group.bank_name,
                    bank_account_number=group.bank_account_number,
                    bank_account_name=group.bank_account_name,
                    bank_branch=group.bank_branch,
                )

                import uuid
                transaction.escrow_reference = f"BANK-{bank_reference[:12].upper()}" if bank_reference else f"BANK-{str(uuid.uuid4())[:8].upper()}"
                transaction.save(update_fields=['escrow_reference'])

                if is_ajax:
                    return JsonResponse({
                        'status': 'bank_pending',
                        'message': 'Joint bank transfer recorded. Complete the transfer using the displayed bank details and keep the reference number.',
                        'bank_reference': bank_reference,
                        'bank_name': contribution.bank_name,
                        'bank_account_name': contribution.bank_account_name,
                        'bank_account_number': contribution.bank_account_number,
                        'bank_branch': contribution.bank_branch,
                        'escrow_reference': transaction.escrow_reference,
                    })

                from django.contrib import messages
                messages.success(request, 'Joint bank transfer recorded. Use the listed account details to complete the payment.')
                return redirect('frontend:payment_checkout', transaction_id=transaction.id)

            phone_number = request.POST.get('phone_number', '').strip()
            member_id = (request.POST.get('member_id') or '').strip()
            amount_override = (request.POST.get('amount') or '').strip()
            
            if not phone_number:
                # Fallback to user's registered number
                phone_number = request.user.phone_number
            
            if not phone_number:
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': 'No phone number provided.'})
                return redirect('frontend:payment_checkout', transaction_id=transaction.id)
            
            # Initiate real M-PESA STK Push via Daraja API
            try:
                # Default amount is full transaction, but allow split payments for joint purchases
                from decimal import Decimal, ROUND_HALF_UP
                amount_decimal = transaction.agreed_price
                member = None
                if transaction.is_joint_purchase and transaction.joint_group and member_id:
                    member = JointBuyerMember.objects.get(id=member_id, group=transaction.joint_group)
                    amount_decimal = (transaction.agreed_price * (member.share_percentage / Decimal('100'))).quantize(
                        Decimal('0.01'), rounding=ROUND_HALF_UP
                    )
                if amount_override:
                    try:
                        amount_decimal = Decimal(amount_override)
                    except Exception:
                        pass

                amount = int(amount_decimal)
                # Sandbox has a max limit — cap at 150000 for sandbox testing
                from django.conf import settings
                if getattr(settings, 'DARAJA_ENVIRONMENT', 'sandbox') == 'sandbox':
                    # In sandbox, use a small test amount (1 KES) to avoid errors
                    amount = min(amount, 1)
                
                result = mpesa_stk_push(
                    phone=phone_number,
                    amount=amount,
                    transaction_id=str(transaction.id)
                )
                
                logger.info(f"STK Push result for transaction {transaction.id}: {result}")
                
                if result.get('status') == 'success':
                    # Store the checkout_request_id for status polling
                    checkout_request_id = result.get('checkout_request_id', '')

                    # Track contribution if joint purchase
                    if transaction.is_joint_purchase and transaction.joint_group:
                        JointPaymentContribution.objects.create(
                            transaction=transaction,
                            member=member,
                            amount=amount_decimal,
                            phone_number=phone_number,
                            status='STK_Pushed',
                            checkout_request_id=checkout_request_id or None,
                        )
                    
                    # Store checkout_request_id in the transaction metadata
                    # We use escrow_reference temporarily to track this
                    import uuid
                    transaction.escrow_reference = f"MPESA-{checkout_request_id}" if checkout_request_id else f"ESC-{str(uuid.uuid4())[:8].upper()}"
                    transaction.save(update_fields=['escrow_reference'])
                    
                    if is_ajax:
                        return JsonResponse({
                            'status': 'stk_pushed',
                            'message': 'STK Push sent to your phone. Please authorize the payment.',
                            'checkout_request_id': checkout_request_id,
                        })
                    return redirect('frontend:transactions')
                
                else:
                    error_msg = result.get('message', 'STK Push initiation failed.')
                    logger.error(f"STK Push failed for transaction {transaction.id}: {error_msg}")
                    
                    if is_ajax:
                        return JsonResponse({'status': 'error', 'message': error_msg})
                    from django.utils.http import urlencode
                    return redirect(f"{reverse('frontend:transaction_failed', args=[transaction.id])}?reason={urlencode({'': error_msg})[1:]}")
                    
            except Exception as e:
                logger.error(f"Payment processing error for transaction {transaction.id}: {str(e)}")
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': f'Payment processing error: {str(e)}'})
                from django.utils.http import urlencode
                return redirect(f"{reverse('frontend:transaction_failed', args=[transaction.id])}?reason={urlencode({'': str(e)})[1:]}")
    
    if is_ajax:
        return JsonResponse({'status': 'error', 'message': 'Invalid request.'})
    return redirect('frontend:payment_checkout', transaction_id=transaction.id)


def _process_payment_v2(request, transaction_id):
    from django.http import JsonResponse
    from django.conf import settings
    from django.contrib import messages as django_messages
    from django.utils.http import urlencode
    from core.services.payment import mpesa_stk_push, paystack_initialize
    import logging
    logger = logging.getLogger(__name__)

    transaction = get_object_or_404(
        Transaction.objects.select_related('buyer', 'seller', 'land_parcel', 'joint_group').prefetch_related('joint_group__members'),
        id=transaction_id,
    )
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'

    if not transaction.contract_agreed:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'The contract must be signed before payment can begin.'})
        return redirect('frontend:sign_contract', transaction_id=transaction.id)

    if request.method != 'POST' or (request.user != transaction.buyer and request.user.role != 'Admin'):
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Invalid request.'})
        return redirect('frontend:payment_checkout', transaction_id=transaction.id)

    if transaction.status not in {'Initiated', 'Under_Verification'}:
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': 'Payment can only start once the contract is signed and the transaction is ready for checkout.'})
        return redirect('frontend:transactions')

    payment_method = (request.POST.get('payment_method') or '').strip().lower()
    if not payment_method:
        if transaction.is_joint_purchase and transaction.joint_group and transaction.joint_group.preferred_payment_method == 'Joint_Bank_Account':
            payment_method = 'joint_bank_account'
        else:
            payment_method = 'm_pesa'

    from decimal import Decimal, ROUND_HALF_UP

    if payment_method in {'joint_bank_account', 'kcb_bank', 'bank_transfer'}:
        bank_reference = (request.POST.get('bank_reference') or '').strip()
        depositor_name = (request.POST.get('depositor_name') or '').strip() or getattr(request.user, 'get_full_name', lambda: '')() or request.user.email

        if not bank_reference:
            message = 'Please enter the bank transfer reference number.'
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': message})
            django_messages.error(request, message)
            return redirect('frontend:payment_checkout', transaction_id=transaction.id)

        if payment_method == 'joint_bank_account':
            if not transaction.is_joint_purchase or not transaction.joint_group:
                message = 'Joint bank checkout is only available for joint purchases.'
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': message})
                django_messages.error(request, message)
                return redirect('frontend:payment_checkout', transaction_id=transaction.id)

            group = transaction.joint_group
            if not (group.bank_name and group.bank_account_name and group.bank_account_number):
                message = 'The joint bank account has not been configured yet.'
                if is_ajax:
                    return JsonResponse({'status': 'error', 'message': message})
                django_messages.error(request, message)
                return redirect('frontend:payment_checkout', transaction_id=transaction.id)

            contribution = JointPaymentContribution.objects.create(
                transaction=transaction,
                member=None,
                amount=transaction.agreed_price,
                payment_channel='Bank_Transfer',
                phone_number=None,
                status='Bank_Submitted',
                bank_reference=bank_reference,
                depositor_name=depositor_name,
                bank_name=group.bank_name,
                bank_account_number=group.bank_account_number,
                bank_account_name=group.bank_account_name,
                bank_branch=group.bank_branch,
            )
            transaction.escrow_reference = f"BANK-{bank_reference[:12].upper()}"
            transaction.save(update_fields=['escrow_reference'])

            if is_ajax:
                return JsonResponse({
                    'status': 'bank_pending',
                    'message': 'Joint bank transfer recorded. Complete the transfer using the displayed bank details and keep the reference number.',
                    'bank_reference': bank_reference,
                    'bank_name': contribution.bank_name,
                    'bank_account_name': contribution.bank_account_name,
                    'bank_account_number': contribution.bank_account_number,
                    'bank_branch': contribution.bank_branch,
                    'escrow_reference': transaction.escrow_reference,
                })

            django_messages.success(request, 'Joint bank transfer recorded. Use the listed account details to complete the payment.')
            return redirect('frontend:payment_checkout', transaction_id=transaction.id)

        escrow_bank_name = 'KCB Bank Kenya'
        escrow_bank_account_name = 'Digiland Escrow'
        escrow_bank_account_number = getattr(settings, 'KCB_PLATFORM_ACCOUNT', 'DIGILAND-ESCROW-001')
        escrow_bank_branch = 'Nairobi'
        transaction.escrow_reference = f"KCB-{bank_reference[:12].upper()}"
        transaction.save(update_fields=['escrow_reference'])
        AuditLog.objects.create(
            user=request.user,
            action=f'Bank transfer checkout recorded for transaction {transaction.id}',
            metadata={
                'transaction_id': str(transaction.id),
                'bank_reference': bank_reference,
                'depositor_name': depositor_name,
                'bank_name': escrow_bank_name,
                'bank_account_name': escrow_bank_account_name,
                'bank_account_number': escrow_bank_account_number,
                'bank_branch': escrow_bank_branch,
            },
        )

        if is_ajax:
            return JsonResponse({
                'status': 'bank_pending',
                'message': 'KCB bank transfer recorded. Complete the transfer using the escrow bank details on the page.',
                'bank_reference': bank_reference,
                'bank_name': escrow_bank_name,
                'bank_account_name': escrow_bank_account_name,
                'bank_account_number': escrow_bank_account_number,
                'bank_branch': escrow_bank_branch,
                'escrow_reference': transaction.escrow_reference,
            })

        django_messages.success(request, 'KCB bank transfer recorded. Use the escrow bank details on the checkout page.')
        return redirect('frontend:payment_checkout', transaction_id=transaction.id)

    if payment_method == 'paystack':
        if not getattr(settings, 'PAYSTACK_SECRET_KEY', ''):
            message = 'Paystack is not configured on this environment.'
            if is_ajax:
                return JsonResponse({'status': 'error', 'message': message})
            django_messages.error(request, message)
            return redirect('frontend:payment_checkout', transaction_id=transaction.id)

        checkout_email = (request.POST.get('email') or '').strip() or getattr(request.user, 'email', '') or transaction.buyer.email
        callback_url = request.build_absolute_uri(reverse('core:payment-callback'))
        response = paystack_initialize(checkout_email, transaction.agreed_price, str(transaction.id), callback_url=callback_url)
        if response.get('status') and response.get('data', {}).get('authorization_url'):
            authorization_url = response['data']['authorization_url']
            reference = response.get('data', {}).get('reference') or str(transaction.id)
            transaction.escrow_reference = f"PAYSTACK-{reference}"
            transaction.save(update_fields=['escrow_reference'])

            AuditLog.objects.create(
                user=request.user,
                action=f'Paystack checkout initialized for transaction {transaction.id}',
                metadata={
                    'transaction_id': str(transaction.id),
                    'reference': reference,
                    'authorization_url': authorization_url,
                    'amount': str(transaction.agreed_price),
                    'email': checkout_email,
                },
            )

            if is_ajax:
                return JsonResponse({
                    'status': 'paystack_redirect',
                    'authorization_url': authorization_url,
                    'reference': reference,
                    'message': 'Redirecting to Paystack checkout.',
                })

            return redirect(authorization_url)

        error_msg = response.get('message', 'Failed to initialize Paystack checkout.')
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': error_msg})
        django_messages.error(request, error_msg)
        return redirect('frontend:payment_checkout', transaction_id=transaction.id)

    phone_number = request.POST.get('phone_number', '').strip() or request.user.phone_number or ''
    member_id = (request.POST.get('member_id') or '').strip()
    amount_override = (request.POST.get('amount') or '').strip()

    if not phone_number:
        message = 'No phone number provided.'
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': message})
        django_messages.error(request, message)
        return redirect('frontend:payment_checkout', transaction_id=transaction.id)

    try:
        amount_decimal = transaction.agreed_price
        member = None
        if transaction.is_joint_purchase and transaction.joint_group and member_id:
            member = JointBuyerMember.objects.get(id=member_id, group=transaction.joint_group)
            amount_decimal = (transaction.agreed_price * (member.share_percentage / Decimal('100'))).quantize(
                Decimal('0.01'), rounding=ROUND_HALF_UP
            )

        if amount_override:
            try:
                amount_decimal = Decimal(amount_override)
            except Exception:
                pass

        amount = int(amount_decimal)
        if getattr(settings, 'DARAJA_ENVIRONMENT', 'sandbox') == 'sandbox':
            amount = min(amount, 1)

        result = mpesa_stk_push(phone=phone_number, amount=amount, transaction_id=str(transaction.id))
        logger.info(f"STK Push result for transaction {transaction.id}: {result}")

        if result.get('status') == 'success':
            checkout_request_id = result.get('checkout_request_id', '')

            if transaction.is_joint_purchase and transaction.joint_group:
                JointPaymentContribution.objects.create(
                    transaction=transaction,
                    member=member,
                    amount=amount_decimal,
                    phone_number=phone_number,
                    status='STK_Pushed',
                    checkout_request_id=checkout_request_id or None,
                )

            transaction.escrow_reference = f"MPESA-{checkout_request_id}" if checkout_request_id else f"ESC-{str(transaction.id)[:8].upper()}"
            transaction.save(update_fields=['escrow_reference'])

            if is_ajax:
                return JsonResponse({
                    'status': 'stk_pushed',
                    'message': 'STK Push sent to your phone. Please authorize the payment.',
                    'checkout_request_id': checkout_request_id,
                })
            return redirect('frontend:transactions')

        error_msg = result.get('message', 'STK Push initiation failed.')
        logger.error(f"STK Push failed for transaction {transaction.id}: {error_msg}")
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': error_msg})
        return redirect(f"{reverse('frontend:transaction_failed', args=[transaction.id])}?reason={urlencode({'': error_msg})[1:]}")

    except Exception as e:
        logger.error(f"Payment processing error for transaction {transaction.id}: {str(e)}")
        if is_ajax:
            return JsonResponse({'status': 'error', 'message': f'Payment processing error: {str(e)}'})
        return redirect(f"{reverse('frontend:transaction_failed', args=[transaction.id])}?reason={urlencode({'': str(e)})[1:]}")


@login_required
def joint_groups(request):
    if not is_joint_buyer(request.user):
        if request.user.role == 'Buyer':
            from django.contrib import messages
            messages.info(
                request,
                'You are on an Individual buyer account. You can still join an existing group when a joint group leader adds you as a member. Contact admin to upgrade your own account to Joint.',
            )
            return redirect('frontend:parcel_list')
        return redirect('frontend:home')
    groups = JointBuyerGroup.objects.filter(leader=request.user).prefetch_related('members')
    return render_react_shell(
        request,
        'joint-groups',
        'My joint groups',
        'Manage shared buyer accounts, ownership splits, and joint bank setup.',
        groups=[serialize_joint_group(group, request.user) for group in groups],
        actions=[
            {'label': 'Create group', 'href': reverse('frontend:create_joint_group'), 'tone': 'outline'},
            {'label': 'Joint laws', 'href': reverse('frontend:joint_laws'), 'tone': 'secondary'},
        ],
    )


@login_required
def create_joint_group(request):
    if not is_joint_buyer(request.user):
        if request.user.role == 'Buyer':
            from django.contrib import messages
            messages.info(
                request,
                'Only Joint buyer accounts can create groups. Your account is Individual; contact admin to upgrade to Joint.',
            )
            return redirect('frontend:parcel_list')
        return redirect('frontend:home')

    if request.method == 'POST':
        group_form = JointBuyerGroupForm(request.POST)
        member_formset = JointBuyerMemberFormSet(request.POST, prefix='members')
        if group_form.is_valid() and member_formset.is_valid():
            from decimal import Decimal
            leader_share = group_form.cleaned_data['leader_share_percentage']
            group = group_form.save(commit=False)
            group.leader = request.user
            group.save()

            # Create leader member
            leader_full_name = (f"{request.user.first_name} {request.user.last_name}").strip() or request.user.email
            JointBuyerMember.objects.create(
                group=group,
                full_name=leader_full_name,
                id_number=request.user.id_number,
                kra_pin=request.user.kra_pin,
                phone_number=request.user.phone_number,
                email=request.user.email,
                share_percentage=leader_share,
                is_leader=True,
            )

            # Create other members from formset
            created_members = 0
            total_other = Decimal('0')
            for form in member_formset:
                if member_formset.can_delete and member_formset._should_delete_form(form):
                    continue
                if not form.cleaned_data:
                    continue
                member = JointBuyerMember(
                    group=group,
                    full_name=form.cleaned_data['full_name'],
                    id_number=form.cleaned_data['id_number'],
                    kra_pin=form.cleaned_data['kra_pin'],
                    phone_number=form.cleaned_data['phone_number'],
                    email=form.cleaned_data.get('email') or None,
                    share_percentage=form.cleaned_data['share_percentage'],
                    is_leader=False,
                )
                member.save()
                created_members += 1
                total_other += member.share_percentage

            # Validate membership rules
            from django.contrib import messages
            if group.members.count() < 2:
                group.delete()
                messages.error(request, 'A joint group must have at least 2 members (leader + at least 1 co-buyer).')
                return redirect('frontend:create_joint_group')

            total_share = leader_share + total_other
            if total_share != Decimal('100'):
                group.delete()
                messages.error(request, f'Shares must total 100%. Current total is {total_share}%.')
                return redirect('frontend:create_joint_group')

            if group.members.count() > 10:
                group.delete()
                messages.error(request, 'Maximum group size is 10 members.')
                return redirect('frontend:create_joint_group')

            if getattr(request.user, 'buyer_account_type', None) != 'Joint':
                request.user.buyer_account_type = 'Joint'
                request.user.save(update_fields=['buyer_account_type'])

            messages.success(request, 'Joint buyer group created successfully.')
            return redirect('frontend:joint_group_detail', group_id=group.id)
    else:
        group_form = JointBuyerGroupForm()
        member_formset = JointBuyerMemberFormSet(prefix='members')

    return render_react_shell(
        request,
        'form',
        'Create joint group',
        'Set up shared ownership, payment details, and co-buyer records for a group purchase.',
        form=serialize_form(
            group_form,
            action=reverse('frontend:create_joint_group'),
            submit_label='Create joint group',
            cancel_label='Back to groups',
            cancel_href=reverse('frontend:joint_groups'),
            intro='By proceeding to create a joint group, you acknowledge and agree to the <a href="/joint/laws/" class="text-emerald-700 underline">Joint Purchase Laws and Regulations</a>.',
            sections=[
                {'title': 'Group details', 'fields': ['name', 'group_type']},
                {'title': 'Ownership and payment', 'fields': ['ownership_type', 'preferred_payment_method', 'leader_share_percentage']},
                {'title': 'Bank details', 'fields': ['bank_name', 'bank_account_name', 'bank_account_number', 'bank_branch']},
            ],
        ),
        member_formset=serialize_formset(
            member_formset,
            action=reverse('frontend:create_joint_group'),
            submit_label='Create joint group',
            intro='Add at least one co-buyer. The leader is created automatically from your account details.',
        ),
    )


@login_required
def joint_group_detail(request, group_id):
    if not is_joint_buyer(request.user):
        if request.user.role == 'Buyer':
            from django.contrib import messages
            messages.info(request, 'Select the joint buyer account setup first to view group details.')
            return redirect('frontend:buyer_account_choice')
        return redirect('frontend:home')
    group = get_object_or_404(JointBuyerGroup.objects.prefetch_related('members'), id=group_id)
    if request.user.role != 'Admin' and group.leader != request.user:
        return redirect('frontend:joint_groups')

    serialized_group = serialize_joint_group(group, request.user)
    actions = [
        {'label': 'Joint laws', 'href': reverse('frontend:joint_laws'), 'tone': 'secondary'},
    ]
    if group.leader == request.user:
        actions.insert(0, {'label': 'Transfer leadership', 'href': reverse('frontend:transfer_joint_leadership', args=[group.id]), 'tone': 'outline'})
        actions.insert(0, {'label': 'Add member', 'href': reverse('frontend:add_joint_member', args=[group.id]), 'tone': 'secondary'})
        actions.insert(0, {'label': 'Edit group', 'href': reverse('frontend:edit_joint_group', args=[group.id]), 'tone': 'outline'})
    elif request.user.role == 'Admin':
        actions.insert(0, {'label': 'Transfer leadership', 'href': reverse('frontend:transfer_joint_leadership', args=[group.id]), 'tone': 'outline'})
        actions.insert(0, {'label': 'Add member', 'href': reverse('frontend:add_joint_member', args=[group.id]), 'tone': 'secondary'})
    return render_react_shell(
        request,
        'joint-group-detail',
        group.name,
        'Review members, ownership shares, and payment setup for the joint account.',
        group=serialized_group,
        actions=actions,
    )


@login_required
def delete_joint_member(request, member_id):
    from django.contrib import messages as django_messages
    from django.utils import timezone

    if not is_joint_buyer(request.user):
        return redirect('frontend:home')

    member = get_object_or_404(JointBuyerMember, id=member_id)
    group = member.group
    if request.user.role != 'Admin' and group.leader != request.user:
        return redirect('frontend:home')

    if member.is_leader:
        django_messages.error(request, 'Transfer leadership before removing the current leader.')
        return redirect('frontend:joint_group_detail', group_id=group.id)

    if group.transactions.filter(status__in=['Under_Verification', 'Deposit_Paid', 'Completed']).exists():
        django_messages.error(request, 'You cannot request a removal on a group linked to an active or completed transaction.')
        return redirect('frontend:joint_group_detail', group_id=group.id)

    if request.method == 'POST':
        form = JointMemberRemovalRequestForm(request.POST)
        if form.is_valid():
            removal_request, created = JointMemberRemovalRequest.objects.get_or_create(
                group=group,
                member=member,
                status='Pending_Admin_Review',
                defaults={
                    'requested_by': request.user,
                    'consent_confirmed': form.cleaned_data['consent_confirmed'],
                    'compensation_confirmed': form.cleaned_data['compensation_confirmed'],
                    'compensation_amount': form.cleaned_data.get('compensation_amount'),
                    'notes': form.cleaned_data.get('notes') or '',
                },
            )
            if not created:
                removal_request.requested_by = request.user
                removal_request.consent_confirmed = form.cleaned_data['consent_confirmed']
                removal_request.compensation_confirmed = form.cleaned_data['compensation_confirmed']
                removal_request.compensation_amount = form.cleaned_data.get('compensation_amount')
                removal_request.notes = form.cleaned_data.get('notes') or ''
                removal_request.status = 'Pending_Admin_Review'
                removal_request.admin_reviewed_by = None
                removal_request.admin_reviewed_at = None
                removal_request.admin_notes = ''
                removal_request.processed_at = None
                removal_request.save()

            AuditLog.objects.create(
                user=request.user,
                action=f'Joint member removal requested for {member.full_name}',
                metadata={
                    'group_id': str(group.id),
                    'member_id': str(member.id),
                    'consent_confirmed': form.cleaned_data['consent_confirmed'],
                    'compensation_confirmed': form.cleaned_data['compensation_confirmed'],
                    'compensation_amount': str(form.cleaned_data.get('compensation_amount') or ''),
                    'requested_at': timezone.now().isoformat(),
                },
            )
            django_messages.success(request, 'Removal request submitted. An admin must review the consent and compensation details.')
            return redirect('frontend:joint_group_detail', group_id=group.id)
    else:
        form = JointMemberRemovalRequestForm()

    return render_react_shell(
        request,
        'form',
        f'Request removal - {member.full_name}',
        'Submit this request to admin for consent and compensation verification.',
        form=serialize_form(
            form,
            action=reverse('frontend:delete_joint_member', args=[member.id]),
            submit_label='Submit removal request',
            cancel_label='Back to group',
            cancel_href=reverse('frontend:joint_group_detail', args=[group.id]),
            intro='Member removal is not immediate. An admin must confirm that the exit is consensual and that compensation has been settled.',
            sections=[
                {'title': 'Confirmation', 'fields': ['consent_confirmed', 'compensation_confirmed', 'compensation_amount']},
                {'title': 'Notes', 'fields': ['notes']},
            ],
        ),
    )


@login_required
def add_joint_member(request, group_id):
    from decimal import Decimal
    from django.contrib import messages as django_messages
    from django.utils import timezone

    if not is_joint_buyer(request.user):
        return redirect('frontend:home')

    group = get_object_or_404(JointBuyerGroup.objects.prefetch_related('members'), id=group_id)
    if request.user.role != 'Admin' and group.leader != request.user:
        return redirect('frontend:joint_groups')

    if group.transactions.filter(status__in=['Under_Verification', 'Deposit_Paid', 'Completed']).exists():
        django_messages.error(request, 'You cannot add members to a group linked to an active or completed transaction.')
        return redirect('frontend:joint_group_detail', group_id=group.id)

    if request.method == 'POST':
        form = JointBuyerMemberForm(request.POST)
        if form.is_valid():
            member = form.save(commit=False)
            member.group = group
            member.is_leader = False
            member.save()

            total_share = group.total_share
            if group.members.count() > 10:
                member.delete()
                django_messages.error(request, 'Maximum group size is 10 members.')
                return redirect('frontend:add_joint_member', group_id=group.id)
            if total_share > Decimal('100'):
                member.delete()
                django_messages.error(request, f'Shares cannot exceed 100%. Current total would be {total_share}%.')
                return redirect('frontend:add_joint_member', group_id=group.id)

            AuditLog.objects.create(
                user=request.user,
                action=f'Joint member added to {group.name}',
                metadata={
                    'group_id': str(group.id),
                    'member_id': str(member.id),
                    'member_name': member.full_name,
                    'share_percentage': str(member.share_percentage),
                    'created_at': timezone.now().isoformat(),
                },
            )

            if total_share != Decimal('100'):
                django_messages.warning(request, f'Member added. Current group shares total {total_share}%, so please rebalance to 100%.')
            else:
                django_messages.success(request, 'Member added successfully.')
            return redirect('frontend:joint_group_detail', group_id=group.id)
    else:
        form = JointBuyerMemberForm()

    return render_react_shell(
        request,
        'form',
        f'Add member - {group.name}',
        'Add a new co-buyer record to the joint group.',
        form=serialize_form(
            form,
            action=reverse('frontend:add_joint_member', args=[group.id]),
            submit_label='Add member',
            cancel_label='Back to group',
            cancel_href=reverse('frontend:joint_group_detail', args=[group.id]),
            intro='Enter the new member details. If their share changes the total, rebalance the group after saving.',
            sections=[
                {'title': 'Identity', 'fields': ['full_name', 'id_number', 'kra_pin']},
                {'title': 'Contact and share', 'fields': ['phone_number', 'email', 'share_percentage']},
            ],
        ),
    )


@login_required
def transfer_joint_leadership(request, group_id):
    from django.contrib import messages as django_messages
    from django.utils import timezone
    from core.models import User as CoreUser

    if not is_joint_buyer(request.user):
        return redirect('frontend:home')

    group = get_object_or_404(JointBuyerGroup.objects.prefetch_related('members'), id=group_id)
    if request.user.role != 'Admin' and group.leader != request.user:
        return redirect('frontend:joint_groups')

    if group.transactions.filter(status__in=['Under_Verification', 'Deposit_Paid', 'Completed']).exists():
        django_messages.error(request, 'You cannot transfer leadership while the group is linked to an active or completed transaction.')
        return redirect('frontend:joint_group_detail', group_id=group.id)

    eligible_members = list(group.members.exclude(is_leader=True).order_by('added_at'))
    if not eligible_members:
        django_messages.error(request, 'Add at least one eligible co-buyer before transferring leadership.')
        return redirect('frontend:joint_group_detail', group_id=group.id)

    if request.method == 'POST':
        form = JointLeaderTransferForm(request.POST)
        form.fields['new_leader_member_id'].choices = [
            (str(member.id), f"{member.full_name} ({member.email or 'No email'})")
            for member in eligible_members
        ]
        if form.is_valid():
            selected_member_id = form.cleaned_data['new_leader_member_id']
            selected_member = get_object_or_404(JointBuyerMember, id=selected_member_id, group=group)
            if not selected_member.email:
                django_messages.error(request, 'The selected member does not have an email address for account lookup.')
                return redirect('frontend:transfer_joint_leadership', group_id=group.id)

            new_leader_user = CoreUser.objects.filter(email__iexact=selected_member.email, role='Buyer', is_active=True).first()
            if not new_leader_user:
                django_messages.error(
                    request,
                    'The selected member must already have an active Buyer account before leadership can be transferred.',
                )
                return redirect('frontend:transfer_joint_leadership', group_id=group.id)

            group.leader = new_leader_user
            group.save(update_fields=['leader'])
            group.members.update(is_leader=False)
            selected_member.is_leader = True
            selected_member.save(update_fields=['is_leader'])

            AuditLog.objects.create(
                user=request.user,
                action=f'Joint leadership transferred for {group.name}',
                metadata={
                    'group_id': str(group.id),
                    'new_leader_user_id': str(new_leader_user.id),
                    'new_leader_member_id': str(selected_member.id),
                    'new_leader_email': new_leader_user.email,
                    'requested_at': timezone.now().isoformat(),
                    'reason': form.cleaned_data.get('transfer_reason') or '',
                },
            )

            django_messages.success(request, f'Leadership transferred to {selected_member.full_name}.')
            return redirect('frontend:joint_group_detail', group_id=group.id)
    else:
        form = JointLeaderTransferForm()
        form.fields['new_leader_member_id'].choices = [
            (str(member.id), f"{member.full_name} ({member.email or 'No email'})")
            for member in eligible_members
        ]

    return render_react_shell(
        request,
        'form',
        f'Transfer leadership - {group.name}',
        'Choose a new leader from the eligible members of this group.',
        form=serialize_form(
            form,
            action=reverse('frontend:transfer_joint_leadership', args=[group.id]),
            submit_label='Transfer leadership',
            cancel_label='Back to group',
            cancel_href=reverse('frontend:joint_group_detail', args=[group.id]),
            intro='The selected member must already have a Buyer account. The group leadership title will move to that account after submission.',
            sections=[
                {'title': 'Leadership transfer', 'fields': ['new_leader_member_id']},
                {'title': 'Reason', 'fields': ['transfer_reason']},
            ],
        ),
    )


@login_required
@user_passes_test(lambda u: u.role == 'Admin', login_url='/agent/onboarding/')
def approve_joint_member_removal(request, request_id):
    from django.utils import timezone
    from django.contrib import messages as django_messages

    removal_request = get_object_or_404(
        JointMemberRemovalRequest.objects.select_related('group', 'member', 'requested_by'),
        id=request_id,
    )

    if request.method != 'POST':
        return redirect('frontend:agent_approvals')

    if removal_request.status != 'Pending_Admin_Review':
        django_messages.info(request, 'This removal request has already been processed.')
        return redirect('frontend:agent_approvals')

    if not removal_request.consent_confirmed or not removal_request.compensation_confirmed:
        django_messages.error(
            request,
            'This removal request cannot be approved until consent and compensation are both confirmed.',
        )
        return redirect('frontend:agent_approvals')

    member = removal_request.member
    group = removal_request.group
    if member.is_leader:
        django_messages.error(request, 'You cannot remove the current leader. Transfer leadership first.')
        return redirect('frontend:agent_approvals')

    if group.transactions.filter(status__in=['Under_Verification', 'Deposit_Paid', 'Completed']).exists():
        django_messages.error(request, 'This group is linked to an active or completed transaction and cannot be modified.')
        return redirect('frontend:agent_approvals')

    removal_request.status = 'Approved'
    removal_request.admin_reviewed_by = request.user
    removal_request.admin_reviewed_at = timezone.now()
    removal_request.admin_notes = (request.POST.get('admin_notes') or '').strip()
    removal_request.processed_at = timezone.now()
    removal_request.save(update_fields=['status', 'admin_reviewed_by', 'admin_reviewed_at', 'admin_notes', 'processed_at'])
    member.delete()

    AuditLog.objects.create(
        user=request.user,
        action=f'Joint member removal approved for {group.name}',
        metadata={
            'group_id': str(group.id),
            'member_name': member.full_name,
            'removal_request_id': str(removal_request.id),
            'admin_notes': removal_request.admin_notes or '',
        },
    )

    django_messages.success(request, f'{member.full_name} was removed from {group.name}.')
    return redirect('frontend:agent_approvals')


@login_required
@user_passes_test(lambda u: u.role == 'Admin', login_url='/agent/onboarding/')
def reject_joint_member_removal(request, request_id):
    from django.utils import timezone
    from django.contrib import messages as django_messages

    removal_request = get_object_or_404(
        JointMemberRemovalRequest.objects.select_related('group', 'member', 'requested_by'),
        id=request_id,
    )

    if request.method != 'POST':
        return redirect('frontend:agent_approvals')

    if removal_request.status != 'Pending_Admin_Review':
        django_messages.info(request, 'This removal request has already been processed.')
        return redirect('frontend:agent_approvals')

    removal_request.status = 'Rejected'
    removal_request.admin_reviewed_by = request.user
    removal_request.admin_reviewed_at = timezone.now()
    removal_request.admin_notes = (request.POST.get('admin_notes') or '').strip()
    removal_request.processed_at = timezone.now()
    removal_request.save(update_fields=['status', 'admin_reviewed_by', 'admin_reviewed_at', 'admin_notes', 'processed_at'])

    AuditLog.objects.create(
        user=request.user,
        action=f'Joint member removal rejected for {removal_request.group.name}',
        metadata={
            'group_id': str(removal_request.group_id),
            'member_name': removal_request.member.full_name,
            'removal_request_id': str(removal_request.id),
            'admin_notes': removal_request.admin_notes or '',
        },
    )

    django_messages.warning(request, f'Removal request for {removal_request.member.full_name} was rejected.')
    return redirect('frontend:agent_approvals')


@login_required
def edit_joint_member(request, member_id):
    """Allow the group leader to replace or update a co-buyer's record."""
    from django.contrib import messages as django_messages

    if not is_joint_buyer(request.user):
        return redirect('frontend:home')

    member = get_object_or_404(JointBuyerMember, id=member_id)
    group = member.group

    if group.leader != request.user or member.is_leader:
        return redirect('frontend:joint_group_detail', group_id=group.id)

    if group.transactions.filter(status__in=['Under_Verification', 'Deposit_Paid', 'Completed']).exists():
        django_messages.error(request, 'You cannot edit members on a group linked to an active or completed transaction.')
        return redirect('frontend:joint_group_detail', group_id=group.id)

    if request.method == 'POST':
        form = JointBuyerMemberForm(request.POST, instance=member)
        if form.is_valid():
            form.save()
            total = group.total_share
            if total != 100:
                django_messages.warning(
                    request,
                    f'Member updated. Current group shares total {total}%, so please rebalance to 100%.',
                )
            else:
                django_messages.success(request, 'Member updated successfully.')
            return redirect('frontend:joint_group_detail', group_id=group.id)
    else:
        form = JointBuyerMemberForm(instance=member)

    return render_react_shell(
        request,
        'form',
        f'Edit member - {member.full_name}',
        'Update a co-buyer record before the group enters an active transaction.',
        form=serialize_form(
            form,
            action=reverse('frontend:edit_joint_member', args=[member.id]),
            submit_label='Save member',
            cancel_label='Back to group',
            cancel_href=reverse('frontend:joint_group_detail', args=[group.id]),
            intro='Keep the co-buyer identity, contact details, and share allocation accurate before checkout.',
            sections=[
                {'title': 'Identity', 'fields': ['full_name', 'id_number', 'kra_pin']},
                {'title': 'Contact and share', 'fields': ['phone_number', 'email', 'share_percentage']},
            ],
        ),
    )


@login_required
def edit_joint_group(request, group_id):
    """Edit group details (name, type, ownership) and leader share before a transaction is initiated."""
    from django.contrib import messages as django_messages

    if not is_joint_buyer(request.user):
        return redirect('frontend:home')

    group = get_object_or_404(JointBuyerGroup, id=group_id, leader=request.user)

    # Block editing if the group is already linked to an active transaction
    if group.transactions.filter(status__in=['Under_Verification', 'Deposit_Paid', 'Completed']).exists():
        django_messages.error(request, 'Cannot edit a group that is linked to an active or completed transaction.')
        return redirect('frontend:joint_group_detail', group_id=group.id)

    leader_member = group.members.filter(is_leader=True).first()

    if request.method == 'POST':
        form = JointBuyerGroupForm(request.POST, instance=group)
        if form.is_valid():
            form.save()
            # Update leader share
            leader_share = form.cleaned_data.get('leader_share_percentage')
            if leader_member and leader_share is not None:
                leader_member.share_percentage = leader_share
                leader_member.save(update_fields=['share_percentage'])

                # Re-validate total
                from decimal import Decimal
                total = sum(m.share_percentage for m in group.members.all())
                if total != Decimal('100'):
                    django_messages.warning(request, f'Group saved but shares total {total}% — please adjust co-buyer shares to reach 100%.')
                else:
                    django_messages.success(request, 'Group updated successfully.')
            else:
                django_messages.success(request, 'Group updated successfully.')
            return redirect('frontend:joint_group_detail', group_id=group.id)
    else:
        initial = {}
        if leader_member:
            initial['leader_share_percentage'] = leader_member.share_percentage
        form = JointBuyerGroupForm(instance=group, initial=initial)

    return render_react_shell(
        request,
        'form',
        f'Edit group - {group.name}',
        'Update the group profile, payment settings, and the leader share before any active transaction starts.',
        form=serialize_form(
            form,
            action=reverse('frontend:edit_joint_group', args=[group.id]),
            submit_label='Save group',
            cancel_label='Back to group',
            cancel_href=reverse('frontend:joint_group_detail', args=[group.id]),
            intro='Keep the ownership structure aligned with the current co-buyer arrangement.',
            sections=[
                {'title': 'Group details', 'fields': ['name', 'group_type']},
                {'title': 'Ownership and payment', 'fields': ['ownership_type', 'preferred_payment_method', 'leader_share_percentage']},
                {'title': 'Bank details', 'fields': ['bank_name', 'bank_account_name', 'bank_account_number', 'bank_branch']},
            ],
        ),
    )


@login_required
@user_passes_test(lambda u: u.role == 'Admin', login_url='/agent/onboarding/')
def rate_agent(request, agent_id):
    """Admin-only: rate an agent's performance."""
    from core.utils import send_agent_rating_notification

    agent = get_object_or_404(CoreUser, id=agent_id, role='Agent')
    form = AgentRatingForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        rating = int(form.cleaned_data['rating'])
        review = form.cleaned_data.get('review', '').strip()
        AgentRating.objects.create(
            agent=agent,
            rating=rating,
            review=review,
            rated_by=request.user,
        )

        # Send rating notification email.
        email_sent, email_message = send_agent_rating_notification(agent, rating, review)

        from django.contrib import messages
        if email_sent:
            messages.success(request, f'Rated {agent.email} with {rating} stars! Rating notification sent.')
        else:
            messages.success(request, f'Rated {agent.email} with {rating} stars! Email failed: {email_message}')

        return redirect('frontend:agent_dashboard')

    return render_react_shell(
        request,
        'form',
        f'Rate agent - {agent.email}',
        'Record a short performance review for the selected agent.',
        form=serialize_form(
            form,
            action=reverse('frontend:rate_agent', args=[agent.id]),
            submit_label='Submit rating',
            cancel_label='Back to dashboard',
            cancel_href=reverse('frontend:agent_dashboard'),
            intro='Score the agent from one to five stars and add a concise review note.',
            sections=[
                {'title': 'Rating', 'fields': ['rating']},
                {'title': 'Review', 'fields': ['review']},
            ],
        ),
    )


@login_required
@user_passes_test(lambda u: u.role == 'Admin', login_url='/agent/onboarding/')
def send_admin_message(request):
    """Admin-only: send messages to users via email."""
    from core.models import User as CoreUser
    from django.contrib import messages
    from core.utils import send_custom_email
    
    if request.method != 'POST':
        return redirect('frontend:agent_dashboard')
    
    recipient_type = request.POST.get('recipient_type', '')
    custom_emails = request.POST.get('custom_emails', '')
    subject = request.POST.get('subject', '').strip()
    message = request.POST.get('message', '').strip()
    send_html = request.POST.get('send_html') == 'on'
    
    if not recipient_type or not subject or not message:
        messages.error(request, 'Please fill in all required fields.')
        return redirect('frontend:agent_dashboard')
    
    # Get recipients based on type
    recipients = []
    
    if recipient_type == 'all_agents':
        recipients = CoreUser.objects.filter(role='Agent', is_active=True).values_list('email', flat=True)
    elif recipient_type == 'verified_agents':
        recipients = CoreUser.objects.filter(role='Agent', is_identity_verified=True, is_active=True).values_list('email', flat=True)
    elif recipient_type == 'pending_agents':
        recipients = CoreUser.objects.filter(role='Agent', is_identity_verified=False, is_active=True).values_list('email', flat=True)
    elif recipient_type == 'all_users':
        recipients = CoreUser.objects.filter(is_active=True).values_list('email', flat=True)
    elif recipient_type == 'buyers':
        recipients = CoreUser.objects.filter(role='Buyer', is_active=True).values_list('email', flat=True)
    elif recipient_type == 'sellers':
        recipients = CoreUser.objects.filter(role='Seller', is_active=True).values_list('email', flat=True)
    elif recipient_type == 'custom':
        if custom_emails:
            recipients = [email.strip() for email in custom_emails.split(',') if email.strip()]
        else:
            messages.error(request, 'Please provide custom email addresses.')
            return redirect('frontend:agent_dashboard')
    
    if not recipients:
        messages.warning(request, 'No recipients found for the selected type.')
        return redirect('frontend:agent_dashboard')
    
    # Send emails
    email_sent, email_message = send_custom_email(
        recipients=list(recipients),
        subject=subject,
        message=message,
        html_message=message if send_html else None
    )
    
    if email_sent:
        messages.success(request, f'Message sent successfully to {len(recipients)} recipient(s)!')
    else:
        messages.error(request, f'Failed to send message: {email_message}')
    
    return redirect('frontend:agent_dashboard')


@login_required
def transaction_failed(request, transaction_id):
    """Dedicated page showing why a transaction failed/was reversed/refunded/disputed."""
    transaction = get_object_or_404(Transaction.objects.select_related('buyer', 'seller', 'land_parcel', 'joint_group'), id=transaction_id)

    # Security: Only involved parties or Admin/Agent can view
    if request.user not in [transaction.buyer, transaction.seller] and request.user.role not in ['Admin', 'Agent']:
        return redirect('frontend:transactions')

    # Build human-readable status label
    STATUS_LABELS = {
        'Reversed': 'Reversed by Admin',
        'Refunded': 'Refunded',
        'Disputed': 'Under Dispute',
    }
    status_label = STATUS_LABELS.get(transaction.status, 'Failed')

    # Reason can come from query param (for payment failures) or model fields
    reason = request.GET.get('reason', '')
    if not reason and transaction.reversal_reason:
        reason = transaction.reversal_reason

    retry_href = None
    if transaction.contract_agreed and transaction.status == 'Under_Verification':
        retry_href = reverse('frontend:payment_checkout', args=[transaction.id])

    return render_react_shell(
        request,
        'status',
        status_label,
        f'Parcel {transaction.land_parcel.parcel_number}',
        status=serialize_status_page(
            icon='alert',
            tone='danger' if transaction.status in {'Reversed', 'Refunded', 'Disputed'} else 'warning',
            title=status_label,
            description=f'{reason or "The payment flow could not be completed."} Transaction ID {str(transaction.id)[:8].upper()} can be reviewed from the action buttons below.',
            primary_action={
                'label': 'Retry checkout' if retry_href else 'Back to transactions',
                'href': retry_href or reverse('frontend:transactions'),
                'tone': 'default',
            },
            secondary_action={
                'label': 'Open support',
                'href': reverse('frontend:support'),
                'tone': 'outline',
            },
        ),
    )


@login_required
def recommendations(request):
    """Personalized parcel recommendations for Buyers."""
    from core.services.recommendation import build_recommendation_feed

    try:
        feed = build_recommendation_feed(request.user, limit=12)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Recommendation error: {e}")
        feed = {
            'recommended': [],
            'rec_type': 'popular',
            'popular_parcels': [],
            'popular_county': 'Nairobi',
            'recently_viewed': [],
            'recently_viewed_similar': [],
            'hot_deals': [],
            'trending_in_target_area': [],
            'people_also_viewed': [],
            'sponsored_listings': [],
            'buyer_category': None,
        }

    return render_react_shell(
        request,
        'recommendations',
        'Recommended parcels',
        'Personalized recommendations, popular alternatives, and recently viewed parcels.',
        popup_context={
            'placement': 'recommendations',
            'county': feed.get('popular_county'),
            'buyer_category': feed.get('buyer_category'),
        },
        recommendations_page=serialize_recommendations_page(
            feed.get('recommended'),
            feed.get('rec_type'),
            feed.get('popular_parcels'),
            feed.get('popular_county'),
            feed.get('recently_viewed'),
            hot_deals=feed.get('hot_deals'),
            recently_viewed_similar=feed.get('recently_viewed_similar'),
            trending_in_target_area=feed.get('trending_in_target_area'),
            people_also_viewed=feed.get('people_also_viewed'),
            sponsored_listings=feed.get('sponsored_listings'),
            user=request.user,
        ),
        actions=[
            {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
            {'label': 'Price estimator', 'href': reverse('frontend:price_prediction'), 'tone': 'secondary'},
        ],
    )


@login_required
def price_prediction(request):
    """Interactive land price prediction tool."""
    from django.conf import settings
    if not getattr(settings, 'ENABLE_AI_PRICE_PREDICTION', True):
        django_messages.warning(request, "The AI Price Estimation feature has been disabled platform-wide by configuration.")
        return render_react_shell(
            request,
            'info',
            'Land Price Estimator (Disabled)',
            'The AI Price Estimation feature is currently disabled by administrative policy.',
            info_message="The AI Price Estimation module is currently disabled. Other AI features (AI Ad Campaigns and AI Document Verification) remain active.",
        )

    from core.services.price_prediction import (
        predict_price, KENYA_COUNTIES, LAND_USE_TYPES,
        get_model_info
    )


    form = PricePredictionForm(
        request.POST or None,
        counties=KENYA_COUNTIES,
        land_use_types=LAND_USE_TYPES,
    )
    prediction = None

    if request.method == 'POST' and form.is_valid():
        cleaned = form.cleaned_data
        try:
            prediction = predict_price(
                county=cleaned['county'],
                constituency=cleaned['constituency'] if cleaned['constituency'] else cleaned['county'],
                land_use=cleaned['land_use'],
                size_acres=float(cleaned['size_acres']),
                has_road_access=cleaned['has_road_access'],
                has_water=cleaned['has_water'],
                has_electricity=cleaned['has_electricity'],
            )
        except (ValueError, TypeError) as e:
            prediction = {'error': f'Invalid input: {e}'}

    model_info = get_model_info()

    return render_react_shell(
        request,
        'price-prediction',
        'Land price estimator',
        'Estimate parcel pricing using county, land use, and infrastructure inputs.',
        prediction_page={
            'counties': KENYA_COUNTIES,
            'land_use_types': LAND_USE_TYPES,
            'form': serialize_form(
                form,
                action=reverse('frontend:price_prediction'),
                submit_label='Estimate price',
                intro='Use the trained model to get a rough market estimate before listing or buying.',
                sections=[
                    {'title': 'Location', 'fields': ['county', 'constituency', 'land_use']},
                    {'title': 'Parcel size', 'fields': ['size_acres']},
                    {'title': 'Infrastructure', 'fields': ['has_road_access', 'has_water', 'has_electricity']},
                ],
            ),
            'model_info': {
                'n_records': str(model_info.get('n_records', 0)),
                'n_counties': str(model_info.get('n_counties', 0)),
                'algorithm': str(model_info.get('algorithm', 'RandomForest')),
            } if model_info else None,
            'prediction': serialize_prediction_result(prediction),
        },
        actions=[
            {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
            {'label': 'Recommendations', 'href': reverse('frontend:recommendations'), 'tone': 'secondary'},
        ],
    )


@login_required
def toggle_favorite(request, parcel_number):
    """Toggle a parcel as favorite/saved for the current user."""
    from django.http import JsonResponse

    if request.method != 'POST':
        return JsonResponse({'error': 'POST required'}, status=405)

    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)

    existing = UserFavorite.objects.filter(user=request.user, parcel=parcel)
    if existing.exists():
        existing.delete()
        is_favorited = False
    else:
        UserFavorite.objects.create(user=request.user, parcel=parcel)
        is_favorited = True

    # Support both AJAX and regular form submission
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
    if is_ajax:
        return JsonResponse({'is_favorited': is_favorited})

    return redirect('frontend:parcel_detail', parcel_number=parcel_number)


@login_required
def admin_finance(request):
    """Admin-only expenditure and tax dashboard."""
    if request.user.role != 'Admin':
        return redirect('frontend:home')

    from django.db.models import Sum, Count, Q
    from django.db.models.functions import TruncMonth
    from django.middleware.csrf import get_token
    from decimal import Decimal

    transactions = Transaction.objects.all()
    completed = transactions.filter(status='Completed')
    reversed_txns = transactions.filter(status='Reversed')

    total_volume = completed.aggregate(total=Sum('agreed_price'))['total'] or Decimal('0')
    reversed_volume = reversed_txns.aggregate(total=Sum('agreed_price'))['total'] or Decimal('0')

    # Platform commission at 4%
    platform_commission = total_volume * Decimal('0.04')
    # Stamp duty estimate at 4% (Kenyan law)
    stamp_duty_estimate = total_volume * Decimal('0.04')
    # Legal fees estimate at 1%
    legal_fees_estimate = total_volume * Decimal('0.01')
    # Total tax obligation
    total_tax = stamp_duty_estimate + legal_fees_estimate

    # Status breakdown
    status_counts = transactions.values('status').annotate(count=Count('id')).order_by('status')

    # Monthly breakdown (last 12 months)
    monthly = (
        completed
        .annotate(month=TruncMonth('created_at'))
        .values('month')
        .annotate(volume=Sum('agreed_price'), count=Count('id'))
        .order_by('-month')[:12]
    )

    # Recent completed transactions
    recent = completed.select_related('buyer', 'seller', 'land_parcel').order_by('-updated_at')[:20]

    finance_dashboard = {
        'total_volume': float(total_volume),
        'platform_commission': float(platform_commission),
        'stamp_duty_estimate': float(stamp_duty_estimate),
        'legal_fees_estimate': float(legal_fees_estimate),
        'total_tax': float(total_tax),
        'reversed_volume': float(reversed_volume),
        'total_transactions': transactions.count(),
        'completed_count': completed.count(),
        'pending_count': transactions.filter(status__in=['Initiated', 'Deposit_Paid', 'Under_Verification', 'Verification_Hiatus']).count(),
        'reversed_count': reversed_txns.count(),
        'status_counts': list(status_counts),
        'monthly': [
            {
                'month': m['month'].strftime('%b %Y') if m['month'] else 'Unknown',
                'volume': float(m['volume'] or 0),
                'count': m['count'],
            }
            for m in monthly
        ],
        'recent_transactions': [serialize_transaction(tx, request.user) for tx in recent],
    }

    return render_react_shell(
        request,
        'finance',
        'Finance & Tax Dashboard',
        'Platform expenditure, revenue, and tax obligations overview.',
        finance_dashboard=finance_dashboard,
        csrf_token=get_token(request),
        finance_pin_verified=bool(request.session.get('finance_pin_verified')),
        finance_verify_url=reverse('frontend:admin_finance_verify'),
        admin_withdraw_url=reverse('frontend:admin_withdraw'),
    )


@login_required
def agent_withdraw(request):
    """Agent withdrawal page: shows available commission balance and triggers M-Pesa B2C payout."""
    if request.user.role != 'Agent':
        return redirect('frontend:home')

    from django.db.models import Sum
    from django.contrib import messages
    from decimal import Decimal

    # Agent gets 1% of the agreed price of completed transactions they verified
    completed_tx = Transaction.objects.filter(
        land_parcel__assigned_agent=request.user, 
        status='Completed'
    )
    total_volume = completed_tx.aggregate(total=Sum('agreed_price'))['total'] or Decimal('0')
    withdrawable_amount = total_volume * Decimal('0.01')

    if request.method == 'POST':
        amount_str = request.POST.get('amount', '0')
        phone = request.POST.get('phone_number', '').strip()
        
        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                messages.error(request, 'Please enter a valid amount.')
            elif amount > withdrawable_amount:
                messages.error(request, 'Insufficient balance.')
            elif not phone:
                messages.error(request, 'Please enter a valid M-Pesa phone number.')
            else:
                # Simulate M-Pesa B2C payout
                import uuid
                ref_number = str(uuid.uuid4())[:8].upper()
                
                AuditLog.objects.create(
                    user=request.user,
                    action=f"Agent commission withdrawal: KES {amount}",
                    metadata={
                        'amount': float(amount),
                        'phone': phone,
                        'reference': ref_number,
                        'balance_before': float(withdrawable_amount)
                    }
                )
                messages.success(request, f'Withdrawal of KES {amount:,.2f} initiated successfully. Ref: {ref_number}')
                return redirect('frontend:home')
        except Exception:
            messages.error(request, 'Invalid withdrawal request.')

    return render_react_shell(
        request,
        'agent-withdraw',
        'Withdraw Earnings',
        'Transfer your earned commissions directly to M-Pesa.',
        withdraw_data={
            'available_balance': float(withdrawable_amount),
            'completed_transactions_count': completed_tx.count(),
            'commission_rate': '1%',
            'phone_number': request.user.phone_number,
        },
        actions=[{'label': 'Back to Dashboard', 'href': reverse('frontend:home'), 'tone': 'outline'}]
    )


@login_required
def seller_withdraw(request):
    """Seller withdrawal page: shows available balance and triggers M-Pesa B2C payout."""
    if request.user.role != 'Seller':
        return redirect('frontend:home')

    from django.db.models import Sum
    from django.contrib import messages

    completed_tx = Transaction.objects.filter(seller=request.user, status='Completed')
    escrow_tx = Transaction.objects.filter(seller=request.user, status__in=['Deposit_Paid', 'Under_Verification', 'Verification_Hiatus'])
    total_received = completed_tx.aggregate(total=Sum('agreed_price'))['total'] or 0
    in_escrow = escrow_tx.aggregate(total=Sum('agreed_price'))['total'] or 0

    # Available balance = completed payments (simplified; in production, track actual payouts)
    available_balance = total_received

    if request.method == 'POST':
        withdraw_amount = request.POST.get('withdraw_amount', '0')
        phone = request.POST.get('phone_number', request.user.phone_number)
        try:
            withdraw_amount = float(withdraw_amount)
        except (ValueError, TypeError):
            withdraw_amount = 0

        if withdraw_amount <= 0 or withdraw_amount > float(available_balance):
            messages.error(request, 'Invalid withdrawal amount. Please enter an amount within your available balance.')
            return redirect('frontend:seller_withdraw')

        # Simulate M-Pesa B2C payout
        import uuid as _uuid
        payout_ref = f"WD-{_uuid.uuid4().hex[:10].upper()}"
        messages.success(request, f'Withdrawal of KES {withdraw_amount:,.0f} to {phone} initiated. Reference: {payout_ref}. You will receive the M-Pesa payment shortly.')

        # Log the withdrawal
        AuditLog.objects.create(
            user=request.user,
            action=f"Seller withdrawal: KES {withdraw_amount:,.0f} to {phone}",
            metadata={
                'reference': payout_ref,
                'amount': withdraw_amount,
                'phone': phone,
            }
        )
        return redirect('frontend:seller_withdraw')

    return render_react_shell(
        request,
        'seller-withdraw',
        'Withdraw funds',
        'Transfer your available balance directly to M-Pesa.',
        withdraw_data={
            'available_balance': str(available_balance),
            'in_escrow': str(in_escrow),
            'total_received': str(total_received),
            'phone_number': request.user.phone_number or '',
            'action_url': reverse('frontend:seller_withdraw'),
        },
        actions=[
            {'label': 'Dashboard', 'href': reverse('frontend:home'), 'tone': 'outline'},
            {'label': 'Transactions', 'href': reverse('frontend:transactions'), 'tone': 'secondary'},
        ],
    )


@login_required
def seller_promotions(request):
    """Seller/agent campaign studio for popup ads and discovery promotions."""
    from django.contrib import messages
    from django.middleware.csrf import get_token
    from decimal import Decimal
    import uuid as _uuid

    if not is_seller_or_agent(request.user) and request.user.role != 'Admin':
        return redirect('frontend:home')

    campaigns_qs = PopupAdCampaign.objects.select_related('parcel', 'created_by')
    if request.user.role != 'Admin':
        campaigns_qs = campaigns_qs.filter(created_by=request.user)

    campaigns_qs = campaigns_qs.order_by('-updated_at', '-created_at')

    if request.method == 'POST':
        form_type = request.POST.get('form_type', 'create').strip()
        if form_type == 'campaign_action':
            campaign_id = request.POST.get('campaign_id')
            action = request.POST.get('campaign_action', '').strip().lower()
            campaign = get_object_or_404(PopupAdCampaign, id=campaign_id)
            if request.user.role != 'Admin' and campaign.created_by_id != request.user.id:
                return redirect('frontend:seller_promotions')

            if action == 'pause':
                campaign.status = 'Paused'
                campaign.save(update_fields=['status', 'updated_at'])
                messages.success(request, f'Campaign "{campaign.campaign_name}" paused.')
            elif action == 'activate':
                campaign.status = 'Active'
                campaign.payment_status = 'Paid'
                if not campaign.payment_reference:
                    campaign.payment_reference = f'POP-{_uuid.uuid4().hex[:10].upper()}'
                if campaign.billing_model == 'Subscription' and Decimal(str(campaign.spent_amount or 0)) == Decimal('0.00'):
                    campaign.spent_amount = campaign.total_budget
                campaign.save(update_fields=['status', 'payment_status', 'payment_reference', 'spent_amount', 'updated_at'])
                messages.success(request, f'Campaign "{campaign.campaign_name}" activated.')
            elif action == 'archive':
                campaign.status = 'Archived'
                campaign.save(update_fields=['status', 'updated_at'])
                messages.success(request, f'Campaign "{campaign.campaign_name}" archived.')
            else:
                messages.error(request, 'Unknown campaign action.')

            AuditLog.objects.create(
                user=request.user,
                action=f'Popup campaign action: {action}',
                metadata={
                    'campaign_id': str(campaign.id),
                    'campaign_name': campaign.campaign_name,
                    'action': action,
                },
            )
            return redirect('frontend:seller_promotions')

        form = PopupAdCampaignForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            campaign = form.save(commit=False)
            campaign.created_by = request.user
            if not campaign.payment_reference:
                campaign.payment_reference = f'POP-{_uuid.uuid4().hex[:10].upper()}'
            if campaign.status == 'Active':
                campaign.payment_status = 'Paid'
            elif not campaign.payment_status:
                campaign.payment_status = 'Pending'
            if campaign.billing_model == 'Subscription' and campaign.status == 'Active' and Decimal(str(campaign.spent_amount or 0)) == Decimal('0.00'):
                campaign.spent_amount = campaign.total_budget
            campaign.save()

            AuditLog.objects.create(
                user=request.user,
                action=f'Popup campaign created: {campaign.campaign_name}',
                metadata={
                    'campaign_id': str(campaign.id),
                    'parcel_number': campaign.parcel.parcel_number,
                    'popup_type': campaign.popup_type,
                    'billing_model': campaign.billing_model,
                    'status': campaign.status,
                },
            )
            messages.success(request, f'Campaign "{campaign.campaign_name}" saved.')
            return redirect('frontend:seller_promotions')
        messages.error(request, 'Please fix the highlighted campaign settings.')
    else:
        form = PopupAdCampaignForm(user=request.user)

    dashboard = build_seller_promotions_dashboard(request.user)

    return render_react_shell(
        request,
        'seller-promotions',
        'Promotions & Ads',
        'Premium popup campaigns, targeting controls, and performance analytics.',
        seller_promotions_page={
            'summary': dashboard['summary'],
            'campaigns': dashboard['campaigns'],
            'heatmap': dashboard['heatmap'],
            'trigger_breakdown': dashboard['trigger_breakdown'],
            'recommendations': dashboard['recommendations'],
            'supported_popup_types': dashboard['supported_popup_types'],
            'supported_billing_models': dashboard['supported_billing_models'],
            'events_count': dashboard['events_count'],
            'campaign_action_url': dashboard['campaign_action_url'],
            'form': serialize_form(
                form,
                action=reverse('frontend:seller_promotions'),
                submit_label='Launch campaign',
                intro='Build a premium popup campaign that follows the buyer journey without interrupting it. In this build, active campaigns are auto-marked paid so you can validate the experience end-to-end.',
                sections=[
                    {'title': 'Campaign setup', 'fields': ['parcel', 'campaign_name', 'popup_type', 'billing_model', 'status']},
                    {'title': 'Creative', 'fields': ['headline', 'subheadline', 'cta_text', 'landing_url', 'creative_image', 'creative_video_url', 'notes']},
                    {'title': 'Targeting', 'fields': ['target_counties_text', 'target_locations_text', 'target_buyer_categories_text', 'target_intent_tags_text']},
                    {'title': 'Budget & rules', 'fields': ['target_budget_min', 'target_budget_max', 'target_acreage_min', 'target_acreage_max', 'travel_radius_km', 'frequency_cap_per_session', 'cooldown_minutes', 'duration_days', 'daily_budget', 'total_budget', 'priority_bid', 'geo_exclusive', 'seller_verified_only']},
                ],
            ),
        },
        actions=[
            {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
            {'label': 'Buyer recommendations', 'href': reverse('frontend:recommendations'), 'tone': 'secondary'},
        ],
    )


def popup_ad_event_api(request):
    """Record popup impressions, clicks, leads, dismissals, and exit-intent signals."""
    from django.http import JsonResponse
    import json

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    payload = {}
    if request.content_type and 'application/json' in request.content_type:
        try:
            payload = json.loads(request.body.decode('utf-8') or '{}')
        except Exception:
            payload = {}
    else:
        payload = request.POST.dict()

    campaign_id = payload.get('campaign_id')
    if not campaign_id:
        return JsonResponse({'status': 'error', 'message': 'Missing campaign_id'}, status=400)

    campaign = get_object_or_404(PopupAdCampaign, id=campaign_id)
    event_type = (payload.get('event_type') or 'Impression').strip()
    placement_area = payload.get('placement_area') or payload.get('page_context') or 'marketplace'
    page_context = payload.get('page_context') or placement_area

    metadata = payload.get('metadata') or {}
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except Exception:
            metadata = {'raw': metadata}

    result = record_popup_event(
        campaign,
        user=request.user if request.user.is_authenticated else None,
        request=request,
        event_type=event_type,
        placement_area=placement_area,
        page_context=page_context,
        buyer_category=payload.get('buyer_category'),
        county_context=payload.get('county_context'),
        intent_score=float(payload.get('intent_score') or 0.0),
        relevance_score=float(payload.get('relevance_score') or 0.0),
        dwell_seconds=float(payload.get('dwell_seconds') or 0.0),
        metadata=metadata,
    )
    return JsonResponse({'status': 'success', 'event': result})


@login_required
def contract_sign_fullpage(request, token):
    """Full-page contract signing experience accessible via encrypted token URL.

    The token is a Django signing token that encodes the transaction ID.
    This view renders outside the dashboard shell for a clean, professional
    document-signing experience.
    """
    from django.core.signing import Signer, BadSignature
    from core.legal import KENYAN_LAND_DOCUMENTS, JOINT_KENYAN_LAND_DOCUMENTS
    from django.middleware.csrf import get_token

    signer = Signer()
    try:
        transaction_id = signer.unsign(token)
    except BadSignature:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden('Invalid or expired contract signing link.')

    transaction = get_object_or_404(
        Transaction.objects.select_related('buyer', 'seller', 'land_parcel', 'joint_group').prefetch_related('joint_group__members'),
        id=transaction_id,
    )

    # Security: Only involved parties, Admin, or Lawyer
    if request.user not in [transaction.buyer, transaction.seller] and request.user.role not in ['Admin', 'Lawyer']:
        return redirect('frontend:transactions')

    # Handle POST (signature submission) — redirect back to dashboard contract page for processing
    if request.method == 'POST':
        # Forward the POST to the standard sign_contract view
        return sign_contract(request, transaction.id)

    # Determine documents
    if request.user.role == 'Admin':
        contract_documents = []
    elif transaction.is_joint_purchase:
        contract_documents = JOINT_KENYAN_LAND_DOCUMENTS
    else:
        contract_documents = KENYAN_LAND_DOCUMENTS

    joint_breakdown = []
    if transaction.is_joint_purchase and transaction.joint_group:
        from decimal import Decimal, ROUND_HALF_UP
        total = transaction.agreed_price
        for m in transaction.joint_group.members.all():
            amt = (total * (m.share_percentage / Decimal('100'))).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
            joint_breakdown.append({'member': m, 'amount': amt})

    contract_data = serialize_contract(
        transaction,
        request.user,
        documents=contract_documents,
        joint_breakdown=joint_breakdown,
        sign_url=reverse('frontend:contract_sign_fullpage', args=[token]),
        payment_url=reverse('frontend:payment_checkout', args=[transaction.id]),
        transactions_url=reverse('frontend:transactions'),
        csrf_token=get_token(request),
    )

    return render_react_shell(
        request,
        'contract-fullpage',
        'Kenyan Land Transfer Agreement',
        f'Property: {transaction.land_parcel.parcel_number}',
        contract=contract_data,
        require_signature=True,
        fullpage_mode=True,
        back_url=reverse('frontend:transactions'),
    )


@login_required
def admin_finance_verify(request):
    """Verify the admin finance PIN before granting access to the finance dashboard."""
    from django.http import JsonResponse
    from django.conf import settings as django_settings

    if request.user.role != 'Admin':
        return JsonResponse({'status': 'error', 'message': 'Unauthorized'}, status=403)

    if request.method != 'POST':
        return JsonResponse({'status': 'error', 'message': 'POST required'}, status=405)

    pin = request.POST.get('finance_pin', '').strip()
    expected_pin = getattr(django_settings, 'ADMIN_FINANCE_PIN', 'admin2026')

    if pin == expected_pin:
        request.session['finance_pin_verified'] = True
        return JsonResponse({'status': 'success', 'message': 'Access granted.'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Incorrect PIN. Access denied.'}, status=403)


@login_required
def admin_withdraw(request):
    """Admin withdrawal: transfer platform commission to M-Pesa or KCB bank account."""
    if request.user.role != 'Admin':
        return redirect('frontend:home')

    from django.db.models import Sum
    from django.contrib import messages
    from decimal import Decimal

    completed_tx = Transaction.objects.filter(status='Completed')
    total_volume = completed_tx.aggregate(total=Sum('agreed_price'))['total'] or Decimal('0')
    platform_commission = total_volume * Decimal('0.04')

    # Track past admin withdrawals
    past_withdrawals = AuditLog.objects.filter(
        user=request.user,
        action__startswith='Admin platform withdrawal'
    )
    total_withdrawn = Decimal('0')
    for log in past_withdrawals:
        meta = log.metadata or {}
        total_withdrawn += Decimal(str(meta.get('amount', 0)))

    available_balance = platform_commission - total_withdrawn

    if request.method == 'POST':
        amount_str = request.POST.get('amount', '0')
        phone = request.POST.get('phone_number', '').strip()
        withdrawal_method = request.POST.get('withdrawal_method', 'm_pesa')
        bank_account = request.POST.get('bank_account', '').strip()

        try:
            amount = Decimal(amount_str)
            if amount <= 0:
                messages.error(request, 'Please enter a valid amount.')
            elif amount > available_balance:
                messages.error(request, 'Insufficient platform balance.')
            else:
                import uuid
                ref_number = f"ADM-{uuid.uuid4().hex[:10].upper()}"

                if withdrawal_method == 'kcb_bank':
                    from core.services.kcb import initiate_b2c_payout
                    result = initiate_b2c_payout(
                        destination_account=bank_account,
                        amount=float(amount),
                        reference=ref_number,
                        beneficiary_name='Digiland Admin',
                        narration=f'Admin withdrawal {ref_number}',
                    )
                    if result.get('status') == 'success':
                        messages.success(request, f'KCB transfer of KES {amount:,.2f} initiated. Ref: {ref_number}')
                    else:
                        messages.error(request, f'KCB transfer failed: {result.get("message", "Unknown error")}')
                        return redirect('frontend:admin_withdraw')
                else:
                    # Simulate M-Pesa B2C
                    messages.success(request, f'M-Pesa withdrawal of KES {amount:,.2f} to {phone} initiated. Ref: {ref_number}')

                AuditLog.objects.create(
                    user=request.user,
                    action=f"Admin platform withdrawal: KES {amount:,.2f}",
                    metadata={
                        'amount': float(amount),
                        'method': withdrawal_method,
                        'phone': phone,
                        'bank_account': bank_account,
                        'reference': ref_number,
                        'balance_before': float(available_balance),
                    }
                )
                return redirect('frontend:admin_finance')
        except Exception:
            messages.error(request, 'Invalid withdrawal request.')

    return render_react_shell(
        request,
        'admin-withdraw',
        'Platform Withdrawal',
        'Transfer platform commission earnings to M-Pesa or bank account.',
        withdraw_data={
            'available_balance': float(available_balance),
            'total_commission': float(platform_commission),
            'total_withdrawn': float(total_withdrawn),
            'phone_number': request.user.phone_number or '',
            'action_url': reverse('frontend:admin_withdraw'),
        },
        actions=[
            {'label': 'Back to Finance', 'href': reverse('frontend:admin_finance'), 'tone': 'outline'},
        ],
    )


from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

@login_required
def ai_kyc_page(request):
    return render_react_shell(
        request,
        'ai-kyc',
        'Identity Verification',
        'Secure AI-powered document and biometric validation.',
        kyc_status_url=reverse('frontend:kyc_status_api'),
        kyc_submit_url=reverse('frontend:submit_kyc_api'),
        csrf_token=get_token(request),
    )

@login_required
def kyc_status_api(request):
    try:
        profile = request.user.kyc_profile
        return JsonResponse({
            'status': profile.status,
            'message': profile.audit_log.get('reason', 'Processing your identity verification...') if profile.status != 'APPROVED' else 'Verification complete.'
        })
    except Exception:
        return JsonResponse({'status': 'NOT_STARTED'})

@login_required
def submit_kyc_api(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=405)
        
    id_front = request.FILES.get('id_front')
    selfie = request.FILES.get('selfie_video') or request.FILES.get('selfie')
    
    if not id_front or not selfie:
        return JsonResponse({'error': 'Missing required documents'}, status=400)
        
    from core.models import KYCProfile
    
    # Create or update profile
    profile, created = KYCProfile.objects.get_or_create(user=request.user)
    
    # If locked, don't allow re-submission
    if profile.status == 'LOCKED':
        return JsonResponse({'error': 'Account locked for security reasons. Please contact support.'}, status=403)
        
    profile.id_front_image = id_front
    profile.selfie_image = selfie
    profile.status = 'APPROVED'
    profile.audit_log = {'reason': 'Verification complete (Manual/Direct approve).'}
    profile.save()
    
    # Instantly verify user identity
    request.user.is_identity_verified = True
    request.user.save()
    
    return JsonResponse({'status': 'processing'})


@login_required
def promotion_tiers(request):
    """Seller promotion tier browsing and subscription management page."""
    if not is_seller_or_agent(request.user) and request.user.role != 'Admin':
        return redirect('frontend:home')

    from core.models import PromotionTier, PromotionPlan
    from core.services.promotion import PromotionTierService

    # Ensure default tiers exist
    PromotionTierService.ensure_default_tiers()

    tiers = PromotionTier.objects.filter(active=True).order_by('tier_level')
    current_plan = PromotionPlan.objects.filter(seller=request.user).select_related('tier').first()

    tiers_data = []
    for tier in tiers:
        features = tier.features_json if isinstance(tier.features_json, list) else []
        tiers_data.append({
            'id': str(tier.id),
            'name': tier.name,
            'slug': tier.slug,
            'tier_level': tier.tier_level,
            'monthly_price': str(tier.monthly_price),
            'features_json': features,
            'active': tier.active,
        })

    current_plan_data = None
    if current_plan:
        tier_obj = current_plan.tier
        current_plan_data = {
            'id': str(current_plan.id),
            'tier': {
                'id': str(tier_obj.id),
                'name': tier_obj.name,
                'slug': tier_obj.slug,
                'tier_level': tier_obj.tier_level,
                'monthly_price': str(tier_obj.monthly_price),
                'features_json': tier_obj.features_json if isinstance(tier_obj.features_json, list) else [],
                'active': tier_obj.active,
            },
            'tier_name': current_plan.tier.name,
            'status': current_plan.status,
            'is_active': current_plan.is_active,
            'auto_renew': current_plan.auto_renew,
            'start_date': str(current_plan.start_date),
            'end_date': str(current_plan.end_date),
        }

    return render_react_shell(
        request,
        'promotion-tiers',
        'Promotion Tiers',
        'Choose a subscription tier to boost your listings and reach more buyers.',
        promotion_tiers_page={
            'tiers': tiers_data,
            'current_plan': current_plan_data,
            'seller_email': request.user.email,
        },
    )


@login_required
def sponsored_ads(request):
    """Sponsored ad campaign management page for sellers."""
    if not is_seller_or_agent(request.user) and request.user.role != 'Admin':
        return redirect('frontend:home')

    from core.models import SponsoredAd, LandParcel
    from core.services.ads import SponsoredAdService

    campaigns_qs = SponsoredAd.objects.filter(seller=request.user).select_related('parcel').order_by('-created_at')
    parcels = LandParcel.objects.filter(listed_by=request.user, verification_status='Verified').values('id', 'parcel_number', 'county', 'asking_price')

    campaigns_data = []
    for ad in campaigns_qs:
        engagement = SponsoredAdService.get_campaign_performance(ad)
        campaigns_data.append({
            'id': str(ad.id),
            'parcel_number': ad.parcel.parcel_number if ad.parcel else '',
            'parcel': {
                'parcel_number': ad.parcel.parcel_number if ad.parcel else '',
                'county': ad.parcel.county if ad.parcel else '',
                'asking_price': str(ad.parcel.asking_price) if ad.parcel and ad.parcel.asking_price else '',
                'image_url': ad.parcel.image.url if ad.parcel and ad.parcel.image else None,
            },
            'tier': ad.tier,
            'title': getattr(ad, 'title', '') or ad.parcel.parcel_number if ad.parcel else '',
            'description': getattr(ad, 'description', '') or '',
            'status': ad.status,
            'billing_model': ad.billing_model,
            'budget_daily': str(ad.budget_daily) if ad.budget_daily else None,
            'budget_total': str(ad.budget_total) if ad.budget_total else None,
            'budget_spent': str(ad.budget_spent),
            'is_active': ad.is_active if hasattr(ad, 'is_active') else ad.status == 'Active',
            'engagement_summary': {
                'impressions': engagement.get('impressions', 0),
                'clicks': engagement.get('clicks', 0),
                'saves': engagement.get('saves', 0) if 'saves' in engagement else 0,
                'inquiries': engagement.get('inquiries', 0),
                'shares': engagement.get('shares', 0) if 'shares' in engagement else 0,
            },
            'starts_at': str(ad.starts_at) if ad.starts_at else '',
            'ends_at': str(ad.ends_at) if ad.ends_at else '',
            'created_at': str(ad.created_at),
        })

    parcels_data = [{'id': str(p['id']), 'parcel_number': p['parcel_number'], 'county': p['county'], 'asking_price': str(p['asking_price'])} for p in parcels]

    active_count = sum(1 for c in campaigns_data if c['status'] == 'Active')
    total_spent = sum(Decimal(c['budget_spent']) for c in campaigns_data)
    total_impressions = sum(c['engagement_summary']['impressions'] for c in campaigns_data)
    total_clicks = sum(c['engagement_summary']['clicks'] for c in campaigns_data)

    return render_react_shell(
        request,
        'sponsored-ads',
        'Sponsored Ads',
        'Create and manage sponsored ad campaigns to promote your listings.',
        sponsored_ads_page={
            'campaigns': campaigns_data,
            'parcels': parcels_data,
            'total_active': active_count,
            'total_spent': str(total_spent),
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
        },
    )

@login_required
def onboarding_select_role(request):
    if request.user.role and getattr(request.user, 'is_onboarded', False):
        if request.user.role == 'Buyer':
            return redirect('frontend:buyer_dashboard')
        elif request.user.role == 'Seller':
            return redirect('frontend:seller_dashboard')
        elif request.user.role == 'Agent':
            return redirect('frontend:agent_signup_complete')
        elif request.user.role == 'Admin':
            return redirect('/admin/')

    if request.method == 'POST':
        role = (request.POST.get('role') or '').strip().title()
        if role in ['Buyer', 'Seller']:
            request.user.role = role
            request.user.is_onboarded = True
            request.user.save(update_fields=['role', 'is_onboarded'])
            if role == 'Buyer':
                return redirect('frontend:buyer_dashboard')
            else:
                return redirect('frontend:seller_dashboard')

    return render_react_shell(
        request,
        'onboarding-select-role',
        'Select Your Role - Digiland',
    )

@login_required
def buyer_dashboard(request):
    if request.user.role != 'Buyer':
        return redirect('frontend:home')
    return home(request)

@login_required
def seller_dashboard(request):
    if request.user.role != 'Seller':
        return redirect('frontend:home')
    return home(request)
