"""
Verification Engine — Backend Views
=====================================

Endpoints for the property verification & due diligence engine:
  - Seller property registration wizard (multi-step)
  - Document upload with AI screening
  - Verification case management (staff)
  - Buyer interest expression (Phase 2 trigger)
  - Verification passport data (customer-facing)
"""

import json
import logging
import hashlib
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_GET
from django.views.decorators.csrf import csrf_protect
from django.utils import timezone
from django.urls import reverse
from django.db import transaction as db_transaction

from core.models import LandParcel, User
from core.models_verification import (
    PropertyVerificationCase,
    VerificationDocumentRequirement,
    VerificationDocument,
    VerificationLayer,
    VerificationCheckItem,
    VerificationRiskFlag,
    VerificationAuditEvent,
    BuyerInterestCase,
)
from core.services.document_requirement_engine import (
    get_document_checklist,
    evaluate_document_completeness,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def _json_body(request):
    """Parse JSON body from request."""
    try:
        return json.loads(request.body)
    except (json.JSONDecodeError, ValueError):
        return {}


def _serialize_case_summary(case):
    """Serialize a PropertyVerificationCase for frontend consumption."""
    return {
        'id': str(case.id),
        'case_number': case.case_number,
        'property_id': str(case.property_id),
        'parcel_number': case.property.parcel_number if case.property else '',
        'current_phase': case.current_phase,
        'status': case.status,
        'status_display': case.get_status_display(),
        'verification_level': case.verification_level,
        'verification_level_display': case.get_verification_level_display(),
        'property_type': case.property_type,
        'tenure_type': case.tenure_type,
        'ownership_type': case.ownership_type,
        'seller_relationship': case.seller_relationship,
        'is_subdivided': case.is_subdivided,
        'is_agricultural': case.is_agricultural,
        'has_spousal_interest': case.has_spousal_interest,
        'registered_owner_name': case.registered_owner_name,
        'overall_risk_level': case.overall_risk_level,
        'wizard_step_completed': case.wizard_step_completed,
        'created_at': case.created_at.isoformat() if case.created_at else None,
        'submitted_at': case.submitted_at.isoformat() if case.submitted_at else None,
        'pre_screened_at': case.pre_screened_at.isoformat() if case.pre_screened_at else None,
        'verified_at': case.verified_at.isoformat() if case.verified_at else None,
    }


def _serialize_layer(layer):
    """Serialize a VerificationLayer for frontend."""
    return {
        'id': str(layer.id),
        'layer_type': layer.layer_type,
        'layer_display': layer.get_layer_type_display(),
        'status': layer.status,
        'status_display': layer.get_status_display(),
        'risk_level': layer.risk_level,
        'assigned_to': layer.assigned_to.email if layer.assigned_to else None,
        'started_at': layer.started_at.isoformat() if layer.started_at else None,
        'completed_at': layer.completed_at.isoformat() if layer.completed_at else None,
        'customer_summary': layer.customer_summary,
        'check_items': [
            {
                'id': str(ci.id),
                'check_name': ci.check_name,
                'status': ci.status,
                'customer_visible': ci.customer_visible,
                'customer_display_text': ci.customer_display_text,
                'timestamp_display': ci.timestamp_display.isoformat() if ci.timestamp_display else None,
            }
            for ci in layer.check_items.all()
        ],
    }


# ---------------------------------------------------------------------------
# SELLER PROPERTY REGISTRATION WIZARD
# ---------------------------------------------------------------------------

@login_required
def verification_wizard(request):
    """
    Main wizard endpoint. GET returns the current wizard state.
    POST creates a new verification case (Step 1).
    """
    if request.user.role not in ('Seller', 'Admin'):
        return JsonResponse({'error': 'Only sellers can register properties.'}, status=403)

    if request.method == 'GET':
        # Check for existing draft cases
        draft_cases = PropertyVerificationCase.objects.filter(
            seller=request.user,
            status='DRAFT',
        ).select_related('property').order_by('-created_at')

        return JsonResponse({
            'draft_cases': [_serialize_case_summary(c) for c in draft_cases[:5]],
            'property_type_choices': PropertyVerificationCase.PROPERTY_TYPE_CHOICES,
            'tenure_choices': PropertyVerificationCase.TENURE_CHOICES,
            'ownership_type_choices': PropertyVerificationCase.OWNERSHIP_TYPE_CHOICES,
            'seller_relationship_choices': PropertyVerificationCase.SELLER_RELATIONSHIP_CHOICES,
            'intended_use_choices': PropertyVerificationCase.INTENDED_USE_CHOICES,
        })

    # POST — create new case (Step 1: Property Basics)
    return _wizard_step_1(request)


@login_required
@require_POST
def verification_wizard_step(request, case_id, step):
    """Handle individual wizard steps."""
    case = get_object_or_404(
        PropertyVerificationCase,
        id=case_id,
        seller=request.user,
    )

    step_handlers = {
        1: _wizard_step_1_update,
        2: _wizard_step_2,
        3: _wizard_step_3,
        4: _wizard_step_4,
        5: _wizard_step_5,
    }

    handler = step_handlers.get(step)
    if not handler:
        return JsonResponse({'error': f'Invalid wizard step: {step}'}, status=400)

    return handler(request, case)


def _wizard_step_1(request):
    """Step 1 — Property Basics: create parcel + verification case."""
    data = _json_body(request) if request.content_type == 'application/json' else request.POST

    parcel_number = data.get('parcel_number', '').strip()
    if not parcel_number:
        return JsonResponse({'error': 'Parcel/LR number is required.'}, status=400)

    # Check if parcel already exists
    existing_parcel = LandParcel.objects.filter(parcel_number=parcel_number).first()
    if existing_parcel and existing_parcel.listed_by != request.user:
        return JsonResponse({'error': 'This parcel number is already registered by another seller.'}, status=400)

    county = data.get('county', '').strip()
    constituency = data.get('constituency', '').strip() or data.get('sub_county', '').strip()
    ward = data.get('ward', '').strip()

    with db_transaction.atomic():
        # Create or get the LandParcel
        if existing_parcel:
            parcel = existing_parcel
        else:
            parcel = LandParcel.objects.create(
                parcel_number=parcel_number,
                land_use_type=data.get('land_use_type', 'Residential'),
                county=county or 'Not Specified',
                constituency=constituency or 'Not Specified',
                ward=ward or 'Not Specified',
                land_size=data.get('land_size', 0) or 0,
                registered_owner_id=data.get('registered_owner_id', ''),
                verification_status='DRAFT',
                listed_by=request.user,
            )

        # Create the verification case
        case, created = PropertyVerificationCase.objects.get_or_create(
            property=parcel,
            seller=request.user,
            defaults={
                'property_type': data.get('property_type', 'LAND_PLOT'),
                'tenure_type': data.get('tenure_type', 'UNKNOWN'),
                'intended_use': data.get('intended_use', 'RESIDENTIAL'),
                'is_agricultural': data.get('property_type') == 'AGRICULTURAL',
                'location_description': data.get('location_description', ''),
                'approximate_latitude': data.get('latitude') or None,
                'approximate_longitude': data.get('longitude') or None,
                'registered_area_value': data.get('land_size') or None,
                'registered_area_unit': data.get('size_unit', 'ACRES'),
                'wizard_step_completed': 1,
            }
        )

        if not created:
            # Update existing draft
            case.property_type = data.get('property_type', case.property_type)
            case.tenure_type = data.get('tenure_type', case.tenure_type)
            case.intended_use = data.get('intended_use', case.intended_use)
            case.is_agricultural = data.get('property_type') == 'AGRICULTURAL'
            case.location_description = data.get('location_description', case.location_description)
            case.wizard_step_completed = max(case.wizard_step_completed, 1)
            case.save()

        # Create initial verification layers
        if created:
            for layer_type, _ in VerificationLayer.LAYER_CHOICES:
                VerificationLayer.objects.get_or_create(
                    case=case, layer_type=layer_type,
                )

            VerificationAuditEvent.objects.create(
                case=case,
                event_type='CASE_CREATED',
                actor=request.user,
                description='Property verification case created',
                customer_visible=True,
                customer_display='Property registration started',
            )

    return JsonResponse({
        'case': _serialize_case_summary(case),
        'next_step': 2,
    }, status=201 if created else 200)


def _wizard_step_1_update(request, case):
    """Update Step 1 data for an existing case."""
    data = _json_body(request) if request.content_type == 'application/json' else request.POST

    case.property_type = data.get('property_type', case.property_type)
    case.tenure_type = data.get('tenure_type', case.tenure_type)
    case.intended_use = data.get('intended_use', case.intended_use)
    case.is_agricultural = data.get('property_type') == 'AGRICULTURAL'
    case.location_description = data.get('location_description', case.location_description)
    case.wizard_step_completed = max(case.wizard_step_completed, 1)
    case.save()

    # Update parcel
    parcel = case.property
    parcel.county = data.get('county', parcel.county)
    parcel.constituency = data.get('constituency', parcel.constituency) or data.get('sub_county', parcel.constituency)
    parcel.ward = data.get('ward', parcel.ward)
    parcel.save()

    VerificationAuditEvent.objects.create(
        case=case,
        event_type='STEP_COMPLETED',
        actor=request.user,
        description='Step 1 (Property Basics) updated',
        metadata={'step': 1},
    )

    return JsonResponse({'case': _serialize_case_summary(case), 'next_step': 2})


def _wizard_step_2(request, case):
    """Step 2 — Ownership & Details."""
    data = _json_body(request) if request.content_type == 'application/json' else request.POST

    case.ownership_type = data.get('ownership_type', case.ownership_type)
    case.seller_relationship = data.get('seller_relationship', case.seller_relationship)
    case.registered_owner_name = data.get('registered_owner_name', case.registered_owner_name)
    case.title_type = data.get('title_type', case.title_type)
    case.is_subdivided = data.get('is_subdivided', False)
    case.has_spousal_interest = data.get('has_spousal_interest', 'UNSURE')
    case.has_recent_transfer = data.get('has_recent_transfer', 'UNSURE')

    if data.get('registered_area'):
        case.registered_area_value = data.get('registered_area')
        case.registered_area_unit = data.get('registered_area_unit', 'ACRES')

    case.wizard_step_completed = max(case.wizard_step_completed, 2)
    case.save()

    VerificationAuditEvent.objects.create(
        case=case,
        event_type='STEP_COMPLETED',
        actor=request.user,
        description='Step 2 (Ownership & Details) completed',
        metadata={'step': 2, 'ownership_type': case.ownership_type},
    )

    # Return document requirements for Step 3
    checklist = get_document_checklist(case, phase='PHASE_1')

    return JsonResponse({
        'case': _serialize_case_summary(case),
        'document_checklist': checklist,
        'next_step': 3,
    })


def _wizard_step_3(request, case):
    """
    Step 3 — Documents.
    Documents are uploaded via the separate upload endpoint.
    This step just validates completeness and advances.
    """
    completeness = evaluate_document_completeness(case)

    if not completeness['can_submit']:
        return JsonResponse({
            'case': _serialize_case_summary(case),
            'completeness': completeness,
            'can_proceed': False,
            'message': 'Required documents are missing. Please upload all required documents before proceeding.',
        })

    case.wizard_step_completed = max(case.wizard_step_completed, 3)
    case.save()

    VerificationAuditEvent.objects.create(
        case=case,
        event_type='STEP_COMPLETED',
        actor=request.user,
        description='Step 3 (Document Collection) completed',
        metadata={'step': 3, **completeness},
    )

    return JsonResponse({
        'case': _serialize_case_summary(case),
        'completeness': completeness,
        'can_proceed': True,
        'next_step': 4,
    })


def _wizard_step_4(request, case):
    """
    Step 4 — AI Screening.
    Triggers AI screening for all unscreened documents.
    """
    from core.services.ai_document_screening import screen_all_documents

    results = screen_all_documents(case)

    case.wizard_step_completed = max(case.wizard_step_completed, 4)
    case.save()

    checklist = get_document_checklist(case, phase='PHASE_1')

    return JsonResponse({
        'case': _serialize_case_summary(case),
        'screening_results': results,
        'document_checklist': checklist,
        'next_step': 5,
    })


def _wizard_step_5(request, case):
    """
    Step 5 — Review & Submit.
    Final submission for Phase 1 pre-screening.
    """
    data = _json_body(request) if request.content_type == 'application/json' else request.POST
    confirmed = data.get('confirmed', False)

    if not confirmed:
        return JsonResponse({
            'error': 'You must confirm the accuracy of your submission.',
        }, status=400)

    completeness = evaluate_document_completeness(case)

    with db_transaction.atomic():
        case.wizard_step_completed = 5
        case.status = 'SUBMITTED'
        case.submitted_at = timezone.now()
        case.save()

        # Update parcel status
        parcel = case.property
        parcel.verification_status = 'DOCS_SUBMITTED'
        parcel.save(update_fields=['verification_status', 'updated_at'])

        VerificationAuditEvent.objects.create(
            case=case,
            event_type='PROPERTY_SUBMITTED',
            actor=request.user,
            description='Property submitted for Phase 1 pre-screening',
            metadata={'completeness': completeness},
            customer_visible=True,
            customer_display='Property submitted for verification screening',
        )

    return JsonResponse({
        'case': _serialize_case_summary(case),
        'completeness': completeness,
        'submitted': True,
        'message': 'Your property has been submitted for Digiland pre-screening. '
                   'We will review your documents and notify you of the results.',
    })


# ---------------------------------------------------------------------------
# DOCUMENT UPLOAD
# ---------------------------------------------------------------------------

@login_required
@require_POST
def verification_document_upload(request, case_id):
    """Upload a document to a verification case."""
    case = get_object_or_404(
        PropertyVerificationCase,
        id=case_id,
        seller=request.user,
    )

    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'No file provided.'}, status=400)

    document_type = request.POST.get('document_type', '')
    requirement_id = request.POST.get('requirement_id', '')

    # Validate document type
    valid_types = dict(VerificationDocumentRequirement.DOCUMENT_TYPE_CHOICES)
    if document_type not in valid_types:
        return JsonResponse({'error': f'Invalid document type: {document_type}'}, status=400)

    # Look up the requirement
    requirement = None
    if requirement_id:
        requirement = VerificationDocumentRequirement.objects.filter(id=requirement_id).first()

    # Check for existing doc of this type (versioning)
    existing = VerificationDocument.objects.filter(
        case=case,
        document_type=document_type,
    ).exclude(
        verification_status__in=['SUPERSEDED', 'REJECTED']
    ).order_by('-version').first()

    version = (existing.version + 1) if existing else 1

    # Compute file hash
    sha256 = hashlib.sha256()
    for chunk in file.chunks(chunk_size=8192):
        sha256.update(chunk)
    file.seek(0)
    file_hash = sha256.hexdigest()

    doc = VerificationDocument.objects.create(
        case=case,
        requirement=requirement,
        document_type=document_type,
        file=file,
        original_filename=file.name,
        mime_type=file.content_type or '',
        file_size=file.size,
        file_hash=file_hash,
        uploaded_by=request.user,
        verification_status='UPLOADED',
        version=version,
        supersedes=existing,
    )

    # Mark previous version as superseded
    if existing:
        existing.verification_status = 'SUPERSEDED'
        existing.save(update_fields=['verification_status', 'updated_at'])

    VerificationAuditEvent.objects.create(
        case=case,
        event_type='DOCUMENT_UPLOADED',
        actor=request.user,
        description=f'{doc.get_document_type_display()} uploaded (v{version})',
        metadata={
            'document_id': str(doc.id),
            'document_type': document_type,
            'version': version,
            'file_size': file.size,
        },
        customer_visible=True,
        customer_display=f'{doc.get_document_type_display()} uploaded',
    )

    return JsonResponse({
        'document': {
            'id': str(doc.id),
            'document_type': doc.document_type,
            'original_filename': doc.original_filename,
            'file_size': doc.file_size,
            'version': doc.version,
            'verification_status': doc.verification_status,
            'uploaded_at': doc.uploaded_at.isoformat() if doc.uploaded_at else None,
        },
    }, status=201)


