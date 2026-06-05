"""
Data Transformation Layer - Digiland External Services Layer
==============================================================

Bidirectional transformation between the application's canonical data
models and provider-specific request/response formats.  Every external
service call passes through this layer to ensure clean separation
between business logic and wire protocols.

Components:
    - **DataTransformer**: Registry-based transformer with request/response
      mappers, schema validation, and nested object support.
    - **CanonicalModel**: Base class for canonical data models.
    - **FieldMapping**: Declarative field mapping descriptor.
    - **TransformationError**: Raised on transformation failures.
    - **ValidationError**: Raised on schema validation failures.

Design:
    Mappers are registered per ``(service_type, provider_name)`` and can
    be defined as plain functions or as classes with ``transform()`` and
    optionally ``validate()`` methods.  This allows providers to ship
    their own mapping modules while the core remains provider-agnostic.

Usage::

    from external_services.transformations import DataTransformer

    transformer = DataTransformer()

    # Register a request mapper (canonical -> provider format)
    transformer.register_request_mapper(
        'payment', 'paystack',
        lambda data: {
            'email': data['customer_email'],
            'amount': int(data['amount'] * 100),  # convert to kobo
            'currency': data.get('currency', 'KES'),
        },
    )

    # Register a response mapper (provider -> canonical)
    transformer.register_response_mapper(
        'payment', 'paystack',
        lambda data: {
            'transaction_id': data['data']['reference'],
            'status': 'completed' if data['status'] else 'failed',
            'provider_reference': data['data']['id'],
        },
    )

    # Transform outbound request
    provider_payload = transformer.transform_request(
        'payment', 'paystack', canonical_data,
    )

    # Transform inbound response
    canonical_result = transformer.transform_response(
        'payment', 'paystack', provider_response,
    )
"""

import copy
import logging
import re
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


# ═══════════════════════════════════════════════════════════════════════════
# Exceptions
# ═══════════════════════════════════════════════════════════════════════════


class TransformationError(Exception):
    """Raised when a data transformation fails.

    Attributes:
        service_type: Service category.
        provider_name: Provider name.
        direction: ``'request'`` or ``'response'``.
        details: Additional context about the failure.
    """

    def __init__(
        self,
        service_type: str,
        provider_name: str,
        direction: str,
        details: str = "",
    ):
        self.service_type = service_type
        self.provider_name = provider_name
        self.direction = direction
        self.details = details
        msg = (
            f"Transformation error ({direction}) for "
            f"{service_type}:{provider_name}: {details}"
        )
        super().__init__(msg)


class SchemaValidationError(Exception):
    """Raised when data does not conform to an expected schema.

    Attributes:
        service_type: Service category.
        provider_name: Provider name.
        direction: ``'request'`` or ``'response'``.
        errors: List of specific validation error messages.
    """

    def __init__(
        self,
        service_type: str,
        provider_name: str,
        direction: str,
        errors: list[str],
    ):
        self.service_type = service_type
        self.provider_name = provider_name
        self.direction = direction
        self.errors = errors
        msg = (
            f"Schema validation ({direction}) failed for "
            f"{service_type}:{provider_name}: {'; '.join(errors)}"
        )
        super().__init__(msg)


# ═══════════════════════════════════════════════════════════════════════════
# Field Mapping Descriptor
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class FieldMapping:
    """Declarative mapping between a canonical field and a provider field.

    Attributes:
        canonical_name: Field name in the canonical model.
        provider_name: Field name in the provider format.
        transform_fn: Optional callable ``(value) -> value`` applied
            during canonical -> provider transformation.
        reverse_fn: Optional callable ``(value) -> value`` applied
            during provider -> canonical transformation.
        required: Whether the field is required (default False).
        default: Default value if the field is missing (default None).
        nested: Dot-path for nested objects (e.g. ``'data.reference'``).
    """

    canonical_name: str
    provider_name: str
    transform_fn: Optional[Callable[[Any], Any]] = None
    reverse_fn: Optional[Callable[[Any], Any]] = None
    required: bool = False
    default: Any = None
    nested: Optional[str] = None


