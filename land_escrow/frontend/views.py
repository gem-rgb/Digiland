from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.middleware.csrf import get_token
from core.models import LandParcel, Transaction, Message, SupportTicket, Document, User as CoreUser, AgentKYCApplication, AgentRating, ParcelView, UserFavorite, JointBuyerGroup, JointBuyerMember, JointPaymentContribution
from core.legal import (
    LAND_TRANSACTION_LAWS,
    LAND_TRANSACTION_CHECKLIST,
    JOINT_LAND_TRANSACTION_LAWS,
    JOINT_LAND_TRANSACTION_CHECKLIST,
    JOINT_PAYMENT_GUIDANCE,
)
from .forms import LandParcelUploadForm
from core.forms import AgentRatingForm, DocumentUploadForm, JointBuyerGroupForm, JointBuyerMemberFormSet, JointBuyerMemberForm, PricePredictionForm
from .react_data import (
    build_nav,
    serialize_checkout,
    serialize_contract,
    serialize_document,
    serialize_form,
    serialize_formset,
    serialize_joint_group,
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
    serialize_user,
)

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
    if user.role == 'Admin':
        return True
    if user.role == 'Agent' and user.is_identity_verified:
        return True
    return False

STAFF_ROLES = {'Admin', 'Agent'}


def render_react_shell(request, page, title, subtitle='', **extra):
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
    bootstrap.update(extra)
    return render(request, 'frontend/react_shell.html', {'react_bootstrap': bootstrap})


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