# ---------------------------------------------------------------------------
# VERIFICATION CASE DATA (read endpoints)
# ---------------------------------------------------------------------------

@login_required
@require_GET
def verification_case_detail(request, case_id):
    """Get full verification case details."""
    case = get_object_or_404(PropertyVerificationCase, id=case_id)

    # Access control
    is_owner = case.seller == request.user
    is_staff = request.user.role in ('Admin', 'Agent', 'Lawyer', 'Surveyor')
    is_buyer = request.user.role == 'Buyer'

    if not (is_owner or is_staff):
        if is_buyer:
            # Buyers only see the verification passport
            return _verification_passport_response(case, buyer_view=True)
        return JsonResponse({'error': 'Access denied.'}, status=403)

    checklist = get_document_checklist(case, phase=case.current_phase)
    completeness = evaluate_document_completeness(case)
    layers = [_serialize_layer(l) for l in case.verification_layers.all()]

    risk_flags = []
    if is_staff or is_owner:
        risk_flags = [
            {
                'id': str(f.id),
                'flag_type': f.flag_type,
                'flag_display': f.get_flag_type_display(),
                'severity': f.severity,
                'description': f.description,
                'source': f.source,
                'resolved': f.resolved,
                'resolution_notes': f.resolution_notes,
                'created_at': f.created_at.isoformat(),
            }
            for f in case.verification_risk_flags.all()
        ]

    response = {
        'case': _serialize_case_summary(case),
        'document_checklist': checklist,
        'completeness': completeness,
        'layers': layers,
        'risk_flags': risk_flags if is_staff else [],  # Only staff sees risk flags
    }

    return JsonResponse(response)


