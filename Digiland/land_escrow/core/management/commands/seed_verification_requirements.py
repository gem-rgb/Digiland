"""
Management command to seed the VerificationDocumentRequirement table
with the Kenyan land due-diligence document rules.

Usage:
  python manage.py seed_verification_requirements
  python manage.py seed_verification_requirements --clear  # wipe and re-seed
"""

from django.core.management.base import BaseCommand
from core.models_verification import VerificationDocumentRequirement


REQUIREMENTS = [
    # ─── CORE (Always Required) ───────────────────────────────────────────
    {
        'document_type': 'TITLE_DEED',
        'display_name': 'Title Deed / Certificate of Lease',
        'description': 'Your original title deed or certificate of lease. This is the primary ownership document for the property.',
        'upload_hint': 'Upload a clear scan or photo of your title deed',
        'phase': 'PHASE_1',
        'is_core': True,
        'condition_rules': {},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 10,
    },
    {
        'document_type': 'SELLER_ID',
        'display_name': 'Seller National ID / Passport',
        'description': 'Your national identification card or Kenyan passport for identity verification.',
        'upload_hint': 'Upload front and back of your National ID',
        'phase': 'PHASE_1',
        'is_core': True,
        'condition_rules': {},
        'primary_reviewer_role': 'OPERATIONS',
        'sort_order': 20,
    },
    {
        'document_type': 'KRA_PIN_CERT',
        'display_name': 'KRA PIN Certificate',
        'description': 'Your Kenya Revenue Authority PIN certificate, required for stamp duty and transfer processing.',
        'upload_hint': 'Upload your KRA PIN certificate',
        'phase': 'PHASE_1',
        'is_core': True,
        'condition_rules': {},
        'primary_reviewer_role': 'OPERATIONS',
        'sort_order': 25,
    },
    {
        'document_type': 'PROPERTY_PHOTOS',
        'display_name': 'Property Photographs',
        'description': 'Recent photographs of the property from multiple angles. Helps buyers and agents assess the property.',
        'upload_hint': 'Upload clear photos of the property',
        'phase': 'PHASE_1',
        'is_core': True,
        'condition_rules': {},
        'primary_reviewer_role': 'OPERATIONS',
        'sort_order': 30,
    },

    # ─── CONDITIONAL: Official Search ─────────────────────────────────────
    {
        'document_type': 'OFFICIAL_SEARCH',
        'display_name': 'Official Land Search / Search Certificate',
        'description': 'An official search from the Ministry of Lands or eCitizen showing ownership and encumbrances. '
                       'Recommended for Phase 1 screening, required for transaction verification.',
        'upload_hint': 'Upload your official land search certificate (if available)',
        'phase': 'BOTH',
        'is_core': False,
        'condition_rules': {},  # Optional in Phase 1, becomes required in Phase 2 via the engine
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 35,
    },

    # ─── CONDITIONAL: Leasehold ───────────────────────────────────────────
    {
        'document_type': 'LAND_RENT_CLEARANCE',
        'display_name': 'Land Rent Clearance Certificate',
        'description': 'Required for leasehold property. Confirms land rent is paid up-to-date with the national government.',
        'upload_hint': 'Upload your current land rent clearance certificate',
        'phase': 'PHASE_1',
        'is_core': False,
        'condition_rules': {'tenure_type': 'LEASEHOLD'},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 40,
    },

    # ─── CONDITIONAL: County Rates ────────────────────────────────────────
    {
        'document_type': 'LAND_RATES_CLEARANCE',
        'display_name': 'County Land Rates Clearance Certificate',
        'description': 'Confirms county land rates are paid up-to-date. Required for properties within rated areas.',
        'upload_hint': 'Upload your county rates clearance certificate',
        'phase': 'PHASE_1',
        'is_core': False,
        'condition_rules': {},  # Recommended for all, engine will handle
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 45,
    },

    # ─── CONDITIONAL: Agricultural / LCB ──────────────────────────────────
    {
        'document_type': 'LCB_CONSENT',
        'display_name': 'Land Control Board Consent',
        'description': 'Required for agricultural land. The Land Control Board must consent to the transfer of agricultural land under the Land Control Act.',
        'upload_hint': 'Upload your Land Control Board consent letter (if already obtained)',
        'phase': 'PHASE_2',
        'is_core': False,
        'condition_rules': {'is_agricultural': True},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 50,
    },

    # ─── CONDITIONAL: Spousal / Matrimonial ───────────────────────────────
    {
        'document_type': 'SPOUSAL_CONSENT',
        'display_name': 'Spousal Consent / Matrimonial Documentation',
        'description': 'If the property owner is married, spousal consent may be required under the Matrimonial Property Act. '
                       'Upload the spouse\'s signed consent affidavit.',
        'upload_hint': 'Upload spousal consent affidavit',
        'phase': 'PHASE_1',
        'is_core': False,
        'condition_rules': {'has_spousal_interest': 'YES'},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 55,
    },

    # ─── CONDITIONAL: Subdivision ─────────────────────────────────────────
    {
        'document_type': 'SUBDIVISION_PLAN',
        'display_name': 'Approved Subdivision Plan / Scheme Plan',
        'description': 'If the parcel is part of a subdivision, the approved subdivision / scheme plan is needed to confirm plot boundaries.',
        'upload_hint': 'Upload the approved subdivision or scheme plan',
        'phase': 'PHASE_1',
        'is_core': False,
        'condition_rules': {'is_subdivided': True},
        'primary_reviewer_role': 'SURVEYOR',
        'sort_order': 60,
    },
    {
        'document_type': 'MUTATION_FORM',
        'display_name': 'Mutation Form',
        'description': 'Required for subdivisions — the mutation form records the new parcels created from the original title.',
        'upload_hint': 'Upload the mutation form',
        'phase': 'PHASE_1',
        'is_core': False,
        'condition_rules': {'is_subdivided': True},
        'primary_reviewer_role': 'SURVEYOR',
        'sort_order': 65,
    },

    # ─── CONDITIONAL: Company Ownership ───────────────────────────────────
    {
        'document_type': 'COMPANY_CERTIFICATE',
        'display_name': 'Certificate of Incorporation',
        'description': 'Required when the property is owned by a company. Upload the company\'s certificate of incorporation.',
        'upload_hint': 'Upload the certificate of incorporation',
        'phase': 'PHASE_1',
        'is_core': False,
        'condition_rules': {'ownership_type': 'COMPANY'},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 70,
    },
    {
        'document_type': 'BOARD_RESOLUTION',
        'display_name': 'Board Resolution / Authority to Sell',
        'description': 'A board resolution authorizing the sale of the property, signed by company directors.',
        'upload_hint': 'Upload the board resolution',
        'phase': 'PHASE_1',
        'is_core': False,
        'condition_rules': {'ownership_type': 'COMPANY'},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 75,
    },
    {
        'document_type': 'COMPANY_KRA',
        'display_name': 'Company KRA PIN Certificate',
        'description': 'The company\'s KRA PIN certificate for stamp duty assessment.',
        'upload_hint': 'Upload the company KRA PIN certificate',
        'phase': 'PHASE_1',
        'is_core': False,
        'condition_rules': {'ownership_type': 'COMPANY'},
        'primary_reviewer_role': 'OPERATIONS',
        'sort_order': 80,
    },

    # ─── CONDITIONAL: Estate / Succession ─────────────────────────────────
    {
        'document_type': 'GRANT_PROBATE',
        'display_name': 'Grant of Probate',
        'description': 'Required when selling from a deceased owner\'s estate where there is a valid will.',
        'upload_hint': 'Upload the Grant of Probate',
        'phase': 'PHASE_1',
        'is_core': False,
        'condition_rules': {'ownership_type': 'ESTATE'},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 85,
    },
    {
        'document_type': 'LETTERS_ADMIN',
        'display_name': 'Letters of Administration',
        'description': 'Required when selling from a deceased owner\'s estate where there is no will (intestacy).',
        'upload_hint': 'Upload Letters of Administration',
        'phase': 'PHASE_1',
        'is_core': False,
        'condition_rules': {'ownership_type': 'ESTATE'},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 90,
    },
    {
        'document_type': 'CONFIRMATION_GRANT',
        'display_name': 'Certificate of Confirmation of Grant',
        'description': 'Confirms that the grant of probate or letters of administration have been registered.',
        'upload_hint': 'Upload the Confirmation of Grant',
        'phase': 'PHASE_1',
        'is_core': False,
        'condition_rules': {'ownership_type': 'ESTATE'},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 95,
    },

    # ─── PHASE 2 ONLY: Survey ─────────────────────────────────────────────
    {
        'document_type': 'SURVEY_PLAN',
        'display_name': 'Survey Plan',
        'description': 'A professional survey plan showing the parcel boundaries, beacons, and measurements.',
        'upload_hint': 'Upload the survey plan',
        'phase': 'PHASE_2',
        'is_core': False,
        'condition_rules': {},
        'primary_reviewer_role': 'SURVEYOR',
        'sort_order': 100,
    },

    # ─── PHASE 2 ONLY: Charge/Mortgage ────────────────────────────────────
    {
        'document_type': 'CHARGE_INSTRUMENT',
        'display_name': 'Charge / Discharge Instrument',
        'description': 'If the property has a charge (mortgage), upload the charge instrument or discharge certificate.',
        'upload_hint': 'Upload the charge or discharge instrument',
        'phase': 'PHASE_2',
        'is_core': False,
        'condition_rules': {},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 110,
    },
    {
        'document_type': 'LENDER_CONSENT',
        'display_name': 'Lender Consent',
        'description': 'Required when selling a property with an existing charge/mortgage — the lender must consent.',
        'upload_hint': 'Upload the lender consent letter',
        'phase': 'PHASE_2',
        'is_core': False,
        'condition_rules': {},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 115,
    },

    # ─── PHASE 2 ONLY: Valuation & Stamp Duty ────────────────────────────
    {
        'document_type': 'VALUATION_REPORT',
        'display_name': 'Valuation Report',
        'description': 'A professional valuation report for stamp duty assessment purposes.',
        'upload_hint': 'Upload the valuation report',
        'phase': 'PHASE_2',
        'is_core': False,
        'condition_rules': {},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 120,
    },
    {
        'document_type': 'STAMP_DUTY_RECEIPT',
        'display_name': 'Stamp Duty Assessment / Payment',
        'description': 'The stamp duty assessment and payment receipt from KRA iTax.',
        'upload_hint': 'Upload the stamp duty receipt',
        'phase': 'PHASE_2',
        'is_core': False,
        'condition_rules': {},
        'primary_reviewer_role': 'LAWYER',
        'sort_order': 125,
    },
]