def home(request):
    from django.db.models import Q
    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    parcels = LandParcel.objects.filter(verification_status='Verified').exclude(transactions__status__in=active_tx_statuses).order_by('-ardhisasa_last_synced')[:5]
    
    transactions = None
    if request.user.is_authenticated:
        if request.user.role == 'Admin':
            transactions = Transaction.objects.all().order_by('-created_at')[:5]
        else:
            transactions = Transaction.objects.filter(Q(buyer=request.user) | Q(seller=request.user)).distinct().order_by('-created_at')[:5]
    
    if request.user.is_authenticated:
        recent_parcels = [serialize_parcel(parcel, request.user) for parcel in parcels]
        recent_transactions = [serialize_transaction(tx, request.user) for tx in transactions] if transactions else []
        return render_react_shell(
            request,
            'dashboard',
            'My Dashboard - Digiland' if request.user.role == 'Buyer' else 'Workspace - Digiland',
            'Unified workspace for parcels, contracts, and escrow activity.',
            parcels=recent_parcels,
            transactions=recent_transactions,
            stats=[
                {'label': 'Verified parcels', 'value': str(len(recent_parcels)), 'tone': 'success'},
                {'label': 'Recent transactions', 'value': str(len(recent_transactions)), 'tone': 'accent'},
                {'label': 'Account type', 'value': getattr(request.user, 'buyer_account_type', None) or request.user.role, 'tone': 'warning'},
                {'label': 'Status', 'value': 'Signed in', 'tone': 'default'},
            ],
            actions=[
                {'label': 'Browse parcels', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
                {'label': 'Open transactions', 'href': reverse('frontend:transactions'), 'tone': 'secondary'},
            ],
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
            {'label': 'Verified parcels', 'value': str(parcels.count()), 'tone': 'success'},
            {'label': 'Active transactions', 'value': str(transactions.count() if transactions else 0), 'tone': 'accent'},
            {'label': 'Joint-ready', 'value': 'Yes', 'tone': 'warning'},
            {'label': 'Status', 'value': 'Live', 'tone': 'default'},
        ],
        actions=[
            {'label': 'Create account', 'href': '/accounts/signup/', 'tone': 'default'},
            {'label': 'Sign in', 'href': '/accounts/login/', 'tone': 'outline'},
        ],
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
    return render_react_shell(
        request,
        'legal',
        'Kenyan land laws',
        'The statutory checklist that applies to a standard land purchase.',
        laws=[serialize_law(law) for law in LAND_TRANSACTION_LAWS],
        checklist=LAND_TRANSACTION_CHECKLIST,
        actions=[
            {'label': 'Joint laws', 'href': reverse('frontend:joint_laws'), 'tone': 'outline'},
            {'label': 'Buyer setup', 'href': reverse('frontend:buyer_account_choice'), 'tone': 'secondary'},
        ],
    )


def joint_legal_requirements(request):
    """Joint-buyer reference page for co-ownership, group purchase, and payment guidance."""
    return render_react_shell(
        request,
        'joint-laws',
        'Joint purchase laws',
        'Kenyan co-ownership rules for group purchases and shared payment setups.',
        laws=[serialize_law(law) for law in JOINT_LAND_TRANSACTION_LAWS],
        checklist=JOINT_LAND_TRANSACTION_CHECKLIST,
        payment_guidance=JOINT_PAYMENT_GUIDANCE,
        actions=[
            {'label': 'Buyer setup', 'href': reverse('frontend:buyer_account_choice'), 'tone': 'outline'},
            {'label': 'Create joint group', 'href': reverse('frontend:create_joint_group'), 'tone': 'secondary'},
        ],
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
            return redirect('frontend:agent_dashboard')
        return redirect('frontend:parcel_list')

    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        password = request.POST.get('password', '').strip()
        user = authenticate(request, email=email, password=password)

        if user is None:
            error = 'Invalid credentials. Please try again.'
        elif getattr(user, 'role', None) not in STAFF_ROLES:
            error = 'This portal is restricted to Staff (Admin / Agent) accounts only.'
        elif not user.is_active:
            error = 'Your account has been deactivated. Contact the system administrator.'
        else:
            auth_login(request, user, backend='django.contrib.auth.backends.ModelBackend')
            if user.role == 'Agent' and not user.is_identity_verified:
                # Check if KYC docs have already been submitted
                try:
                    if user.kyc_application.kyc_submitted:
                        return redirect('frontend:agent_onboarding')
                except Exception:
                    pass
                return redirect('frontend:agent_kyc')
            return redirect('frontend:agent_dashboard')

    # Consume the "just signed up" session flag set by agent_signup_complete
    signup_success = request.session.pop('agent_signup_success', False)

    form = {
        'action': reverse('frontend:staff_login'),
        'method': 'post',
        'enctype': 'application/x-www-form-urlencoded',
        'submitLabel': 'Authenticate',
        'intro': 'Restricted to authorised agents and administrators only.',
        'fields': [
            {
                'name': 'email',
                'label': 'Email address',
                'type': 'email',
                'value': '',
                'placeholder': 'staff@digiland.co.ke',
                'required': True,
                'autoFocus': True,
            },
            {
                'name': 'password',
                'label': 'Password',
                'type': 'password',
                'value': '',
                'placeholder': 'Enter your password',
                'required': True,
            },
        ],
        'hiddenFields': [],
        'errors': [error] if error else [],
    }

    return render_react_shell(
        request,
        'staff-login',
        'Staff Login - Digiland',
        'Restricted to authorised agents and administrators only.',
        form=form,
        notice='Agent sign-up complete' if signup_success else None,
        actions=[{'label': 'Public login', 'href': reverse('account_login'), 'tone': 'outline'}],
    )

def parcel_list(request):
    from django.db.models import Q
    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    
    if request.user.is_authenticated and request.user.role == 'Seller':
        # Sellers ONLY see their own listed parcels
        parcels = LandParcel.objects.filter(
            listed_by=request.user
        ).order_by('-ardhisasa_last_synced')
    elif request.user.is_authenticated and request.user.role in ['Agent', 'Admin']:
        # Agents/Admins see all verified parcels + their own assignments
        parcels = LandParcel.objects.filter(
            Q(assigned_agent=request.user) | Q(verification_status='Verified')
        ).exclude(
            transactions__status__in=active_tx_statuses
        ).distinct().order_by('-ardhisasa_last_synced')
    else:
        # Buyers & guests see only Verified, available parcels
        parcels = LandParcel.objects.filter(
            verification_status='Verified'
        ).exclude(
            transactions__status__in=active_tx_statuses
        ).order_by('-ardhisasa_last_synced')
        
    return render_react_shell(
        request,
        'parcel-list',
        'Marketplace',
        'Verified parcels available for purchase or management.',
        parcels=[serialize_parcel(parcel, request.user) for parcel in parcels],
        actions=[
            {'label': 'Legal checklist', 'href': reverse('frontend:escrow_acts'), 'tone': 'outline'},
            {'label': 'Joint laws', 'href': reverse('frontend:joint_laws'), 'tone': 'secondary'},
        ],
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
    else:
        # Agent gets restricted dashboard
        return render_agent_dashboard(request, context)


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

    context.update({
        'pending_parcels': pending_parcels,
        'completed_parcels': completed_parcels,
        'pending_transactions': pending_transactions,
        'pending_agents': pending_agents,
        'verified_agents': verified_agents,
        'pending_users': None,  # Admins don't need user approval section
    })
    recent_parcels = [serialize_parcel(parcel, request.user) for parcel in pending_parcels[:6]]
    recent_transactions = [serialize_transaction(tx, request.user) for tx in pending_transactions[:6]]
    return render_react_shell(
        request,
        'admin-dashboard',
        'Command Centre',
        'Full system access for approvals, assignments, transactions, and messaging.',
        parcels=recent_parcels,
        transactions=recent_transactions,
        stats=[
            {'label': 'Pending parcels', 'value': str(pending_parcels.count()), 'tone': 'warning'},
            {'label': 'Pending transactions', 'value': str(pending_transactions.count()), 'tone': 'accent'},
            {'label': 'Pending agents', 'value': str(pending_agents.count()), 'tone': 'danger'},
            {'label': 'Verified agents', 'value': str(verified_agents.count()), 'tone': 'success'},
        ],
        actions=[
            {'label': 'Task management', 'href': reverse('frontend:task_management'), 'tone': 'outline'},
            {'label': 'Create joint account', 'href': reverse('frontend:create_joint_group'), 'tone': 'accent'},
            {'label': 'System admin', 'href': '/admin/', 'tone': 'secondary', 'external': True},
        ],
    )


def temp_approve_agent(request, email):
    """Temporary view to approve an agent for testing purposes."""
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

    # Agents can only see their assigned parcels and completed tasks
    pending_parcels = LandParcel.objects.filter(
        assigned_agent=request.user, verification_status='Pending'
    ).order_by('-ardhisasa_last_synced')
    completed_parcels = LandParcel.objects.filter(
        assigned_agent=request.user, verification_status__in=['Verified', 'Fraudulent']
    ).order_by('-ardhisasa_last_synced')[:30]
    
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
    })
    recent_parcels = [serialize_parcel(parcel, request.user) for parcel in pending_parcels[:6]]
    recent_transactions = [serialize_transaction(tx, request.user) for tx in pending_transactions[:6]]
    return render_react_shell(
        request,
        'agent-dashboard',
        'Command Centre',
        'Your assigned pipeline for parcel verification and escrow support.',
        parcels=recent_parcels,
        transactions=recent_transactions,
        stats=[
            {'label': 'Pending parcels', 'value': str(pending_parcels.count()), 'tone': 'warning'},
            {'label': 'Pending transactions', 'value': str(pending_transactions.count()), 'tone': 'accent'},
            {'label': 'Pending users', 'value': str(pending_users.count()), 'tone': 'danger'},
            {'label': 'Completed parcels', 'value': str(completed_parcels.count()), 'tone': 'success'},
        ],
        actions=[
            {'label': 'Task management', 'href': reverse('frontend:task_management'), 'tone': 'outline'},
            {'label': 'User approvals', 'href': reverse('frontend:agent_approvals'), 'tone': 'secondary'},
        ],
    )


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
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_verify_parcel(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    if request.method == 'POST':
        action = request.POST.get('verify_action') or request.POST.get('action')
        if action == 'verify':
            parcel.verification_status = 'Verified'
        elif action == 'reject':
            parcel.verification_status = 'Fraudulent'
        parcel.save()
    return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)

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

    return render_react_shell(
        request,
        'approvals',
        'Approvals',
        'Central approvals hub for users, parcels, and transactions.',
        approvals_page={
            'pending_users': [serialize_review_user(user) for user in context['pending_users']],
            'pending_parcels': [serialize_parcel(parcel, request.user) for parcel in context['pending_parcels']],
            'pending_transactions': [serialize_transaction(tx, request.user) for tx in context['pending_transactions']],
        },
    )


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_user_review(request, user_id):
    """Agent/Admin: detailed review page for a specific user's identity."""
    from core.models import User as CoreUser

    reviewed_user = get_object_or_404(CoreUser, id=user_id)

    # Security: agents can only review Buyers/Sellers
    if reviewed_user.role in ['Admin', 'Agent']:
        from django.contrib import messages
        messages.error(request, 'You cannot review Admin or Agent accounts.')
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

    # Hard security fence — agents cannot elevate Admin or other Agent accounts
    if user.role in ['Admin', 'Agent']:
        messages.error(request, 'Permission denied: you cannot approve Admin or Agent accounts through this portal.')
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
    transaction = get_object_or_404(Transaction, id=transaction_id)
    if request.method == 'POST' and transaction.contract_agreed:
        transaction.status = 'Completed'
        transaction.save()
    return redirect('frontend:agent_dashboard')

@login_required
@user_passes_test(is_seller_or_agent, login_url='/parcels/', redirect_field_name=None)
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
def parcel_edit(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    
    if request.user != parcel.listed_by and request.user.role != 'Admin':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    if parcel.verification_status not in ['Awaiting_Documents', 'Pending', 'Disputed'] and request.user.role != 'Admin':
        # Can only edit if still pending or disputed or awaiting docs - Admins override this lock.
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    if request.method == 'POST':
        form = LandParcelUploadForm(request.POST, request.FILES, instance=parcel)
        if form.is_valid():
            form.save()
            return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)
    else:
        form = LandParcelUploadForm(instance=parcel)
        
    return render_react_shell(
        request,
        'form',
        f'Edit parcel - {parcel.parcel_number}',
        'Update parcel details before verification is finalised.',
        form=serialize_form(
            form,
            action=reverse('frontend:parcel_edit', args=[parcel.parcel_number]),
            submit_label='Save changes',
            cancel_label='Cancel',
            cancel_href=reverse('frontend:parcel_detail', args=[parcel.parcel_number]),
            intro='Parcel records can be edited while they are awaiting documents, pending, or disputed.',
        ),
    )

@login_required
def parcel_delete(request, parcel_number):
    # Strict Privilege Fencing: Only Admins can permanently delete a parcel
    if request.user.role != 'Admin':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
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
    
    # Security: Only Buyers can initiate escrow, Admins can force initiate for testing
    if request.user.role not in ['Buyer', 'Admin']:
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    if parcel.verification_status != 'Verified':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    if request.method == 'POST':
        joint_group_id = (request.POST.get('joint_group_id') or '').strip()
        purchase_mode = (request.POST.get('purchase_mode') or '').strip()

        joint_group = None
        if purchase_mode == 'joint' or joint_group_id:
            if request.user.role != 'Buyer':
                return redirect('frontend:parcel_detail', parcel_number=parcel_number)
            if not is_joint_buyer(request.user):
                from django.contrib import messages
                messages.error(request, 'Joint purchases require a joint buyer account. Choose the joint option after signup first.')
                return redirect('frontend:buyer_account_choice')
            if joint_group_id:
                joint_group = get_object_or_404(JointBuyerGroup, id=joint_group_id, leader=request.user)
                if not joint_group.is_valid:
                    from django.contrib import messages
                    messages.error(request, 'This joint group is not valid. Ensure it has at least 2 members and shares total 100%.')
                    return redirect('frontend:parcel_detail', parcel_number=parcel_number)
            if getattr(request.user, 'buyer_account_type', None) != 'Joint':
                request.user.buyer_account_type = 'Joint'
                request.user.save(update_fields=['buyer_account_type'])

        # Safely instantiate or retrieve the explicit Escrow transaction
        tx, created = Transaction.objects.get_or_create(
            land_parcel=parcel,
            buyer=request.user if request.user.role == 'Buyer' else parcel.listed_by,
            seller=parcel.listed_by,
            defaults={
                'agreed_price': parcel.displayed_price, # Securely derived from Seller limit + 10% Platform Cut
                'status': 'Under_Verification'
            }
        )

        if joint_group:
            tx.is_joint_purchase = True
            tx.joint_group = joint_group
            tx.save(update_fields=['is_joint_purchase', 'joint_group'])

        # Redirect Buyer to Payment Onboarding instead of Sign Contract
        return redirect('frontend:payment_onboarding', transaction_id=tx.id)
        
    return redirect('frontend:parcel_detail', parcel_number=parcel_number)

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

    # Get AI price estimate
    ai_price = None
    try:
        from core.services.price_prediction import predict_price
        result = predict_price(
            county=parcel.county,
            constituency=parcel.constituency,
            land_use=parcel.land_use_type,
            size_acres=float(parcel.land_size),
        )
        if 'error' not in result:
            ai_price = result
    except Exception:
        pass

    joint_groups = []
    can_use_joint_purchase = False
    if request.user.is_authenticated and request.user.role == 'Buyer':
        joint_groups = JointBuyerGroup.objects.filter(leader=request.user).prefetch_related('members')
        can_use_joint_purchase = is_joint_buyer(request.user)

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
        'displayed_price': str(parcel.displayed_price),
        'is_favorited': is_favorited,
        'ai_price': None if not ai_price else {
            'total_value': str(ai_price.get('total_value', '')),
            'price_per_acre': str(ai_price.get('price_per_acre', '')),
            'confidence_low': str(ai_price.get('confidence_low', '')),
            'confidence_high': str(ai_price.get('confidence_high', '')),
        },
        'documents': [serialize_document(doc) for doc in parcel.documents.all()],
        'can_edit': bool(request.user.is_authenticated and (request.user.role == 'Admin' or request.user == parcel.listed_by)),
        'can_upload_document': bool(request.user.is_authenticated and (request.user.role == 'Admin' or request.user == parcel.listed_by)),
        'can_initiate_escrow': bool(request.user.is_authenticated and request.user.role in ['Buyer', 'Admin'] and parcel.verification_status == 'Verified'),
        'can_use_joint_purchase': can_use_joint_purchase,
        'assigned_agent_email': parcel.assigned_agent.email if parcel.assigned_agent else None,
        'joint_groups': [serialize_joint_group(group) for group in joint_groups] if joint_groups else [],
        'purchase_modes': [
            {'value': 'individual', 'label': 'Individual purchase', 'selected': True},
            {'value': 'joint', 'label': 'Joint group purchase', 'selected': False},
        ],
        'initiate_escrow_url': reverse('frontend:initiate_escrow', args=[parcel.parcel_number]),
        'upload_document_url': reverse('frontend:upload_document', args=[parcel.parcel_number]) if request.user.is_authenticated else None,
        'edit_url': reverse('frontend:parcel_edit', args=[parcel.parcel_number]) if request.user.is_authenticated else None,
        'delete_url': reverse('frontend:parcel_delete', args=[parcel.parcel_number]) if request.user.is_authenticated and request.user.role == 'Admin' else None,
        'toggle_favorite_url': reverse('frontend:toggle_favorite', args=[parcel.parcel_number]) if request.user.is_authenticated else None,
        'agent_verify_url': reverse('frontend:agent_verify_parcel', args=[parcel.parcel_number]) if request.user.is_authenticated and request.user.role in ['Admin', 'Agent'] else None,
    }

    return render_react_shell(
        request,
        'parcel-detail',
        f'Parcel details - {parcel.parcel_number}',
        'Review parcel information, documents, and next workflow actions.',
        parcel_detail=parcel_data,
        actions=[{'label': 'Back to marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'}],
    )

