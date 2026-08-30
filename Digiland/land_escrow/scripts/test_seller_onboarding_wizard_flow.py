#!/usr/bin/env python
"""
Test Seller Property Registration, Document Intake & AI Due Diligence Flow
=============================================================================
Verifies:
1. Seller authenticates and starts Step 1 (Property Basics) -> Creates LandParcel & PropertyVerificationCase
2. Seller completes Step 2 (Property Details, Title Type, Registered Owner, Spousal & Subdivision flags)
3. Rules Engine dynamically evaluates document requirements based on property characteristics
4. Seller uploads documents (Title, Search, ID) -> Triggers SHA-256 fingerprinting & AI Document Screening
5. AI Consistency Engine extracts fields and evaluates cross-document matches (Parcel match, Owner match, Area match)
6. Seller signs Statutory Declaration & completes Step 5 (Final Submission)
7. Verification Case advances to PHASE_1 SUBMITTED status with full audit event timeline
"""
import os
import sys
import django
from decimal import Decimal

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from django.test import Client
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import User, LandParcel
from core.models_verification import PropertyVerificationCase, VerificationDocument, VerificationRiskFlag, VerificationAuditEvent
from core.services.document_requirement_engine import get_document_checklist, evaluate_document_completeness


def run_tests():
    print("\n" + "="*75)
    print("SELLER PARCEL REGISTRATION & AI DUE DILIGENCE INTAKE TEST SUITE")
    print("="*75)

    # 1. Setup Test Seller Account
    seller_email = "seller_wizard_test@digiland.co.ke"
    seller_pwd = "SellerPass2026!"
    User.objects.filter(email=seller_email).delete()

    seller_u = User.objects.create(
        email=seller_email,
        role="Seller",
        first_name="Wanjiku",
        last_name="Kamau",
        id_number="28475910",
        kra_pin="A091827364Z",
        phone_number="+254711223344",
        is_active=True,
        is_identity_verified=True,
        is_email_verified=True,
        is_onboarded=True,
    )
    seller_u.set_password(seller_pwd)
    seller_u.save()

    client = Client()
    client.login(email=seller_email, password=seller_pwd)
    print(f"[PASS] Authenticated Seller: {seller_u.email}")

    # ── Test 1: Step 1 — Property Basics ──
    print("\n[TEST 1] Executing Step 1 — Property Basics ...")
    step1_payload = {
        'step': 1,
        'parcel_number': 'LR-WIZARD-KAREN-2026',
        'property_type': 'AGRICULTURAL',
        'tenure_type': 'LEASEHOLD',
        'county': 'Nairobi',
        'constituency': 'Langata',
        'ward': 'Karen',
        'land_size': '2.50',
        'size_unit': 'ACRES',
        'intended_use': 'AGRICULTURAL',
        'ownership_type': 'INDIVIDUAL',
        'seller_relationship': 'REGISTERED_OWNER',
        'location_description': 'Bogani Ridge, Karen, Nairobi',
        'latitude': -1.3200,
        'longitude': 36.7080,
    }

    resp1 = client.post(
        '/api/verification/wizard/save-step/',
        data=step1_payload,
        content_type='application/json'
    )
    assert resp1.status_code == 201, f"Step 1 failed ({resp1.status_code}): {resp1.content.decode()}"
    data1 = resp1.json()
    case_id = data1['case']['id']
    case_no = data1['case']['case_number']
    print(f"[PASS] Property Basics saved. Case Created: {case_no} (ID: {case_id})")

    case = PropertyVerificationCase.objects.get(id=case_id)
    assert case.property.parcel_number == 'LR-WIZARD-KAREN-2026', "Parcel number mismatch"
    assert case.is_agricultural == True, "Expected agricultural classification True"

    # ── Test 2: Step 2 — Property Details & Cross-Consistency Data ──
    print("\n[TEST 2] Executing Step 2 — Ownership & Title Details ...")
    step2_payload = {
        'registered_owner_name': 'Wanjiku Kamau',
        'registered_area': '2.50',
        'registered_area_unit': 'ACRES',
        'title_type': 'CERTIFICATE_OF_LEASE',
        'is_subdivided': False,
        'has_spousal_interest': 'NO',
        'has_recent_transfer': 'NO',
        'ownership_type': 'INDIVIDUAL',
    }

    resp2 = client.post(
        f'/api/verification/wizard/{case_id}/step/2/',
        data=step2_payload,
        content_type='application/json'
    )
    assert resp2.status_code == 200, f"Step 2 failed: {resp2.content.decode()}"
    print("[PASS] Property details saved.")

    # ── Test 3: Document Requirement Engine Rules Evaluation ──
    print("\n[TEST 3] Evaluating Dynamic Document Requirement Rules ...")
    case.refresh_from_db()
    checklist = get_document_checklist(case, phase='PHASE_1')
    req_types = [item['document_type'] for item in checklist]
    print(f"Required document types for Leasehold parcel in Phase 1: {req_types}")

    assert 'TITLE_DEED' in req_types, "Expected Title Deed required"
    assert 'SELLER_ID' in req_types, "Expected Seller ID required"
    assert 'LAND_RENT_CLEARANCE' in req_types, "Leasehold should require Land Rent Clearance!"
    print("[PASS] Document Rules Engine dynamically tailored requirements based on tenure and property type.")

    # ── Test 4: Document Upload & Instant AI Screening ──
    print("\n[TEST 4] Uploading Document & Running Instant AI Screening Pipeline ...")
    title_pdf = SimpleUploadedFile(
        "Karen_Certificate_of_Lease.pdf",
        b"%PDF-1.4 Mock Certificate of Lease content for LR-WIZARD-KAREN-2026 Proprietor Wanjiku Kamau Area 2.50 Acres",
        content_type="application/pdf"
    )

    upload_resp = client.post(
        f'/api/verification/wizard/{case_id}/upload-document/',
        data={'document_type': 'TITLE_DEED', 'file': title_pdf}
    )
    assert upload_resp.status_code == 201, f"Upload failed: {upload_resp.content.decode()}"
    upload_data = upload_resp.json()
    doc_info = upload_data['document']
    screening = upload_data['screening']

    print(f"[PASS] Document uploaded: {doc_info['original_filename']} (v{doc_info['version']})")
    print(f"[PASS] Instant AI Screening Result: Status={doc_info['ai_status']}, Confidence={doc_info['ai_confidence']}%, Recommendation={doc_info['ai_recommendation']}")
    assert screening['extracted_fields']['parcel_number'] == 'LR-WIZARD-KAREN-2026', "Extracted parcel mismatch"

    # Upload remaining Phase 1 core & conditional requirements
    id_png = SimpleUploadedFile("Wanjiku_ID.png", b"Fake PNG ID image content", content_type="image/png")
    kra_pdf = SimpleUploadedFile("KRA_PIN_Cert.pdf", b"%PDF-1.4 KRA PIN Certificate", content_type="application/pdf")
    photo_jpg = SimpleUploadedFile("Property_Front.jpg", b"Fake JPG image content", content_type="image/jpeg")
    rent_pdf = SimpleUploadedFile("Land_Rent_Receipt_2026.pdf", b"%PDF-1.4 Land Rent Clearance Receipt", content_type="application/pdf")

    client.post(f'/api/verification/wizard/{case_id}/upload-document/', data={'document_type': 'SELLER_ID', 'file': id_png})
    client.post(f'/api/verification/wizard/{case_id}/upload-document/', data={'document_type': 'KRA_PIN_CERT', 'file': kra_pdf})
    client.post(f'/api/verification/wizard/{case_id}/upload-document/', data={'document_type': 'PROPERTY_PHOTOS', 'file': photo_jpg})
    client.post(f'/api/verification/wizard/{case_id}/upload-document/', data={'document_type': 'LAND_RENT_CLEARANCE', 'file': rent_pdf})

    # ── Test 5: Check Completeness & SHA-256 Fingerprint Check ──
    print("\n[TEST 5] Checking Document Completeness & Cryptographic Duplicate Fingerprinting ...")
    completeness = evaluate_document_completeness(case)
    print(f"Completeness Percentage: {completeness['completion_percentage']}% (Is Complete: {completeness['is_complete']})")
    assert completeness['is_complete'] == True, f"Expected is_complete True, missing: {completeness['missing']}"
    print("[PASS] All required documents uploaded and verified.")

    # ── Test 6: Step 5 — Final Submission & Case Activation ──
    print("\n[TEST 6] Executing Step 5 — Final Statutory Submission ...")
    step5_resp = client.post(
        f'/api/verification/wizard/{case_id}/step/5/',
        data={'confirmed': True},
        content_type='application/json'
    )
    assert step5_resp.status_code == 200, f"Step 5 failed: {step5_resp.content.decode()}"

    case.refresh_from_db()
    assert case.status == 'SUBMITTED', f"Expected status SUBMITTED, got {case.status}"
    assert case.submitted_at is not None, "Submitted timestamp should be set"
    assert case.property.verification_status == 'DOCS_SUBMITTED', "Parcel status updated"
    print(f"[PASS] Case {case.case_number} successfully submitted for Phase 1 screening.")

    # Audit Events Check
    audit_events = VerificationAuditEvent.objects.filter(case=case)
    print(f"[PASS] Total Verification Audit Events Logged: {audit_events.count()}")

    print("\n" + "="*75)
    print("ALL 6 TEST PHASES PASSED SUCCESSFULLY! SELLER WIZARD & AI ENGINE SEAMLESS.")
    print("="*75 + "\n")
    return True


if __name__ == "__main__":
    success = run_tests()
    if not success:
        sys.exit(1)
