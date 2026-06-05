"""Document validation helpers used by the KYC and parcel review flows."""

from core.ai_kyc import analyze_document_file


def validate_title_deed(uploaded_file, parcel_number):
    """
    Validate a title deed against the expected parcel number.

    Returns a structured result so callers can distinguish a clean match from
    manual-review or rejection states.
    """
    return analyze_document_file(
        uploaded_file,
        parcel_number=parcel_number,
        doc_type="title_deed",
    )


def validate_id_document(uploaded_file, expected_id_number):
    """
    Validate a government-issued identity document against the expected ID number.
    """
    return analyze_document_file(
        uploaded_file,
        expected_id_number=expected_id_number,
        doc_type="id_document",
    )
