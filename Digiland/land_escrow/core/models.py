import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.conf import settings

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
        ('Lawyer', 'Lawyer'),
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
    id_number = models.CharField(max_length=50, db_index=True, validators=[id_number_regex], blank=True, null=True)
    phone_number = models.CharField(max_length=20, validators=[phone_regex], blank=True, null=True)
    kra_pin = models.CharField(max_length=11, validators=[kra_pin_regex], help_text='KRA PIN e.g. A123456789B', blank=True, null=True)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, blank=True, null=True)
    is_onboarded = models.BooleanField(default=False)
    buyer_account_type = models.CharField(
        max_length=20,
        choices=BUYER_ACCOUNT_TYPE_CHOICES,
        blank=True,
        null=True,
        help_text='Buyer onboarding choice: individual or joint purchase mode.',
    )
    is_identity_verified = models.BooleanField(default=False)
    is_email_verified = models.BooleanField(default=False, help_text='Whether the user has verified their email address (distinct from identity verification via KRA PIN/ID)')
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
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='ratings', limit_choices_to={'role': 'Agent'})
    rating = models.IntegerField(choices=[(i, f'{i} Stars') for i in range(1, 6)], help_text='Rating from 1-5 stars')
    review = models.TextField(help_text='Performance review comments')
    rated_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='given_ratings')
    created_at = models.DateTimeField(auto_now_add=True)
    
    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f'{self.agent.email} - {self.rating} stars'


class AgentKYCApplication(models.Model):
    """Stores KYC submission details for Agent applicants awaiting admin approval."""
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
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

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    def __str__(self):
        return f'KYC: {self.agent.email} [{self.status}]'


class KYCProfile(models.Model):
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='kyc_profile')
    status = models.CharField(max_length=20, choices=[
        ('PENDING', 'Pending'), ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'), ('FLAGGED_FOR_REVIEW', 'Flagged for Review'),
        ('LOCKED', 'Locked / Fraud')
    ], default='PENDING')
    
    # Extracted OCR Data
    id_number = models.CharField(max_length=100, db_index=True, blank=True, null=True)
    id_number_hash = models.CharField(max_length=128, db_index=True, blank=True, null=True)
    full_name = models.CharField(max_length=200, blank=True, null=True)
    date_of_birth = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    
    # Biometrics stored as JSON array of floats instead of pgvector
    face_embedding = models.JSONField(null=True, blank=True)
    liveness_score = models.FloatField(default=0.0)
    
    # Audit & Files
    id_front_image = models.FileField(upload_to='kyc/secure/id/', blank=True, null=True)
    selfie_image = models.FileField(upload_to='kyc/secure/selfie/', blank=True, null=True)
    audit_log = models.JSONField(default=dict, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    def __str__(self):
        return f"KYCProfile for {self.user.email} - {self.status}"


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

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
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
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Geospatial latitude")
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True, help_text="Geospatial longitude")
    dist_to_road = models.FloatField(default=0.5, help_text="Distance to closest road in km")
    dist_to_school = models.FloatField(default=1.5, help_text="Distance to closest school in km")
    dist_to_hospital = models.FloatField(default=2.0, help_text="Distance to closest hospital in km")
    dist_to_mall = models.FloatField(default=5.0, help_text="Distance to closest mall in km")
    dist_to_industrial_zone = models.FloatField(default=8.0, help_text="Distance to closest industrial zone in km")
    dist_to_transport_hub = models.FloatField(default=3.0, help_text="Distance to closest transport hub in km")

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    @property
    def displayed_price(self):
        from decimal import Decimal
        if self.asking_price:
            return self.asking_price * Decimal('1.10')
        return Decimal('0.00')

    class Meta:
        indexes = [
            models.Index(fields=['tenant_id', 'verification_status', 'county'], name='idx_lp_tenant_vsts_county'),
            models.Index(fields=['tenant_id', 'listed_by'], name='idx_lp_tenant_listed_by'),
            models.Index(fields=['tenant_id', 'asking_price'], name='idx_lp_tenant_ask_price'),
            models.Index(fields=['tenant_id', 'land_use_type', 'county'], name='idx_lp_tenant_lut_county'),
        ]

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

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    buyer = models.ForeignKey(User, on_delete=models.CASCADE, related_name='buying_transactions')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='selling_transactions')
    agent = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='agent_transactions')
    land_parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='transactions')
    agreed_price = models.DecimalField(max_digits=14, decimal_places=2)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Initiated')
    escrow_reference = models.CharField(max_length=100, blank=True, null=True)
    platform_service_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    escrow_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    processing_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    legal_verification_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    due_diligence_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0.00)
    include_legal_verification = models.BooleanField(default=False)
    include_due_diligence = models.BooleanField(default=False)
    total_payable = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    
    buyer_signature = models.TextField(null=True, blank=True, help_text="Base64 encoded cryptographic signature graphic of the buyer")
    seller_signature = models.TextField(null=True, blank=True, help_text="Base64 encoded cryptographic signature graphic of the seller")
    lawyer_signature = models.TextField(null=True, blank=True, help_text="Base64 encoded cryptographic signature graphic of the LSK verified lawyer")
    lawyer_name = models.CharField(max_length=200, null=True, blank=True, help_text="Full name of the LSK verified lawyer")
    lawyer_lsk_number = models.CharField(max_length=100, null=True, blank=True, help_text="LSK Admission Number of the lawyer")
    lawyer_signed_at = models.DateTimeField(null=True, blank=True, help_text="Timestamp when the lawyer signed the transaction")
    contract_agreed = models.BooleanField(default=False, help_text="Has the contract been fully signed by all parties?")
    
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

    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        indexes = [
            models.Index(fields=['tenant_id', 'buyer', 'status'], name='idx_txn_tenant_buyer_sts'),
            models.Index(fields=['tenant_id', 'seller', 'status'], name='idx_txn_tenant_seller_sts'),
            models.Index(fields=['tenant_id', 'status'], name='idx_txn_tenant_status'),
            models.Index(fields=['tenant_id', 'created_at'], name='idx_txn_tenant_crt_at'),
        ]

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

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='uploaded_documents')
    land_parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='documents', null=True, blank=True)
    document_type = models.CharField(max_length=30, choices=DOC_TYPE_CHOICES)
    file_url = models.FileField(upload_to='documents/')
    verification_status = models.CharField(max_length=25, choices=VERIFICATION_STATUS_CHOICES, default='Pending')
    fraud_flag_notes = models.TextField(blank=True, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        indexes = [
            models.Index(fields=['tenant_id', 'land_parcel', 'verification_status'], name='idx_doc_tenant_pcl_vsts'),
        ]

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
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='support_tickets')
    subject = models.CharField(max_length=255)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Open')
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    def __str__(self):
        return f"Ticket {self.subject} by {self.user.email}"