@login_required
@require_GET
def verification_timeline(request, case_id):
    """Get the Trust Timeline for customer display."""
    case = get_object_or_404(PropertyVerificationCase, id=case_id)

    events = case.audit_events.filter(
        customer_visible=True,
    ).order_by('timestamp').values(
        'event_type', 'customer_display', 'timestamp'
    )

    return JsonResponse({
        'case_number': case.case_number,
        'timeline': [
            {
                'event_type': e['event_type'],
                'display': e['customer_display'],
                'timestamp': e['timestamp'].isoformat(),
            }
            for e in events
        ],
    })


@login_required
@require_GET
def verification_passport(request, case_id):
    """Get the full Verification Passport for customer display."""
    case = get_object_or_404(PropertyVerificationCase, id=case_id)
    return _verification_passport_response(case, buyer_view=(request.user.role == 'Buyer'))


def _verification_passport_response(case, buyer_view=False):
    """Build the Verification Passport response."""
    timeline = list(case.audit_events.filter(
        customer_visible=True,
    ).order_by('timestamp').values('event_type', 'customer_display', 'timestamp'))

    layers = []
    for layer in case.verification_layers.all():
        layer_data = {
            'layer_type': layer.layer_type,
            'layer_display': layer.get_layer_type_display(),
            'status': layer.status,
            'status_display': layer.get_status_display(),
            'customer_summary': layer.customer_summary,
            'check_items': [
                {
                    'check_name': ci.check_name,
                    'status': ci.status,
                    'customer_display_text': ci.customer_display_text,
                    'timestamp_display': ci.timestamp_display.isoformat() if ci.timestamp_display else None,
                }
                for ci in layer.check_items.filter(customer_visible=True)
            ],
        }
        layers.append(layer_data)

    return JsonResponse({
        'case_number': case.case_number,
        'verification_level': case.verification_level,
        'verification_level_display': case.get_verification_level_display(),
        'current_phase': case.current_phase,
        'status': case.status,
        'status_display': case.get_status_display(),
        'submitted_at': case.submitted_at.isoformat() if case.submitted_at else None,
        'pre_screened_at': case.pre_screened_at.isoformat() if case.pre_screened_at else None,
        'verified_at': case.verified_at.isoformat() if case.verified_at else None,
        'layers': layers,
        'timeline': [
            {
                'event_type': e['event_type'],
                'display': e['customer_display'],
                'timestamp': e['timestamp'].isoformat(),
            }
            for e in timeline
        ],
    })


