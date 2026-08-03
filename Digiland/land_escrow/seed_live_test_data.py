"""
Seed Live Test Data Script

Populates persistent test records for:
1. Seller (legalhusla@gmail.com) with Promoted Parcel & Active AI Ad Campaign.
2. Buyer (buyer_demo@example.com) with Fully Verified Parcel (AGENT_APPROVED) visible on marketplace.
3. Verified Agent (agent_demo@example.com) with active verification task & check-ins.
4. Verified Lawyer (lawyer_demo@example.com) with post-transaction legal checklist duties in progress.
"""

import os
import django
from decimal import Decimal
from datetime import timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from django.utils import timezone
from core.models import (
    User, LandParcel, Document, PopupAdCampaign,
    PurchaseCommission, Transaction, DocumentAccessGrant,
    LawyerPostTransactionTask, AuditLog, AuthenticDocumentReference
)


def run_seed():
    print("Seeding live test data...")

    # 1. Ensure User Accounts
    seller, _ = User.objects.get_or_create(
        email="legalhusla@gmail.com",
        defaults={
            "role": "Seller",
            "first_name": "Legal",
            "last_name": "Husla",
            "is_active": True,
            "is_identity_verified": True,
        }
    )
    if not seller.has_usable_password():
        seller.set_password("LegalHusla2026!")
        seller.save()

    buyer, _ = User.objects.get_or_create(
        email="buyer_demo@example.com",
        defaults={
            "role": "Buyer",
            "first_name": "Demo",
            "last_name": "Buyer",
            "is_active": True,
            "is_identity_verified": True,
        }
    )
    if not buyer.has_usable_password():
        buyer.set_password("BuyerDigiland2026!")
        buyer.save()

    agent, _ = User.objects.get_or_create(
        email="agent_demo@example.com",
        defaults={
            "role": "Agent",
            "first_name": "David",
            "last_name": "Agent",
            "is_active": True,
            "is_identity_verified": True,
            "agent_county": "Nairobi",
            "agent_constituency": "Dagoretti North",
        }
    )
    if not agent.has_usable_password():
        agent.set_password("AgentDigiland2026!")
        agent.save()

    lawyer, _ = User.objects.get_or_create(
        email="lawyer_demo@example.com",
        defaults={
            "role": "Lawyer",
            "first_name": "Sarah",
            "last_name": "Lawyer",
            "is_active": True,
            "is_identity_verified": True,
        }
    )
    if not lawyer.has_usable_password():
        lawyer.set_password("LawyerDigiland2026!")
        lawyer.save()

    print("Users initialized: Seller, Buyer, Agent, Lawyer.")

    # 2. Promoted Parcel & Active AI Ad Campaign
    promoted_parcel, _ = LandParcel.objects.get_or_create(
        parcel_number="LR-PROMO-PARKLANDS-2026",
        defaults={
            "land_use_type": "Commercial",
            "county": "Nairobi",
            "constituency": "Westlands",
            "ward": "Parklands",
            "land_size": Decimal("1.5000"),
            "registered_owner_id": "12345678",
            "asking_price": Decimal("15000000.00"),
            "verification_status": "AGENT_APPROVED",
            "listed_by": seller,
            "ai_verification_score": Decimal("96.50"),
            "ai_discrepancy_flags": [],
        }
    )

    ad_campaign, _ = PopupAdCampaign.objects.get_or_create(
        parcel=promoted_parcel,
        defaults={
            "created_by": seller,
            "campaign_name": "Parklands Commercial Prime Launch",
            "popup_type": "Smart_Recommendation",
            "billing_model": "PPC",
            "headline": "Prime Commercial Parklands Investment Plot",
            "subheadline": "High-yield multi-use commercial plot with main road access.",
            "cta_text": "View Listing & Verified Docs",
            "target_counties": ["Nairobi", "Kiambu"],
            "target_buyer_categories": ["Investor", "Commercial"],
            "daily_budget": Decimal("5000.00"),
            "total_budget": Decimal("35000.00"),
            "status": "Active",
            "impressions_count": 128,
            "clicks_count": 14,
            "quality_score": 9.2,
        }
    )
    print(f"Promoted parcel ({promoted_parcel.parcel_number}) and campaign ({ad_campaign.campaign_name}) created.")

    # 3. Fully Verified Land Parcel Unlocked for Buyer Marketplace
    verified_parcel, _ = LandParcel.objects.get_or_create(
        parcel_number="LR-VERIFIED-KAREN-2026",
        defaults={
            "land_use_type": "Residential",
            "county": "Nairobi",
            "constituency": "Langata",
            "ward": "Karen",
            "land_size": Decimal("0.7500"),
            "registered_owner_id": "87654321",
            "asking_price": Decimal("25000000.00"),
            "verification_status": "AGENT_APPROVED",
            "listed_by": seller,
            "assigned_agent": agent,
            "ai_verification_score": Decimal("94.50"),
            "ai_discrepancy_flags": [],
            "assignment_expires_at": timezone.now() + timedelta(days=25),
            "last_agent_checkin_at": timezone.now(),
            "agent_checkin_notes": [
                {
                    "agent_email": agent.email,
                    "timestamp": timezone.now().isoformat(),
                    "note": "Completed site visit and verified beacons with Ministry of Lands surveyor.",
                }
            ],
        }
    )

    # Add verified documents for verified_parcel
    for doc_type, label in [("Title_Deed", "Title Deed Certificate"), ("ID_Card", "National ID Front/Back"), ("Passport_Photo", "Owner Passport Photo"), ("Spousal_Consent", "Spousal Consent Affidavit")]:
        Document.objects.get_or_create(
            land_parcel=verified_parcel,
            document_type=doc_type,
            defaults={
                "uploaded_by": seller,
                "file_url": f"documents/{doc_type.lower()}_sample.pdf",
                "verification_status": "Match",
            }
        )

    # 4. Additional Verified Land Parcel Unlocked for Marketplace (No Transaction - Always Visible)
    kilifi_parcel, _ = LandParcel.objects.get_or_create(
        parcel_number="LR-VERIFIED-KILIFI-2026",
        defaults={
            "land_use_type": "Agricultural",
            "county": "Kilifi",
            "constituency": "Kilifi North",
            "ward": "Tezo",
            "land_size": Decimal("5.0000"),
            "registered_owner_id": "99887766",
            "asking_price": Decimal("8500000.00"),
            "verification_status": "AGENT_APPROVED",
            "listed_by": seller,
            "assigned_agent": agent,
            "ai_verification_score": Decimal("98.00"),
            "ai_discrepancy_flags": [],
        }
    )

    # 5. Agent Document Access Grant & Dual Signature Record
    grant, _ = DocumentAccessGrant.objects.get_or_create(
        parcel=verified_parcel,
        accessor=agent,
        defaults={
            "seller_auth_token": "AUTH-PIN-8899",
            "accessor_auth_token": "AGENT-PIN-1122",
            "access_granted": True,
            "seller_signed_at": timezone.now() - timedelta(hours=2),
            "accessor_signed_at": timezone.now() - timedelta(hours=1),
            "expires_at": timezone.now() + timedelta(hours=23),
        }
    )

    # 5. Active Transaction & Lawyer Checklist Duties
    tx, _ = Transaction.objects.get_or_create(
        land_parcel=verified_parcel,
        defaults={
            "buyer": buyer,
            "seller": seller,
            "agent": agent,
            "agreed_price": Decimal("24500000.00"),
            "status": "Under_Verification",
            "contract_agreed": True,
        }
    )


    for task_key, label in LawyerPostTransactionTask.TASK_CHOICES:
        is_done = task_key in ["registry_search", "title_deed_check"]
        LawyerPostTransactionTask.objects.get_or_create(
            transaction=tx,
            task_key=task_key,
            defaults={
                "lawyer": lawyer,
                "completed": is_done,
                "completed_at": timezone.now() if is_done else None,
                "notes": "Verified against Ardhisasa digital title registry records." if is_done else "Pending legal clearance.",
            }
        )

    print("Fully verified parcel, agent check-ins, and lawyer checklist seeded successfully!")


if __name__ == "__main__":
    run_seed()