class Message(models.Model):
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_messages')
    transaction = models.ForeignKey(Transaction, on_delete=models.CASCADE, related_name='messages', null=True, blank=True)
    content = models.TextField()
    is_read = models.BooleanField(default=False)
    timestamp = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    def __str__(self):
        return f"From {self.sender.email} to {self.receiver.email}"


class ParcelView(models.Model):
    """Tracks parcel detail page views for the recommendation engine."""
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='parcel_views')
    parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='views')
    viewed_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-viewed_at']
        indexes = [
            models.Index(fields=['tenant_id', 'user', 'parcel', 'viewed_at'], name='idx_pv_tenant_usr_parcel'),
        ]

    def __str__(self):
        return f"{self.user.email} viewed {self.parcel.parcel_number}"


class UserFavorite(models.Model):
    """Explicit save/favorite signal for the recommendation engine."""
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='favorites')
    parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='favorited_by')
    saved_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        unique_together = ('user', 'parcel')
        ordering = ['-saved_at']
        indexes = [
            models.Index(fields=['tenant_id', 'user', 'parcel'], name='idx_uf_tenant_usr_parcel'),
        ]

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

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
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

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
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
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
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

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
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

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
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

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        member_label = self.member.full_name if self.member else "Leader/Full"
        channel = "Bank" if self.payment_channel == 'Bank_Transfer' else "M-Pesa"
        return f"{self.transaction_id} {member_label} {self.amount} ({channel}, {self.status})"


class JointMemberRemovalRequest(models.Model):
    """Tracks a leader-requested member removal that requires admin verification."""

    STATUS_CHOICES = [
        ('Pending_Admin_Review', 'Pending Admin Review'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
    ]

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    group = models.ForeignKey(JointBuyerGroup, on_delete=models.CASCADE, related_name='removal_requests')
    member = models.ForeignKey(JointBuyerMember, on_delete=models.CASCADE, related_name='removal_requests')
    requested_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='joint_removal_requests')
    consent_confirmed = models.BooleanField(default=False, help_text="Leader confirms the member agreed to exit the group.")
    compensation_confirmed = models.BooleanField(default=False, help_text="Leader confirms the member has received their compensation.")
    compensation_amount = models.DecimalField(max_digits=14, decimal_places=2, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='Pending_Admin_Review')
    admin_reviewed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        related_name='reviewed_joint_removal_requests',
    )
    admin_reviewed_at = models.DateTimeField(blank=True, null=True)
    admin_notes = models.TextField(blank=True, null=True)
    processed_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.group.name} - {self.member.full_name} [{self.get_status_display()}]"


