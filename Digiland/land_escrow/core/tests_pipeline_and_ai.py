"""
Comprehensive Unit Tests for AI Reactivation & 7-Stage Verification Pipeline
"""

from decimal import Decimal
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.utils import timezone

from core.models import (
    AuditLog,
    AuthenticDocumentReference,
    Document,
    DocumentAccessGrant,
    LandParcel,
    PopupAdCampaign,
    User,
)
from core.services.ai_ad_campaigns import AIAdCampaignService
from core.services.ai_doc_authenticity import AIDocumentAuthenticityVerifier
from core.services.commission import (
    accept_parcel_verification_job,
    check_agent_exclusivity_lock,
)


class AIAdCampaignServiceTestCase(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller_ad_test@example.com",
            password="Password123!",
            role="Seller",
        )
        self.parcel = LandParcel.objects.create(
            parcel_number="LR-TEST-AD-101",
            land_use_type="Commercial",
            county="Nairobi",
            constituency="Westlands",
            ward="Parklands",
            land_size=Decimal("1.5000"),
            registered_owner_id="12345678",
            asking_price=Decimal("10000000.00"),
            listed_by=self.seller,
        )
        self.campaign = PopupAdCampaign.objects.create(
            parcel=self.parcel,
            created_by=self.seller,
            campaign_name="Test Campaign",
            popup_type="Smart_Recommendation",
            billing_model="PPC",
            headline="Test Headline",
            daily_budget=Decimal("5000.00"),
            impressions_count=100,
            clicks_count=5,
        )

    def test_ad_copy_generation_fallback(self):
        service = AIAdCampaignService()
        result = service.generate_ad_copy(self.parcel)
        self.assertTrue(result["success"])
        self.assertIn("Commercial", result["headline"])

    @override_settings(ENABLE_AI_AD_CAMPAIGNS=False)
    def test_disabled_feature_flag_uses_fallback(self):
        service = AIAdCampaignService()
        self.assertFalse(service.enabled)
        result = service.generate_ad_copy(self.parcel)
        self.assertFalse(result["ai_generated"])

    def test_budget_optimization(self):
        service = AIAdCampaignService()
        result = service.optimize_campaign_budget(self.campaign)
        self.assertIn("suggested_trigger_type", result)
        self.assertEqual(result["campaign_id"], str(self.campaign.id))


class PipelineVerificationTestCase(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller_pipe@example.com",
            password="Password123!",
            role="Seller",
        )
        self.agent1 = User.objects.create_user(
            email="agent1_pipe@example.com",
            password="Password123!",
            role="Agent",
            is_identity_verified=True,
        )
        self.agent2 = User.objects.create_user(
            email="agent2_pipe@example.com",
            password="Password123!",
            role="Agent",
            is_identity_verified=True,
        )
        self.parcel = LandParcel.objects.create(
            parcel_number="LR-PIPE-2026",
            land_use_type="Residential",
            county="Kiambu",
            constituency="Riru",
            ward="Kiuu",
            land_size=Decimal("0.5000"),
            registered_owner_id="87654321",
            asking_price=Decimal("4000000.00"),
            listed_by=self.seller,
            verification_status="DRAFT",
        )
        self.ref_corpus = AuthenticDocumentReference.objects.create(
            doc_type="Title_Deed",
            issuing_authority="Ministry of Lands",
            version_label="v1.0",
        )

    def test_stage_0_completeness_check_fails_when_docs_missing(self):
        verifier = AIDocumentAuthenticityVerifier()
        result = verifier.run_pipeline_stage_0_and_1(self.parcel)
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "AI_REJECTED")

    def test_stage_0_and_1_passes_with_all_docs(self):
        # Create mandatory documents
        for doc_type in ["Title_Deed", "ID_Card", "Passport_Photo", "Spousal_Consent"]:
            Document.objects.create(
                land_parcel=self.parcel,
                document_type=doc_type,
                file_url="documents/test_deed.pdf",
                uploaded_by=self.seller,
                verification_status="Uploaded",
            )



        verifier = AIDocumentAuthenticityVerifier()
        result = verifier.run_pipeline_stage_0_and_1(self.parcel)
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "AGENT_JOB_POSTED")

        # Refresh parcel
        self.parcel.refresh_from_db()
        self.assertEqual(self.parcel.verification_status, "AGENT_JOB_POSTED")

    def test_first_come_job_claiming_and_exclusivity_lock(self):
        self.parcel.verification_status = "AGENT_JOB_POSTED"
        self.parcel.save()

        # Agent 1 accepts job
        claimed = accept_parcel_verification_job(self.agent1, self.parcel)
        self.assertEqual(claimed.assigned_agent, self.agent1)
        self.assertEqual(claimed.verification_status, "AGENT_ASSIGNED")

        # Create second parcel
        parcel2 = LandParcel.objects.create(
            parcel_number="LR-PIPE-2027",
            land_use_type="Residential",
            county="Kiambu",
            constituency="Riru",
            ward="Kiuu",
            land_size=Decimal("1.0000"),
            registered_owner_id="99999999",
            asking_price=Decimal("5000000.00"),
            listed_by=self.seller,
            verification_status="AGENT_JOB_POSTED",
        )

        # Agent 1 attempts to accept parcel2 -> Should be blocked by Exclusivity Lock!
        with self.assertRaises(ValidationError) as ctx:
            accept_parcel_verification_job(self.agent1, parcel2)
        self.assertIn("Exclusivity Lock", str(ctx.exception))

        # Agent 2 can accept parcel2 cleanly
        claimed2 = accept_parcel_verification_job(self.agent2, parcel2)
        self.assertEqual(claimed2.assigned_agent, self.agent2)

    def test_ai_score_and_flags_saved_on_parcel(self):
        for doc_type in ["Title_Deed", "ID_Card", "Passport_Photo", "Spousal_Consent"]:
            Document.objects.create(
                land_parcel=self.parcel,
                document_type=doc_type,
                file_url="documents/sample_deed.pdf",
                uploaded_by=self.seller,
                verification_status="Uploaded",
            )

        verifier = AIDocumentAuthenticityVerifier()
        result = verifier.run_pipeline_stage_0_and_1(self.parcel)

        self.parcel.refresh_from_db()
        self.assertIsNotNone(self.parcel.ai_verification_score)
        self.assertIsNotNone(self.parcel.job_expires_at)

    def test_exclusivity_lock_auto_expires_after_30_days(self):
        self.parcel.verification_status = "AGENT_JOB_POSTED"
        self.parcel.save()

        # Claim job
        claimed = accept_parcel_verification_job(self.agent1, self.parcel)
        self.assertEqual(claimed.verification_status, "AGENT_ASSIGNED")

        # Artificially set assignment_expires_at to past
        claimed.assignment_expires_at = timezone.now() - timezone.timedelta(days=1)
        claimed.save()

        # Agent 1 can now accept a new job because the previous lock auto-expired!
        parcel2 = LandParcel.objects.create(
            parcel_number="LR-EXPIRE-30",
            land_use_type="Residential",
            county="Kiambu",
            constituency="Riru",
            ward="Kiuu",
            land_size=Decimal("1.0000"),
            registered_owner_id="99999999",
            asking_price=Decimal("5000000.00"),
            listed_by=self.seller,
            verification_status="AGENT_JOB_POSTED",
        )
        claimed2 = accept_parcel_verification_job(self.agent1, parcel2)
        self.assertEqual(claimed2.assigned_agent, self.agent1)