# ---------------------------------------------------------------------------
# BUYER INTEREST (Phase 2 trigger)
# ---------------------------------------------------------------------------

@login_required
@require_POST
def express_buyer_interest(request, parcel_number):
    """Buyer expresses serious interest in a property, triggering Phase 2 due diligence."""
    if request.user.role != 'Buyer':
        return JsonResponse({'error': 'Only buyers can express interest.'}, status=403)

    parcel = get_object_or_404(LandParcel, parcel_number=parcel_number)

    # Check property has a verification case
    try:
        case = parcel.verification_case
    except PropertyVerificationCase.DoesNotExist:
        return JsonResponse({
            'error': 'This property has not completed registration.',
        }, status=400)

    # Check the property is at least pre-screened
    if case.verification_level not in ('PRE_SCREENED', 'VERIFIED', 'VERIFIED_WITH_CONDITIONS'):
        return JsonResponse({
            'error': 'This property has not completed initial screening yet.',
        }, status=400)

    # Check for existing interest
    existing = BuyerInterestCase.objects.filter(
        buyer=request.user,
        property=parcel,
        status__in=['EXPRESSED', 'DUE_DILIGENCE_REQUESTED', 'IN_PROGRESS'],
    ).first()

    if existing:
        return JsonResponse({
            'interest': {
                'id': str(existing.id),
                'interest_number': existing.interest_number,
                'status': existing.status,
            },
            'message': 'You have already expressed interest in this property.',
        })

    interest = BuyerInterestCase.objects.create(
        buyer=request.user,
        property=parcel,
        verification_case=case,
        status='EXPRESSED',
        notes=request.POST.get('notes', ''),
    )

    # Log audit event
    VerificationAuditEvent.objects.create(
        case=case,
        event_type='BUYER_INTEREST',
        actor=request.user,
        description=f'Buyer {request.user.email} expressed interest',
        metadata={'interest_id': str(interest.id)},
        customer_visible=True,
        customer_display='A buyer has expressed interest in this property',
    )

    return JsonResponse({
        'interest': {
            'id': str(interest.id),
            'interest_number': interest.interest_number,
            'status': interest.status,
        },
        'message': 'Your interest has been registered. Due diligence review may begin shortly.',
    }, status=201)


