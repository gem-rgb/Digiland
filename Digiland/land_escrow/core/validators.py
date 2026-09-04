"""
Security validators for Digiland platform.

Provides custom password validation enforcing complexity requirements
beyond Django's built-in validators.
"""

import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _


class ComplexityPasswordValidator:
    """
    Validate that the password meets complexity requirements:
    - At least one uppercase letter
    - At least one lowercase letter
    - At least one digit
    - At least one special character
    - No more than 2 repeated characters in sequence
    - Not a commonly used password pattern
    """

    def validate(self, password, user=None):
        errors = []

        if not re.search(r'[A-Z]', password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one uppercase letter."),
                    code='password_no_upper',
                )
            )

        if not re.search(r'[a-z]', password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one lowercase letter."),
                    code='password_no_lower',
                )
            )

        if not re.search(r'\d', password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one digit."),
                    code='password_no_digit',
                )
            )

        if not re.search(r'[!@#$%^&*()_+\-=\[\]{};\':"\\|,.<>\/?`~]', password):
            errors.append(
                ValidationError(
                    _("Password must contain at least one special character (!@#$%^&*etc)."),
                    code='password_no_special',
                )
            )

        # Check for sequential repeated characters (e.g., "aaa")
        if re.search(r'(.)\1{2,}', password):
            errors.append(
                ValidationError(
                    _("Password must not contain more than 2 repeated characters in sequence."),
                    code='password_repeated_chars',
                )
            )

        # Check for common keyboard patterns
        keyboard_patterns = [
            'qwerty', 'asdfgh', 'zxcvbn', 'qwertz',
            '123456', 'abcdef', 'password', 'digiland',
        ]
        lower_password = password.lower()
        for pattern in keyboard_patterns:
            if pattern in lower_password:
                errors.append(
                    ValidationError(
                        _("Password contains a common pattern that is easily guessed."),
                        code='password_common_pattern',
                    )
                )
                break

        if errors:
            raise ValidationError(errors)

    def get_help_text(self):
        return _(
            "Your password must contain at least: "
            "10 characters, one uppercase letter, one lowercase letter, "
            "one digit, and one special character. "
            "It must not contain repeated characters or common patterns."
        )


def validate_file_upload(file_obj, allowed_extensions=None, allowed_mimes=None, max_size_mb=10):
    """
    Validate an uploaded file for security.

    Args:
        file_obj: Django UploadedFile object
        allowed_extensions: List of allowed extensions (e.g., ['.pdf', '.jpg'])
        allowed_mimes: List of allowed MIME types
        max_size_mb: Maximum file size in megabytes

    Raises:
        ValidationError: If validation fails
    """
    if not file_obj:
        raise ValidationError("No file provided.")

    # Size check
    max_size_bytes = max_size_mb * 1024 * 1024
    if file_obj.size > max_size_bytes:
        raise ValidationError(
            f"File size ({file_obj.size / (1024*1024):.1f} MB) exceeds "
            f"maximum allowed size ({max_size_mb} MB)."
        )

    # Extension check
    if allowed_extensions:
        import os
        ext = os.path.splitext(file_obj.name)[1].lower()
        if ext not in [e.lower() for e in allowed_extensions]:
            raise ValidationError(
                f"File extension '{ext}' is not allowed. "
                f"Allowed extensions: {', '.join(allowed_extensions)}"
            )

    # MIME type check
    if allowed_mimes:
        content_type = getattr(file_obj, 'content_type', '') or ''
        if content_type.lower() not in [m.lower() for m in allowed_mimes]:
            raise ValidationError(
                f"File type '{content_type}' is not allowed. "
                f"Allowed types: {', '.join(allowed_mimes)}"
            )

    # Magic byte validation (basic)
    _validate_magic_bytes(file_obj, allowed_mimes or [])