class PlatformLegalDocument(models.Model):
    """Stores platform-wide legal documents (e.g., Joint Laws, Terms of Service) editable by Admin."""
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    title = models.CharField(max_length=255, unique=True)
    content = models.TextField(help_text="Enter the legal document paragraphs here.")
    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        verbose_name = 'Legal Document'
        verbose_name_plural = 'Legal Documents'
        ordering = ['title']

    def __str__(self):
        return self.title


class LandPromotion(models.Model):
    TIER_CHOICES = [
        ('Basic', 'Basic Promotion'),
        ('Pro', 'Pro Promotion'),
        ('Elite', 'Elite Promotion'),
    ]
    BILLING_CHOICES = [
        ('Daily', 'Pay-per-day'),
        ('PPC', 'Pay-per-click'),
        ('PPI', 'Pay-per-impression'),
        ('Bundle', 'Subscription Bundle'),
    ]
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='promotions')
    tier = models.CharField(max_length=20, choices=TIER_CHOICES)
    billing_model = models.CharField(max_length=20, choices=BILLING_CHOICES)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='purchased_promotions')
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    
    # Targeting fields
    target_counties = models.JSONField(default=list, blank=True, help_text="Targeted counties/regions")
    target_budget_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    target_budget_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    target_buyer_intents = models.JSONField(default=list, blank=True, help_text="List of buyer intents targeted")
    
    # Payment details
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    payment_status = models.CharField(max_length=20, default='Pending') # Pending, Paid, Failed
    price_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Cached metrics
    views_count = models.IntegerField(default=0)
    impressions_count = models.IntegerField(default=0)
    clicks_count = models.IntegerField(default=0)
    inquiries_count = models.IntegerField(default=0)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['tenant_id', 'is_active', 'tier'], name='idx_lpromo_tenant_act_tier'),
            models.Index(fields=['tenant_id', 'created_by'], name='idx_lpromo_tenant_crt_by'),
        ]

    def __str__(self):
        return f"{self.tier} - {self.parcel.parcel_number}"


class PopupAdCampaign(models.Model):
    POPUP_TYPE_CHOICES = [
        ('Smart_Recommendation', 'Smart Recommendation'),
        ('Exit_Intent', 'Exit Intent'),
        ('Geo_Targeted', 'Geo-Targeted'),
        ('Urgency', 'Urgency'),
        ('Behavioral_Retargeting', 'Behavioral Retargeting'),
    ]
    BILLING_CHOICES = [
        ('PPV', 'Pay Per View'),
        ('PPC', 'Pay Per Click'),
        ('PPL', 'Pay Per Lead'),
        ('Subscription', 'Premium Subscription'),
        ('Geo_Exclusive', 'Geo-Exclusive Campaign'),
    ]
    STATUS_CHOICES = [
        ('Draft', 'Draft'),
        ('Active', 'Active'),
        ('Paused', 'Paused'),
        ('Completed', 'Completed'),
        ('Archived', 'Archived'),
    ]

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='popup_campaigns')
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='popup_campaigns')
    campaign_name = models.CharField(max_length=220)
    popup_type = models.CharField(max_length=30, choices=POPUP_TYPE_CHOICES)
    billing_model = models.CharField(max_length=20, choices=BILLING_CHOICES)
    headline = models.CharField(max_length=220)
    subheadline = models.TextField(blank=True, null=True)
    cta_text = models.CharField(max_length=80, default='View listing')
    landing_url = models.URLField(blank=True, null=True)
    target_counties = models.JSONField(default=list, blank=True)
    target_locations = models.JSONField(default=list, blank=True)
    target_buyer_categories = models.JSONField(default=list, blank=True)
    target_intent_tags = models.JSONField(default=list, blank=True)
    target_budget_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    target_budget_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    target_acreage_min = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    target_acreage_max = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    travel_radius_km = models.FloatField(default=20.0)
    frequency_cap_per_session = models.PositiveIntegerField(default=1)
    cooldown_minutes = models.PositiveIntegerField(default=45)
    duration_days = models.PositiveIntegerField(default=7)
    daily_budget = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    total_budget = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    priority_bid = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    geo_exclusive = models.BooleanField(default=False)
    seller_verified_only = models.BooleanField(default=True)
    creative_image = models.ImageField(upload_to='popup_ads/images/', blank=True, null=True)
    creative_video_url = models.URLField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Draft')
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    payment_status = models.CharField(max_length=20, default='Pending')
    spent_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    revenue_value = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    impressions_count = models.IntegerField(default=0)
    clicks_count = models.IntegerField(default=0)
    leads_count = models.IntegerField(default=0)
    dismissals_count = models.IntegerField(default=0)
    quality_score = models.FloatField(default=0.0)
    engagement_score = models.FloatField(default=0.0)
    auction_score = models.FloatField(default=0.0)
    roi_score = models.FloatField(default=0.0)
    last_scored_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    start_date = models.DateField(auto_now_add=True)
    end_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        indexes = [
            models.Index(fields=['tenant_id', 'status', 'billing_model'], name='idx_pac_tenant_sts_bill'),
            models.Index(fields=['tenant_id', 'created_by'], name='idx_pac_tenant_crt_by'),
        ]
        ordering = ['-created_at']

    @property
    def remaining_budget(self):
        from decimal import Decimal
        return max(Decimal('0.00'), (self.total_budget or Decimal('0.00')) - (self.spent_amount or Decimal('0.00')))

    @property
    def is_delivery_ready(self):
        from django.utils import timezone

        if self.status != 'Active' or self.payment_status != 'Paid':
            return False

        today = timezone.now().date()
        if self.start_date and self.start_date > today:
            return False
        if self.end_date and self.end_date < today:
            return False
        return True

    def __str__(self):
        return f"{self.campaign_name} - {self.parcel.parcel_number}"


