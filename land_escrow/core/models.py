import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _

class CustomUserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError('The Email field must be set')
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self.create_user(email, password, **extra_fields)

import re
from django.core.validators import RegexValidator

class User(AbstractUser):
    ROLE_CHOICES = [
        ('Buyer', 'Buyer'),
        ('Seller', 'Seller'),
        ('Agent', 'Agent'),
        ('Land_Official', 'Land Official'),
        ('Admin', 'Admin'),
    ]
    BUYER_ACCOUNT_TYPE_CHOICES = [
        ('Individual', 'Individual'),
        ('Joint', 'Joint'),
    ]

    phone_regex = RegexValidator(
        regex=r'^(\+254|0)\d{9}$',
        message='Phone number must start with +254 or 0 and have 10 digits total (e.g. +254712345678 or 0712345678).'
    )
    id_number_regex = RegexValidator(
        regex=r'^\d{7,9}$',
        message='ID number must be 7, 8, or 9 digits.'
    )
    kra_pin_regex = RegexValidator(
        regex=r'^[A-Z]\d{9}[A-Z]$',
        message='KRA PIN must be 11 characters: Letter + 9 digits + Letter (e.g. A123456789B).'
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(_('email address'), unique=True)
    id_number = models.CharField(max_length=50, db_index=True, validators=[id_number_regex])
    phone_number = models.CharField(max_length=20, validators=[phone_regex])
    kra_pin = models.CharField(max_length=11, validators=[kra_pin_regex], help_text='KRA PIN e.g. A123456789B')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
    buyer_account_type = models.CharField(
        max_length=20,
        choices=BUYER_ACCOUNT_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text='Buyer onboarding choice: individual or joint purchase mode.',
    )
    is_identity_verified = models.BooleanField(default=False)
    gavakonect_verification_id = models.CharField(max_length=100, blank=True, null=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = CustomUserManager()

    @property
    def average_rating(self):
        """Calculate average rating for this agent"""
        if self.role != 'Agent':
            return None
        ratings = self.ratings.all()
        if ratings.exists():
            return round(sum(r.rating for r in ratings) / ratings.count(), 1)
        return None

    @property
    def total_tasks_completed(self):
        """Count completed tasks for this agent"""
        if self.role != 'Agent':
            return 0
        from .models import LandParcel
        return LandParcel.objects.filter(
            assigned_agent=self, 
            verification_status__in=['Verified', 'Fraudulent']
        ).count()

    def __str__(self):
        return self.email


class AgentRating(models.Model):
    """Store performance ratings for agents"""
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings', limit_choices_to={'role': 'Agent'})
    rating = models.IntegerField(choices=[(i, f'{i} Stars') for i in range(1, 6)], help_text='Rating from 1-5 stars')
    review = models.TextField(help_text='Performance review comments')
    rated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_ratings')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.agent.email} - {self.rating} stars'


class AgentKYCApplication(models.Model):
    """Stores KYC submission details for Agent applicants awaiting admin approval."""
    STATUS_CHOICES = [
        ('Pending', 'Pending Review'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    agent = models.OneToOneField(
        User, on_delete=models.CASCADE,
        related_name='kyc_application',
        limit_choices_to={'role': 'Agent'}
    )
    kra_pin = models.CharField(max_length=20, help_text='Kenya Revenue Authority PIN')
    id_number = models.CharField(max_length=20, help_text='National ID or Passport Number')
    id_photo = models.FileField(upload_to='kyc/id_photos/', help_text='Scanned copy of National ID / Passport')
    resume = models.FileField(upload_to='kyc/resumes/', help_text='Current CV / Resume (PDF)')
    certificate_of_good_conduct = models.FileField(
        upload_to='kyc/conduct_certs/',
        help_text='DCI Certificate of Good Conduct (PDF)'
    )
    practicing_certificate = models.FileField(
        upload_to='kyc/practicing_certs/',
        blank=True, null=True,
        help_text='LSK / Real Estate Board Practicing Certificate (if applicable)'
    )
    kyc_submitted = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='Pending')
    submitted_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return f'KYC: {self.agent.email} [{self.status}]'


class LandParcel(models.Model):
    LAND_USE_CHOICES = [
        ('Residential', 'Residential'),
        ('Commercial', 'Commercial'),
        ('Agricultural', 'Agricultural'),
    ]
    VERIFICATION_STATUS_CHOICES = [
        ('Awaiting_Documents', 'Awaiting Documents'),
        ('Pending', 'Pending'),
        ('Verified', 'Verified'),
        ('Disputed', 'Disputed'),
        ('Fraudulent', 'Fraudulent'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcel_number = models.CharField(max_length=100, unique=True, db_index=True)
    land_use_type = models.CharField(max_length=20, choices=LAND_USE_CHOICES)
    county = models.CharField(max_length=100, default='Nairobi')
    constituency = models.CharField(max_length=100)
    ward = models.CharField(max_length=100)
    land_size = models.DecimalField(max_digits=10, decimal_places=4)
    registered_owner_id = models.CharField(max_length=100, help_text="ID number of registered owner")
    verification_status = models.CharField(max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='Pending')
    ardhisasa_last_synced = models.DateTimeField(null=True, blank=True)
    current_risk_score = models.FloatField(default=0.0)
    image = models.ImageField(upload_to='land_images/', null=True, blank=True, help_text="Upload a photo of the land")
    listed_by = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='listed_parcels', help_text="The seller who listed this parcel")
    assigned_agent = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='assigned_parcels',
        limit_choices_to={'role': 'Agent', 'is_identity_verified': True},
        help_text="The verified agent assigned to review this parcel"
    )
    asking_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text="Seller's absolute asking price")
    lowest_negotiable_price = models.DecimalField(max_digits=15, decimal_places=2, null=True, blank=True, help_text="Hidden bottom limit for auto-negotiation")

    @property
    def displayed_price(self):
        from decimal import Decimal
        if self.asking_price:
            return self.asking_price * Decimal('1.10')
        return Decimal('0.00')

    def __str__(self):
        return self.parcel_number

class Transaction(models.Model):
    STATUS_CHOICES = [
        ('Initiated', 'Initiated'),
        ('Deposit_Paid', 'Deposit Paid'),
        ('Under_Verification', 'Under Verification'),
        ('Verification_Hiatus', 'Verification Hiatus'),
        ('Completed', 'Completed'),
        ('Disputed', 'Disputed'),
        ('Refunded', 'Refunded'),
        ('Reversed', 'Reversed by Admin'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buying_transactions')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='selling_transactions')
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_transactions')
    land_parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='transactions')
    agreed_price = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Initiated')
    escrow_reference = models.CharField(max_length=100, blank=True, null=True)
    
    buyer_signature = models.TextField(null=True, blank=True, help_text="Base64 encoded cryptographic signature graphic of the buyer")
    seller_signature = models.TextField(null=True, blank=True, help_text="Base64 encoded cryptographic signature graphic of the seller")
    contract_agreed = models.BooleanField(default=False, help_text="Has the contract been fully signed by both parties?")
    
    # 7-Day Buyer Validation Protocol
    buyer_validation_deadline = models.DateTimeField(null=True, blank=True, help_text="Deadline by which buyer must confirm or disputes ownership. Funds are fully refundable until this date.")
    buyer_accepted = models.BooleanField(null=True, blank=True, help_text="True=buyer confirmed legitimacy, False=buyer disputed/requested refund, None=still in validation window")
    
    # Land Verification Fields
    land_verification_started = models.DateTimeField(null=True, blank=True, help_text="When land verification process started")
    land_verified = models.BooleanField(default=False, help_text="Whether land location and details have been verified")
    land_verification_notes = models.TextField(blank=True, null=True, help_text="Notes from land verification process")
    verification_agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_transactions', help_text="Agent who verified the land details")
    
    # Payment Reversal Fields
    reversal_reason = models.TextField(blank=True, null=True, help_text="Reason for payment reversal")
    reversal_initiated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='reversed_transactions', help_text="Admin who initiated the reversal")
    reversal_initiated_at = models.DateTimeField(null=True, blank=True, help_text="When reversal was initiated")
    reversal_reference = models.CharField(max_length=100, blank=True, null=True, help_text="Reference number for the reversal transaction")
    
    # Joint Purchase Fields
    is_joint_purchase = models.BooleanField(default=False, help_text="Whether this is a joint/group purchase")
    joint_group = models.ForeignKey('JointBuyerGroup', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='transactions', help_text="The joint buyer group for group purchases")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id} - {self.status}"
    
    @property
    def is_in_verification_hiatus(self):
        """Check if transaction is in the 7-day verification hiatus period"""
        from django.utils import timezone
        return (
            self.status == 'Verification_Hiatus' and 
            self.land_verification_started and 
            self.land_verification_started < timezone.now() < self.buyer_validation_deadline
        )
    
    @property
    def verification_deadline_passed(self):
        """Check if the 7-day verification deadline has passed"""
        from django.utils import timezone
        return self.buyer_validation_deadline and self.buyer_validation_deadline < timezone.now()
    
    @property
    def days_remaining_for_verification(self):
        """Calculate days remaining in verification period"""
        from django.utils import timezone
        if self.buyer_validation_deadline:
            remaining = self.buyer_validation_deadline - timezone.now()
            return max(0, remaining.days)
        return 0
    
    def start_verification_hiatus(self):
        """Start the 7-day verification hiatus period"""
        from django.utils import timezone
        from datetime import timedelta
        
        if not self.land_verification_started:
            self.land_verification_started = timezone.now()
            self.buyer_validation_deadline = timezone.now() + timedelta(days=7)
            self.status = 'Verification_Hiatus'
            self.save()
    
    def complete_verification(self, verification_agent, notes=""):
        """Complete land verification and end hiatus period"""
        self.land_verified = True
        self.verification_agent = verification_agent
        self.land_verification_notes = notes
        self.status = 'Under_Verification'
        self.save()
    
    def reverse_payment(self, admin_user, reason=""):
        """Initiate payment reversal by admin"""
        from .services.payment import reverse_escrow_payment
        from django.utils import timezone
        import uuid
        
        # Only allow reversal for transactions with paid deposits
        if self.status not in ['Deposit_Paid', 'Under_Verification', 'Verification_Hiatus']:
            raise ValueError("Cannot reverse payment for transaction in status: {}".format(self.status))
        
        # Generate reversal reference
        self.reversal_reference = f"REV-{uuid.uuid4().hex[:12].upper()}"
        self.reversal_reason = reason
        self.reversal_initiated_by = admin_user
        self.reversal_initiated_at = timezone.now()
        
        # Initiate actual reversal via payment service
        reversal_result = reverse_escrow_payment(self, reason)
        
        if reversal_result.get("status") == "success":
            self.status = 'Reversed'
            self.save()
            
            # Log the successful reversal
            from .models import AuditLog
            AuditLog.objects.create(
                user=admin_user,
                action=f"Payment reversal initiated for transaction {self.id}",
                metadata={
                    'reversal_reference': self.reversal_reference,
                    'amount': float(self.agreed_price),
                    'reason': reason,
                    'payment_reversal_id': reversal_result.get('reversal_reference')
                }
            )
            
            return self.reversal_reference
        else:
            # If reversal failed, don't change status but log the attempt
            self.save()
            
            # Log the failed reversal attempt
            from .models import AuditLog
            AuditLog.objects.create(
                user=admin_user,
                action=f"Failed payment reversal attempt for transaction {self.id}",
                metadata={
                    'reversal_reference': self.reversal_reference,
                    'amount': float(self.agreed_price),
                    'reason': reason,
                    'error': reversal_result.get('message', 'Unknown error')
                }
            )
            
            raise Exception(f"Payment reversal failed: {reversal_result.get('message', 'Unknown error')}")

class Document(models.Model):
    DOC_TYPE_CHOICES = [
        ('Title_Deed', 'Title Deed'),
        ('ID_Card', 'ID Card'),
        ('Passport_Photo', 'Passport Photo'),
        ('Sale_Agreement', 'Sale Agreement'),
        ('Spousal_Consent', 'Spousal Consent Affidavit'),
        ('Land_Search', 'Land Search Certificate'),
        ('Land_Rates_Clearance', 'Land Rates Clearance'),
        ('Land_Rent_Clearance', 'Land Rent Clearance'),
        ('Survey_Plan', 'Survey Plan / Mutation Form'),
        ('Consent_To_Transfer', 'Land Control Board Consent'),
        ('Stamp_Duty_Receipt', 'Stamp Duty Receipt'),
        ('Valuation_Report', 'Valuation Report'),
    ]
    VERIFICATION_STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Match', 'Match'),
        ('Mismatch', 'Mismatch'),
        ('Forgery_Suspected', 'Forgery Suspected'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_documents')
    land_parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    document_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    file_url = models.FileField(upload_to='documents/')
    verification_status = models.CharField(max_length=25, choices=VERIFICATION_STATUS_CHOICES, default='Pending')
    fraud_flag_notes = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.document_type} - {self.id}"

class AuditLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=255)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    metadata = models.JSONField(blank=True, null=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.action} at {self.timestamp}"