@login_required
def user_transactions(request):
    if request.user.role == 'Admin':
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
            {'label': 'Legal checklist', 'href': reverse('frontend:escrow_acts'), 'tone': 'secondary'},
        ],
    )

@login_required
def messages_list(request):
    from django.db.models import Q
    from django.middleware.csrf import get_token
    from core.models import User as CoreUser
    user = request.user

    all_msgs = Message.objects.filter(Q(sender=user) | Q(receiver=user)).order_by('-timestamp')

    # Aggregate into threads keyed by counterparty
    threads = {}
    for msg in all_msgs:
        partner = msg.sender if msg.receiver == user else msg.receiver
        if partner not in threads:
            threads[partner] = []
        threads[partner].append(msg)

    # Determine who this user is ALLOWED to compose to
    # Rule: Buyers & Sellers can ONLY contact Admins/Agents
    # Rule: Admins/Agents can contact anyone
    if user.role in ['Buyer', 'Seller']:
        allowed_recipients = CoreUser.objects.filter(
            role__in=['Admin', 'Agent']
        ).exclude(id=user.id)
    else:  # Admin / Agent
        allowed_recipients = CoreUser.objects.exclude(id=user.id)

    context = {
        'allowed_recipients': [serialize_user(user) for user in allowed_recipients],
        'msg_error': request.session.pop('msg_error', None),
    }

    if user.role == 'Buyer':
        context['header'] = 'My Inbox'
        context['threads'] = [
            serialize_message_thread(partner, msgs, user)
            for partner, msgs in threads.items()
            if partner.role in ['Admin', 'Agent']
        ]
        context['mode'] = 'single'
    elif user.role == 'Seller':
        context['header'] = 'My Inbox'
        context['threads'] = [
            serialize_message_thread(partner, msgs, user)
            for partner, msgs in threads.items()
            if partner.role in ['Admin', 'Agent']
        ]
        context['mode'] = 'single'
    else:  # Admin / Agent
        context['header'] = 'Platform Communications'
        context['buyer_threads'] = [
            serialize_message_thread(partner, msgs, user)
            for partner, msgs in threads.items()
            if partner.role == 'Buyer'
        ]
        context['seller_threads'] = [
            serialize_message_thread(partner, msgs, user)
            for partner, msgs in threads.items()
            if partner.role == 'Seller'
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
def send_message(request):
    from core.models import User as CoreUser
    if request.method != 'POST':
        return redirect('frontend:messages')

    sender = request.user
    content = request.POST.get('content', '').strip()
    receiver_id = request.POST.get('receiver_id', '').strip()
    receiver_email = request.POST.get('receiver_email', '').strip()

    recipient_type = request.POST.get('recipient_type', 'single').strip()

    if not content:
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
            request.session['msg_error'] = f'No account found with email: {receiver_email}'
            return redirect('frontend:messages')

    if not receiver:
        return redirect('frontend:messages')

    # Strict mediation: Buyers and Sellers CANNOT message each other directly
    if sender.role in ['Buyer', 'Seller'] and receiver.role in ['Buyer', 'Seller']:
        request.session['msg_error'] = 'You cannot message another Buyer or Seller directly.'
        return redirect('frontend:messages')

    Message.objects.create(sender=sender, receiver=receiver, content=content)
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

@login_required
def sign_contract(request, transaction_id):
    transaction = get_object_or_404(
        Transaction.objects.select_related('buyer', 'seller', 'land_parcel', 'joint_group').prefetch_related('joint_group__members'),
        id=transaction_id,
    )
    
    # Security: Only involved parties (buyer, seller) or Admin can access
    if request.user not in [transaction.buyer, transaction.seller] and request.user.role != 'Admin':
        return redirect('frontend:transactions')
        
    if request.method == 'POST':
        # Admin-only dual signing capability
        if request.user.role == 'Admin' and request.POST.get('admin_dual_sign'):
            buyer_sig = request.POST.get('buyer_signature_data')
            seller_sig = request.POST.get('seller_signature_data')
            
            if buyer_sig:
                transaction.buyer_signature = buyer_sig
            if seller_sig:
                transaction.seller_signature = seller_sig

            if transaction.buyer_signature and transaction.seller_signature:
                transaction.contract_agreed = True
                
            transaction.save()
            if transaction.contract_agreed and request.user == transaction.buyer and transaction.status == 'Under_Verification':
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
                if transaction.buyer_signature and transaction.seller_signature and transaction.joint_group.all_signed:
                    transaction.contract_agreed = True
                    transaction.save(update_fields=['contract_agreed'])
                if transaction.contract_agreed and request.user == transaction.buyer and transaction.status == 'Under_Verification':
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
            
            if transaction.buyer_signature and transaction.seller_signature:
                if transaction.is_joint_purchase and transaction.joint_group:
                    if transaction.joint_group.all_signed:
                        transaction.contract_agreed = True
                else:
                    transaction.contract_agreed = True
                
            transaction.save()
            if transaction.contract_agreed and request.user == transaction.buyer and transaction.status == 'Under_Verification':
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
    contract_laws = [] if request.user.role == 'Admin' else LAND_TRANSACTION_LAWS

    return render_react_shell(
        request,
        'contract',
        'Kenyan Land Transfer Agreement',
        f'Property: {transaction.land_parcel.parcel_number}',
        contract=serialize_contract(
            transaction,
            request.user,
            laws=contract_laws,
            joint_breakdown=joint_breakdown,
            sign_url=reverse('frontend:sign_contract', args=[transaction.id]),
            payment_url=reverse('frontend:payment_checkout', args=[transaction.id]),
            transactions_url=reverse('frontend:transactions'),
            csrf_token=get_token(request),
        ),
    )

@login_required
def payment_onboarding(request, transaction_id):
    transaction = get_object_or_404(Transaction.objects.select_related('buyer', 'seller', 'land_parcel', 'joint_group'), id=transaction_id)
    
    # Security: Only the Buyer can pay (or Admin verifying)
    if (request.user != transaction.buyer and request.user.role != 'Admin'):
        return redirect('frontend:transactions')
        
    if transaction.status != 'Under_Verification':
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
            description=f'Payment can now be initiated for parcel {transaction.land_parcel.parcel_number}. Continue to checkout to start the escrow deposit.',
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
        
    if transaction.status != 'Under_Verification':
        return redirect('frontend:transactions')

    if not transaction.contract_agreed:
        return redirect('frontend:sign_contract', transaction_id=transaction.id)

    joint_breakdown = None
    contributions = None
    joint_bank_ready = False
    joint_payment_method = None
    if transaction.is_joint_purchase and transaction.joint_group:
        from decimal import Decimal, ROUND_HALF_UP
        total = transaction.agreed_price
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

    from django.middleware.csrf import get_token

    return render_react_shell(
        request,
        'checkout',
        'Escrow checkout',
        'Complete payment using M-Pesa or the shared joint bank account.',
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
        ),
    )

