from django.db import migrations
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone


def seed_demo_data(apps, schema_editor):
    User = apps.get_model('core', 'User')
    LandParcel = apps.get_model('core', 'LandParcel')
    Document = apps.get_model('core', 'Document')
    PopupAdCampaign = apps.get_model('core', 'PopupAdCampaign')
    DocumentAccessGrant = apps.get_model('core', 'DocumentAccessGrant')
    Transaction = apps.get_model('core', 'Transaction')
    LawyerPostTransactionTask = apps.get_model('core', 'LawyerPostTransactionTask')

    now = timezone.now()

    # 1. Users
    seller, _ = User.objects.get_or_create(
        email="legalhusla@gmail.com",
        defaults={
            "role": "Seller",
            "first_name": "Legal",
            "last_name": "Husla",
            "is_active": True,
            "is_onboarded": True,
            "is_identity_verified": True,
            "is_email_verified": True,
        }
    )
    if not seller.is_onboarded:
        seller.is_onboarded = True
        seller.is_identity_verified = True
        seller.is_email_verified = True
        seller.save()

    buyer, _ = User.objects.get_or_create(
        email="buyer_demo@example.com",
        defaults={
            "role": "Buyer",
            "first_name": "Demo",
            "last_name": "Buyer",
            "is_active": True,
            "is_onboarded": True,
            "is_identity_verified": True,
            "is_email_verified": True,
        }
    )
    if not buyer.is_onboarded:
        buyer.is_onboarded = True
        buyer.is_identity_verified = True
        buyer.is_email_verified = True
        buyer.save()

    agent, _ = User.objects.get_or_create(
        email="agent_demo@example.com",
        defaults={
            "role": "Agent",
            "first_name": "David",
            "last_name": "Agent",
            "is_active": True,
            "is_onboarded": True,
            "is_identity_verified": True,
            "is_email_verified": True,
            "agent_county": "Nairobi",
            "agent_constituency": "Dagoretti North",
        }
    )
    if not agent.is_onboarded:
        agent.is_onboarded = True
        agent.is_identity_verified = True
        agent.is_email_verified = True
        agent.save()

    lawyer, _ = User.objects.get_or_create(
        email="lawyer_demo@example.com",
        defaults={
            "role": "Lawyer",
            "first_name": "Sarah",
            "last_name": "Lawyer",
            "is_active": True,
            "is_onboarded": True,
            "is_identity_verified": True,
            "is_email_verified": True,
        }
    )
    if not lawyer.is_onboarded:
        lawyer.is_onboarded = True
        lawyer.is_identity_verified = True
        lawyer.is_email_verified = True
        lawyer.save()

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

    PopupAdCampaign.objects.get_or_create(
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

    # 3. Verified Kilifi Parcel (Visible on Marketplace without Transaction Lock)
    LandParcel.objects.get_or_create(
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

    # 4. Verified Karen Parcel with Active Transaction
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
            "assignment_expires_at": now + timedelta(days=25),
            "last_agent_checkin_at": now,
            "agent_checkin_notes": [
                {
                    "agent_email": agent.email,
                    "timestamp": now.isoformat(),
                    "note": "Completed site visit and verified beacons with Ministry of Lands surveyor.",
                }
            ],
        }
    )

    for doc_type in ["Title_Deed", "ID_Card", "Passport_Photo", "Spousal_Consent"]:
        Document.objects.get_or_create(
            land_parcel=verified_parcel,
            document_type=doc_type,
            defaults={
                "uploaded_by": seller,
                "file_url": f"documents/{doc_type.lower()}_sample.pdf",
                "verification_status": "Match",
            }
        )

    DocumentAccessGrant.objects.get_or_create(
        parcel=verified_parcel,
        accessor=agent,
        defaults={
            "seller_auth_token": "AUTH-PIN-8899",
            "accessor_auth_token": "AGENT-PIN-1122",
            "access_granted": True,
            "seller_signed_at": now - timedelta(hours=2),
            "accessor_signed_at": now - timedelta(hours=1),
            "expires_at": now + timedelta(hours=23),
        }
    )

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

    task_choices = [
        ('lodge_caution', 'Lodge Registry Caution/Caveat'),
        ('lcb_consent', 'Obtain Land Control Board Consent'),
        ('rates_clearance', 'Obtain Land Rates Clearance Certificate'),
        ('rent_clearance', 'Obtain Land Rent Clearance'),
        ('stamp_duty', 'Calculate & Pay Stamp Duty'),
        ('submit_transfer', 'Submit Transfer Documents to Registry'),
        ('title_handover', 'Final Title Deed Handover to Buyer'),
    ]

    for key, name in task_choices:
        is_done = key in ["lodge_caution", "lcb_consent"]
        LawyerPostTransactionTask.objects.get_or_create(
            transaction=tx,
            task_key=key,
            defaults={
                "lawyer": lawyer,
                "completed": is_done,
                "completed_at": now if is_done else None,
                "notes": "Verified against Ardhisasa digital title registry records." if is_done else "Pending legal clearance.",
            }
        )


def reverse_seed(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0041_alter_lawyerposttransactiontask_options_and_more'),
    ]

    operations = [
        migrations.RunPython(seed_demo_data, reverse_code=reverse_seed),
    ]