class SupportTicket(models.Model):
    STATUS_CHOICES = [
        ('Open', 'Open'),
        ('In_Progress', 'In Progress'),
        ('Resolved', 'Resolved'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Ticket {self.subject} by {self.user.email}"

class Message(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"From {self.sender.email} to {self.receiver.email}"


class ParcelView(models.Model):
    """Tracks parcel detail page views for the recommendation engine."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='parcel_views')
    parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='views')
    viewed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-viewed_at']

    def __str__(self):
        return f"{self.user.email} viewed {self.parcel.parcel_number}"


class UserFavorite(models.Model):
    """Explicit save/favorite signal for the recommendation engine."""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='favorited_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('user', 'parcel')
        ordering = ['-saved_at']

    def __str__(self):
        return f"{self.user.email} saved {self.parcel.parcel_number}"


class JointBuyerGroup(models.Model):
    """A group of co-buyers purchasing land jointly (chama, couple, family, etc.)."""
    GROUP_TYPE_CHOICES = [
        ('Couple', 'Couple'),
        ('Chama', 'Chama / Investment Group'),
        ('Family', 'Family Trust'),
        ('Investment_Group', 'Investment Group'),
    ]
    OWNERSHIP_TYPE_CHOICES = [
        ('Joint_Tenancy', 'Joint Tenancy (spouses only or with court leave)'),
        ('Tenancy_In_Common', 'Tenancy in Common (recommended for most group purchases)'),
    ]
    PAYMENT_METHOD_CHOICES = [
        ('M_Pesa_Split', 'M-Pesa Split Contributions'),
        ('Joint_Bank_Account', 'Joint Bank Account'),
        ('Leader_Managed', 'Leader Manages Payment'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=200, help_text="Group or chama name (e.g. 'Wanjiku Family Trust')")
    group_type = models.CharField(max_length=20, choices=GROUP_TYPE_CHOICES)
    ownership_type = models.CharField(max_length=20, choices=OWNERSHIP_TYPE_CHOICES, default='Tenancy_In_Common')
    preferred_payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default='M_Pesa_Split',
        help_text="Preferred payment method for the joint checkout flow.",
    )
    bank_name = models.CharField(max_length=120, blank=True, null=True, help_text="Bank name for the joint account")
    bank_account_name = models.CharField(max_length=150, blank=True, null=True, help_text="Account name as held at the bank")
    bank_account_number = models.CharField(max_length=50, blank=True, null=True, help_text="Joint bank account number")
    bank_branch = models.CharField(max_length=100, blank=True, null=True, help_text="Branch where the account is held")
    leader = models.ForeignKey(User, on_delete=models.CASCADE, related_name='led_joint_groups',
                               limit_choices_to={'role': 'Buyer'},
                               help_text="The registered Buyer who manages this group")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_group_type_display()})"

    @property
    def total_share(self):
        """Sum of all member shares — must equal 100 for a valid group."""
        return sum(m.share_percentage for m in self.members.all())

    @property
    def is_valid(self):
        """Group is valid when shares total 100% and has at least 2 members."""
        return self.members.count() >= 2 and self.total_share == 100

    @property
    def all_signed(self):
        """True when every member has provided their signature."""
        return self.members.count() > 0 and all(m.has_signed for m in self.members.all())


class JointBuyerMember(models.Model):
    """Individual member within a joint buyer group."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(JointBuyerGroup, on_delete=models.CASCADE, related_name='members')
    full_name = models.CharField(max_length=200, help_text="Full legal name as per National ID")
    id_number = models.CharField(max_length=20, help_text="National ID number")
    kra_pin = models.CharField(max_length=11, help_text="KRA PIN (e.g. A123456789B)")
    phone_number = models.CharField(max_length=20, help_text="Phone number for M-PESA payments")
    email = models.EmailField(blank=True, null=True, help_text="Optional email for notifications")
    share_percentage = models.DecimalField(max_digits=5, decimal_places=2, help_text="Ownership share (must total 100% per group)")
    signature = models.TextField(null=True, blank=True, help_text="Base64 encoded drawn signature")
    has_signed = models.BooleanField(default=False)
    is_leader = models.BooleanField(default=False, help_text="Whether this member is the registered group leader")
    added_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-is_leader', 'added_at']

    def __str__(self):
        return f"{self.full_name} ({self.share_percentage}%)"


class JointPaymentContribution(models.Model):
    """Tracks individual contributions for a joint purchase (split payments)."""
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('STK_Pushed', 'STK Push Sent'),
        ('Bank_Submitted', 'Bank Transfer Submitted'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
    ]
    PAYMENT_CHANNEL_CHOICES = [
        ('M_Pesa', 'M-Pesa STK'),
        ('Bank_Transfer', 'Joint Bank Transfer'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='joint_contributions')
    member = models.ForeignKey(JointBuyerMember, on_delete=models.SET_NULL, null=True, blank=True, related_name='contributions')
    amount = models.DecimalField(max_digits=14, decimal_places=2)
    payment_channel = models.CharField(max_length=20, choices=PAYMENT_CHANNEL_CHOICES, default='M_Pesa')
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    checkout_request_id = models.CharField(max_length=100, blank=True, null=True)
    mpesa_receipt = models.CharField(max_length=100, blank=True, null=True)
    bank_reference = models.CharField(max_length=100, blank=True, null=True)
    depositor_name = models.CharField(max_length=150, blank=True, null=True)
    bank_name = models.CharField(max_length=120, blank=True, null=True)
    bank_account_number = models.CharField(max_length=50, blank=True, null=True)
    bank_account_name = models.CharField(max_length=150, blank=True, null=True)
    bank_branch = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        member_label = self.member.full_name if self.member else "Leader/Full"
        channel = "Bank" if self.payment_channel == 'Bank_Transfer' else "M-Pesa"
        return f"{self.transaction_id} {member_label} {self.amount} ({channel}, {self.status})"