class PopupAdEvent(models.Model):
    EVENT_CHOICES = [
        ('Impression', 'Impression'),
        ('Click', 'Click'),
        ('Lead', 'Lead'),
        ('Dismissed', 'Dismissed'),
        ('Suppressed', 'Suppressed'),
        ('Exit_Intent', 'Exit Intent'),
    ]

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(PopupAdCampaign, on_delete=models.CASCADE, related_name='events')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='popup_ad_events')
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    placement_area = models.CharField(max_length=50, blank=True, null=True)
    session_key = models.CharField(max_length=64, blank=True, null=True, db_index=True)
    page_context = models.CharField(max_length=80, blank=True, null=True)
    buyer_category = models.CharField(max_length=30, blank=True, null=True)
    county_context = models.CharField(max_length=100, blank=True, null=True)
    intent_score = models.FloatField(default=0.0)
    relevance_score = models.FloatField(default=0.0)
    dwell_seconds = models.FloatField(default=0.0)
    charge_amount = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    conversion_value = models.DecimalField(max_digits=14, decimal_places=2, default=0.00)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['campaign', 'event_type']),
            models.Index(fields=['placement_area', 'created_at']),
            models.Index(fields=['county_context', 'created_at']),
        ]

    def __str__(self):
        return f"{self.campaign_id} - {self.event_type}"


class PromotionAnalyticsLog(models.Model):
    EVENT_CHOICES = [
        ('Impression', 'Impression'),
        ('Click', 'Click'),
        ('Inquiry', 'Inquiry'),
    ]
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    promotion = models.ForeignKey(LandPromotion, on_delete=models.CASCADE, related_name='logs')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    placement_area = models.CharField(max_length=50, blank=True, null=True) # homepage, search, map, recs, email, push

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-timestamp']


class SearchQueryLog(models.Model):
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='search_logs', null=True, blank=True)
    query = models.CharField(max_length=255)
    filters = models.JSONField(default=dict, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-timestamp']


class BuyerInterestProfile(models.Model):
    CATEGORY_CHOICES = [
        ('Residential', 'Residential Buyer'),
        ('Agricultural', 'Agricultural Investor'),
        ('Commercial', 'Commercial Developer'),
        ('Speculator', 'Speculator'),
        ('Luxury', 'Luxury Buyer'),
        ('Diaspora', 'Diaspora Investor'),
    ]
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='interest_profile')
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES, default='Residential')
    preferred_counties = models.JSONField(default=list, blank=True)
    budget_min = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    budget_max = models.DecimalField(max_digits=14, decimal_places=2, null=True, blank=True)
    preferred_acreage_min = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    preferred_acreage_max = models.DecimalField(max_digits=10, decimal_places=4, null=True, blank=True)
    preferred_land_use = models.CharField(max_length=20, blank=True, null=True)
    last_location_lat = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    last_location_lng = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        indexes = [
            models.Index(fields=['tenant_id', 'user', 'category'], name='idx_bip_tenant_usr_cat'),
        ]

    def __str__(self):
        return f"{self.user.email} Profile - {self.category}"


class BuyerEngagementSignal(models.Model):
    SIGNAL_CHOICES = [
        ('View', 'View Listing'),
        ('Click', 'Click Listing'),
        ('Favorite', 'Favorite Listing'),
        ('Inquiry', 'Inquiry/Message'),
        ('Map_Interaction', 'Map Interaction'),
        ('Video_Watch', 'Video Watch Time'),
        ('Offer_Submitted', 'Offer Submitted'),
    ]
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='engagement_signals')
    parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='engagement_signals')
    signal_type = models.CharField(max_length=20, choices=SIGNAL_CHOICES)
    value = models.FloatField(default=1.0, help_text="Watch time in seconds or other weight indicator")
    timestamp = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-timestamp']


# ==================== PREMIUM PROMOTION TIER MODELS ====================

class PromotionTier(models.Model):
    """Seller promotion subscription tiers"""
    TIER_LEVELS = [
        ('Basic', 'Basic - Free'),
        ('Pro', 'Pro - $100/month'),
        ('Elite', 'Elite - $500/month'),
    ]

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=50, choices=TIER_LEVELS, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    tier_level = models.IntegerField(choices=[(0, 'Basic'), (1, 'Pro'), (2, 'Elite')])
    monthly_price = models.DecimalField(max_digits=10, decimal_places=2)
    features_json = models.JSONField(default=dict, help_text='Features available in this tier')
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['tier_level']
        verbose_name_plural = 'Promotion Tiers'

    def __str__(self):
        return f"{self.name} (${self.monthly_price}/mo)"


class PromotionPlan(models.Model):
    """Seller's active promotion subscription"""
    PLAN_STATUS = [
        ('Active', 'Active'),
        ('Expired', 'Expired'),
        ('Paused', 'Paused'),
        ('Cancelled', 'Cancelled'),
    ]

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    seller = models.OneToOneField(User, on_delete=models.CASCADE, related_name='promotion_plan',
                                  limit_choices_to={'role__in': ['Seller', 'Agent']})
    tier = models.ForeignKey(PromotionTier, on_delete=models.PROTECT)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    auto_renew = models.BooleanField(default=True)
    status = models.CharField(max_length=20, choices=PLAN_STATUS, default='Active')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        verbose_name_plural = 'Promotion Plans'

    def __str__(self):
        return f"{self.seller.email} - {self.tier.name}"

    @property
    def is_active(self):
        from django.utils import timezone
        if self.status != 'Active':
            return False
        if self.end_date and self.end_date <= timezone.now():
            return False
        return True


class PromotionPlanPayment(models.Model):
    """Payment tracking for promotion subscriptions"""
    PAYMENT_STATUS = [
        ('Initiated', 'Initiated'),
        ('Completed', 'Completed'),
        ('Failed', 'Failed'),
        ('Refunded', 'Refunded'),
    ]

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    plan = models.ForeignKey(PromotionPlan, on_delete=models.CASCADE, related_name='payments')
    transaction = models.ForeignKey(Transaction, on_delete=models.SET_NULL, null=True, blank=True)
    status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='Initiated')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_reference = models.CharField(max_length=100, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        verbose_name_plural = 'Promotion Plan Payments'

    def __str__(self):
        return f"Plan Payment: {self.plan.seller.email} - {self.status}"


# ==================== SPONSORED AD MODELS ====================

class SponsoredAd(models.Model):
    """Individual sponsored ad/campaign"""
    AD_STATUS = [
        ('Draft', 'Draft'),
        ('Scheduled', 'Scheduled'),
        ('Active', 'Active'),
        ('Paused', 'Paused'),
        ('Ended', 'Ended'),
        ('Rejected', 'Rejected'),
    ]

    AD_BILLING_MODELS = [
        ('PayPerDay', 'Pay Per Day'),
        ('PayPerClick', 'Pay Per Click'),
        ('PayPerImpression', 'Pay Per Impression'),
        ('Subscription', 'Subscription Bundle'),
    ]

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='sponsored_ads')
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sponsored_ads',
                               limit_choices_to={'role__in': ['Seller', 'Agent']})
    tier = models.CharField(max_length=20, default='Basic')

    title = models.CharField(max_length=200, blank=True, help_text='Custom ad title (optional)')
    description = models.TextField(max_length=500, blank=True, help_text='Ad description')
    image_url = models.URLField(max_length=500, blank=True, help_text='Custom ad image')

    status = models.CharField(max_length=20, choices=AD_STATUS, default='Draft')
    billing_model = models.CharField(max_length=20, choices=AD_BILLING_MODELS, default='PayPerDay')

    budget_daily = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True,
                                       help_text='Daily budget for this campaign')
    budget_total = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True,
                                       help_text='Total campaign budget')
    budget_spent = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    targeting_criteria = models.JSONField(default=dict, blank=True,
                                          help_text='Location, budget, buyer type targeting')

    created_at = models.DateTimeField(auto_now_add=True)
    starts_at = models.DateTimeField(null=True, blank=True)
    ends_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        indexes = [
            models.Index(fields=['tenant_id', 'status', 'billing_model'], name='idx_sad_tenant_sts_bill'),
            models.Index(fields=['tenant_id', 'seller'], name='idx_sad_tenant_seller'),
        ]
        ordering = ['-created_at']
        verbose_name_plural = 'Sponsored Ads'

    def __str__(self):
        return f"Ad: {self.parcel.parcel_number} - {self.status}"

    @property
    def is_active(self):
        from django.utils import timezone
        if self.status != 'Active':
            return False
        now = timezone.now()
        if self.starts_at and self.starts_at > now:
            return False
        if self.ends_at and self.ends_at <= now:
            return False
        return True