class Command(BaseCommand):
    help = 'Seed the VerificationDocumentRequirement table with Kenyan due-diligence rules'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear', action='store_true',
            help='Delete all existing requirements before seeding',
        )

    def handle(self, *args, **options):
        if options['clear']:
            deleted, _ = VerificationDocumentRequirement.objects.all().delete()
            self.stdout.write(self.style.WARNING(f'Deleted {deleted} existing requirements'))

        created_count = 0
        updated_count = 0
        for req_data in REQUIREMENTS:
            obj, created = VerificationDocumentRequirement.objects.update_or_create(
                document_type=req_data['document_type'],
                phase=req_data['phase'],
                defaults={
                    'display_name': req_data['display_name'],
                    'description': req_data['description'],
                    'upload_hint': req_data.get('upload_hint', ''),
                    'is_core': req_data['is_core'],
                    'condition_rules': req_data['condition_rules'],
                    'primary_reviewer_role': req_data['primary_reviewer_role'],
                    'sort_order': req_data['sort_order'],
                    'is_active': True,
                    'ai_screening_enabled': True,
                    'customer_visible': True,
                },
            )
            if created:
                created_count += 1
            else:
                updated_count += 1

        self.stdout.write(self.style.SUCCESS(
            f'OK - Seeded {created_count} new + {updated_count} updated requirements ({len(REQUIREMENTS)} total rules)'
        ))