# ═══════════════════════════════════════════════════════════════════════════
# Canonical Model Base
# ═══════════════════════════════════════════════════════════════════════════


class CanonicalModel:
    """Base class for canonical data models used across the application.

    Provides a structured, typed container for data that flows between
    the application and external services.  Subclasses define fields
    using class attributes, and instances hold the actual data.

    Features:
        - Type-annotated field definitions
        - Automatic validation of required fields
        - Serialization to/from plain dicts
        - Immutability option for safety

    Example::

        class PaymentRequest(CanonicalModel):
            customer_email: str
            amount: float
            currency: str = 'KES'
            reference: Optional[str] = None

        req = PaymentRequest(customer_email='a@b.com', amount=1000.0)
        data = req.to_dict()
        req2 = PaymentRequest.from_dict(data)
    """

    _field_defaults: dict[str, Any] = {}
    _required_fields: set[str] = set()

    def __init__(self, **kwargs: Any) -> None:
        """Initialise the model, filling defaults for missing optional fields."""
        # Merge class-level defaults with provided kwargs
        all_fields = {**self._field_defaults, **kwargs}

        # Check required fields
        missing = self._required_fields - set(all_fields.keys())
        if missing:
            raise TypeError(
                f"{self.__class__.__name__} missing required fields: {missing}"
            )

        for name, value in all_fields.items():
            setattr(self, name, value)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CanonicalModel":
        """Create an instance from a plain dictionary.

        Only keys that correspond to declared fields are used; extra
        keys are silently ignored.
        """
        known = set(cls._field_defaults.keys()) | cls._required_fields
        filtered = {k: v for k, v in data.items() if k in known}
        return cls(**filtered)

    def to_dict(self) -> dict[str, Any]:
        """Serialize the model to a plain dictionary."""
        known = set(self._field_defaults.keys()) | self._required_fields
        return {k: getattr(self, k) for k in known if hasattr(self, k)}

    def __repr__(self) -> str:
        fields = self.to_dict()
        items = ", ".join(f"{k}={v!r}" for k, v in fields.items())
        return f"{self.__class__.__name__}({items})"

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, self.__class__):
            return NotImplemented
        return self.to_dict() == other.to_dict()


# Metaclass-like initialisation: scan annotations on subclass definition
_original_init_subclass = CanonicalModel.__init_subclass__


def _scan_subclass(cls: type) -> None:
    """Scan a CanonicalModel subclass for type-annotated fields."""
    defaults: dict[str, Any] = {}
    required: set[str] = set()

    for base in reversed(cls.__mro__):
        if base is object or base is CanonicalModel:
            continue
        annotations = getattr(base, "__annotations__", {})
        for field_name, field_type in annotations.items():
            if field_name.startswith("_"):
                continue
            if hasattr(base, field_name):
                defaults[field_name] = getattr(base, field_name)
            else:
                required.add(field_name)
                # Check for Optional[X] — not required if Optional
                origin = getattr(field_type, "__origin__", None)
                if origin is not None:
                    # typing.Optional[X] is Union[X, None]
                    import typing
                    args = getattr(field_type, "__args__", ())
                    if type(None) in args:
                        required.discard(field_name)

    cls._field_defaults = defaults
    cls._required_fields = required


# Patch __init_subclass__ to auto-scan fields
def _patched_init_subclass(cls, **kwargs):
    _scan_subclass(cls)
    # Call original if it exists
    if _original_init_subclass is not object.__init_subclass__:
        try:
            _original_init_subclass(**kwargs)
        except TypeError:
            pass


CanonicalModel.__init_subclass__ = classmethod(_patched_init_subclass)  # type: ignore[assignment]


# ═══════════════════════════════════════════════════════════════════════════
# Mapper Protocol
# ═══════════════════════════════════════════════════════════════════════════


class RequestMapper:
    """Base class for request mappers (canonical -> provider).

    Subclasses must implement :meth:`transform` and optionally
    :meth:`validate`.

    Example::

        class PaystackRequestMapper(RequestMapper):
            def transform(self, data):
                return {
                    'email': data['customer_email'],
                    'amount': int(data['amount'] * 100),
                }
    """

    def transform(self, data: dict[str, Any]) -> dict[str, Any]:
        """Transform canonical data to provider format.

        Args:
            data: Canonical request data.

        Returns:
            Provider-formatted request payload.
        """
        raise NotImplementedError("Subclasses must implement transform()")

    def validate(self, data: dict[str, Any]) -> list[str]:
        """Validate canonical data before transformation.

        Args:
            data: Canonical request data.

        Returns:
            List of validation error strings (empty if valid).
        """
        return []


class ResponseMapper:
    """Base class for response mappers (provider -> canonical).

    Example::

        class PaystackResponseMapper(ResponseMapper):
            def transform(self, data):
                return {
                    'transaction_id': data['data']['reference'],
                    'status': 'completed' if data['status'] else 'failed',
                }
    """

    def transform(self, data: dict[str, Any]) -> dict[str, Any]:
        """Transform provider response to canonical format.

        Args:
            data: Provider response data.

        Returns:
            Canonical response data.
        """
        raise NotImplementedError("Subclasses must implement transform()")

    def validate(self, data: dict[str, Any]) -> list[str]:
        """Validate provider response before transformation.

        Args:
            data: Provider response data.

        Returns:
            List of validation error strings (empty if valid).
        """
        return []


# ═══════════════════════════════════════════════════════════════════════════
# Schema Helpers
# ═══════════════════════════════════════════════════════════════════════════


@dataclass
class SchemaDefinition:
    """A simple schema definition for validating dicts.

    Attributes:
        required_fields: Fields that must be present and non-None.
        optional_fields: Fields that may be absent.
        field_types: Mapping of field name to expected Python type.
        nested_schemas: Mapping of field name to child SchemaDefinition.
    """

    required_fields: list[str] = field(default_factory=list)
    optional_fields: list[str] = field(default_factory=list)
    field_types: dict[str, type] = field(default_factory=dict)
    nested_schemas: dict[str, "SchemaDefinition"] = field(default_factory=dict)

    def validate(self, data: dict[str, Any]) -> list[str]:
        """Validate *data* against this schema.

        Returns:
            List of error strings (empty if valid).
        """
        errors: list[str] = []

        # Check required fields
        for name in self.required_fields:
            if name not in data or data[name] is None:
                errors.append(f"Missing required field: '{name}'")

        # Check types
        for name, expected_type in self.field_types.items():
            if name in data and data[name] is not None:
                if not isinstance(data[name], expected_type):
                    errors.append(
                        f"Field '{name}' expected type {expected_type.__name__}, "
                        f"got {type(data[name]).__name__}"
                    )

        # Check nested schemas
        for name, child_schema in self.nested_schemas.items():
            if name in data and isinstance(data[name], dict):
                child_errors = child_schema.validate(data[name])
                for err in child_errors:
                    errors.append(f"{name}.{err}")

        return errors


# ═══════════════════════════════════════════════════════════════════════════
# Data Transformer
# ═══════════════════════════════════════════════════════════════════════════


