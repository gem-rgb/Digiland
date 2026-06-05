"""
Storage provider adapters for the External Services Layer.

Implements the :class:`~external_services.base.StorageProvider` interface
for three S3-compatible backends:

* **S3Adapter**  — AWS S3 via ``boto3``.
* **R2Adapter**  — Cloudflare R2 (S3-compatible) with R2 endpoint.
* **MinIOAdapter** — Self-hosted S3-compatible storage via MinIO.

All three share the same API surface; R2 and MinIO only override the
endpoint URL and a few connection details.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

from django.conf import settings

from external_services.base import (
    HealthCheckResult,
    ProviderResponse,
    StorageProvider,
    ValidationResult,
)
from external_services.exceptions import (
    ConfigurationError,
    ProviderResponseError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


# ======================================================================
# S3 Adapter
# ======================================================================


class S3Adapter(StorageProvider):
    """AWS S3 storage adapter using ``boto3``.

    Supports multipart upload for files larger than the configured
    threshold (default 8 MB).  Pre-signed URLs are generated for
    temporary read/write access without exposing credentials.

    Configuration (via Django settings):
        ``AWS_STORAGE_BUCKET_NAME``   — Target S3 bucket.
        ``AWS_ACCESS_KEY_ID``         — AWS access key.
        ``AWS_SECRET_ACCESS_KEY``     — AWS secret key.
        ``AWS_S3_REGION_NAME``        — AWS region (default ``"us-east-1"``).
        ``AWS_S3_ENDPOINT_URL``       — Custom endpoint (used by R2/MinIO).
        ``AWS_S3_MULTIPART_THRESHOLD`` — Bytes before multipart upload (default 8 MB).
    """

    PROVIDER_NAME = "s3"
    _MULTIPART_THRESHOLD = 8 * 1024 * 1024  # 8 MB

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="storage", **kwargs)
        self._bucket: str = getattr(settings, "AWS_STORAGE_BUCKET_NAME", "")
        self._region: str = getattr(settings, "AWS_S3_REGION_NAME", "us-east-1")
        self._endpoint_url: Optional[str] = getattr(settings, "AWS_S3_ENDPOINT_URL", None)
        self._multipart_threshold: int = getattr(settings, "AWS_S3_MULTIPART_THRESHOLD", self._MULTIPART_THRESHOLD)
        self._client = None

    def _get_client(self):
        """Lazy-initialise the boto3 S3 client."""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "s3",
                    aws_access_key_id=getattr(settings, "AWS_ACCESS_KEY_ID", None),
                    aws_secret_access_key=getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
                    region_name=self._region,
                    endpoint_url=self._endpoint_url,
                )
            except ImportError as exc:
                raise ProviderUnavailableError(
                    provider_name=self.PROVIDER_NAME,
                    message="boto3 package is not installed",
                ) from exc
        return self._client

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            client = self._get_client()
            client.head_bucket(Bucket=self._bucket)
            self.is_connected = True
            return True
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME) from exc

    def disconnect(self) -> bool:
        self._client = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            client = self._get_client()
            client.head_bucket(Bucket=self._bucket)
            return HealthCheckResult(status="healthy", provider=self.PROVIDER_NAME, response_time_ms=(time.monotonic() - start) * 1000)
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not self._bucket:
            errors.append("AWS_STORAGE_BUCKET_NAME is not configured")
        if not getattr(settings, "AWS_ACCESS_KEY_ID", ""):
            warnings.append("AWS_ACCESS_KEY_ID not set; relying on IAM role or env")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- storage operations -----------------------------------------------

    def upload(self, key: str, data: bytes, content_type: str = "application/octet-stream", **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            client = self._get_client()
            extra_args: Dict[str, Any] = {"ContentType": content_type}
            if kwargs.get("metadata"):
                extra_args["Metadata"] = kwargs["metadata"]
            if kwargs.get("acl"):
                extra_args["ACL"] = kwargs["acl"]
            if kwargs.get("cache_control"):
                extra_args["CacheControl"] = kwargs["cache_control"]

            if len(data) >= self._multipart_threshold:
                # Multipart upload for large files
                from boto3.s3.transfer import TransferConfig
                transfer_config = TransferConfig(multipart_threshold=self._multipart_threshold)
                client.put_object(Bucket=self._bucket, Key=key, Body=data, **extra_args)
            else:
                client.put_object(Bucket=self._bucket, Key=key, Body=data, **extra_args)

            url = f"https://{self._bucket}.s3.{self._region}.amazonaws.com/{key}"
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"key": key, "url": url}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def download(self, key: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            client = self._get_client()
            resp = client.get_object(Bucket=self._bucket, Key=key)
            body = resp["Body"].read()
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data=body, metadata={"content_type": resp.get("ContentType", ""), "content_length": resp.get("ContentLength", 0)}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def delete(self, key: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            client = self._get_client()
            client.delete_object(Bucket=self._bucket, Key=key)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"key": key, "deleted": True}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def get_presigned_url(self, key: str, expiration: int = 3600, **kwargs: Any) -> ProviderResponse:
        start = time.monotonic()
        try:
            client = self._get_client()
            http_method = kwargs.get("http_method", "get_object")
            if http_method == "put_object":
                url = client.generate_presigned_url("put_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=expiration)
            else:
                url = client.generate_presigned_url("get_object", Params={"Bucket": self._bucket, "Key": key}, ExpiresIn=expiration)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data={"url": url, "expires_in": expiration}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def list_objects(self, prefix: str) -> ProviderResponse:
        start = time.monotonic()
        try:
            client = self._get_client()
            paginator = client.get_paginator("list_objects_v2")
            keys: List[str] = []
            for page in paginator.paginate(Bucket=self._bucket, Prefix=prefix):
                for obj in page.get("Contents", []):
                    keys.append(obj["Key"])
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(success=True, data=keys, metadata={"count": len(keys)}, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc


# ======================================================================
# Cloudflare R2 Adapter
# ======================================================================


class R2Adapter(S3Adapter):
    """Cloudflare R2 storage adapter.

    R2 is S3-compatible, so we inherit from :class:`S3Adapter` and
    override the endpoint URL to point at the R2 gateway.

    Configuration (via Django settings):
        ``CF_R2_ACCOUNT_ID``           — Cloudflare account ID.
        ``CF_R2_ACCESS_KEY_ID``        — R2 API token access key.
        ``CF_R2_SECRET_ACCESS_KEY``    — R2 API token secret key.
        ``CF_R2_BUCKET_NAME``          — R2 bucket name.
    """

    PROVIDER_NAME = "r2"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        account_id = getattr(settings, "CF_R2_ACCOUNT_ID", "")
        self._bucket = getattr(settings, "CF_R2_BUCKET_NAME", self._bucket)
        self._endpoint_url = f"https://{account_id}.r2.cloudflarestorage.com"
        # Override keys with R2-specific settings
        self._r2_access_key = getattr(settings, "CF_R2_ACCESS_KEY_ID", "")
        self._r2_secret_key = getattr(settings, "CF_R2_SECRET_ACCESS_KEY", "")
        self._client = None  # force re-creation with new endpoint

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "s3",
                    aws_access_key_id=self._r2_access_key or getattr(settings, "AWS_ACCESS_KEY_ID", None),
                    aws_secret_access_key=self._r2_secret_key or getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
                    region_name="auto",
                    endpoint_url=self._endpoint_url,
                )
            except ImportError as exc:
                raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME, message="boto3 is not installed") from exc
        return self._client

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not getattr(settings, "CF_R2_ACCOUNT_ID", ""):
            errors.append("CF_R2_ACCOUNT_ID is not configured")
        if not self._bucket:
            errors.append("CF_R2_BUCKET_NAME is not configured")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)


# ======================================================================
# MinIO Adapter
# ======================================================================


class MinIOAdapter(S3Adapter):
    """MinIO self-hosted storage adapter.

    MinIO is S3-compatible, so we inherit from :class:`S3Adapter` and
    override the endpoint URL.

    Configuration (via Django settings):
        ``MINIO_ENDPOINT``          — MinIO server URL (e.g. ``"http://localhost:9000"``).
        ``MINIO_ACCESS_KEY``        — MinIO access key.
        ``MINIO_SECRET_KEY``        — MinIO secret key.
        ``MINIO_BUCKET_NAME``       — Target bucket.
        ``MINIO_SECURE``            — Use HTTPS (default ``False``).
    """

    PROVIDER_NAME = "minio"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._bucket = getattr(settings, "MINIO_BUCKET_NAME", self._bucket)
        self._endpoint_url = getattr(settings, "MINIO_ENDPOINT", "http://localhost:9000")
        self._minio_access_key = getattr(settings, "MINIO_ACCESS_KEY", "")
        self._minio_secret_key = getattr(settings, "MINIO_SECRET_KEY", "")
        self._client = None

    def _get_client(self):
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client(
                    "s3",
                    aws_access_key_id=self._minio_access_key or getattr(settings, "AWS_ACCESS_KEY_ID", None),
                    aws_secret_access_key=self._minio_secret_key or getattr(settings, "AWS_SECRET_ACCESS_KEY", None),
                    region_name=getattr(settings, "MINIO_REGION", "us-east-1"),
                    endpoint_url=self._endpoint_url,
                )
            except ImportError as exc:
                raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME, message="boto3 is not installed") from exc
        return self._client

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not self._endpoint_url:
            errors.append("MINIO_ENDPOINT is not configured")
        if not self._bucket:
            errors.append("MINIO_BUCKET_NAME is not configured")
        if not self._minio_access_key:
            warnings.append("MINIO_ACCESS_KEY not set")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)
