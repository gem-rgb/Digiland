"""
Document Requirement Engine
============================

Rules-driven engine that determines which documents are required for a
PropertyVerificationCase based on its property characteristics (tenure,
ownership type, subdivision status, agricultural classification, etc.).

This replaces the hardcoded compliance checks in the existing
`upload_parcel_document` view (Title + ID + Photo + Spousal Consent).
"""

from core.models_verification import (
    PropertyVerificationCase,
    VerificationDocumentRequirement,
)


def get_applicable_requirements(case: PropertyVerificationCase, phase: str = None) -> list[VerificationDocumentRequirement]:
    """
    Evaluate all active document requirement rules against a verification case
    and return the ones that apply.

    Args:
        case: The PropertyVerificationCase to evaluate.
        phase: Optional filter — 'PHASE_1', 'PHASE_2', or None for all.

    Returns:
        List of VerificationDocumentRequirement objects that apply.
    """
    qs = VerificationDocumentRequirement.objects.filter(is_active=True)
    if phase:
        qs = qs.filter(phase__in=[phase, 'BOTH'])

    applicable = []
    for req in qs.order_by('sort_order', 'display_name'):
        if req.is_core or req.matches_case(case):
            applicable.append(req)

    return applicable


def get_document_checklist(case: PropertyVerificationCase, phase: str = None) -> list[dict]:
    """
    Generate the full document checklist for a verification case, including
    upload status and AI screening results.

    Returns a list of dicts for frontend consumption:
    [
        {
            "requirement_id": "...",
            "document_type": "TITLE_DEED",
            "display_name": "Title Deed / Certificate of Lease",
            "description": "...",
            "upload_hint": "...",
            "is_required": True,
            "phase": "PHASE_1",
            "sort_order": 10,
            "accepted_formats": "PDF, JPG, PNG",
            "max_file_size_mb": 20,
            "status": "UPLOADED" | "AI_SCREENED" | "NOT_UPLOADED" | ...,
            "document": { ... } | None,  # uploaded doc summary
        },
        ...
    ]
    """
    requirements = get_applicable_requirements(case, phase)
    uploaded_docs = {
        doc.document_type: doc
        for doc in case.verification_documents.filter(
            verification_status__in=[
                'UPLOADED', 'PROCESSING', 'AI_SCREENED', 'AI_FLAGGED',
                'UNABLE_TO_VERIFY', 'HUMAN_REVIEW', 'HUMAN_VERIFIED',
            ]
        ).exclude(
            verification_status='SUPERSEDED'
        ).order_by('-version')
    }

    checklist = []
    for req in requirements:
        doc = uploaded_docs.get(req.document_type)
        entry = {
            'requirement_id': str(req.id),
            'document_type': req.document_type,
            'display_name': req.display_name,
            'description': req.description,
            'upload_hint': req.upload_hint,
            'is_required': req.is_core or req.matches_case(case),
            'phase': req.phase,
            'sort_order': req.sort_order,
            'accepted_formats': req.accepted_formats,
            'max_file_size_mb': req.max_file_size_mb,
            'customer_visible': req.customer_visible,
            'status': doc.verification_status if doc else 'NOT_UPLOADED',
            'document': _serialize_document(doc) if doc else None,
        }
        checklist.append(entry)

    return checklist


def evaluate_document_completeness(case: PropertyVerificationCase) -> dict:
    """
    Evaluate how complete the document submission is for a case.

    Returns:
    {
        "total_required": 5,
        "total_uploaded": 3,
        "total_verified": 2,
        "missing": ["OFFICIAL_SEARCH", "LAND_RATES_CLEARANCE"],
        "is_complete": False,
        "completion_percentage": 60.0,
        "can_submit": False,
        "blockers": ["Missing required document: Official Land Search"]
    }
    """
    requirements = get_applicable_requirements(case, phase=case.current_phase)
    required_reqs = [r for r in requirements if r.is_core or r.matches_case(case)]

    uploaded_types = set(
        case.verification_documents.exclude(
            verification_status__in=['SUPERSEDED', 'REJECTED', 'EXPIRED']
        ).values_list('document_type', flat=True)
    )

    verified_types = set(
        case.verification_documents.filter(
            verification_status__in=['AI_SCREENED', 'HUMAN_VERIFIED']
        ).values_list('document_type', flat=True)
    )

    missing = [r.document_type for r in required_reqs if r.document_type not in uploaded_types]
    blockers = [f"Missing required document: {r.display_name}" for r in required_reqs if r.document_type in missing]

    total_required = len(required_reqs)
    total_uploaded = len([r for r in required_reqs if r.document_type in uploaded_types])
    total_verified = len([r for r in required_reqs if r.document_type in verified_types])

    return {
        'total_required': total_required,
        'total_uploaded': total_uploaded,
        'total_verified': total_verified,
        'missing': missing,
        'is_complete': len(missing) == 0,
        'completion_percentage': round((total_uploaded / total_required * 100) if total_required else 100, 1),
        'can_submit': len(missing) == 0,
        'blockers': blockers,
    }


def _serialize_document(doc) -> dict:
    """Serialize a VerificationDocument for frontend consumption."""
    return {
        'id': str(doc.id),
        'document_type': doc.document_type,
        'original_filename': doc.original_filename,
        'file_size': doc.file_size,
        'file_url': doc.file.url if doc.file else None,
        'version': doc.version,
        'verification_status': doc.verification_status,
        'ai_status': doc.ai_status,
        'ai_confidence': float(doc.ai_confidence) if doc.ai_confidence else None,
        'ai_confidence_level': doc.ai_confidence_level,
        'ai_classification': doc.ai_classification,
        'ai_flags': doc.ai_flags,
        'ai_recommendation': doc.ai_recommendation,
        'human_status': doc.human_status,
        'uploaded_at': doc.uploaded_at.isoformat() if doc.uploaded_at else None,
    }
