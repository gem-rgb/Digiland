"""
Maps / geolocation provider adapter for the External Services Layer.

Implements the :class:`~external_services.base.MapsProvider` interface
for:

* **GoogleMapsAdapter** — Google Maps Geocoding, Distance Matrix, and
  Directions APIs.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import requests
from django.conf import settings

from external_services.base import (
    HealthCheckResult,
    MapsProvider,
    ProviderResponse,
    ValidationResult,
)
from external_services.exceptions import (
    ProviderResponseError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class GoogleMapsAdapter(MapsProvider):
    """Google Maps adapter using the Geocoding, Distance Matrix, and Directions APIs.

    Configuration (via Django settings):
        ``GOOGLE_MAPS_API_KEY`` — Google Maps API key.
    """

    PROVIDER_NAME = "google_maps"
    _GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"
    _DISTANCE_URL = "https://maps.googleapis.com/maps/api/distancematrix/json"
    _DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="maps", **kwargs)
        self._api_key: str = getattr(settings, "GOOGLE_MAPS_API_KEY", "")
        self._session: Optional[requests.Session] = None

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            self._session = requests.Session()
            # Verify API key with a lightweight geocode request
            resp = self._session.get(self._GEOCODE_URL, params={"address": "Nairobi", "key": self._api_key}, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("status") in ("OK", "ZERO_RESULTS"):
                    self.is_connected = True
                    return True
                if data.get("status") == "REQUEST_DENIED":
                    from external_services.exceptions import AuthenticationError
                    raise AuthenticationError(provider_name=self.PROVIDER_NAME, message=data.get("error_message", "API key invalid"))
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME)
        except (AuthenticationError, ProviderUnavailableError):
            raise
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME) from exc

    def disconnect(self) -> bool:
        if self._session:
            self._session.close()
            self._session = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            resp = requests.get(self._GEOCODE_URL, params={"address": "Nairobi", "key": self._api_key}, timeout=5)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json() if resp.status_code == 200 else {}
            status = "healthy" if data.get("status") in ("OK", "ZERO_RESULTS") else "degraded"
            return HealthCheckResult(status=status, provider=self.PROVIDER_NAME, response_time_ms=elapsed)
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not self._api_key:
            errors.append("GOOGLE_MAPS_API_KEY is not configured")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- maps operations --------------------------------------------------

    def geocode(self, address: str) -> ProviderResponse:
        """Convert a street address to geographic coordinates.

        Returns latitude and longitude of the top result.
        """
        start = time.monotonic()
        try:
            resp = self._session.get(self._GEOCODE_URL, params={"address": address, "key": self._api_key}, timeout=10)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if data.get("status") == "OK" and data.get("results"):
                location = data["results"][0]["geometry"]["location"]
                return ProviderResponse(
                    success=True,
                    data={"lat": location["lat"], "lng": location["lng"], "formatted_address": data["results"][0].get("formatted_address", ""), "place_id": data["results"][0].get("place_id", "")},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            return ProviderResponse(success=False, error=f"Geocode failed: {data.get('status', 'unknown')}", data=data, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def reverse_geocode(self, lat: float, lng: float) -> ProviderResponse:
        """Convert geographic coordinates to a street address."""
        start = time.monotonic()
        try:
            resp = self._session.get(self._GEOCODE_URL, params={"latlng": f"{lat},{lng}", "key": self._api_key}, timeout=10)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if data.get("status") == "OK" and data.get("results"):
                result = data["results"][0]
                components = {}
                for comp in result.get("address_components", []):
                    types = comp.get("types", [])
                    if "locality" in types:
                        components["city"] = comp["long_name"]
                    elif "administrative_area_level_1" in types:
                        components["region"] = comp["long_name"]
                    elif "country" in types:
                        components["country"] = comp["long_name"]
                return ProviderResponse(
                    success=True,
                    data={"formatted_address": result.get("formatted_address", ""), "components": components, "place_id": result.get("place_id", "")},
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            return ProviderResponse(success=False, error=f"Reverse geocode failed: {data.get('status', 'unknown')}", provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def get_distance(self, origin: str, destination: str, **kwargs: Any) -> ProviderResponse:
        """Calculate the distance between two locations.

        Args:
            origin: Origin address or ``"lat,lng"`` string.
            destination: Destination address or ``"lat,lng"`` string.
            **kwargs: ``mode`` (``"driving"``, ``"walking"``), ``units`` (``"metric"`` or ``"imperial"``).
        """
        start = time.monotonic()
        try:
            params: Dict[str, Any] = {
                "origins": origin,
                "destinations": destination,
                "key": self._api_key,
                "units": kwargs.get("units", "metric"),
            }
            if kwargs.get("mode"):
                params["mode"] = kwargs["mode"]
            resp = self._session.get(self._DISTANCE_URL, params=params, timeout=10)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if data.get("status") == "OK":
                element = data["rows"][0]["elements"][0]
                if element.get("status") == "OK":
                    return ProviderResponse(
                        success=True,
                        data={
                            "distance": {"text": element["distance"]["text"], "meters": element["distance"]["value"]},
                            "duration": {"text": element["duration"]["text"], "seconds": element["duration"]["value"]},
                        },
                        provider=self.PROVIDER_NAME,
                        latency_ms=elapsed,
                    )
            return ProviderResponse(success=False, error="Distance calculation failed", data=data, provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def get_directions(self, origin: str, destination: str, **kwargs: Any) -> ProviderResponse:
        """Get turn-by-turn directions between two locations.

        Args:
            origin: Origin address or ``"lat,lng"`` string.
            destination: Destination address or ``"lat,lng"`` string.
            **kwargs: ``mode``, ``waypoints`` (comma-separated), ``avoid`` (tolls/highways/ferries).
        """
        start = time.monotonic()
        try:
            params: Dict[str, Any] = {
                "origin": origin,
                "destination": destination,
                "key": self._api_key,
            }
            if kwargs.get("mode"):
                params["mode"] = kwargs["mode"]
            if kwargs.get("waypoints"):
                params["waypoints"] = kwargs["waypoints"]
            if kwargs.get("avoid"):
                params["avoid"] = kwargs["avoid"]

            resp = self._session.get(self._DIRECTIONS_URL, params=params, timeout=15)
            elapsed = (time.monotonic() - start) * 1000
            data = resp.json()
            if data.get("status") == "OK" and data.get("routes"):
                route = data["routes"][0]
                legs = route.get("legs", [])
                steps = []
                for leg in legs:
                    for step in leg.get("steps", []):
                        steps.append({
                            "instruction": step.get("html_instructions", ""),
                            "distance": step.get("distance", {}).get("text", ""),
                            "duration": step.get("duration", {}).get("text", ""),
                        })
                return ProviderResponse(
                    success=True,
                    data={
                        "summary": route.get("summary", ""),
                        "total_distance": legs[0]["distance"]["text"] if legs else "",
                        "total_duration": legs[0]["duration"]["text"] if legs else "",
                        "steps": steps,
                    },
                    provider=self.PROVIDER_NAME,
                    latency_ms=elapsed,
                )
            return ProviderResponse(success=False, error=f"Directions failed: {data.get('status', 'unknown')}", provider=self.PROVIDER_NAME, latency_ms=elapsed)
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc
