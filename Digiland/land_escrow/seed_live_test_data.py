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
    from allauth.account.models import EmailAddress

    # Delete any temporary/duplicate test users to keep user database clean
    User.objects.filter(email__in=[
        "admin_test@digiland.co.ke",
        "admin_verified@digiland.co.ke",
        "agent_verified@digiland.co.ke",
        "lawyer_verified@digiland.co.ke",
        "buyer_verified@digiland.co.ke",
        "test_lawyer_check@digiland.co.ke",
    ]).delete()

    # Official Admin accounts
    for admin_email, first, last in [
        ("admin@digiland.co.ke", "Digiland", "Administrator"),
        ("karanitaitumu@gmail.com", "Karani", "Taitumu"),
    ]:
        admin_u, _ = User.objects.get_or_create(
            email=admin_email,
            defaults={
                "role": "Admin",
                "first_name": first,
                "last_name": last,
                "is_staff": True,
                "is_superuser": True,
                "is_active": True,
                "is_identity_verified": True,
                "is_email_verified": True,
                "is_onboarded": True,
            }
        )
        admin_u.role = "Admin"
        admin_u.is_staff = True
        admin_u.is_superuser = True
        admin_u.is_active = True
        admin_u.is_identity_verified = True
        admin_u.is_email_verified = True
        admin_u.is_onboarded = True
        admin_u.set_password("AdminDigiland2026!")
        admin_u.save()
        EmailAddress.objects.update_or_create(user=admin_u, email=admin_email, defaults={"verified": True, "primary": True})

    seller, _ = User.objects.get_or_create(
        email="legalhusla@gmail.com",
        defaults={
            "role": "Seller",
            "first_name": "Legal",
            "last_name": "Husla",
            "is_staff": False,
            "is_superuser": False,
            "is_active": True,
            "is_identity_verified": True,
            "is_email_verified": True,
            "is_onboarded": True,
        }
    )
    seller.role = "Seller"
    seller.is_staff = False
    seller.is_superuser = False
    seller.is_active = True
    seller.is_identity_verified = True
    seller.is_email_verified = True
    seller.is_onboarded = True
    seller.set_password("LegalHusla2026!")
    seller.save()
    EmailAddress.objects.update_or_create(user=seller, email="legalhusla@gmail.com", defaults={"verified": True, "primary": True})

    buyer, _ = User.objects.get_or_create(
        email="buyer_demo@example.com",
        defaults={
            "role": "Buyer",
            "first_name": "Demo",
            "last_name": "Buyer",
            "is_active": True,
            "is_identity_verified": True,
            "is_email_verified": True,
            "is_onboarded": True,
        }
    )
    buyer.role = "Buyer"
    buyer.is_active = True
    buyer.is_identity_verified = True
    buyer.is_email_verified = True
    buyer.is_onboarded = True
    buyer.set_password("BuyerDigiland2026!")
    buyer.save()
    EmailAddress.objects.update_or_create(user=buyer, email="buyer_demo@example.com", defaults={"verified": True, "primary": True})

    for agent_email, first, last in [
        ("agent_demo@example.com", "David", "Agent"),
        ("agent@digiland.co.ke", "Field", "Agent"),
    ]:
        agent, _ = User.objects.get_or_create(
            email=agent_email,
            defaults={
                "role": "Agent",
                "first_name": first,
                "last_name": last,
                "is_staff": False,
                "is_superuser": False,
                "is_active": True,
                "is_identity_verified": True,
                "is_email_verified": True,
                "is_onboarded": True,
                "agent_county": "Nairobi",
                "agent_constituency": "Dagoretti North",
            }
        )
        agent.role = "Agent"
        agent.is_staff = False
        agent.is_superuser = False
        agent.is_active = True
        agent.is_identity_verified = True
        agent.is_email_verified = True
        agent.is_onboarded = True
        agent.set_password("AgentDigiland2026!")
        agent.save()
        EmailAddress.objects.update_or_create(user=agent, email=agent_email, defaults={"verified": True, "primary": True})

    for lawyer_email, first, last in [
        ("lawyer_demo@example.com", "Sarah", "Lawyer"),
        ("lawyer@digiland.co.ke", "LSK", "Advocate"),
    ]:
        lawyer, _ = User.objects.get_or_create(
            email=lawyer_email,
            defaults={
                "role": "Lawyer",
                "first_name": first,
                "last_name": last,
                "is_staff": False,
                "is_superuser": False,
                "is_active": True,
                "is_identity_verified": True,
                "is_email_verified": True,
                "is_onboarded": True,
            }
        )
        lawyer.role = "Lawyer"
        lawyer.is_staff = False
        lawyer.is_superuser = False
        lawyer.is_active = True
        lawyer.is_identity_verified = True
        lawyer.is_email_verified = True
        lawyer.is_onboarded = True
        lawyer.set_password("LawyerDigiland2026!")
        lawyer.save()
        EmailAddress.objects.update_or_create(user=lawyer, email=lawyer_email, defaults={"verified": True, "primary": True})

    print("Users initialized: Admin, Seller, Buyer, Agent, Lawyer.")

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

    # 6. Surveyor User & Realistic Survey Assignments
    from core.models import (
        SurveyAssignment, SurveyBeacon, SurveyBoundaryObservation,
        SurveyMeasurement, SurveyDocument, SurveyIssue, SurveyReport, SurveyAuditLog
    )

    surveyor, _ = User.objects.get_or_create(
        email="surveyor_demo@example.com",
        defaults={
            "role": "Surveyor",
            "first_name": "Jane",
            "last_name": "Surveyor",
            "is_staff": False,
            "is_superuser": False,
            "is_active": True,
            "is_identity_verified": True,
            "is_email_verified": True,
            "is_onboarded": True,
            "surveyor_license_number": "ISLK-4092/2026",
            "surveyor_firm": "Geospatial Surveys Kenya Ltd",
            "surveyor_county": "Nairobi & Kiambu",
            "is_surveyor_verified": True,
            "phone_number": "+254711889900",
        }
    )
    surveyor.role = "Surveyor"
    surveyor.is_staff = False
    surveyor.is_superuser = False
    surveyor.is_active = True
    surveyor.is_identity_verified = True
    surveyor.is_email_verified = True
    surveyor.is_onboarded = True
    surveyor.surveyor_license_number = "ISLK-4092/2026"
    surveyor.surveyor_firm = "Geospatial Surveys Kenya Ltd"
    surveyor.surveyor_county = "Nairobi & Kiambu"
    surveyor.is_surveyor_verified = True
    surveyor.phone_number = "+254711889900"
    surveyor.set_password("SurveyorDigiland2026!")
    surveyor.save()
    EmailAddress.objects.update_or_create(user=surveyor, email="surveyor_demo@example.com", defaults={"verified": True, "primary": True})

    # Assignment 1: Karen Prime Parcel (Active Site Visit & Beacons Observed)
    sv1, created1 = SurveyAssignment.objects.get_or_create(
        assignment_number="SV-000101",
        defaults={
            "land_parcel": verified_parcel,
            "surveyor": surveyor,
            "requested_by": admin_u,
            "assignment_type": "BOUNDARY_VERIFICATION",
            "status": "FIELDWORK_IN_PROGRESS",
            "priority": "HIGH",
            "instructions": "Verify all 4 corner boundary beacons along Bogani Road, measure exact GPS coordinates, check live hedge abuttals, and reconcile surveyed area with RIM Sheet 42.",
            "due_date": timezone.now().date() + timedelta(days=3),
            "accepted_at": timezone.now() - timedelta(days=2),
            "site_visit_date": timezone.now().date() + timedelta(days=1),
            "site_visit_time": "09:30:00",
            "site_visit_status": "IN_PROGRESS",
            "site_visit_contact_name": "James Mwangi (Caretaker)",
            "site_visit_contact_phone": "+254722001122",
            "site_visit_assistant_names": "Dennis Otieno (Chainman), Kelvin Kiprono (RTK Tech)",
            "device_gps_lat": -1.319500,
            "device_gps_lng": 36.706200,
            "device_gps_accuracy_meters": 0.015,
            "official_documented_area_sqm": Decimal("2023.43"),
            "survey_calculated_area_sqm": Decimal("2020.15"),
            "pre_survey_checklist": {
                "parcel_ref": True,
                "seller_docs": True,
                "cadastral_rim": True,
                "coords_reviewed": True,
            },
        }
    )

    if created1 or not sv1.beacons.exists():
        # Corner beacons for Karen parcel
        beacons_data = [
            ("B01", "OBSERVED", "GOOD", -1.319350, 36.705980, Decimal("245012.35"), Decimal("9854100.12"), Decimal("1782.40"), "NW Corner beacon - Concrete post firmly seated along Bogani Rd setback"),
            ("B02", "OBSERVED", "GOOD", -1.319340, 36.706420, Decimal("245061.20"), Decimal("9854101.50"), Decimal("1782.10"), "NE Corner beacon - Iron pin in concrete block adjacent to Parcel KRN/5502"),
            ("B03", "RE_ESTABLISHED", "WEATHERED", -1.319650, 36.706410, Decimal("245060.10"), Decimal("9854067.20"), Decimal("1781.50"), "SE Corner beacon - Re-aligned with coordinate fix from mutation survey plan"),
            ("B04", "OBSERVED", "GOOD", -1.319660, 36.705970, Decimal("245011.00"), Decimal("9854065.80"), Decimal("1781.80"), "SW Corner beacon - Concrete post at South boundary live fence"),
        ]
        for b_id, stat, cond, lat, lng, east, north, elev, desc in beacons_data:
            SurveyBeacon.objects.get_or_create(
                assignment=sv1,
                beacon_id=b_id,
                defaults={
                    "status": stat,
                    "condition": cond,
                    "latitude": lat,
                    "longitude": lng,
                    "easting": east,
                    "northing": north,
                    "elevation_meters": elev,
                    "description": desc,
                }
            )

        # Boundaries
        boundary_data = [
            ("NORTH", "Bogani Park Road Reserve", "ROAD_RESERVE", "GOOD", "CONSISTENT", "Direct road frontage with 6m road reserve setback maintained."),
            ("EAST", "LR 209/18902 (Adjacent Residential)", "LIVE_HEDGE", "GOOD", "CONSISTENT", "Established kei-apple hedge aligns precisely with boundary beacons B02 and B03."),
            ("SOUTH", "LR 209/18904 (Private Residence)", "CHAIN_LINK", "FAIR", "CONSISTENT", "Chain-link fence on concrete posts conforms to cadastral mutation plan."),
            ("WEST", "LR 209/18900 (Vacant Plot)", "BARBED_WIRE", "GOOD", "CONSISTENT", "Five-strand barbed wire fence matches RIM boundary line."),
        ]
        for seg, neigh, feat, cond, cons, obs in boundary_data:
            SurveyBoundaryObservation.objects.get_or_create(
                assignment=sv1,
                segment=seg,
                defaults={
                    "neighbouring_parcel_reference": neigh,
                    "physical_feature": feat,
                    "condition_description": cond,
                    "consistency_status": cons,
                    "observation_notes": obs,
                }
            )

        # Measurements
        meas_data = [
            ("P01", Decimal("245012.35"), Decimal("9854100.12"), Decimal("1782.40"), Decimal("48.85"), "089°45'12\"", "RTK GNSS / Leica Viva GS16", "±0.012m"),
            ("P02", Decimal("245061.20"), Decimal("9854101.50"), Decimal("1782.10"), Decimal("34.30"), "178°12'05\"", "RTK GNSS / Leica Viva GS16", "±0.010m"),
            ("P03", Decimal("245060.10"), Decimal("9854067.20"), Decimal("1781.50"), Decimal("49.10"), "269°30'40\"", "RTK GNSS / Leica Viva GS16", "±0.014m"),
            ("P04", Decimal("245011.00"), Decimal("9854065.80"), Decimal("1781.80"), Decimal("34.32"), "358°50'18\"", "RTK GNSS / Leica Viva GS16", "±0.011m"),
        ]
        for pid, east, north, elev, dist, bear, inst, acc in meas_data:
            SurveyMeasurement.objects.get_or_create(
                assignment=sv1,
                point_id=pid,
                defaults={
                    "eastings": east,
                    "northings": north,
                    "elevation": elev,
                    "distance_meters": dist,
                    "bearing_degrees": bear,
                    "instrument_method": inst,
                    "accuracy_quality_note": acc,
                }
            )

        # Documents
        SurveyDocument.objects.get_or_create(
            assignment=sv1,
            title="Survey Plan & Mutation KRN/5501",
            defaults={
                "land_parcel": verified_parcel,
                "document_type": "SURVEY_PLAN",
                "source_type": "SURVEY_OF_KENYA",
                "visibility": "INTERNAL_STAFF",
                "file_format": "pdf",
                "file_size_bytes": 2450000,
                "version": 1,
                "uploaded_by": surveyor,
                "description": "Authenticated survey plan retrieved from Survey of Kenya Ruaraka headquarters.",
            }
        )

        # Audit log
        SurveyAuditLog.objects.create(
            assignment=sv1,
            user=surveyor,
            action="FIELDWORK_INITIALIZED",
            details={"beacons_observed": 4, "accuracy": "±0.012m", "status": "FIELDWORK_IN_PROGRESS"}
        )

    # Assignment 2: Runda Subdivided Parcel with Slight Discrepancy Flag
    sv2, created2 = SurveyAssignment.objects.get_or_create(
        assignment_number="SV-000102",
        defaults={
            "land_parcel": promoted_parcel,
            "surveyor": surveyor,
            "requested_by": admin_u,
            "assignment_type": "SUBDIVISION_VERIFICATION",
            "status": "DISCREPANCY_FOUND",
            "priority": "CRITICAL",
            "instructions": "Re-establish corner beacon B03 near riparian reserve and check eastern abuttal encroachment.",
            "due_date": timezone.now().date() + timedelta(days=1),
            "accepted_at": timezone.now() - timedelta(days=4),
            "site_visit_date": timezone.now().date() - timedelta(days=1),
            "site_visit_time": "11:00:00",
            "site_visit_status": "COMPLETED",
            "site_visit_contact_name": "Patrick Njoroge",
            "site_visit_contact_phone": "+254733445566",
            "device_gps_lat": -1.218500,
            "device_gps_lng": 36.812400,
            "official_documented_area_sqm": Decimal("4046.86"),
            "survey_calculated_area_sqm": Decimal("3980.20"),
            "area_discrepancy_detected": True,
            "area_discrepancy_percentage": Decimal("1.65"),
            "pre_survey_checklist": {
                "parcel_ref": True,
                "seller_docs": True,
                "cadastral_rim": True,
                "coords_reviewed": True,
            },
        }
    )

    if created2 or not sv2.issues.exists():
        SurveyIssue.objects.get_or_create(
            assignment=sv2,
            issue_number="ISS-SV-000102-01",
            defaults={
                "issue_type": "BOUNDARY_ENCROACHMENT",
                "severity": "HIGH",
                "status": "OPEN",
                "title": "East Boundary Live Fence Incursion (1.2m offset)",
                "description": "The neighboring parcel perimeter hedge extends 1.2m into the eastern boundary line, creating a 66.6 sqm area shortfall compared to Deed Plan 1982.",
                "evidence_notes": "Measured via Total Station from control point CP-04. Offset confirmed against Survey of Kenya RIM Sheet Kiambu/Block 12.",
                "surveyor_recommendation": "Notify adjacent land owner for joint boundary realignment before lawyer executes deed transfer.",
                "assigned_to": surveyor,
            }
        )

    print("Fully verified parcel, agent check-ins, lawyer checklist, and surveyor workspace data seeded successfully!")


if __name__ == "__main__":
    run_seed()
