from django.shortcuts import render, get_object_or_404, redirect
from django.urls import reverse
from django.contrib.auth.decorators import login_required, user_passes_test
from core.models import LandParcel, Transaction, Message, SupportTicket, Document, User as CoreUser, AgentKYCApplication, AgentRating
from .forms import LandParcelUploadForm
from core.forms import DocumentUploadForm

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
    
    context = {
        'parcels': parcels,
        'transactions': transactions
    }
    return render(request, 'frontend/index.html', context)

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

    return render(request, 'frontend/staff_login.html', {
        'error': error,
        'signup_success': signup_success,
    })

def parcel_list(request):
    from django.db.models import Q
    active_tx_statuses = ['Initiated', 'Deposit_Paid', 'Under_Verification', 'Completed']
    
    if request.user.is_authenticated and request.user.role in ['Seller', 'Agent', 'Admin']:
        # Show the Seller's unsold properties PLUS the generic Verified unsold marketplace
        parcels = LandParcel.objects.filter(
            Q(listed_by=request.user) | Q(verification_status='Verified')
        ).exclude(
            transactions__status__in=active_tx_statuses
        ).distinct().order_by('-ardhisasa_last_synced')
    else:
        # Strict Public Marketplace (Guests & Buyers ONLY see Verified, Available Land)
        parcels = LandParcel.objects.filter(
            verification_status='Verified'
        ).exclude(
            transactions__status__in=active_tx_statuses
        ).order_by('-ardhisasa_last_synced')
        
    return render(request, 'frontend/parcel_list.html', {'parcels': parcels})

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

    return render(request, 'frontend/agent_kyc.html', {'form': form})


@login_required
def agent_onboarding(request):
    if request.user.role != 'Agent':
        return redirect('frontend:home')
    # Pass the approval state to the template
    # - approved=True  → shows "Use Staff Login" message
    # - approved=False → shows "Awaiting admin review" spinner
    return render(request, 'frontend/agent_onboarding.html', {
        'approved': request.user.is_identity_verified,
    })

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
    return render(request, 'frontend/admin_dashboard.html', context)


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
        
        return render(request, 'frontend/temp_approve.html', {
            'agent': agent,
            'success': True
        })
    except CoreUser.DoesNotExist:
        return render(request, 'frontend/temp_approve.html', {
            'success': False,
            'error': f'No agent found with email: {email}'
        })
    except Exception as e:
        return render(request, 'frontend/temp_approve.html', {
            'success': False,
            'error': str(e)
        })


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
    return render(request, 'frontend/agent_dashboard_restricted.html', context)


@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def task_management(request):
    """Dedicated task management page: assign/reassign/unassign parcels + view allocated/completed."""
    from core.models import User as CoreUser

    if request.user.role != 'Admin':
        # Agents see their own pipeline view
        pending_parcels = LandParcel.objects.filter(
            assigned_agent=request.user, verification_status='Pending'
        ).order_by('-ardhisasa_last_synced')
        completed_parcels = LandParcel.objects.filter(
            assigned_agent=request.user, verification_status__in=['Verified', 'Fraudulent']
        ).order_by('-ardhisasa_last_synced')[:30]
        return render(request, 'frontend/task_management.html', {
            'pending_parcels': pending_parcels,
            'completed_parcels': completed_parcels,
        })

    # Admin view
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

    return render(request, 'frontend/task_management.html', {
        'all_pending_parcels': all_pending_parcels,
        'unassigned_count': len(unassigned_parcels),
        'verified_agents': verified_agents,
        'completed_parcels': completed_parcels,
    })

