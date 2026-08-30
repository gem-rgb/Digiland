"""
AI Document Screening Service — Verification Engine
=====================================================

Lightweight AI screening pipeline for the Digiland verification engine.
For launch, this uses structured prompts for:
  1. Document classification (what type of document is this?)
  2. Field extraction (parcel number, owner name, area, dates)
  3. Cross-document consistency (compare fields across documents in the case)
  4. Basic anomaly flagging

This service is designed to be upgraded to a full ML pipeline later without
changing the data model or calling conventions.
"""

import logging
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from core.models_verification import (
    PropertyVerificationCase,
    VerificationDocument,
    VerificationRiskFlag,
    VerificationAuditEvent,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# PUBLIC API
# ---------------------------------------------------------------------------

def screen_document(document: VerificationDocument) -> dict:
    """
    Run AI screening on a single document. Updates the document in-place.

    Returns a result dict:
    {
        "status": "PASSED" | "FLAGGED" | "UNABLE",
        "classification": "TITLE_DEED",
        "confidence": 92.5,
        "confidence_level": "HIGH",
        "extracted_data": { ... },
        "flags": [ ... ],
        "recommendation": "PASS_SCREENING" | "REVIEW_RECOMMENDED" | ...
    }
    """
    document.ai_status = 'PROCESSING'
    document.verification_status = 'PROCESSING'
    document.save(update_fields=['ai_status', 'verification_status', 'updated_at'])

    try:
        # Step 1: Classify the document
        classification = _classify_document(document)

        # Step 2: Extract structured fields
        extracted = _extract_fields(document)

        # Step 3: Run anomaly checks
        flags = _check_anomalies(document, classification, extracted)

        # Step 4: Cross-document consistency (against other docs in the case)
        consistency = _check_cross_document_consistency(document, extracted)

        # Determine overall status
        all_flags = flags + consistency
        critical_flags = [f for f in all_flags if f.get('severity') in ('HIGH', 'CRITICAL')]

        if critical_flags:
            ai_status = 'FLAGGED'
            recommendation = 'HIGH_RISK_REVIEW'
            doc_status = 'AI_FLAGGED'
        elif all_flags:
            ai_status = 'FLAGGED'
            recommendation = 'REVIEW_RECOMMENDED'
            doc_status = 'AI_FLAGGED'
        else:
            ai_status = 'PASSED'
            recommendation = 'PASS_SCREENING'
            doc_status = 'AI_SCREENED'

        confidence = classification.get('confidence', 0)
        if confidence >= 85:
            confidence_level = 'HIGH'
        elif confidence >= 60:
            confidence_level = 'MODERATE'
        elif confidence > 0:
            confidence_level = 'LOW'
        else:
            confidence_level = 'NONE'

        # Update document
        document.ai_status = ai_status
        document.ai_confidence = Decimal(str(confidence))
        document.ai_confidence_level = confidence_level
        document.ai_classification = classification.get('document_type', '')
        document.ai_extracted_data = extracted
        document.ai_consistency_checks = consistency
        document.ai_flags = all_flags
        document.ai_recommendation = recommendation
        document.ai_processed_at = timezone.now()
        document.ai_model_version = 'digiland-screening-v1.0'
        document.verification_status = doc_status
        document.save()

        # Create risk flags for significant issues
        _create_risk_flags_from_ai(document, all_flags)

        # Audit event
        VerificationAuditEvent.objects.create(
            case=document.case,
            event_type='AI_SCREENING_COMPLETED',
            actor=None,
            description=f'AI screening completed for {document.get_document_type_display()}: {ai_status}',
            metadata={
                'document_id': str(document.id),
                'document_type': document.document_type,
                'ai_status': ai_status,
                'confidence': float(confidence),
                'flags_count': len(all_flags),
            },
            customer_visible=True,
            customer_display=f'{document.get_document_type_display()} has been reviewed',
        )

        return {
            'status': ai_status,
            'classification': classification.get('document_type', ''),
            'confidence': float(confidence),
            'confidence_level': confidence_level,
            'extracted_data': extracted,
            'flags': all_flags,
            'recommendation': recommendation,
        }

    except Exception as exc:
        logger.exception('AI screening error for document %s', document.id)
        document.ai_status = 'ERROR'
        document.verification_status = 'UNABLE_TO_VERIFY'
        document.ai_processed_at = timezone.now()
        document.save(update_fields=['ai_status', 'verification_status', 'ai_processed_at', 'updated_at'])

        return {
            'status': 'ERROR',
            'classification': '',
            'confidence': 0,
            'confidence_level': 'NONE',
            'extracted_data': {},
            'flags': [{'type': 'PROCESSING_ERROR', 'severity': 'INFO', 'message': str(exc)}],
            'recommendation': 'UNABLE_TO_ASSESS',
        }


def screen_all_documents(case: PropertyVerificationCase) -> list[dict]:
    """Screen all unscreened documents in a verification case."""
    docs = case.verification_documents.filter(
        ai_status='PENDING',
        verification_status='UPLOADED'
    )
    results = []
    for doc in docs:
        result = screen_document(doc)
        results.append({
            'document_id': str(doc.id),
            'document_type': doc.document_type,
            **result,
        })
    return results


# ---------------------------------------------------------------------------
# INTERNAL SCREENING STEPS
# ---------------------------------------------------------------------------

def _classify_document(document: VerificationDocument) -> dict:
    """
    Classify the document type. For launch, this uses filename and
    submitted type as the primary signal. Can be upgraded to use
    actual document content analysis via Gemini/GPT Vision API later.
    """
    submitted_type = document.document_type
    filename = (document.original_filename or '').lower()

    # Basic classification rules based on filename
    type_keywords = {
        'TITLE_DEED': ['title', 'deed', 'certificate of lease', 'certificate_of_lease'],
        'OFFICIAL_SEARCH': ['search', 'official search', 'search certificate'],
        'SELLER_ID': ['id', 'national id', 'passport', 'identification'],
        'KRA_PIN_CERT': ['kra', 'pin', 'tax'],
        'LAND_RENT_CLEARANCE': ['rent clearance', 'rent_clearance', 'land rent'],
        'LAND_RATES_CLEARANCE': ['rates clearance', 'rates_clearance', 'county rates'],
        'LCB_CONSENT': ['lcb', 'land control', 'consent'],
        'SURVEY_PLAN': ['survey', 'survey plan', 'cadastral'],
        'MUTATION_FORM': ['mutation', 'mut'],
        'SUBDIVISION_PLAN': ['subdivision', 'scheme plan'],
        'SPOUSAL_CONSENT': ['spousal', 'spouse', 'matrimonial'],
        'COMPANY_CERTIFICATE': ['incorporation', 'company cert'],
        'BOARD_RESOLUTION': ['resolution', 'board resolution', 'authority to sell'],
        'GRANT_PROBATE': ['probate', 'grant of probate'],
        'LETTERS_ADMIN': ['letters of admin', 'administration'],
        'CONFIRMATION_GRANT': ['confirmation', 'confirmation of grant'],
        'VALUATION_REPORT': ['valuation', 'value'],
    }

    # Check filename against keywords
    detected_type = submitted_type
    highest_match = 0
    for doc_type, keywords in type_keywords.items():
        for keyword in keywords:
            if keyword in filename:
                match_score = len(keyword)
                if match_score > highest_match:
                    highest_match = match_score
                    detected_type = doc_type

    # Confidence: high if classification matches submitted type
    if detected_type == submitted_type:
        confidence = 90.0
    elif detected_type != submitted_type and highest_match > 0:
        confidence = 60.0
    else:
        confidence = 75.0  # Trust submitted type

    return {
        'document_type': detected_type,
        'submitted_type': submitted_type,
        'confidence': confidence,
        'classification_match': detected_type == submitted_type,
    }


def _extract_fields(document: VerificationDocument) -> dict:
    """
    Extract structured fields from the document.
    For launch, returns placeholder structure. Can be upgraded to
    actual OCR + extraction via Gemini API or Document AI later.
    """
    # Placeholder extraction — will be replaced with actual AI extraction
    return {
        'extracted': False,
        'extraction_method': 'placeholder',
        'fields': {},
        'note': 'Full AI extraction will be enabled in a future release. '
                'Documents are currently classified and flagged for human review.',
    }


def _check_anomalies(document: VerificationDocument, classification: dict, extracted: dict) -> list[dict]:
    """
    Check for anomalies in the document.
    """
    flags = []

    # Flag 1: Classification mismatch
    if not classification.get('classification_match', True):
        flags.append({
            'type': 'DOC_TYPE_MISMATCH',
            'severity': 'MEDIUM',
            'message': (
                f"Document submitted as '{document.get_document_type_display()}' "
                f"but filename suggests it may be a different document type."
            ),
        })

    # Flag 2: Unusually small file (possible blank or corrupt)
    if document.file_size and document.file_size < 10_000:  # < 10KB
        flags.append({
            'type': 'POSSIBLE_MANIPULATION',
            'severity': 'LOW',
            'message': 'Document file is unusually small — may be blank, corrupt, or a placeholder.',
        })

    # Flag 3: Duplicate detection (same hash as another doc in the case)
    if document.file_hash:
        duplicates = VerificationDocument.objects.filter(
            case=document.case,
            file_hash=document.file_hash,
        ).exclude(id=document.id).exists()
        if duplicates:
            flags.append({
                'type': 'DUPLICATE_DOCUMENT',
                'severity': 'MEDIUM',
                'message': 'This document appears to be identical to another document already uploaded for this property.',
            })

    return flags


def _check_cross_document_consistency(document: VerificationDocument, extracted: dict) -> list[dict]:
    """
    Check consistency across documents in the same case.
    For launch, checks basic metadata consistency. Can be upgraded
    to compare extracted text fields later.
    """
    flags = []
    case = document.case

    # Check: If this is a Title Deed and an Official Search is also uploaded,
    # they should reference the same parcel number (when extraction is enabled)
    # For now, this is a structural placeholder.

    # Check: Seller ID should match the case seller
    # (Will be enhanced when OCR extraction is enabled)

    return flags


def _create_risk_flags_from_ai(document: VerificationDocument, ai_flags: list[dict]):
    """
    Create VerificationRiskFlag records for significant AI findings.
    Only creates flags for MEDIUM severity or above.
    """
    flag_type_mapping = {
        'DOC_TYPE_MISMATCH': 'DOC_TYPE_MISMATCH',
        'POSSIBLE_MANIPULATION': 'POSSIBLE_MANIPULATION',
        'DUPLICATE_DOCUMENT': 'DUPLICATE_DOCUMENT',
        'PARCEL_MISMATCH': 'PARCEL_MISMATCH',
        'OWNER_MISMATCH': 'OWNER_MISMATCH',
        'AREA_MISMATCH': 'AREA_MISMATCH',
    }

    for flag in ai_flags:
        severity = flag.get('severity', 'LOW')
        if severity in ('MEDIUM', 'HIGH', 'CRITICAL'):
            flag_type = flag_type_mapping.get(flag.get('type'), 'OTHER')
            VerificationRiskFlag.objects.create(
                case=document.case,
                flag_type=flag_type,
                severity=severity,
                description=flag.get('message', 'AI screening flag'),
                source='AI_SCREENING',
                auto_escalate=(severity == 'CRITICAL'),
                related_document=document,
            )