@login_required
def process_payment(request, transaction_id):
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


@login_required
def joint_groups(request):
    if not is_joint_buyer(request.user):
        if request.user.role == 'Buyer':
            from django.contrib import messages
            messages.info(request, 'Select the joint buyer account setup first to manage group purchases.')
            return redirect('frontend:buyer_account_choice')
        return redirect('frontend:home')
    groups = JointBuyerGroup.objects.filter(leader=request.user).prefetch_related('members')
    return render_react_shell(
        request,
        'joint-groups',
        'My joint groups',
        'Manage shared buyer accounts, ownership splits, and joint bank setup.',
        groups=[serialize_joint_group(group) for group in groups],
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
            messages.info(request, 'Select the joint buyer account setup first to create a group.')
            return redirect('frontend:buyer_account_choice')
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
            intro='Enter the group profile first, then add at least one co-buyer in the rows below. Shares must total 100%.',
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
    group = get_object_or_404(JointBuyerGroup.objects.prefetch_related('members'), id=group_id, leader=request.user)
    serialized_group = serialize_joint_group(group)
    return render_react_shell(
        request,
        'joint-group-detail',
        group.name,
        'Review members, ownership shares, and payment setup for the joint account.',
        group=serialized_group,
        actions=[
            {'label': 'Edit group', 'href': reverse('frontend:edit_joint_group', args=[group.id]), 'tone': 'outline'},
            {'label': 'Joint laws', 'href': reverse('frontend:joint_laws'), 'tone': 'secondary'},
        ],
    )


@login_required
def delete_joint_member(request, member_id):
    if not is_joint_buyer(request.user):
        return redirect('frontend:home')
    member = get_object_or_404(JointBuyerMember, id=member_id)
    group = member.group
    if group.leader != request.user:
        return redirect('frontend:home')
    if request.method == 'POST':
        if member.is_leader:
            return redirect('frontend:joint_group_detail', group_id=group.id)
        member.delete()
    return redirect('frontend:joint_group_detail', group_id=group.id)


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
    from core.services.recommendation import get_recommendations, get_popular_in_county, get_recently_viewed

    recommended = []
    rec_type = 'popular'
    popular_parcels = []
    popular_county = 'Nairobi'
    recently_viewed = []

    try:
        recommended, rec_type = get_recommendations(request.user, limit=12)
        popular_parcels, popular_county = get_popular_in_county(request.user, limit=6)
        recently_viewed = get_recently_viewed(request.user, limit=6)
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Recommendation error: {e}")

    return render_react_shell(
        request,
        'recommendations',
        'Recommended parcels',
        'Personalized recommendations, popular alternatives, and recently viewed parcels.',
        recommendations_page=serialize_recommendations_page(
            recommended,
            rec_type,
            popular_parcels,
            popular_county,
            recently_viewed,
            request.user,
        ),
        actions=[
            {'label': 'Marketplace', 'href': reverse('frontend:parcel_list'), 'tone': 'outline'},
            {'label': 'Price estimator', 'href': reverse('frontend:price_prediction'), 'tone': 'secondary'},
        ],
    )


@login_required
def price_prediction(request):
    """Interactive land price prediction tool."""
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
    if request.user.role not in ('Admin', 'Agent'):
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
    )
