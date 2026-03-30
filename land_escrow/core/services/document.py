# Document Validation Service

def extract_text_from_document(file):
    """
    Uses OCR to extract text from a document. Mock returns a placeholder string.
    """
    return "Extracted mock text from document."

def validate_title_deed(uploaded_file, parcel_number):
    """
    Validates uploaded title deed against parcel info. Mock returns True.
    """
    text = extract_text_from_document(uploaded_file)
    return True

def validate_id_document(uploaded_file, user_id):
    """
    Validates uploaded ID document. Mock returns True.
    """
    text = extract_text_from_document(uploaded_file)
    return True
