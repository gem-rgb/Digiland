"""
Encryption Utilities for Admin Control Plane
==============================================

Provides AES-256-GCM encryption, field-level encryption, and audit-log
integrity verification for the admin control plane security domain.

All encryption uses the ``cryptography`` library with:

- AES-256-GCM for symmetric authenticated encryption
- PBKDF2-HMAC-SHA256 for key derivation from passphrases
- HMAC-SHA256 for message authentication and log integrity
- RSA-PSS (optional) for digital signatures on audit entries

Classes
-------
AES256GCMEncryptor
    Low-level encrypt/decrypt with AES-256-GCM.

FieldEncryptor
    Encrypt/decrypt model field values with per-field key management
    and key rotation support.

AuditLogEncryptor
    One-way hashing, HMAC integrity verification, and digital
    signatures for audit log entries.

Security Notes
--------------
- Encryption keys are NEVER logged, serialized, or stored in plaintext.
- Nonces are generated using ``os.urandom`` (CSPRNG) and are never reused.
- The GCM authentication tag is verified on every decrypt — tampered
  ciphertext is rejected with ``InvalidTag``.
- Key derivation uses 600 000 PBKDF2 iterations (OWASP 2023 recommendation).
"""

import base64
import hashlib
import hmac
import json
import logging
import os
from typing import Optional, Tuple

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidTag

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AES_KEY_SIZE_BYTES = 32          # 256-bit key
GCM_NONCE_SIZE_BYTES = 12        # 96-bit nonce (NIST recommendation)
PBKDF2_ITERATIONS = 600_000      # OWASP 2023 recommendation
PBKDF2_SALT_SIZE_BYTES = 32      # 256-bit salt
HMAC_DIGEST_SIZE_BYTES = 32      # SHA-256 output
AESGCM_TAG_LENGTH = 16           # 128-bit tag


# ===========================================================================
# AES-256-GCM Encryptor
# ===========================================================================

class AES256GCMEncryptor:
    """Low-level AES-256-GCM authenticated encryption.

    Provides encrypt, decrypt, key generation, and key derivation
    operations.  All methods are stateless and thread-safe.

    Example
    -------
    >>> key = AES256GCMEncryptor.generate_key()
    >>> nonce, ciphertext = AES256GCMEncryptor.encrypt(b"secret", key)
    >>> plaintext = AES256GCMEncryptor.decrypt(ciphertext, key, nonce)
    >>> plaintext == b"secret"
    True
    """

    @staticmethod
    def generate_key() -> bytes:
        """Generate a cryptographically secure AES-256 key.

        Returns
        -------
        bytes
            32-byte (256-bit) random key from ``os.urandom``.
        """
        return os.urandom(AES_KEY_SIZE_BYTES)

    @staticmethod
    def derive_key(password: str, salt: Optional[bytes] = None) -> Tuple[bytes, bytes]:
        """Derive an AES-256 key from a password using PBKDF2-HMAC-SHA256.

        Parameters
        ----------
        password : str
            The passphrase to derive the key from.
        salt : bytes, optional
            A 32-byte salt.  If not provided, a random salt is generated.

        Returns
        -------
        tuple[bytes, bytes]
            ``(derived_key, salt)`` — both 32 bytes.

        Notes
        -----
        Uses 600 000 PBKDF2 iterations as recommended by OWASP (2023).
        The salt is returned so it can be stored alongside the ciphertext
        for future derivations.
        """
        if salt is None:
            salt = os.urandom(PBKDF2_SALT_SIZE_BYTES)

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=AES_KEY_SIZE_BYTES,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        derived_key = kdf.derive(password.encode("utf-8"))
        return derived_key, salt

    @staticmethod
    def encrypt(plaintext: bytes, key: bytes) -> Tuple[bytes, bytes]:
        """Encrypt plaintext with AES-256-GCM.

        Parameters
        ----------
        plaintext : bytes
            Data to encrypt.
        key : bytes
            32-byte AES-256 key.

        Returns
        -------
        tuple[bytes, bytes]
            ``(nonce, ciphertext_with_tag)`` where the nonce is 12 bytes
            and the ciphertext includes the 16-byte GCM authentication tag
            appended by the ``cryptography`` library.

        Raises
        ------
        ValueError
            If the key is not exactly 32 bytes.
        """
        if len(key) != AES_KEY_SIZE_BYTES:
            raise ValueError(
                f"AES-256 key must be {AES_KEY_SIZE_BYTES} bytes, "
                f"got {len(key)}."
            )

        nonce = os.urandom(GCM_NONCE_SIZE_BYTES)
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
        return nonce, ciphertext

    @staticmethod
    def decrypt(ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
        """Decrypt AES-256-GCM ciphertext.

        Parameters
        ----------
        ciphertext : bytes
            Ciphertext including the 16-byte GCM authentication tag.
        key : bytes
            32-byte AES-256 key.
        nonce : bytes
            12-byte nonce used during encryption.

        Returns
        -------
        bytes
            Decrypted plaintext.

        Raises
        ------
        ValueError
            If the key or nonce have incorrect lengths.
        InvalidTag
            If the ciphertext has been tampered with or the key is wrong.
        """
        if len(key) != AES_KEY_SIZE_BYTES:
            raise ValueError(
                f"AES-256 key must be {AES_KEY_SIZE_BYTES} bytes, "
                f"got {len(key)}."
            )
        if len(nonce) != GCM_NONCE_SIZE_BYTES:
            raise ValueError(
                f"GCM nonce must be {GCM_NONCE_SIZE_BYTES} bytes, "
                f"got {len(nonce)}."
            )

        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ciphertext, associated_data=None)

    @staticmethod
    def encrypt_string(plaintext: str, key: bytes) -> str:
        """Encrypt a string and return a URL-safe base64-encoded result.

        The output format is ``base64(nonce || ciphertext)`` which allows
        the nonce to be recovered during decryption without separate storage.

        Parameters
        ----------
        plaintext : str
            String to encrypt.
        key : bytes
            32-byte AES-256 key.

        Returns
        -------
        str
            URL-safe base64-encoded ``nonce + ciphertext``.
        """
        nonce, ciphertext = AES256GCMEncryptor.encrypt(
            plaintext.encode("utf-8"), key
        )
        return base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

    @staticmethod
    def decrypt_string(encoded: str, key: bytes) -> str:
        """Decrypt a URL-safe base64-encoded ciphertext string.

        Parameters
        ----------
        encoded : str
            URL-safe base64-encoded ``nonce + ciphertext``.
        key : bytes
            32-byte AES-256 key.

        Returns
        -------
        str
            Decrypted plaintext string.

        Raises
        ------
        ValueError
            If the encoded data is too short to contain a nonce.
        InvalidTag
            If the ciphertext has been tampered with.
        """
        raw = base64.urlsafe_b64decode(encoded)
        if len(raw) < GCM_NONCE_SIZE_BYTES + AESGCM_TAG_LENGTH:
            raise ValueError("Encoded ciphertext is too short.")

        nonce = raw[:GCM_NONCE_SIZE_BYTES]
        ciphertext = raw[GCM_NONCE_SIZE_BYTES:]
        plaintext = AES256GCMEncryptor.decrypt(ciphertext, key, nonce)
        return plaintext.decode("utf-8")


# ===========================================================================
# Field Encryptor
# ===========================================================================

class FieldEncryptor:
    """Encrypt and decrypt model field values with per-field key management.

    Each field can have its own encryption key (stored securely in the
    secrets vault).  This allows independent key rotation per field
    without re-encrypting the entire database.

    The encrypted value format is:

        ``base64(nonce || ciphertext)``

    Key Rotation
    ------------
    ``rotate_field_key()`` decrypts all values encrypted under the old
    key and re-encrypts them with the new key.  This is an expensive
    operation and should be performed during maintenance windows.

    Example
    -------
    >>> key = AES256GCMEncryptor.generate_key()
    >>> encrypted = FieldEncryptor.encrypt_field("sensitive-data", "ssn", key)
    >>> FieldEncryptor.decrypt_field(encrypted, "ssn", key)
    'sensitive-data'
    """

    # Cache of field → key mappings (populated from settings or vault)
    _field_keys: dict = {}

    @staticmethod
    def _derive_field_key(field_name: str, master_key: bytes) -> bytes:
        """Derive a per-field encryption key from the master key.

        Uses HKDF-like construction: HMAC-SHA256(master_key, field_name).

        Parameters
        ----------
        field_name : str
            The model field name (e.g. ``"ssn"``, ``"bank_account"``).
        master_key : bytes
            The master encryption key.

        Returns
        -------
        bytes
            32-byte derived key unique to this field.
        """
        return hmac.new(
            master_key,
            field_name.encode("utf-8"),
            hashlib.sha256,
        ).digest()

    @staticmethod
    def encrypt_field(value: str, field_name: str, key: bytes) -> str:
        """Encrypt a model field value.

        Parameters
        ----------
        value : str
            The plaintext value to encrypt.
        field_name : str
            The field name (used for key derivation context).
        key : bytes
            The encryption key (or master key from which a per-field key
            is derived).

        Returns
        -------
        str
            URL-safe base64-encoded encrypted value.
        """
        field_key = FieldEncryptor._derive_field_key(field_name, key)
        return AES256GCMEncryptor.encrypt_string(value, field_key)

    @staticmethod
    def decrypt_field(encrypted_value: str, field_name: str, key: bytes) -> str:
        """Decrypt an encrypted model field value.

        Parameters
        ----------
        encrypted_value : str
            URL-safe base64-encoded encrypted value.
        field_name : str
            The field name (must match the name used during encryption).
        key : bytes
            The encryption key used during encryption.

        Returns
        -------
        str
            Decrypted plaintext value.

        Raises
        ------
        InvalidTag
            If the value has been tampered with or the key is wrong.
        """
        field_key = FieldEncryptor._derive_field_key(field_name, key)
        return AES256GCMEncryptor.decrypt_string(encrypted_value, field_key)

    @staticmethod
    def rotate_field_key(
        field_name: str,
        old_key: bytes,
        new_key: bytes,
        encrypted_values: list,
    ) -> list:
        """Re-encrypt field values with a new key.

        This is used during key rotation.  Each value is decrypted with
        the old key and re-encrypted with the new key.

        Parameters
        ----------
        field_name : str
            The field name being rotated.
        old_key : bytes
            The current encryption key.
        new_key : bytes
            The new encryption key.
        encrypted_values : list[str]
            List of encrypted values to re-encrypt.

        Returns
        -------
        list[str]
            List of re-encrypted values in the same order.

        Raises
        ------
        InvalidTag
            If any value cannot be decrypted with the old key.
        """
        old_field_key = FieldEncryptor._derive_field_key(field_name, old_key)
        new_field_key = FieldEncryptor._derive_field_key(field_name, new_key)

        re_encrypted = []
        for encrypted_value in encrypted_values:
            plaintext = AES256GCMEncryptor.decrypt_string(
                encrypted_value, old_field_key
            )
            new_encrypted = AES256GCMEncryptor.encrypt_string(
                plaintext, new_field_key
            )
            re_encrypted.append(new_encrypted)

        logger.info(
            "FieldEncryptor: Rotated key for field '%s' — %d values re-encrypted.",
            field_name,
            len(re_encrypted),
        )
        return re_encrypted