class AdEngagement(models.Model):
    """Track ad interactions (impressions, clicks, conversions)"""
    EVENT_TYPES = [
        ('Impression', 'Impression'),
        ('Click', 'Click'),
        ('Save', 'Save'),
        ('Inquiry', 'Inquiry/Conversion'),
        ('Share', 'Share'),
    ]

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ad = models.ForeignKey(SponsoredAd, on_delete=models.CASCADE, related_name='engagements')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    event_type = models.CharField(max_length=20, choices=EVENT_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)

    source_page = models.CharField(max_length=50, blank=True, help_text='homepage, search, recommendations, etc.')
    device_type = models.CharField(max_length=20, blank=True, help_text='mobile, desktop, tablet')
    geolocation = models.JSONField(default=dict, blank=True, help_text='User location at time of engagement')

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Ad Engagement: {self.ad.parcel.parcel_number} - {self.event_type}"


class AdBillingEvent(models.Model):
    """Billable events for ads (impressions, clicks, conversions)"""
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ad = models.ForeignKey(SponsoredAd, on_delete=models.CASCADE, related_name='billing_events')

    event_type = models.CharField(max_length=20, choices=[
        ('Impression', 'Impression'),
        ('Click', 'Click'),
        ('Conversion', 'Conversion'),
    ])
    amount_charged = models.DecimalField(max_digits=10, decimal_places=2)
    engagement = models.ForeignKey(AdEngagement, on_delete=models.SET_NULL, null=True, blank=True)

    timestamp = models.DateTimeField(auto_now_add=True)
    billing_status = models.CharField(max_length=20, default='Pending', choices=[
        ('Pending', 'Pending'),
        ('Billed', 'Billed'),
        ('Paid', 'Paid'),
    ])

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-timestamp']
        verbose_name_plural = 'Ad Billing Events'

    def __str__(self):
        return f"Billing: {self.ad.parcel.parcel_number} - {self.event_type}"


# ==================== ANALYTICS MODELS ====================

class AnalyticsEvent(models.Model):
    """General engagement tracking for analytics"""
    EVENT_TYPES = [
        ('View', 'Parcel View'),
        ('SearchImpression', 'Search Result Impression'),
        ('Click', 'Click Listing'),
        ('Save', 'Save Favorite'),
        ('Inquiry', 'Send Inquiry'),
        ('Share', 'Share Listing'),
        ('MapInteraction', 'Map Interaction'),
        ('VideoWatch', 'Video Watch'),
    ]

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='analytics_events')
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)

    event_type = models.CharField(max_length=30, choices=EVENT_TYPES)
    timestamp = models.DateTimeField(auto_now_add=True)
    metadata = models.JSONField(default=dict, blank=True)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['parcel', 'timestamp']),
            models.Index(fields=['event_type', 'timestamp']),
        ]

    def __str__(self):
        return f"{self.event_type}: {self.parcel.parcel_number}"


class RecommendationLog(models.Model):
    """Track what was recommended to whom"""
    ALGORITHM_TYPES = [
        ('ContentBased', 'Content Based'),
        ('Collaborative', 'Collaborative'),
        ('GeoSpatial', 'Geo-Spatial'),
        ('Trending', 'Trending'),
        ('Sponsored', 'Sponsored'),
        ('Hybrid', 'Hybrid'),
    ]

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='recommendation_logs')
    parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='recommendation_logs')

    algorithm_type = models.CharField(max_length=30, choices=ALGORITHM_TYPES)
    rank = models.IntegerField(help_text='Position in recommendation list')
    score = models.FloatField(default=0, help_text='Recommendation score (0-100)')

    clicked = models.BooleanField(default=False)
    saved = models.BooleanField(default=False)
    inquired = models.BooleanField(default=False)

    timestamp = models.DateTimeField(auto_now_add=True)
    feedback_score = models.IntegerField(null=True, blank=True, help_text='User feedback: -1 (bad), 0 (neutral), 1 (good)')

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-timestamp']

    def __str__(self):
        return f"Rec: {self.user.email} -> {self.parcel.parcel_number}"


# ==================== FRAUD & TRUST MODELS ====================

class FraudScore(models.Model):
    """Risk scoring for users"""
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='fraud_score')

    score = models.IntegerField(default=0, help_text='0-100 fraud risk score')
    risk_factors = models.JSONField(default=list, blank=True, help_text='List of detected risk factors')

    flagged_for_review = models.BooleanField(default=False)
    review_notes = models.TextField(blank=True, null=True)
    reviewed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='fraud_reviews')

    last_calculated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        verbose_name_plural = 'Fraud Scores'

    def __str__(self):
        return f"Fraud Score: {self.user.email} = {self.score}/100"

    @property
    def risk_level(self):
        if self.score < 20:
            return 'Low'
        elif self.score < 50:
            return 'Medium'
        elif self.score < 75:
            return 'High'
        else:
            return 'Critical'