@login_required
@user_passes_test(is_verified_agent_or_admin, login_url='/agent/onboarding/')
def agent_verify_parcel(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    if request.method == 'POST':
        action = request.POST.get('action')
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
def agent_approve_user(request, user_id):
    """Agent/Admin: approve identity of a Buyer or Seller user (NOT Admin / Agent accounts)."""
    from core.models import User as CoreUser
    from django.contrib import messages

    if request.method != 'POST':
        return redirect('frontend:agent_dashboard')

    user = get_object_or_404(CoreUser, id=user_id)

    # Hard security fence — agents cannot elevate Admin or other Agent accounts
    if user.role in ['Admin', 'Agent']:
        messages.error(request, 'Permission denied: you cannot approve Admin or Agent accounts through this portal.')
        return redirect('frontend:agent_dashboard')

    user.is_identity_verified = True
    user.is_active = True
    user.save()
    messages.success(request, f'{user.role} account {user.email} has been verified and approved.')
    return redirect('frontend:agent_dashboard')



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
    return render(request, 'frontend/parcel_upload.html', {'form': form})

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
                
            return redirect('frontend:parcel_detail', parcel_number=parcel.parcel_number)
    else:
        form = DocumentUploadForm()
        
    return render(request, 'frontend/document_upload.html', {'form': form, 'parcel': parcel})

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
        
    return render(request, 'frontend/parcel_edit.html', {'form': form, 'parcel': parcel})

@login_required
def parcel_delete(request, parcel_number):
    # Strict Privilege Fencing: Only Admins can permanently delete a parcel
    if request.user.role != 'Admin':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    if request.method == 'POST':
        parcel.delete()
        return redirect('frontend:parcel_list')
        
    return render(request, 'frontend/parcel_confirm_delete.html', {'parcel': parcel})

@login_required
def initiate_escrow(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    
    # Security: Only Buyers can initiate escrow, Admins can force initiate for testing
    if request.user.role not in ['Buyer', 'Admin']:
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    if parcel.verification_status != 'Verified':
        return redirect('frontend:parcel_detail', parcel_number=parcel_number)
        
    if request.method == 'POST':
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
        # Instantly slingshot the Buyer into the Cryptographic Signatures terminal
        return redirect('frontend:sign_contract', transaction_id=tx.id)
        
    return redirect('frontend:parcel_detail', parcel_number=parcel_number)

def parcel_detail(request, parcel_number):
    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)
    return render(request, 'frontend/parcel_detail.html', {'parcel': parcel})

@login_required
def user_transactions(request):
    if request.user.role == 'Admin':
        transactions = Transaction.objects.all().order_by('-created_at')
    else:
        transactions = (
            Transaction.objects.filter(buyer=request.user) |
            Transaction.objects.filter(seller=request.user)
        ).order_by('-created_at')
    return render(request, 'frontend/transactions.html', {'transactions': transactions})

@login_required
def messages_list(request):
    from django.db.models import Q
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
        'allowed_recipients': allowed_recipients,
        'msg_error': request.session.pop('msg_error', None),
    }

    if user.role == 'Buyer':
        context['header'] = 'My Inbox'
        context['threads'] = {p: msgs for p, msgs in threads.items() if p.role in ['Admin', 'Agent']}
        context['mode'] = 'single'
    elif user.role == 'Seller':
        context['header'] = 'My Inbox'
        context['threads'] = {p: msgs for p, msgs in threads.items() if p.role in ['Admin', 'Agent']}
        context['mode'] = 'single'
    else:  # Admin / Agent
        context['header'] = 'Platform Communications'
        context['buyer_threads'] = {p: msgs for p, msgs in threads.items() if p.role == 'Buyer'}
        context['seller_threads'] = {p: msgs for p, msgs in threads.items() if p.role == 'Seller'}
        context['mode'] = 'dual'

    return render(request, 'frontend/messages.html', context)


@login_required
def send_message(request):
    from core.models import User as CoreUser
    if request.method != 'POST':
        return redirect('frontend:messages')

    sender = request.user
    content = request.POST.get('content', '').strip()
    receiver_id = request.POST.get('receiver_id', '').strip()
    receiver_email = request.POST.get('receiver_email', '').strip()

    if not content:
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
    tickets = SupportTicket.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'frontend/support.html', {'tickets': tickets})

@login_required
def sign_contract(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    
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
                transaction.contract_agreed = True
                
            transaction.save()
            return redirect('frontend:sign_contract', transaction_id=transaction.id)
            
    return render(request, 'frontend/contract.html', {'transaction': transaction})

@login_required
def payment_onboarding(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    
    # Security: Only the Buyer can pay (or Admin verifying), and only if contract is signed
    if (request.user != transaction.buyer and request.user.role != 'Admin') or not transaction.contract_agreed:
        return redirect('frontend:transactions')
        
    if transaction.status != 'Under_Verification':
        return redirect('frontend:transactions')
        
    return render(request, 'frontend/payment_onboarding.html', {'transaction': transaction})

@login_required
def payment_checkout(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    
    if (request.user != transaction.buyer and request.user.role != 'Admin') or not transaction.contract_agreed:
        return redirect('frontend:transactions')
        
    if transaction.status != 'Under_Verification':
        return redirect('frontend:transactions')
        
    return render(request, 'frontend/checkout.html', {'transaction': transaction})

@login_required
def process_payment(request, transaction_id):
    transaction = get_object_or_404(Transaction, id=transaction_id)
    
    if request.method == 'POST' and (request.user == transaction.buyer or request.user.role == 'Admin'):
        if transaction.contract_agreed and transaction.status == 'Under_Verification':
            # Simulate a successful Paystack / M-PESA API call processing the deposit
            transaction.status = 'Deposit_Paid'
            import uuid
            transaction.escrow_reference = f"ESC-{str(uuid.uuid4())[:8].upper()}"
            transaction.save()
            return redirect('frontend:transactions')
            
    return redirect('frontend:payment_checkout', transaction_id=transaction.id)


@login_required
@user_passes_test(lambda u: u.role == 'Admin', login_url='/agent/onboarding/')
def rate_agent(request, agent_id):
    """Admin-only: rate an agent's performance."""
    from core.utils import send_agent_rating_notification
    
    if request.method != 'POST':
        return redirect('frontend:agent_dashboard')
    
    agent = get_object_or_404(CoreUser, id=agent_id, role='Agent')
    
    if request.method == 'POST':
        rating = request.POST.get('rating')
        review = request.POST.get('review', '').strip()
        
        if rating and rating.isdigit() and 1 <= int(rating) <= 5:
            AgentRating.objects.create(
                agent=agent,
                rating=int(rating),
                review=review,
                rated_by=request.user
            )
            
            # Send rating notification email
            email_sent, email_message = send_agent_rating_notification(agent, int(rating), review)
            
            from django.contrib import messages
            if email_sent:
                messages.success(request, f'Rated {agent.email} with {rating} stars! Rating notification sent.')
            else:
                messages.success(request, f'Rated {agent.email} with {rating} stars! Email failed: {email_message}')
        else:
            from django.contrib import messages
            messages.error(request, 'Invalid rating. Please provide a rating between 1-5.')
        
        return redirect('frontend:agent_dashboard')
    
    return render(request, 'frontend/rate_agent.html', {'agent': agent})


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
