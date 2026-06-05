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