# ===========================================================================
# Audit Log Encryptor
# ===========================================================================

class AuditLogEncryptor:
    """Integrity verification and digital signatures for audit log entries.

    Provides three levels of protection for audit log entries:

    1. **Hashing** — One-way SHA-256 hash for tamper detection.
    2. **HMAC** — Keyed hash for message authentication.
    3. **Digital Signatures** — RSA-PSS signatures for non-repudiation.

    The hash chain in ``AdminActionLog`` already provides basic tamper
    detection.  This class adds additional cryptographic assurance via
    HMAC and digital signatures.

    Example
    -------
    >>> key = AES256GCMEncryptor.generate_key()
    >>> entry = {"action": "WITHDRAWAL", "amount": 50000}
    >>> entry_hash = AuditLogEncryptor.hash_log_entry(entry)
    >>> AuditLogEncryptor.verify_log_integrity(entry, entry_hash)
    True
    >>> signature = AuditLogEncryptor.sign_log_entry(entry, private_key)
    >>> AuditLogEncryptor.verify_log_signature(entry, signature, public_key)
    True
    """

    # HMAC key — loaded from settings or vault at startup
    _hmac_key: Optional[bytes] = None

    @classmethod
    def _get_hmac_key(cls) -> bytes:
        """Retrieve the HMAC key for audit log authentication.

        Loads from Django settings ``AUDIT_LOG_HMAC_KEY`` (hex-encoded)
        or generates a new one on first access.

        Returns
        -------
        bytes
            The HMAC key.
        """
        if cls._hmac_key is None:
            from django.conf import settings
            hex_key = getattr(settings, "AUDIT_LOG_HMAC_KEY", None)
            if hex_key:
                cls._hmac_key = bytes.fromhex(hex_key)
            else:
                cls._hmac_key = os.urandom(32)
                logger.warning(
                    "AuditLogEncryptor: AUDIT_LOG_HMAC_KEY not set in "
                    "settings.  A random key was generated — it will not "
                    "persist across restarts.  Set AUDIT_LOG_HMAC_KEY in "
                    "production."
                )
        return cls._hmac_key

    @staticmethod
    def hash_log_entry(entry: dict) -> str:
        """Compute a one-way SHA-256 hash of an audit log entry.

        The entry is JSON-serialised (sorted keys) before hashing to
        ensure deterministic output regardless of dict ordering.

        Parameters
        ----------
        entry : dict
            The audit log entry to hash.

        Returns
        -------
        str
            Hex-encoded SHA-256 digest.
        """
        canonical = json.dumps(entry, sort_keys=True, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @staticmethod
    def verify_log_integrity(entry: dict, expected_hash: str) -> bool:
        """Verify that an audit log entry matches its expected hash.

        Parameters
        ----------
        entry : dict
            The audit log entry to verify.
        expected_hash : str
            The hex-encoded SHA-256 hash to compare against.

        Returns
        -------
        bool
            ``True`` if the hash matches, ``False`` otherwise.
        """
        computed = AuditLogEncryptor.hash_log_entry(entry)
        is_valid = hmac.compare_digest(computed, expected_hash)

        if not is_valid:
            logger.warning(
                "AuditLogEncryptor: Integrity check FAILED for entry "
                "with action=%s.  Expected hash=%s, computed=%s.",
                entry.get("action", "unknown"),
                expected_hash[:16],
                computed[:16],
            )

        return is_valid

    @classmethod
    def sign_log_entry(cls, entry: dict, private_key=None) -> str:
        """Create an HMAC-SHA256 signature for an audit log entry.

        If a private RSA key is provided, an RSA-PSS signature is
        generated instead of HMAC for stronger non-repudiation.

        Parameters
        ----------
        entry : dict
            The audit log entry to sign.
        private_key : RSAPrivateKey, optional
            RSA private key for digital signatures.  If ``None``,
            HMAC-SHA256 is used.

        Returns
        -------
        str
            Hex-encoded signature.
        """
        canonical = json.dumps(entry, sort_keys=True, default=str)
        message = canonical.encode("utf-8")

        if private_key is not None:
            # RSA-PSS signature
            signature = private_key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.MAX_LENGTH,
                ),
                hashes.SHA256(),
            )
            return signature.hex()

        # HMAC-SHA256 fallback
        key = cls._get_hmac_key()
        return hmac.new(key, message, hashlib.sha256).hexdigest()

    @classmethod
    def verify_log_signature(
        cls,
        entry: dict,
        signature: str,
        public_key=None,
    ) -> bool:
        """Verify the signature of an audit log entry.

        Parameters
        ----------
        entry : dict
            The audit log entry to verify.
        signature : str
            Hex-encoded signature to verify.
        public_key : RSAPublicKey, optional
            RSA public key corresponding to the private key used for
            signing.  If ``None``, HMAC verification is used.

        Returns
        -------
        bool
            ``True`` if the signature is valid, ``False`` otherwise.
        """
        canonical = json.dumps(entry, sort_keys=True, default=str)
        message = canonical.encode("utf-8")
        sig_bytes = bytes.fromhex(signature)

        if public_key is not None:
            try:
                public_key.verify(
                    sig_bytes,
                    message,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH,
                    ),
                    hashes.SHA256(),
                )
                return True
            except Exception as exc:
                logger.warning(
                    "AuditLogEncryptor: RSA signature verification FAILED: %s",
                    exc,
                )
                return False

        # HMAC verification
        key = cls._get_hmac_key()
        expected = hmac.new(key, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, signature)

    @staticmethod
    def generate_signing_keypair(
        key_size: int = 4096,
    ) -> Tuple[rsa.RSAPrivateKey, rsa.RSAPublicKey]:
        """Generate an RSA key pair for audit log digital signatures.

        Parameters
        ----------
        key_size : int
            RSA key size in bits (default 4096).

        Returns
        -------
        tuple[RSAPrivateKey, RSAPublicKey]
            The generated key pair.
        """
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=key_size,
        )
        return private_key, private_key.public_key()

    @staticmethod
    def serialize_private_key(
        private_key: rsa.RSAPrivateKey,
        password: str,
    ) -> str:
        """Serialize an RSA private key to PEM format, encrypted.

        Parameters
        ----------
        private_key : RSAPrivateKey
            The key to serialize.
        password : str
            Encryption password for the PEM file.

        Returns
        -------
        str
            PEM-encoded, encrypted private key.
        """
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.BestAvailableEncryption(
                password.encode("utf-8")
            ),
        )
        return pem.decode("ascii")

    @staticmethod
    def serialize_public_key(public_key: rsa.RSAPublicKey) -> str:
        """Serialize an RSA public key to PEM format.

        Parameters
        ----------
        public_key : RSAPublicKey
            The key to serialize.

        Returns
        -------
        str
            PEM-encoded public key.
        """
        pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return pem.decode("ascii")

    @staticmethod
    def load_private_key(pem_data: str, password: str) -> rsa.RSAPrivateKey:
        """Load an RSA private key from encrypted PEM data.

        Parameters
        ----------
        pem_data : str
            PEM-encoded encrypted private key.
        password : str
            Decryption password.

        Returns
        -------
        RSAPrivateKey
            The loaded private key.
        """
        return serialization.load_pem_private_key(
            pem_data.encode("ascii"),
            password=password.encode("utf-8"),
        )

    @staticmethod
    def load_public_key(pem_data: str) -> rsa.RSAPublicKey:
        """Load an RSA public key from PEM data.

        Parameters
        ----------
        pem_data : str
            PEM-encoded public key.

        Returns
        -------
        RSAPublicKey
            The loaded public key.
        """
        return serialization.load_pem_public_key(pem_data.encode("ascii"))