# ---------------------------------------------------------------------------
# STAFF: VERIFICATION CASE MANAGEMENT
# ---------------------------------------------------------------------------

@login_required
@require_POST
def staff_review_document(request, case_id, document_id):
    """Staff reviews a document (approve, reject, escalate)."""
    if request.user.role not in ('Admin', 'Agent', 'Lawyer', 'Surveyor'):
        return JsonResponse({'error': 'Insufficient permissions.'}, status=403)

    case = get_object_or_404(PropertyVerificationCase, id=case_id)
    doc = get_object_or_404(VerificationDocument, id=document_id, case=case)

    data = _json_body(request) if request.content_type == 'application/json' else request.POST
    action = data.get('action', '')
    notes = data.get('notes', '')

    action_map = {
        'confirm': 'CONFIRMED',
        'request_better_copy': 'REQUEST_BETTER_COPY',
        'request_additional': 'REQUEST_ADDITIONAL',
        'escalate_surveyor': 'ESCALATE_SURVEYOR',
        'escalate_lawyer': 'ESCALATE_LAWYER',
        'reject': 'REJECTED',
        'not_applicable': 'NOT_APPLICABLE',
    }

    human_status = action_map.get(action)
    if not human_status:
        return JsonResponse({'error': f'Invalid action: {action}'}, status=400)

    doc.human_status = human_status
    doc.human_reviewer = request.user
    doc.human_reviewed_at = timezone.now()
    doc.human_notes = notes

    if action == 'confirm':
        doc.verification_status = 'HUMAN_VERIFIED'
    elif action == 'reject':
        doc.verification_status = 'REJECTED'
    elif action in ('request_better_copy', 'request_additional'):
        doc.verification_status = 'HUMAN_REVIEW'

    doc.save()

    VerificationAuditEvent.objects.create(
        case=case,
        event_type='HUMAN_REVIEW_COMPLETED',
        actor=request.user,
        description=f'{doc.get_document_type_display()} reviewed: {human_status}',
        metadata={
            'document_id': str(doc.id),
            'action': action,
            'reviewer_role': request.user.role,
        },
        customer_visible=(action == 'confirm'),
        customer_display=f'{doc.get_document_type_display()} has been reviewed' if action == 'confirm' else '',
    )

    return JsonResponse({
        'document_id': str(doc.id),
        'human_status': doc.human_status,
        'verification_status': doc.verification_status,
    })


@login_required
@require_POST
def staff_update_layer(request, case_id, layer_type):
    """Staff updates a verification layer status."""
    if request.user.role not in ('Admin', 'Agent', 'Lawyer', 'Surveyor'):
        return JsonResponse({'error': 'Insufficient permissions.'}, status=403)

    case = get_object_or_404(PropertyVerificationCase, id=case_id)
    layer = get_object_or_404(VerificationLayer, case=case, layer_type=layer_type)

    # Role-based access control for layers
    role_layer_map = {
        'Agent': ['PHYSICAL_SURVEY'],
        'Surveyor': ['PHYSICAL_SURVEY'],
        'Lawyer': ['LEGAL_TITLE', 'TRANSACTION_RISK'],
        'Admin': list(dict(VerificationLayer.LAYER_CHOICES).keys()),
    }

    allowed_layers = role_layer_map.get(request.user.role, [])
    if layer_type not in allowed_layers:
        return JsonResponse({
            'error': f'{request.user.role} cannot update the {layer.get_layer_type_display()} layer.',
        }, status=403)

    data = _json_body(request) if request.content_type == 'application/json' else request.POST

    new_status = data.get('status')
    if new_status and new_status in dict(VerificationLayer.STATUS_CHOICES):
        old_status = layer.status
        layer.status = new_status
        if new_status == 'IN_PROGRESS' and not layer.started_at:
            layer.started_at = timezone.now()
        if new_status in ('COMPLETED', 'COMPLETED_WITH_CONDITIONS', 'FAILED'):
            layer.completed_at = timezone.now()

    if data.get('risk_level'):
        layer.risk_level = data['risk_level']
    if data.get('customer_summary'):
        layer.customer_summary = data['customer_summary']
    if data.get('notes'):
        layer.notes = data['notes']

    layer.assigned_to = request.user
    layer.save()

    VerificationAuditEvent.objects.create(
        case=case,
        event_type='STATUS_CHANGED',
        actor=request.user,
        description=f'{layer.get_layer_type_display()} updated to {layer.get_status_display()}',
        metadata={
            'layer_type': layer_type,
            'new_status': layer.status,
            'risk_level': layer.risk_level,
        },
        customer_visible=(layer.status in ('COMPLETED', 'COMPLETED_WITH_CONDITIONS')),
        customer_display=f'{layer.get_layer_type_display()} completed' if layer.status in ('COMPLETED', 'COMPLETED_WITH_CONDITIONS') else '',
    )

    return JsonResponse({'layer': _serialize_layer(layer)})


