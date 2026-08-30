"""
Digiland Property Verification & Due Diligence Engine — Models
==============================================================

Two-Phase verification architecture:
  Phase 1: Pre-Interest Screening (seller registration → AI screening → pre-screened listing)
  Phase 2: Interest-Triggered Due Diligence (buyer interest → Agent + Surveyor + Lawyer → verified)

Core entities:
  PropertyVerificationCase   — One per property, the digital due-diligence passport
  VerificationDocumentRequirement — Rules engine for conditional document checklists
  VerificationDocument       — Enhanced document with AI screening + human review chain
  VerificationLayer          — Tracks each of the 5 verification layers
  VerificationCheckItem      — Individual check items within each layer
  VerificationRiskFlag       — Risk flags raised during verification
  VerificationAuditEvent     — Complete audit trail / Trust Timeline source
  BuyerInterestCase          — Phase 2 trigger when buyer expresses serious interest
"""

import uuid
import hashlib
from django.db import models
from django.conf import settings
from django.utils import timezone


# ---------------------------------------------------------------------------
# PROPERTY VERIFICATION CASE — Central entity
# ---------------------------------------------------------------------------

class PropertyVerificationCase(models.Model):
    """
    The property's digital due-diligence passport.
    Every parcel registered on Digiland gets exactly one verification case that
    follows it from seller submission through to transaction completion.
    """

    PHASE_CHOICES = [
        ('PHASE_1', 'Pre-Interest Screening'),
        ('PHASE_2', 'Interest-Triggered Due Diligence'),
    ]

    STATUS_CHOICES = [
        # Phase 1 — Pre-Interest Screening
        ('DRAFT', 'Draft — Seller has not completed registration'),
        ('SUBMITTED', 'Submitted — Seller completed registration'),
        ('DOCUMENTS_PENDING', 'Documents Pending — Required documents incomplete'),
        ('AI_SCREENING', 'AI Screening — Documents being processed'),
        ('PRELIMINARY_REVIEW', 'Preliminary Review — Initial human review'),
        ('PRE_SCREENED', 'Pre-Screened — Passed initial screening'),
        ('PRE_SCREENED_WITH_FLAGS', 'Pre-Screened with Flags — Issues noted'),
        ('NOT_READY', 'Not Ready — Cannot be listed yet'),
        # Phase 2 — Interest-Triggered Due Diligence
        ('DUE_DILIGENCE_REQUESTED', 'Due Diligence Requested'),
        ('AGENT_ASSIGNED', 'Agent Assigned'),
        ('AGENT_ASSESSMENT', 'Agent Physical Assessment'),
        ('SURVEYOR_ASSIGNED', 'Surveyor Assigned'),
        ('SURVEY_VERIFICATION', 'Survey Verification'),
        ('LAWYER_ASSIGNED', 'Lawyer Assigned'),
        ('LEGAL_DUE_DILIGENCE', 'Legal Due Diligence'),
        ('ADDITIONAL_INFO_REQUIRED', 'Additional Information Required'),
        ('ISSUE_IDENTIFIED', 'Issue Identified — Requires resolution'),
        ('QUALITY_CONTROL', 'Quality Control Review'),
        ('VERIFIED_FOR_TRANSACTION', 'Verified for Transaction'),
        ('ON_HOLD', 'On Hold'),
        ('FAILED', 'Failed Due Diligence'),
        ('SUSPENDED', 'Suspended — Investigation pending'),
    ]

    VERIFICATION_LEVEL_CHOICES = [
        ('NONE', 'No Verification'),
        ('PRE_SCREENED', 'Digiland Pre-Screened'),
        ('VERIFIED', 'Digiland Verified'),
        ('VERIFIED_WITH_CONDITIONS', 'Verified with Conditions'),
        ('ADDITIONAL_REQUIRED', 'Additional Verification Required'),
        ('NOT_VERIFIED', 'Not Verified'),
        ('SUSPENDED', 'Suspended'),
    ]

    PROPERTY_TYPE_CHOICES = [
        ('LAND_PLOT', 'Land / Plot'),
        ('AGRICULTURAL', 'Agricultural Land'),
        ('RESIDENTIAL', 'Residential Property'),
        ('COMMERCIAL', 'Commercial Property'),
        ('DEVELOPMENT', 'Development Land'),
        ('OTHER', 'Other'),
    ]

    TENURE_CHOICES = [
        ('FREEHOLD', 'Freehold'),
        ('LEASEHOLD', 'Leasehold'),
        ('UNKNOWN', 'Not Sure'),
    ]

    OWNERSHIP_TYPE_CHOICES = [
        ('INDIVIDUAL', 'Individual'),
        ('JOINT', 'Joint Ownership'),
        ('COMPANY', 'Company / Organization'),
        ('ESTATE', 'Estate / Deceased Owner'),
        ('TRUST', 'Trust / Other Legal Entity'),
        ('UNKNOWN', 'Not Sure'),
    ]

    SELLER_RELATIONSHIP_CHOICES = [
        ('REGISTERED_OWNER', 'I am the registered owner'),
        ('REPRESENTATIVE', 'I am selling on behalf of the owner'),
        ('COMPANY_REP', 'I represent a company'),
        ('ESTATE_REP', 'I represent an estate'),
        ('OTHER', 'Other'),
    ]

    INTENDED_USE_CHOICES = [
        ('RESIDENTIAL', 'Residential'),
        ('AGRICULTURAL', 'Agricultural'),
        ('COMMERCIAL', 'Commercial'),
        ('MIXED_USE', 'Mixed Use'),
        ('DEVELOPMENT', 'Development'),
        ('OTHER', 'Other'),
    ]

    RISK_LEVEL_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]

    SIZE_UNIT_CHOICES = [
        ('ACRES', 'Acres'),
        ('HECTARES', 'Hectares'),
        ('SQ_METRES', 'Square Metres'),
        ('SQ_FEET', 'Square Feet'),
    ]

    # Identity
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case_number = models.CharField(
        max_length=30, unique=True, db_index=True,
        help_text='Verification case number e.g. DL-VER-2026-004821'
    )
    property = models.OneToOneField(
        'core.LandParcel', on_delete=models.CASCADE,
        related_name='verification_case',
        help_text='The LandParcel this verification case belongs to'
    )
    seller = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='verification_cases_as_seller',
        help_text='The seller who registered this property'
    )

    # Verification state
    current_phase = models.CharField(max_length=10, choices=PHASE_CHOICES, default='PHASE_1')
    status = models.CharField(max_length=40, choices=STATUS_CHOICES, default='DRAFT')
    verification_level = models.CharField(max_length=30, choices=VERIFICATION_LEVEL_CHOICES, default='NONE')

    # ── Seller-provided property characteristics (drives conditional requirements) ──
    property_type = models.CharField(max_length=20, choices=PROPERTY_TYPE_CHOICES, default='LAND_PLOT')
    tenure_type = models.CharField(max_length=15, choices=TENURE_CHOICES, default='UNKNOWN')
    ownership_type = models.CharField(max_length=15, choices=OWNERSHIP_TYPE_CHOICES, default='INDIVIDUAL')
    seller_relationship = models.CharField(max_length=20, choices=SELLER_RELATIONSHIP_CHOICES, default='REGISTERED_OWNER')
    intended_use = models.CharField(max_length=15, choices=INTENDED_USE_CHOICES, default='RESIDENTIAL')

    is_subdivided = models.BooleanField(default=False, help_text='Whether the property is part of a subdivision')
    is_agricultural = models.BooleanField(default=False, help_text='Whether the property is agricultural (may trigger LCB consent)')
    has_spousal_interest = models.CharField(
        max_length=10, choices=[('YES', 'Yes'), ('NO', 'No'), ('UNSURE', 'Not Sure')],
        default='UNSURE', help_text='Whether spousal/matrimonial interest may apply'
    )
    has_recent_transfer = models.CharField(
        max_length=10, choices=[('YES', 'Yes'), ('NO', 'No'), ('UNSURE', 'Not Sure')],
        default='UNSURE', help_text='Whether the property has been transferred recently'
    )
    title_type = models.CharField(
        max_length=30, choices=[
            ('TITLE_DEED', 'Title Deed'),
            ('CERTIFICATE_OF_LEASE', 'Certificate of Lease'),
            ('OTHER', 'Other'),
            ('UNKNOWN', 'Not Sure'),
        ],
        default='UNKNOWN', help_text='Type of title document'
    )

    # Registered details from title (for cross-document comparison)
    registered_owner_name = models.CharField(max_length=300, blank=True, help_text='Owner name exactly as on title')
    registered_area_value = models.DecimalField(max_digits=12, decimal_places=4, null=True, blank=True, help_text='Area as shown on title')
    registered_area_unit = models.CharField(max_length=15, choices=SIZE_UNIT_CHOICES, default='ACRES')

    # Location (approximate seller-provided, NOT cadastral)
    approximate_latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    approximate_longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    location_description = models.CharField(max_length=300, blank=True, help_text='Locality name e.g. Ruiru, Karen')

    # Risk assessment
    overall_risk_level = models.CharField(max_length=10, choices=RISK_LEVEL_CHOICES, default='LOW')

    # Wizard progress tracking
    wizard_step_completed = models.IntegerField(
        default=0,
        help_text='Last completed wizard step (1=Property Basics, 2=Ownership, 3=Documents, 4=AI Screening, 5=Review)'
    )

    # Phase 2 assignments
    assigned_agent = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verification_agent_assignments'
    )
    assigned_surveyor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verification_surveyor_assignments'
    )
    assigned_lawyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verification_lawyer_assignments'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(null=True, blank=True, help_text='When seller submitted for screening')
    pre_screened_at = models.DateTimeField(null=True, blank=True, help_text='When Phase 1 screening completed')
    phase2_activated_at = models.DateTimeField(null=True, blank=True, help_text='When Phase 2 due diligence began')
    verified_at = models.DateTimeField(null=True, blank=True, help_text='When full verification completed')
    expires_at = models.DateTimeField(null=True, blank=True, help_text='Verification expiry — requires refresh')

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Property Verification Case'
        verbose_name_plural = 'Property Verification Cases'
        indexes = [
            models.Index(fields=['status', 'current_phase'], name='idx_pvc_status_phase'),
            models.Index(fields=['seller', 'status'], name='idx_pvc_seller_status'),
            models.Index(fields=['verification_level'], name='idx_pvc_ver_level'),
        ]

    def __str__(self):
        return f"{self.case_number} — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.case_number:
            self.case_number = self._generate_case_number()
        super().save(*args, **kwargs)

    def _generate_case_number(self):
        from django.utils import timezone as tz
        year = tz.now().year
        count = PropertyVerificationCase.objects.filter(
            created_at__year=year
        ).count() + 1
        return f"DL-VER-{year}-{count:06d}"