class VerificationBadge(models.Model):
    """Trust badges for verified listings"""
    BADGE_TYPES = [
        ('Verified', 'Verified Listing'),
        ('LegalChecked', 'Legal Checked'),
        ('TransactionSuccess', 'Transaction Success'),
        ('SellerTrusted', 'Trusted Seller'),
    ]

    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    parcel = models.ForeignKey(LandParcel, on_delete=models.CASCADE, related_name='verification_badges')

    badge_type = models.CharField(max_length=20, choices=BADGE_TYPES)
    issued_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                 limit_choices_to={'role__in': ['Agent', 'Admin']})

    issued_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked = models.BooleanField(default=False)

    updated_at = models.DateTimeField(auto_now=True)
    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        ordering = ['-issued_at']
        unique_together = ['parcel', 'badge_type']

    def __str__(self):
        return f"{self.get_badge_type_display()}: {self.parcel.parcel_number}"

    @property
    def is_active(self):
        from django.utils import timezone
        if self.revoked:
            return False
        if self.expires_at and self.expires_at <= timezone.now():
            return False
        return True


# ==================== SERVICE FEE MODELS ====================

class ServiceFee(models.Model):
    """Track service fees for transactions"""
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True, help_text='Organization tenant ID for row-level security isolation')
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction = models.OneToOneField(Transaction, on_delete=models.CASCADE, related_name='service_fee')

    platform_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                       help_text='4% platform service fee')
    escrow_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                     help_text='2% escrow holding fee')
    processing_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                         help_text='Flat payment processing fee')
    verification_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                           help_text='Optional verification fee')
    due_diligence_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0,
                                            help_text='Optional due diligence fee')

    total_fees = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    breakdown = models.JSONField(default=dict, blank=True,
                                help_text='Detailed breakdown of fees')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    deleted_at = models.DateTimeField(null=True, blank=True, help_text='Soft delete timestamp — null means active record')
    updated_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='%(class)s_updates', help_text='Last user who modified this record')
    class Meta:
        indexes = [
            models.Index(fields=['tenant_id', 'transaction'], name='idx_sf_tenant_txn'),
        ]
        verbose_name_plural = 'Service Fees'

    def __str__(self):
        return f"Fees for Transaction {self.transaction.id}"

    @property
    def total_with_fees(self):
        return self.transaction.agreed_price + self.total_fees


# ==================== AUTH & MFA MODELS ====================


class UserMFA(models.Model):
    """MFA configuration for users."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='mfa_config')
    
    # TOTP
    totp_secret = models.CharField(max_length=64, blank=True, default='')
    is_enabled = models.BooleanField(default=False, db_index=True)
    setup_started_at = models.DateTimeField(null=True, blank=True)
    verified_at = models.DateTimeField(null=True, blank=True)
    
    # Recovery codes (hashed)
    recovery_codes = models.JSONField(default=list, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'is_enabled'], name='idx_mfa_user_enabled'),
        ]
    
    def __str__(self):
        status = "enabled" if self.is_enabled else "disabled"
        return f"MFA for {self.user.email} ({status})"


class TrustedDevice(models.Model):
    """Trusted device for MFA bypass."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trusted_devices')
    trust_token = models.CharField(max_length=128, db_index=True)
    device_name = models.CharField(max_length=200, default='Unknown Device')
    device_type = models.CharField(max_length=50, default='unknown')
    user_agent = models.TextField(blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    expires_at = models.DateTimeField(db_index=True)
    last_used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['user', 'trust_token'], name='idx_device_user_token'),
            models.Index(fields=['user', 'expires_at'], name='idx_device_user_expires'),
        ]
    
    def __str__(self):
        return f"{self.device_name} - {self.user.email}"