@login_required
@require_POST
def staff_raise_flag(request, case_id):
    """Staff raises a risk flag on a verification case."""
    if request.user.role not in ('Admin', 'Agent', 'Lawyer', 'Surveyor'):
        return JsonResponse({'error': 'Insufficient permissions.'}, status=403)

    case = get_object_or_404(PropertyVerificationCase, id=case_id)
    data = _json_body(request) if request.content_type == 'application/json' else request.POST

    flag_type = data.get('flag_type', 'OTHER')
    severity = data.get('severity', 'MEDIUM')
    description = data.get('description', '')

    if not description:
        return JsonResponse({'error': 'Description is required.'}, status=400)

    source_map = {
        'Agent': 'AGENT',
        'Surveyor': 'SURVEYOR',
        'Lawyer': 'LAWYER',
        'Admin': 'OPERATIONS',
    }

    flag = VerificationRiskFlag.objects.create(
        case=case,
        flag_type=flag_type,
        severity=severity,
        description=description,
        source=source_map.get(request.user.role, 'OPERATIONS'),
        auto_escalate=(severity == 'CRITICAL'),
        raised_by=request.user,
    )

    VerificationAuditEvent.objects.create(
        case=case,
        event_type='RISK_FLAG_RAISED',
        actor=request.user,
        description=f'Risk flag raised: [{severity}] {flag.get_flag_type_display()}',
        metadata={
            'flag_id': str(flag.id),
            'flag_type': flag_type,
            'severity': severity,
        },
    )

    # CRITICAL flags automatically change case status
    if severity == 'CRITICAL':
        case.status = 'ISSUE_IDENTIFIED'
        case.overall_risk_level = 'CRITICAL'
        case.save(update_fields=['status', 'overall_risk_level', 'updated_at'])

    return JsonResponse({
        'flag': {
            'id': str(flag.id),
            'flag_type': flag.flag_type,
            'severity': flag.severity,
            'description': flag.description,
        },
    }, status=201)