# ---------------------------------------------------------------------------
# VERIFICATION DOCUMENT REQUIREMENT — Rules engine
# ---------------------------------------------------------------------------

class VerificationDocumentRequirement(models.Model):
    """
    Configurable rules defining which documents are required based on
    property type, tenure, ownership structure, and transaction circumstances.
    Admins can manage these without code changes.
    """

    DOCUMENT_TYPE_CHOICES = [
        # Core ownership
        ('TITLE_DEED', 'Title Deed / Certificate of Lease'),
        ('OFFICIAL_SEARCH', 'Official Land Search / Search Certificate'),
        ('SELLER_ID', 'Seller National ID / Passport'),
        ('KRA_PIN_CERT', 'KRA PIN Certificate'),
        # Government / clearances
        ('LAND_RENT_CLEARANCE', 'Land Rent Clearance Certificate'),
        ('LAND_RATES_CLEARANCE', 'County Land Rates Clearance Certificate'),
        ('LCB_CONSENT', 'Land Control Board Consent'),
        # Survey / subdivision
        ('SURVEY_PLAN', 'Survey Plan'),
        ('MUTATION_FORM', 'Mutation Form'),
        ('SUBDIVISION_PLAN', 'Approved Subdivision Plan / Scheme'),
        ('PARCEL_PLAN', 'Parcel Plan / RIM Extract'),
        # Spousal / ownership authority
        ('SPOUSAL_CONSENT', 'Spousal Consent / Matrimonial Documentation'),
        # Company ownership
        ('COMPANY_CERTIFICATE', 'Certificate of Incorporation'),
        ('BOARD_RESOLUTION', 'Board Resolution / Authority to Sell'),
        ('COMPANY_PROFILE', 'Company Registration Profile'),
        ('COMPANY_KRA', 'Company KRA PIN Certificate'),
        # Estate / succession
        ('GRANT_PROBATE', 'Grant of Probate'),
        ('LETTERS_ADMIN', 'Letters of Administration'),
        ('CONFIRMATION_GRANT', 'Certificate of Confirmation of Grant'),
        ('COURT_ORDER', 'Court Order'),
        # Charge / mortgage
        ('CHARGE_INSTRUMENT', 'Charge / Discharge Instrument'),
        ('LENDER_CONSENT', 'Lender Consent'),
        # Transfer (Phase 2 / transaction stage)
        ('TRANSFER_INSTRUMENT', 'Executed Transfer Instrument'),
        ('VALUATION_REPORT', 'Valuation Report'),
        ('STAMP_DUTY_RECEIPT', 'Stamp Duty Assessment / Payment'),
        # Planning
        ('PLANNING_PERMISSION', 'Development / Planning Permission'),
        ('CHANGE_OF_USE', 'Change / Extension of User Document'),
        ('ENVIRONMENTAL_REPORT', 'Environmental Assessment'),
        # Photos / site
        ('PROPERTY_PHOTOS', 'Property Photographs'),
        ('SITE_MAP', 'Site Location Map'),
        # Other
        ('OTHER', 'Other Supporting Document'),
    ]

    PHASE_CHOICES = [
        ('PHASE_1', 'Phase 1 — Pre-Interest Screening'),
        ('PHASE_2', 'Phase 2 — Transaction Due Diligence'),
        ('BOTH', 'Both Phases'),
    ]

    REVIEWER_ROLE_CHOICES = [
        ('OPERATIONS', 'Operations / Admin'),
        ('AGENT', 'Agent'),
        ('SURVEYOR', 'Surveyor'),
        ('LAWYER', 'Lawyer'),
        ('LAWYER_OPERATIONS', 'Lawyer or Operations'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    document_type = models.CharField(max_length=30, choices=DOCUMENT_TYPE_CHOICES, db_index=True)
    display_name = models.CharField(max_length=150, help_text='Human-readable label shown to seller')
    description = models.TextField(blank=True, help_text='Help text shown to seller explaining this document')
    upload_hint = models.CharField(max_length=300, blank=True, help_text='Placeholder text e.g. "Upload your current title deed"')

    phase = models.CharField(max_length=10, choices=PHASE_CHOICES, default='PHASE_1')
    is_core = models.BooleanField(default=False, help_text='Always required regardless of property characteristics')

    # Conditional rules — JSON object with property characteristics that trigger this requirement
    # e.g. {"tenure_type": "LEASEHOLD"} or {"ownership_type": "COMPANY"} or {"is_subdivided": true}
    # Empty dict {} means no conditions (always shown if is_core=True, otherwise optional)
    condition_rules = models.JSONField(
        default=dict, blank=True,
        help_text='Conditions under which this document is required. JSON object matching PropertyVerificationCase fields.'
    )

    primary_reviewer_role = models.CharField(max_length=20, choices=REVIEWER_ROLE_CHOICES, default='OPERATIONS')
    ai_screening_enabled = models.BooleanField(default=True, help_text='Whether AI should automatically screen this document type')
    customer_visible = models.BooleanField(default=True, help_text='Whether customers can see this requirement and its status')
    accepted_formats = models.CharField(max_length=100, default='PDF, JPG, PNG', help_text='Accepted file formats')
    max_file_size_mb = models.IntegerField(default=20, help_text='Maximum file size in MB')
    sort_order = models.IntegerField(default=100, help_text='Display order in the document checklist')

    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'display_name']
        verbose_name = 'Document Requirement Rule'
        verbose_name_plural = 'Document Requirement Rules'

    def __str__(self):
        return f"{self.display_name} ({'Required' if self.is_core else 'Conditional'})"

    def matches_case(self, case: 'PropertyVerificationCase') -> bool:
        """Check whether this requirement applies to a given verification case."""
        if not self.condition_rules:
            return self.is_core
        for field, expected_value in self.condition_rules.items():
            actual_value = getattr(case, field, None)
            if isinstance(expected_value, bool):
                if bool(actual_value) != expected_value:
                    return False
            elif isinstance(expected_value, list):
                if actual_value not in expected_value:
                    return False
            else:
                if str(actual_value) != str(expected_value):
                    return False
        return True


# ---------------------------------------------------------------------------
# VERIFICATION DOCUMENT — Enhanced document entity
# ---------------------------------------------------------------------------

class VerificationDocument(models.Model):
    """
    Enhanced document entity with AI screening, versioning, and human review chain.
    Replaces the simplistic Document model for the verification workflow.
    """

    VERIFICATION_STATUS_CHOICES = [
        ('NOT_UPLOADED', 'Not Uploaded'),
        ('UPLOADED', 'Uploaded'),
        ('PROCESSING', 'Processing'),
        ('AI_SCREENED', 'AI Screened'),
        ('AI_FLAGGED', 'AI Flagged — Review Recommended'),
        ('UNABLE_TO_VERIFY', 'Unable to Verify by AI'),
        ('HUMAN_REVIEW', 'Requires Human Review'),
        ('HUMAN_VERIFIED', 'Human Verified'),
        ('REJECTED', 'Rejected'),
        ('EXPIRED', 'Expired'),
        ('SUPERSEDED', 'Superseded by Newer Version'),
    ]

    AI_STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('PROCESSING', 'Processing'),
        ('PASSED', 'Passed Screening'),
        ('FLAGGED', 'Flagged — Review Recommended'),
        ('FAILED', 'Failed Screening'),
        ('UNABLE', 'Unable to Assess'),
        ('ERROR', 'Processing Error'),
    ]

    AI_CONFIDENCE_CHOICES = [
        ('HIGH', 'High Confidence (≥85%)'),
        ('MODERATE', 'Moderate Confidence (60-84%)'),
        ('LOW', 'Low Confidence (<60%)'),
        ('NONE', 'Unable to Assess'),
    ]

    HUMAN_STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('CONFIRMED', 'Confirmed — Document acceptable'),
        ('REQUEST_BETTER_COPY', 'Request Better Copy'),
        ('REQUEST_ADDITIONAL', 'Request Additional Document'),
        ('ESCALATE_SURVEYOR', 'Escalated to Surveyor'),
        ('ESCALATE_LAWYER', 'Escalated to Lawyer'),
        ('REJECTED', 'Rejected'),
        ('NOT_APPLICABLE', 'Marked Not Applicable'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        PropertyVerificationCase, on_delete=models.CASCADE,
        related_name='verification_documents',
        help_text='The verification case this document belongs to'
    )
    requirement = models.ForeignKey(
        VerificationDocumentRequirement, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='uploaded_documents',
        help_text='The requirement rule this document fulfils'
    )
    document_type = models.CharField(
        max_length=30,
        choices=VerificationDocumentRequirement.DOCUMENT_TYPE_CHOICES,
        db_index=True
    )

    # File
    file = models.FileField(upload_to='verification_documents/%Y/%m/')
    original_filename = models.CharField(max_length=300)
    mime_type = models.CharField(max_length=100, blank=True)
    file_size = models.IntegerField(default=0, help_text='File size in bytes')
    file_hash = models.CharField(
        max_length=128, blank=True, db_index=True,
        help_text='SHA-256 fingerprint for duplicate detection'
    )

    # Upload metadata
    uploaded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='verification_documents_uploaded'
    )
    uploaded_at = models.DateTimeField(auto_now_add=True)
    document_date = models.DateField(null=True, blank=True, help_text='Date on the document itself')
    expiry_date = models.DateField(null=True, blank=True, help_text='Document expiry/validity date')

    # ── AI screening results ──
    ai_status = models.CharField(max_length=15, choices=AI_STATUS_CHOICES, default='PENDING')
    ai_confidence = models.DecimalField(
        max_digits=5, decimal_places=2, null=True, blank=True,
        help_text='AI confidence score 0.00 to 100.00'
    )
    ai_confidence_level = models.CharField(max_length=10, choices=AI_CONFIDENCE_CHOICES, default='NONE')
    ai_classification = models.CharField(
        max_length=30, blank=True,
        help_text='What document type AI classified this as (may differ from submitted type)'
    )
    ai_extracted_data = models.JSONField(
        default=dict, blank=True,
        help_text='Structured fields extracted by AI: parcel_number, owner_name, area, dates, etc.'
    )
    ai_consistency_checks = models.JSONField(
        default=list, blank=True,
        help_text='Cross-document consistency check results'
    )
    ai_flags = models.JSONField(
        default=list, blank=True,
        help_text='Anomaly and consistency flags from AI screening'
    )
    ai_recommendation = models.CharField(
        max_length=30, blank=True,
        choices=[
            ('PASS_SCREENING', 'Pass Screening'),
            ('REVIEW_RECOMMENDED', 'Human Review Recommended'),
            ('HIGH_RISK_REVIEW', 'High-Risk Review Required'),
            ('UNABLE_TO_ASSESS', 'Unable to Assess'),
        ]
    )
    ai_processed_at = models.DateTimeField(null=True, blank=True)
    ai_model_version = models.CharField(max_length=50, blank=True, help_text='AI model/version used')

    # ── Human review ──
    human_status = models.CharField(max_length=25, choices=HUMAN_STATUS_CHOICES, default='PENDING')
    human_reviewer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verification_documents_reviewed'
    )
    human_reviewed_at = models.DateTimeField(null=True, blank=True)
    human_notes = models.TextField(blank=True, help_text='Internal reviewer notes — not shown to seller')

    # ── Overall status ──
    verification_status = models.CharField(
        max_length=20, choices=VERIFICATION_STATUS_CHOICES, default='UPLOADED'
    )

    # ── Versioning ──
    version = models.IntegerField(default=1)
    supersedes = models.ForeignKey(
        'self', on_delete=models.SET_NULL,
        null=True, blank=True, related_name='superseded_by',
        help_text='Previous version this document replaces'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-uploaded_at']
        verbose_name = 'Verification Document'
        verbose_name_plural = 'Verification Documents'
        indexes = [
            models.Index(fields=['case', 'document_type'], name='idx_vdoc_case_type'),
            models.Index(fields=['verification_status'], name='idx_vdoc_ver_status'),
            models.Index(fields=['file_hash'], name='idx_vdoc_file_hash'),
        ]

    def __str__(self):
        return f"{self.get_document_type_display()} v{self.version} — {self.get_verification_status_display()}"

    def compute_file_hash(self):
        """Compute SHA-256 hash of the uploaded file for duplicate detection."""
        if self.file:
            sha256 = hashlib.sha256()
            self.file.seek(0)
            for chunk in self.file.chunks(chunk_size=8192):
                sha256.update(chunk)
            self.file.seek(0)
            self.file_hash = sha256.hexdigest()
        return self.file_hash


# ---------------------------------------------------------------------------
# VERIFICATION LAYER — 5-layer verification tracking
# ---------------------------------------------------------------------------

class VerificationLayer(models.Model):
    """
    Tracks each of the 5 verification layers for a property:
      1. Seller Verification
      2. Legal Title Verification
      3. Physical & Survey Verification
      4. Government & Planning Checks
      5. Transaction & Ownership Risk
    """

    LAYER_CHOICES = [
        ('SELLER', 'Layer 1 — Seller Verification'),
        ('LEGAL_TITLE', 'Layer 2 — Legal Title Verification'),
        ('PHYSICAL_SURVEY', 'Layer 3 — Physical & Survey Verification'),
        ('GOVERNMENT_PLANNING', 'Layer 4 — Government & Planning Checks'),
        ('TRANSACTION_RISK', 'Layer 5 — Transaction & Ownership Risk'),
    ]

    STATUS_CHOICES = [
        ('NOT_STARTED', 'Not Started'),
        ('IN_PROGRESS', 'In Progress'),
        ('COMPLETED', 'Completed'),
        ('COMPLETED_WITH_CONDITIONS', 'Completed with Conditions'),
        ('FAILED', 'Failed'),
        ('NOT_APPLICABLE', 'Not Applicable'),
    ]

    RISK_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        PropertyVerificationCase, on_delete=models.CASCADE,
        related_name='verification_layers'
    )
    layer_type = models.CharField(max_length=25, choices=LAYER_CHOICES)
    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='NOT_STARTED')
    risk_level = models.CharField(max_length=10, choices=RISK_CHOICES, default='LOW')

    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verification_layer_assignments'
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    findings = models.JSONField(default=dict, blank=True, help_text='Structured findings for this layer')
    issues = models.JSONField(default=list, blank=True, help_text='Issues discovered in this layer')
    notes = models.TextField(blank=True, help_text='Internal professional notes')

    # Customer-facing summary (sanitized)
    customer_summary = models.TextField(
        blank=True,
        help_text='Sanitized summary for customer view e.g. "Ownership verified against official records"'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['layer_type']
        unique_together = [('case', 'layer_type')]
        verbose_name = 'Verification Layer'
        verbose_name_plural = 'Verification Layers'

    def __str__(self):
        return f"{self.get_layer_type_display()} — {self.get_status_display()}"


# ---------------------------------------------------------------------------
# VERIFICATION CHECK ITEM — Individual check within a layer
# ---------------------------------------------------------------------------

class VerificationCheckItem(models.Model):
    """
    Individual check items within each verification layer.
    Populated by the due diligence engine based on property characteristics.
    """

    STATUS_CHOICES = [
        ('NOT_CHECKED', 'Not Checked'),
        ('PASSED', '✓ Passed'),
        ('FLAGGED', '⚠ Flagged'),
        ('FAILED', '✗ Failed'),
        ('NOT_APPLICABLE', 'N/A'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    layer = models.ForeignKey(
        VerificationLayer, on_delete=models.CASCADE,
        related_name='check_items'
    )
    check_name = models.CharField(max_length=150, help_text='e.g. "Ownership/title", "Official land search"')
    check_description = models.TextField(blank=True, help_text='What this check verifies')
    sort_order = models.IntegerField(default=100)

    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='NOT_CHECKED')
    result_text = models.TextField(
        blank=True,
        help_text='Internal result e.g. "Title owner matches seller. LR No confirmed."'
    )

    evidence_documents = models.ManyToManyField(
        VerificationDocument, blank=True,
        related_name='check_items',
        help_text='Documents used as evidence for this check'
    )

    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verification_checks_performed'
    )
    checked_at = models.DateTimeField(null=True, blank=True)

    # Customer-facing presentation
    customer_visible = models.BooleanField(default=True, help_text='Whether customers see this check')
    customer_display_text = models.TextField(
        blank=True,
        help_text='Sanitized text for customer view e.g. "Ownership verified against official land records"'
    )
    timestamp_display = models.DateTimeField(
        null=True, blank=True,
        help_text='Date shown on Trust Timeline e.g. "27 Aug 2026"'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sort_order', 'check_name']
        verbose_name = 'Verification Check Item'
        verbose_name_plural = 'Verification Check Items'

    def __str__(self):
        return f"{self.check_name} — {self.get_status_display()}"


# ---------------------------------------------------------------------------
# VERIFICATION RISK FLAG
# ---------------------------------------------------------------------------

class VerificationRiskFlag(models.Model):
    """
    Risk flags raised during verification — these are signals, not accusations.
    CRITICAL flags can automatically block listing.
    """

    SEVERITY_CHOICES = [
        ('INFO', 'Information'),
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'),
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical — Blocks Listing'),
    ]

    FLAG_TYPE_CHOICES = [
        ('PARCEL_MISMATCH', 'Parcel Number Mismatch'),
        ('OWNER_MISMATCH', 'Owner Name Mismatch'),
        ('AREA_MISMATCH', 'Area/Size Mismatch'),
        ('DOC_TYPE_MISMATCH', 'Document Type Mismatch'),
        ('POSSIBLE_MANIPULATION', 'Possible Document Manipulation'),
        ('DUPLICATE_DOCUMENT', 'Duplicate Document Detected'),
        ('STALE_DOCUMENT', 'Stale/Outdated Document'),
        ('MISSING_DOCUMENT', 'Missing Required Document'),
        ('ENCUMBRANCE_DETECTED', 'Encumbrance Detected'),
        ('CHARGE_DETECTED', 'Charge Detected'),
        ('CAUTION_DETECTED', 'Caution Detected'),
        ('RESTRICTION_DETECTED', 'Restriction Detected'),
        ('CONSENT_REQUIRED', 'Consent Required'),
        ('CONSENT_MISSING', 'Consent Missing'),
        ('SPOUSAL_REVIEW', 'Spousal Review Required'),
        ('SUCCESSION_REVIEW', 'Succession Review Required'),
        ('SUBDIVISION_MISSING', 'Subdivision Documentation Missing'),
        ('TITLE_OWNER_SELLER_MISMATCH', 'Title Owner ≠ Seller'),
        ('SEARCH_TITLE_MISMATCH', 'Official Search ≠ Title Information'),
        ('BOUNDARY_INCONSISTENT', 'Boundary Materially Inconsistent'),
        ('TRANSFER_DOC_MISSING', 'Missing Required Transfer Documentation'),
        ('OUTSTANDING_CLEARANCE', 'Outstanding Required Clearance'),
        ('OWNERSHIP_DISPUTE', 'Unresolved Ownership Dispute'),
        ('POTENTIAL_SUCCESSION_ISSUE', 'Potential Succession Issue'),
        ('OTHER', 'Other'),
    ]

    SOURCE_CHOICES = [
        ('AI_SCREENING', 'AI Document Screening'),
        ('AGENT', 'Agent Assessment'),
        ('SURVEYOR', 'Surveyor Verification'),
        ('LAWYER', 'Lawyer Due Diligence'),
        ('OPERATIONS', 'Operations Review'),
        ('SYSTEM', 'System Auto-Detection'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        PropertyVerificationCase, on_delete=models.CASCADE,
        related_name='verification_risk_flags'
    )
    flag_type = models.CharField(max_length=40, choices=FLAG_TYPE_CHOICES, db_index=True)
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES)
    description = models.TextField(help_text='Detailed description of the risk flag')
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)

    auto_escalate = models.BooleanField(
        default=False,
        help_text='CRITICAL flags auto-stop listing until resolved'
    )

    # Related document (if flag was raised from document analysis)
    related_document = models.ForeignKey(
        VerificationDocument, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='risk_flags'
    )

    # Resolution
    resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='resolved_risk_flags'
    )
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    raised_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='raised_risk_flags'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-severity', '-created_at']
        verbose_name = 'Verification Risk Flag'
        verbose_name_plural = 'Verification Risk Flags'

    def __str__(self):
        return f"[{self.severity}] {self.get_flag_type_display()} — {'Resolved' if self.resolved else 'Open'}"


