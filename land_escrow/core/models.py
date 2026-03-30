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

class User(AbstractUser):
    ROLE_CHOICES = [
        ('Buyer', 'Buyer'),
        ('Seller', 'Seller'),
        ('Agent', 'Agent'),
        ('Land_Official', 'Land Official'),
        ('Admin', 'Admin'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    username = None
    email = models.EmailField(_('email address'), unique=True)
    id_number = models.CharField(max_length=50, db_index=True)
    phone_number = models.CharField(max_length=20)
    role = models.CharField(max_length=20, choices=ROLE_CHOICES)
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
        ('Completed', 'Completed'),
        ('Disputed', 'Disputed'),
        ('Refunded', 'Refunded'),
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
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.id} - {self.status}"

class Document(models.Model):
    DOC_TYPE_CHOICES = [
        ('Title_Deed', 'Title Deed'),
        ('ID_Card', 'ID Card'),
        ('Passport_Photo', 'Passport Photo'),
        ('Sale_Agreement', 'Sale Agreement'),
        ('Spousal_Consent', 'Spousal Consent Affidavit'),
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
    document_type = models.CharField(max_length=20, choices=DOC_TYPE_CHOICES)
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