@login_required
@require_POST
def staff_resolve_flag(request, case_id, flag_id):
    """Resolve a risk flag."""
    if request.user.role not in ('Admin', 'Lawyer'):
        return JsonResponse({'error': 'Only Admins and Lawyers can resolve risk flags.'}, status=403)

    case = get_object_or_404(PropertyVerificationCase, id=case_id)
    flag = get_object_or_404(VerificationRiskFlag, id=flag_id, case=case)

    data = _json_body(request) if request.content_type == 'application/json' else request.POST

    flag.resolved = True
    flag.resolved_by = request.user
    flag.resolved_at = timezone.now()
    flag.resolution_notes = data.get('resolution_notes', '')
    flag.save()

    VerificationAuditEvent.objects.create(
        case=case,
        event_type='RISK_FLAG_RESOLVED',
        actor=request.user,
        description=f'Risk flag resolved: {flag.get_flag_type_display()}',
        metadata={'flag_id': str(flag.id), 'resolution_notes': flag.resolution_notes},
    )

    # Reassess overall risk level
    open_flags = case.verification_risk_flags.filter(resolved=False)
    if open_flags.filter(severity='CRITICAL').exists():
        case.overall_risk_level = 'CRITICAL'
    elif open_flags.filter(severity='HIGH').exists():
        case.overall_risk_level = 'HIGH'
    elif open_flags.filter(severity='MEDIUM').exists():
        case.overall_risk_level = 'MEDIUM'
    else:
        case.overall_risk_level = 'LOW'
    case.save(update_fields=['overall_risk_level', 'updated_at'])

    return JsonResponse({
        'flag_id': str(flag.id),
        'resolved': True,
        'overall_risk_level': case.overall_risk_level,
    })


@login_required
@require_POST
def staff_approve_case(request, case_id):
    """Final approval gate — Operations/Admin approves the verification case."""
    if request.user.role != 'Admin':
        return JsonResponse({'error': 'Only Admins can give final approval.'}, status=403)

    case = get_object_or_404(PropertyVerificationCase, id=case_id)
    data = _json_body(request) if request.content_type == 'application/json' else request.POST

    approval_type = data.get('approval_type', 'PRE_SCREENED')  # PRE_SCREENED or VERIFIED

    # Check for unresolved critical flags
    critical_flags = case.verification_risk_flags.filter(
        severity='CRITICAL', resolved=False,
    )
    if critical_flags.exists():
        return JsonResponse({
            'error': 'Cannot approve: unresolved CRITICAL risk flags exist.',
            'critical_flags': [
                {'flag_type': f.flag_type, 'description': f.description}
                for f in critical_flags
            ],
        }, status=400)

    with db_transaction.atomic():
        if approval_type == 'PRE_SCREENED':
            case.status = 'PRE_SCREENED'
            case.verification_level = 'PRE_SCREENED'
            case.pre_screened_at = timezone.now()

            parcel = case.property
            parcel.verification_status = 'Verified'  # Listed as pre-screened
            parcel.save(update_fields=['verification_status', 'updated_at'])

            display = 'Property has been Digiland Pre-Screened'

        elif approval_type == 'VERIFIED':
            case.status = 'VERIFIED_FOR_TRANSACTION'
            case.verification_level = 'VERIFIED'
            case.verified_at = timezone.now()
            case.current_phase = 'PHASE_2'

            parcel = case.property
            parcel.verification_status = 'Verified'
            parcel.save(update_fields=['verification_status', 'updated_at'])

            display = 'Property has been Digiland Verified for transaction'

        case.save()

        VerificationAuditEvent.objects.create(
            case=case,
            event_type='APPROVED',
            actor=request.user,
            description=f'Case approved as {approval_type}',
            metadata={'approval_type': approval_type},
            customer_visible=True,
            customer_display=display,
        )

    return JsonResponse({
        'case': _serialize_case_summary(case),
        'approved': True,
        'approval_type': approval_type,
    })