# ---------------------------------------------------------------------------
# VERIFICATION AUDIT EVENT — Complete audit trail / Trust Timeline
# ---------------------------------------------------------------------------

class VerificationAuditEvent(models.Model):
    """
    Complete audit trail for every significant action in a verification case.
    Events marked as customer_visible become the Trust Timeline on the property page.
    """

    EVENT_TYPE_CHOICES = [
        ('CASE_CREATED', 'Verification Case Created'),
        ('STEP_COMPLETED', 'Wizard Step Completed'),
        ('PROPERTY_SUBMITTED', 'Property Submitted for Screening'),
        ('DOCUMENT_UPLOADED', 'Document Uploaded'),
        ('DOCUMENT_REPLACED', 'Document Replaced with New Version'),
        ('AI_SCREENING_STARTED', 'AI Screening Started'),
        ('AI_SCREENING_COMPLETED', 'AI Screening Completed'),
        ('AI_FLAG_RAISED', 'AI Flag Raised'),
        ('HUMAN_REVIEW_ASSIGNED', 'Human Review Assigned'),
        ('HUMAN_REVIEW_COMPLETED', 'Human Review Completed'),
        ('DOCUMENT_VERIFIED', 'Document Verified'),
        ('DOCUMENT_REJECTED', 'Document Rejected'),
        ('PRE_SCREENED', 'Property Pre-Screened'),
        ('BUYER_INTEREST', 'Buyer Expressed Interest'),
        ('PHASE2_ACTIVATED', 'Phase 2 Due Diligence Activated'),
        ('AGENT_ASSIGNED', 'Agent Assigned'),
        ('AGENT_ASSESSMENT_COMPLETED', 'Physical Inspection Completed'),
        ('SURVEYOR_ASSIGNED', 'Surveyor Assigned'),
        ('SURVEY_COMPLETED', 'Survey Verification Completed'),
        ('LAWYER_ASSIGNED', 'Lawyer Assigned'),
        ('LEGAL_REVIEW_COMPLETED', 'Legal Due Diligence Completed'),
        ('RISK_FLAG_RAISED', 'Risk Flag Raised'),
        ('RISK_FLAG_RESOLVED', 'Risk Flag Resolved'),
        ('QUALITY_REVIEW', 'Quality Control Review'),
        ('APPROVED', 'Property Approved for Transaction'),
        ('VERIFICATION_EXPIRED', 'Verification Expired'),
        ('STATUS_CHANGED', 'Verification Status Changed'),
        ('ADDITIONAL_INFO_REQUESTED', 'Additional Information Requested'),
        ('NOTE_ADDED', 'Internal Note Added'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    case = models.ForeignKey(
        PropertyVerificationCase, on_delete=models.CASCADE,
        related_name='audit_events'
    )
    event_type = models.CharField(max_length=40, choices=EVENT_TYPE_CHOICES, db_index=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='verification_audit_events'
    )
    description = models.TextField(help_text='Internal description of the event')
    metadata = models.JSONField(default=dict, blank=True, help_text='Additional structured event data')

    # Customer-facing Trust Timeline
    customer_visible = models.BooleanField(
        default=False,
        help_text='If True, this event appears on the customer Trust Timeline'
    )
    customer_display = models.CharField(
        max_length=300, blank=True,
        help_text='Sanitized text for customer view e.g. "Title documents reviewed"'
    )

    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Verification Audit Event'
        verbose_name_plural = 'Verification Audit Events'
        indexes = [
            models.Index(fields=['case', 'event_type'], name='idx_vae_case_event'),
            models.Index(fields=['case', 'customer_visible'], name='idx_vae_case_visible'),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} — {self.timestamp:%d %b %Y %H:%M}"


# ---------------------------------------------------------------------------
# BUYER INTEREST CASE — Phase 2 trigger
# ---------------------------------------------------------------------------

class BuyerInterestCase(models.Model):
    """
    Created when a buyer expresses serious interest in a property.
    Triggers Phase 2 interest-triggered due diligence.
    """

    STATUS_CHOICES = [
        ('EXPRESSED', 'Interest Expressed'),
        ('DUE_DILIGENCE_REQUESTED', 'Due Diligence Requested'),
        ('IN_PROGRESS', 'Due Diligence In Progress'),
        ('COMPLETED', 'Due Diligence Completed'),
        ('WITHDRAWN', 'Buyer Withdrew Interest'),
        ('EXPIRED', 'Interest Expired'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('NOT_REQUIRED', 'Not Required'),
        ('PENDING', 'Payment Pending'),
        ('PAID', 'Paid'),
        ('REFUNDED', 'Refunded'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interest_number = models.CharField(max_length=30, unique=True, db_index=True, help_text='e.g. INT-2026-004821')
    buyer = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='property_interest_cases'
    )
    property = models.ForeignKey(
        'core.LandParcel', on_delete=models.CASCADE,
        related_name='buyer_interest_cases'
    )
    verification_case = models.ForeignKey(
        PropertyVerificationCase, on_delete=models.CASCADE,
        related_name='buyer_interest_cases'
    )

    status = models.CharField(max_length=30, choices=STATUS_CHOICES, default='EXPRESSED')
    payment_status = models.CharField(max_length=15, choices=PAYMENT_STATUS_CHOICES, default='NOT_REQUIRED')
    estimated_verification_cost = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)

    notes = models.TextField(blank=True, help_text='Buyer notes or special requests')

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Buyer Interest Case'
        verbose_name_plural = 'Buyer Interest Cases'

    def __str__(self):
        return f"{self.interest_number} — {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.interest_number:
            self.interest_number = self._generate_interest_number()
        super().save(*args, **kwargs)

    def _generate_interest_number(self):
        from django.utils import timezone as tz
        year = tz.now().year
        count = BuyerInterestCase.objects.filter(
            created_at__year=year
        ).count() + 1
        return f"INT-{year}-{count:06d}"
