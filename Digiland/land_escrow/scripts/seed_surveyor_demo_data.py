import os
import sys
import django
from django.utils import timezone
from datetime import timedelta

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import (
    User, LandParcel, SurveyAssignment, SurveyBeacon
)

def seed_surveyor():
    email = "surveyor_maina_test@digiland.co.ke"
    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "first_name": "Peter",
            "last_name": "Maina Kamau",
            "role": "Surveyor",
            "is_staff": True,
            "is_superuser": False,
            "is_active": True,
            "is_identity_verified": True,
            "is_email_verified": True,
            "is_onboarded": True,
            "surveyor_license_number": "ISLK-9941/2026",
            "surveyor_firm": "Maina & Associates Geospatial Surveys Ltd",
            "surveyor_county": "Kiambu & Nairobi",
            "is_surveyor_verified": True,
            "phone_number": "+254799334455",
        }
    )
    user.first_name = "Peter"
    user.last_name = "Maina Kamau"
    user.role = "Surveyor"
    user.is_staff = True
    user.is_active = True
    user.is_surveyor_verified = True
    user.surveyor_license_number = "ISLK-9941/2026"
    user.surveyor_firm = "Maina & Associates Geospatial Surveys Ltd"
    user.surveyor_county = "Kiambu & Nairobi"
    user.phone_number = "+254799334455"
    user.set_password("SurveyorPass@2026!")
    user.save()

    print(f"[OK] Surveyor ready: {user.email} (ISLK-9941/2026)")

    # Find or create parcels
    admin_u = User.objects.filter(is_superuser=True).first() or user
    p1, _ = LandParcel.objects.get_or_create(
        parcel_number="KMB/KIKUYU/BLOCK-4/1042",
        defaults={
            "county": "Kiambu",
            "constituency": "Kikuyu",
            "ward": "Kikuyu",
            "land_size": 0.5,
            "verification_status": "AGENT_VERIFYING",
            "listed_by": admin_u
        }
    )
    p2, _ = LandParcel.objects.get_or_create(
        parcel_number="NRB/KAREN/BLK-12/409",
        defaults={
            "county": "Nairobi",
            "constituency": "Langata",
            "ward": "Karen",
            "land_size": 1.2,
            "verification_status": "Verified",
            "listed_by": admin_u
        }
    )
    parcels = [p1, p2]

    # Create survey assignments for user
    for idx, parcel in enumerate(parcels):
        assign_num = f"SRV-2026-{1000 + idx}"
        assign, _ = SurveyAssignment.objects.get_or_create(
            assignment_number=assign_num,
            defaults={
                "land_parcel": parcel,
                "surveyor": user,
                "requested_by": admin_u,
                "assignment_type": "BOUNDARY_VERIFICATION" if idx == 0 else "BEACON_REESTABLISHMENT",
                "status": "FIELDWORK_IN_PROGRESS" if idx == 0 else "PRE_SURVEY_REVIEW",
                "priority": "HIGH" if idx == 0 else "NORMAL",
                "site_visit_status": "SCHEDULED" if idx == 0 else "NOT_SCHEDULED",
                "due_date": (timezone.now() + timedelta(days=5)).date(),
                "site_visit_contact_name": "Joseph Njoroge (Caretaker)",
                "site_visit_contact_phone": "+254722112233",
                "instructions": "Verify all 4 corner boundary beacons and ensure no road reserve encroachment on Eastern flank.",
            }
        )
        assign.surveyor = user
        assign.save()

        # Add sample beacons
        if not assign.beacons.exists():
            SurveyBeacon.objects.create(
                assignment=assign,
                beacon_id="BK-01",
                condition="GOOD",
                latitude=-1.248300,
                longitude=36.662100,
                status="OBSERVED",
                description="Original beacon in solid concrete found undisturbed."
            )
            SurveyBeacon.objects.create(
                assignment=assign,
                beacon_id="BK-02",
                condition="GOOD",
                latitude=-1.248600,
                longitude=36.662500,
                status="OBSERVED",
                description="Corner beacon verified against RIM sheet 4."
            )
            SurveyBeacon.objects.create(
                assignment=assign,
                beacon_id="BK-03",
                condition="DISTURBED",
                latitude=-1.248900,
                longitude=36.662300,
                status="RE_ESTABLISHED",
                description="Iron pin displaced during road drainage works; re-established per deed plan."
            )
            SurveyBeacon.objects.create(
                assignment=assign,
                beacon_id="BK-04",
                condition="GOOD",
                latitude=-1.248400,
                longitude=36.661900,
                status="OBSERVED",
                description="Northern boundary beacon verified."
            )

        print(f"[OK] Assignment created/updated: {assign.assignment_number} for {parcel.parcel_number}")

if __name__ == "__main__":
    seed_surveyor()