class UserSession(models.Model):
    """Track user sessions for security and revocation."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sessions')
    session_key = models.CharField(max_length=128, db_index=True)
    refresh_token_jti = models.CharField(max_length=128, db_index=True, blank=True, default='')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, default='')
    device_type = models.CharField(max_length=50, blank=True, default='')
    location = models.CharField(max_length=200, blank=True, default='')
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    expires_at = models.DateTimeField(db_index=True)
    
    class Meta:
        ordering = ['-last_activity']
        indexes = [
            models.Index(fields=['user', 'is_active'], name='idx_session_user_active'),
            models.Index(fields=['refresh_token_jti'], name='idx_session_jti'),
            models.Index(fields=['user', 'is_active', 'last_activity'], name='idx_session_user_activity'),
        ]
    
    def __str__(self):
        return f"Session {self.session_key[:8]}... for {self.user.email}"


class OAuthProvider(models.Model):
    """OAuth/SSO provider configuration."""
    PROVIDER_CHOICES = [
        ('google', 'Google'),
        ('github', 'GitHub'),
        ('microsoft', 'Microsoft'),
        ('oidc', 'OpenID Connect'),
        ('saml', 'SAML'),
    ]
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=100)
    provider = models.CharField(max_length=20, choices=PROVIDER_CHOICES, db_index=True)
    client_id = models.CharField(max_length=500)
    client_secret = models.TextField()  # Encrypted at rest
    authorization_url = models.URLField()
    token_url = models.URLField()
    userinfo_url = models.URLField(blank=True, default='')
    scope = models.CharField(max_length=200, default='openid email profile')
    is_active = models.BooleanField(default=True, db_index=True)
    config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['provider', 'is_active'], name='idx_oauth_provider_active'),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.provider})"


class OAuthAccount(models.Model):
    """Links OAuth provider accounts to local users."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='oauth_accounts')
    provider = models.ForeignKey(OAuthProvider, on_delete=models.CASCADE, related_name='accounts')
    provider_user_id = models.CharField(max_length=255, db_index=True)
    email = models.EmailField(blank=True, default='')
    access_token = models.TextField(blank=True, default='')  # Encrypted
    refresh_token = models.TextField(blank=True, default='')  # Encrypted
    token_expires_at = models.DateTimeField(null=True, blank=True)
    profile_data = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('provider', 'provider_user_id')
        indexes = [
            models.Index(fields=['user', 'provider'], name='idx_oauth_user_provider'),
            models.Index(fields=['provider', 'provider_user_id'], name='idx_oauth_provider_uid'),
        ]
    
    def __str__(self):
        return f"{self.user.email} via {self.provider.name}"


class Permission(models.Model):
    """Granular permission for ABAC system."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    codename = models.CharField(max_length=100, unique=True, db_index=True)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True, default='')
    resource_type = models.CharField(max_length=50, db_index=True)
    action = models.CharField(max_length=50)  # create, read, update, delete, manage
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['resource_type', 'action']
        indexes = [
            models.Index(fields=['resource_type', 'action'], name='idx_perm_resource_action'),
        ]
    
    def __str__(self):
        return f"{self.codename}"


class RolePermission(models.Model):
    """Maps roles to permissions (RBAC + ABAC hybrid)."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    role = models.CharField(max_length=20, db_index=True)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, related_name='role_assignments')
    conditions = models.JSONField(default=dict, blank=True, help_text='ABAC conditions for this role-permission mapping')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('role', 'permission')
        indexes = [
            models.Index(fields=['role'], name='idx_roleperm_role'),
        ]
    
    def __str__(self):
        return f"{self.role} -> {self.permission.codename}"


class LoginAttempt(models.Model):
    """Track login attempts for brute-force protection."""
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(db_index=True)
    ip_address = models.GenericIPAddressField(db_index=True)
    user_agent = models.TextField(blank=True, default='')
    success = models.BooleanField(default=False)
    failure_reason = models.CharField(max_length=100, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['email', 'success', 'created_at'], name='idx_login_email_success'),
            models.Index(fields=['ip_address', 'success', 'created_at'], name='idx_login_ip_success'),
        ]
    
    def __str__(self):
        status = "success" if self.success else "failed"
        return f"{self.email} ({status}) at {self.created_at}"


class PricePredictionLog(models.Model):
    """Logs every price prediction for monitoring and model improvement."""
    prediction_id = models.CharField(max_length=100, unique=True, editable=False)
    county = models.CharField(max_length=100)
    constituency = models.CharField(max_length=100, blank=True)
    town = models.CharField(max_length=100, blank=True)
    land_use = models.CharField(max_length=50)
    size_acres = models.DecimalField(max_digits=10, decimal_places=2)
    has_road_access = models.BooleanField(default=True)
    has_water = models.BooleanField(default=True)
    has_electricity = models.BooleanField(default=True)
    proximity_to_tarmac_km = models.FloatField(null=True, blank=True)
    proximity_to_school_km = models.FloatField(null=True, blank=True)
    proximity_to_hospital_km = models.FloatField(null=True, blank=True)
    plot_grade = models.CharField(max_length=1, blank=True)
    predicted_price_per_acre = models.DecimalField(max_digits=15, decimal_places=0)
    predicted_total_value = models.DecimalField(max_digits=18, decimal_places=0)
    confidence_low = models.DecimalField(max_digits=15, decimal_places=0)
    confidence_high = models.DecimalField(max_digits=15, decimal_places=0)
    confidence_label = models.CharField(max_length=50)
    model_version = models.CharField(max_length=50)
    created_at = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['county', 'land_use'], name='idx_pred_county_lu'),
            models.Index(fields=['created_at'], name='idx_pred_created'),
        ]
    
    def __str__(self):
        return f"Prediction {self.prediction_id[:8]}... {self.county} {self.land_use} KES {self.predicted_price_per_acre:,}/acre"