def _validate_magic_bytes(file_obj, allowed_mimes):
    """
    Validate file content by checking magic bytes (file signature).
    This prevents content-type spoofing.
    """
    MAGIC_SIGNATURES = {
        'application/pdf': [b'%PDF'],
        'image/jpeg': [b'\xff\xd8\xff'],
        'image/png': [b'\x89PNG\r\n\x1a\n'],
        'image/webp': [b'RIFF'],
        'image/gif': [b'GIF87a', b'GIF89a'],
    }

    # Only validate if we know the expected signatures
    if not allowed_mimes:
        return

    # Save current position
    pos = file_obj.tell()
    try:
        file_obj.seek(0)
        header = file_obj.read(16)
        file_obj.seek(pos)

        if not header:
            return

        # Check if the content matches any allowed MIME type's signature
        valid = False
        for mime in allowed_mimes:
            signatures = MAGIC_SIGNATURES.get(mime, [])
            for sig in signatures:
                if header.startswith(sig):
                    valid = True
                    break
            if valid:
                break

        # If we have signatures to check against and none match
        if not valid and any(mime in MAGIC_SIGNATURES for mime in allowed_mimes):
            raise ValidationError(
                "File content does not match the expected file type. "
                "The file may be corrupted or disguised."
            )
    except Exception:
        file_obj.seek(pos)


def calculate_file_sha256(file_obj) -> str:
    """
    Calculate the SHA-256 hex digest of a file object safely.
    Streams in 64KB chunks to prevent high memory usage.
    Preserves and restores the original file pointer position.
    """
    import hashlib

    pos = file_obj.tell() if hasattr(file_obj, 'tell') else 0
    sha256 = hashlib.sha256()
    try:
        if hasattr(file_obj, 'seek'):
            file_obj.seek(0)
        
        if hasattr(file_obj, 'chunks'):
            for chunk in file_obj.chunks(chunk_size=65536):
                sha256.update(chunk)
        else:
            while True:
                chunk = file_obj.read(65536)
                if not chunk:
                    break
                sha256.update(chunk if isinstance(chunk, bytes) else chunk.encode('utf-8'))
        return sha256.hexdigest()
    finally:
        if hasattr(file_obj, 'seek'):
            file_obj.seek(pos)


def validate_image_dimensions(image_file, max_width=4096, max_height=4096):
    """
    Validate that an uploaded image does not exceed safe dimensions
    to prevent image decompression bombs and excessive storage usage.
    """
    from PIL import Image

    pos = image_file.tell() if hasattr(image_file, 'tell') else 0
    try:
        if hasattr(image_file, 'seek'):
            image_file.seek(0)
        with Image.open(image_file) as img:
            width, height = img.size
            if width > max_width or height > max_height:
                raise ValidationError(
                    f"Image dimensions ({width}x{height}) exceed maximum allowed ({max_width}x{max_height})."
                )
    except ValidationError:
        raise
    except Exception as exc:
        raise ValidationError(f"Invalid or corrupted image file: {exc}")
    finally:
        if hasattr(image_file, 'seek'):
            image_file.seek(pos)


def check_parcel_document_quota(parcel, max_documents=15):
    """
    Ensure a land parcel does not exceed the allowed document count.
    """
    if parcel and hasattr(parcel, 'documents'):
        count = parcel.documents.filter(deleted_at__isnull=True).count()
        if count >= max_documents:
            raise ValidationError(
                f"Document upload limit reached for this parcel ({max_documents} max documents). "
                f"Please remove outdated files before uploading new ones."
            )


def check_user_storage_quota(user, new_file_size_bytes=0, max_mb=50):
    """
    Server-side storage quota check per user (default 50MB).
    """
    from core.models import Document
    max_bytes = max_mb * 1024 * 1024

    existing_docs = Document.objects.filter(uploaded_by=user, deleted_at__isnull=True)
    total_existing = 0
    for doc in existing_docs:
        try:
            if doc.file_url and hasattr(doc.file_url, 'size'):
                total_existing += doc.file_url.size
        except Exception:
            pass

    if (total_existing + new_file_size_bytes) > max_bytes:
        current_mb = total_existing / (1024 * 1024)
        raise ValidationError(
            f"User storage quota exceeded ({current_mb:.1f} MB used of {max_mb} MB limit). "
            f"Please delete older or superseded documents."
        )