class DataTransformer:
    """Transform data between application canonical models and provider formats.

    Manages a registry of request/response mappers and schemas per
    ``(service_type, provider_name)``.  Provides declarative field
    mapping via :class:`FieldMapping` descriptors and nested object
    traversal via dot-path notation.

    Features:
        - Request mappers (canonical -> provider format)
        - Response mappers (provider format -> canonical)
        - Schema validation for both directions
        - Declarative field mappings with transform / reverse functions
        - Nested object transformation via dot-path
        - Identity mapping fallback (pass-through when no mapper is
          registered)

    Example::

        transformer = DataTransformer()

        # Register field mappings
        transformer.register_field_mappings('payment', 'paystack', [
            FieldMapping('customer_email', 'email', required=True),
            FieldMapping('amount', 'amount', transform_fn=lambda v: int(v * 100)),
            FieldMapping('currency', 'currency', default='KES'),
        ])

        # Transform
        payload = transformer.transform_request(
            'payment', 'paystack',
            {'customer_email': 'a@b.com', 'amount': 1000.0},
        )
        # => {'email': 'a@b.com', 'amount': 100000, 'currency': 'KES'}
    """

    _global_instance: Optional["DataTransformer"] = None
    _global_lock = threading.Lock()

    def __init__(self) -> None:
        self._lock = threading.RLock()

        # Mapper registry: (service_type, provider_name) -> mapper
        self._request_mappers: dict[str, Any] = {}
        self._response_mappers: dict[str, Any] = {}

        # Field mapping registry
        self._field_mappings: dict[str, list[FieldMapping]] = {}

        # Schema registry
        self._request_schemas: dict[str, SchemaDefinition] = {}
        self._response_schemas: dict[str, SchemaDefinition] = {}

    @classmethod
    def get_global(cls) -> "DataTransformer":
        """Return the process-wide singleton transformer."""
        if cls._global_instance is None:
            with cls._global_lock:
                if cls._global_instance is None:
                    cls._global_instance = cls()
        return cls._global_instance

    @classmethod
    def reset_global(cls) -> None:
        """Reset the global singleton (useful in tests)."""
        with cls._global_lock:
            cls._global_instance = None

    # ------------------------------------------------------------------
    # Mapper registration
    # ------------------------------------------------------------------

    def register_request_mapper(
        self,
        service_type: str,
        provider_name: str,
        mapper: Any,
    ) -> None:
        """Register a request mapper for a provider.

        Args:
            service_type: Service category.
            provider_name: Provider name.
            mapper: A callable ``(dict) -> dict`` or a :class:`RequestMapper`
                instance with a ``transform()`` method.
        """
        key = self._make_key(service_type, provider_name)
        with self._lock:
            self._request_mappers[key] = mapper
        logger.debug(
            "DataTransformer: registered request mapper for '%s'", key
        )

    def register_response_mapper(
        self,
        service_type: str,
        provider_name: str,
        mapper: Any,
    ) -> None:
        """Register a response mapper for a provider.

        Args:
            service_type: Service category.
            provider_name: Provider name.
            mapper: A callable ``(dict) -> dict`` or a :class:`ResponseMapper`
                instance with a ``transform()`` method.
        """
        key = self._make_key(service_type, provider_name)
        with self._lock:
            self._response_mappers[key] = mapper
        logger.debug(
            "DataTransformer: registered response mapper for '%s'", key
        )

    def register_field_mappings(
        self,
        service_type: str,
        provider_name: str,
        mappings: list[FieldMapping],
    ) -> None:
        """Register declarative field mappings for a provider.

        When both a mapper function and field mappings are registered
        for the same provider, the mapper function takes precedence.

        Args:
            service_type: Service category.
            provider_name: Provider name.
            mappings: List of :class:`FieldMapping` descriptors.
        """
        key = self._make_key(service_type, provider_name)
        with self._lock:
            self._field_mappings[key] = mappings
        logger.debug(
            "DataTransformer: registered %d field mappings for '%s'",
            len(mappings),
            key,
        )

    def register_request_schema(
        self,
        service_type: str,
        provider_name: str,
        schema: SchemaDefinition,
    ) -> None:
        """Register a request validation schema."""
        key = self._make_key(service_type, provider_name)
        with self._lock:
            self._request_schemas[key] = schema

    def register_response_schema(
        self,
        service_type: str,
        provider_name: str,
        schema: SchemaDefinition,
    ) -> None:
        """Register a response validation schema."""
        key = self._make_key(service_type, provider_name)
        with self._lock:
            self._response_schemas[key] = schema

    # ------------------------------------------------------------------
    # Transformation
    # ------------------------------------------------------------------

    def transform_request(
        self,
        service_type: str,
        provider_name: str,
        canonical_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform canonical request data to provider format.

        Resolution order:
            1. Explicit request mapper (callable or RequestMapper instance)
            2. Declarative field mappings
            3. Identity mapping (pass-through copy)

        Args:
            service_type: Service category.
            provider_name: Provider name.
            canonical_data: Data in canonical application format.

        Returns:
            Data in provider-specific format.

        Raises:
            TransformationError: If the transformation fails.
            SchemaValidationError: If the input fails schema validation.
        """
        key = self._make_key(service_type, provider_name)

        # Validate input
        self.validate_request(service_type, provider_name, canonical_data)

        with self._lock:
            mapper = self._request_mappers.get(key)
            field_mappings = self._field_mappings.get(key)

        try:
            if mapper is not None:
                result = self._apply_mapper(mapper, canonical_data)
            elif field_mappings:
                result = self._apply_field_mappings(
                    field_mappings, canonical_data, direction="forward"
                )
            else:
                # Identity mapping — deep copy to prevent mutation
                result = copy.deepcopy(canonical_data)
        except TransformationError:
            raise
        except Exception as exc:
            raise TransformationError(
                service_type, provider_name, "request", str(exc)
            ) from exc

        return result

    def transform_response(
        self,
        service_type: str,
        provider_name: str,
        provider_data: dict[str, Any],
    ) -> dict[str, Any]:
        """Transform provider response data to canonical format.

        Resolution order:
            1. Explicit response mapper (callable or ResponseMapper instance)
            2. Declarative field mappings (reverse direction)
            3. Identity mapping (pass-through copy)

        Args:
            service_type: Service category.
            provider_name: Provider name.
            provider_data: Data in provider-specific format.

        Returns:
            Data in canonical application format.

        Raises:
            TransformationError: If the transformation fails.
            SchemaValidationError: If the output fails canonical schema
                validation.
        """
        key = self._make_key(service_type, provider_name)

        with self._lock:
            mapper = self._response_mappers.get(key)
            field_mappings = self._field_mappings.get(key)

        try:
            if mapper is not None:
                result = self._apply_mapper(mapper, provider_data)
            elif field_mappings:
                result = self._apply_field_mappings(
                    field_mappings, provider_data, direction="reverse"
                )
            else:
                result = copy.deepcopy(provider_data)
        except TransformationError:
            raise
        except Exception as exc:
            raise TransformationError(
                service_type, provider_name, "response", str(exc)
            ) from exc

        # Validate output against canonical schema
        self.validate_response(service_type, provider_name, result)

        return result

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate_request(
        self,
        service_type: str,
        provider_name: str,
        data: dict[str, Any],
    ) -> list[str]:
        """Validate request data against the registered schema.

        Also validates required fields in declarative field mappings if
        no explicit schema is registered.

        Args:
            service_type: Service category.
            provider_name: Provider name.
            data: Canonical request data.

        Returns:
            List of validation error strings (empty if valid).

        Raises:
            SchemaValidationError: If validation fails and strict mode
                is enabled.
        """
        key = self._make_key(service_type, provider_name)

        with self._lock:
            schema = self._request_schemas.get(key)
            field_mappings = self._field_mappings.get(key)

        errors: list[str] = []

        # Schema validation
        if schema is not None:
            if hasattr(schema, "validate"):
                errors.extend(schema.validate(data))

        # Field mapping required-field validation
        if field_mappings:
            for fm in field_mappings:
                if fm.required and (fm.canonical_name not in data or data[fm.canonical_name] is None):
                    errors.append(
                        f"Missing required field: '{fm.canonical_name}'"
                    )

        if errors:
            raise SchemaValidationError(
                service_type, provider_name, "request", errors
            )

        return errors

    def validate_response(
        self,
        service_type: str,
        provider_name: str,
        data: dict[str, Any],
    ) -> list[str]:
        """Validate response data against the registered canonical schema.

        Args:
            service_type: Service category.
            provider_name: Provider name.
            data: Canonical response data.

        Returns:
            List of validation error strings (empty if valid).

        Raises:
            SchemaValidationError: If validation fails.
        """
        key = self._make_key(service_type, provider_name)

        with self._lock:
            schema = self._response_schemas.get(key)

        errors: list[str] = []

        if schema is not None:
            if hasattr(schema, "validate"):
                errors.extend(schema.validate(data))

        if errors:
            raise SchemaValidationError(
                service_type, provider_name, "response", errors
            )

        return errors

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _make_key(service_type: str, provider_name: str) -> str:
        return f"{service_type}:{provider_name}"

    @staticmethod
    def _apply_mapper(mapper: Any, data: dict[str, Any]) -> dict[str, Any]:
        """Apply a mapper (callable or class instance) to data."""
        if callable(mapper) and not hasattr(mapper, "transform"):
            return mapper(data)
        if hasattr(mapper, "transform"):
            return mapper.transform(data)
        raise TransformationError(
            "", "", "", f"Invalid mapper type: {type(mapper)}"
        )

    @staticmethod
    def _apply_field_mappings(
        mappings: list[FieldMapping],
        data: dict[str, Any],
        direction: str = "forward",
    ) -> dict[str, Any]:
        """Apply declarative field mappings to data.

        Args:
            mappings: List of FieldMapping descriptors.
            data: Input data dict.
            direction: ``'forward'`` (canonical -> provider) or
                ``'reverse'`` (provider -> canonical).

        Returns:
            Transformed data dict.
        """
        result: dict[str, Any] = {}

        for fm in mappings:
            if direction == "forward":
                source_key = fm.canonical_name
                target_key = fm.provider_name
                transform_fn = fm.transform_fn
            else:
                source_key = fm.provider_name
                target_key = fm.canonical_name
                transform_fn = fm.reverse_fn or fm.transform_fn

            # Handle nested dot-path for source
            value = _get_nested(data, fm.nested or source_key, source_key)

            if value is _MISSING:
                if fm.default is not None:
                    value = fm.default
                elif fm.required and direction == "forward":
                    raise TransformationError(
                        "", "", direction,
                        f"Missing required field '{source_key}'",
                    )
                else:
                    continue

            # Apply transform function
            if transform_fn is not None:
                try:
                    value = transform_fn(value)
                except Exception as exc:
                    raise TransformationError(
                        "", "", direction,
                        f"Transform function failed for '{source_key}': {exc}",
                    ) from exc

            # Set value in result (handle nested target paths)
            _set_nested(result, target_key, value)

        return result


# ═══════════════════════════════════════════════════════════════════════════
# Utility functions
# ═══════════════════════════════════════════════════════════════════════════

_MISSING = object()


def _get_nested(data: dict[str, Any], path: str, fallback_key: str) -> Any:
    """Retrieve a value from a nested dict using a dot-path.

    If the dot-path doesn't exist, falls back to the plain key.

    Args:
        data: The dict to search.
        path: Dot-separated path (e.g. ``'data.reference'``) or plain key.
        fallback_key: Simple key to try if the dot-path fails.

    Returns:
        The found value, or ``_MISSING``.
    """
    if "." in path:
        parts = path.split(".")
        current: Any = data
        for part in parts:
            if isinstance(current, dict) and part in current:
                current = current[part]
            else:
                # Fallback to simple key
                return data.get(fallback_key, _MISSING)
        return current
    return data.get(path, _MISSING)


def _set_nested(data: dict[str, Any], key: str, value: Any) -> None:
    """Set a value in a dict, handling dot-path notation for nested objects.

    If the key contains dots, intermediate dicts are created as needed.

    Args:
        data: The dict to modify.
        key: Simple key or dot-separated path.
        value: The value to set.
    """
    if "." in key:
        parts = key.split(".")
        current = data
        for part in parts[:-1]:
            if part not in current or not isinstance(current[part], dict):
                current[part] = {}
            current = current[part]
        current[parts[-1]] = value
    else:
        data[key] = value


# ═══════════════════════════════════════════════════════════════════════════
# Module exports
# ═══════════════════════════════════════════════════════════════════════════

__all__ = [
    "CanonicalModel",
    "DataTransformer",
    "FieldMapping",
    "RequestMapper",
    "ResponseMapper",
    "SchemaDefinition",
    "SchemaValidationError",
    "TransformationError",
]
