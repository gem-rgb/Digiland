"""
Search provider adapter for the External Services Layer.

Implements the :class:`~external_services.base.SearchProvider` interface
for:

* **ElasticsearchAdapter** — Elasticsearch via the ``elasticsearch-py``
  client library.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional, Sequence

from django.conf import settings

from external_services.base import (
    HealthCheckResult,
    ProviderResponse,
    SearchProvider,
    ValidationResult,
)
from external_services.exceptions import (
    ProviderResponseError,
    ProviderUnavailableError,
)

logger = logging.getLogger(__name__)


class ElasticsearchAdapter(SearchProvider):
    """Elasticsearch search adapter.

    Uses the official ``elasticsearch-py`` client for indexing, searching,
    deleting, and bulk operations.

    Configuration (via Django settings):
        ``ELASTICSEARCH_URL``    — Elasticsearch cluster URL (default ``"http://localhost:9200"``).
        ``ELASTICSEARCH_API_KEY`` — Optional API key for authentication.
    """

    PROVIDER_NAME = "elasticsearch"

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(provider_name=self.PROVIDER_NAME, service_type="search", **kwargs)
        self._url: str = getattr(settings, "ELASTICSEARCH_URL", "http://localhost:9200")
        self._api_key: str = getattr(settings, "ELASTICSEARCH_API_KEY", "")
        self._es_client = None

    def _get_client(self):
        """Lazy-initialise the Elasticsearch client."""
        if self._es_client is None:
            try:
                from elasticsearch import Elasticsearch
                kwargs: Dict[str, Any] = {"hosts": [self._url]}
                if self._api_key:
                    kwargs["api_key"] = self._api_key
                self._es_client = Elasticsearch(**kwargs)
            except ImportError as exc:
                raise ProviderUnavailableError(
                    provider_name=self.PROVIDER_NAME,
                    message="elasticsearch package is not installed",
                ) from exc
        return self._es_client

    # -- lifecycle --------------------------------------------------------

    def connect(self) -> bool:
        try:
            es = self._get_client()
            if es.ping():
                self.is_connected = True
                return True
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME, message="Elasticsearch ping failed")
        except ProviderUnavailableError:
            raise
        except Exception as exc:
            raise ProviderUnavailableError(provider_name=self.PROVIDER_NAME) from exc

    def disconnect(self) -> bool:
        if self._es_client:
            self._es_client.close()
            self._es_client = None
        self.is_connected = False
        return True

    def health_check(self) -> HealthCheckResult:
        start = time.monotonic()
        try:
            es = self._get_client()
            cluster_health = es.cluster.health()
            elapsed = (time.monotonic() - start) * 1000
            status = cluster_health.get("status", "red")
            # Map ES status: green → healthy, yellow → degraded, red → unhealthy
            status_map = {"green": "healthy", "yellow": "degraded", "red": "unhealthy"}
            return HealthCheckResult(
                status=status_map.get(status, "unhealthy"),
                provider=self.PROVIDER_NAME,
                response_time_ms=elapsed,
                details={"cluster_name": cluster_health.get("cluster_name"), "number_of_nodes": cluster_health.get("number_of_nodes")},
            )
        except Exception:
            return HealthCheckResult(status="unhealthy", provider=self.PROVIDER_NAME)

    def validate_configuration(self) -> ValidationResult:
        errors, warnings = [], []
        if not self._url:
            errors.append("ELASTICSEARCH_URL is not configured")
        return ValidationResult(is_valid=len(errors) == 0, errors=errors, warnings=warnings)

    # -- search operations ------------------------------------------------

    def index_document(self, index: str, doc_id: str, document: Dict[str, Any]) -> ProviderResponse:
        """Index (create or update) a single document."""
        start = time.monotonic()
        try:
            es = self._get_client()
            result = es.index(index=index, id=doc_id, body=document)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(
                success=result.get("result") in ("created", "updated"),
                data={"index": index, "id": doc_id, "result": result.get("result"), "version": result.get("_version")},
                provider=self.PROVIDER_NAME,
                latency_ms=elapsed,
            )
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def search(self, index: str, query: str, **kwargs: Any) -> ProviderResponse:
        """Execute a search query against an index.

        Args:
            index: Index name.
            query: Search query string (uses ``multi_match`` by default).
            **kwargs: ``filters``, ``page``, ``page_size``, ``sort``, ``fields``.
        """
        start = time.monotonic()
        try:
            es = self._get_client()
            body: Dict[str, Any] = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": kwargs.get("fields", ["*"]),
                    }
                },
            }
            if kwargs.get("filters"):
                body["query"] = {"bool": {"must": [body["query"]], "filter": kwargs["filters"]}}
            if kwargs.get("sort"):
                body["sort"] = kwargs["sort"]

            page = kwargs.get("page", 1)
            page_size = kwargs.get("page_size", 20)
            body["from"] = (page - 1) * page_size
            body["size"] = page_size

            result = es.search(index=index, body=body)
            elapsed = (time.monotonic() - start) * 1000
            hits = [hit["_source"] | {"_id": hit["_id"], "_score": hit["_score"]} for hit in result.get("hits", {}).get("hits", [])]
            total = result.get("hits", {}).get("total", {}).get("value", 0)
            return ProviderResponse(
                success=True,
                data={"hits": hits, "total": total, "page": page, "page_size": page_size},
                provider=self.PROVIDER_NAME,
                latency_ms=elapsed,
            )
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def delete_document(self, index: str, doc_id: str) -> ProviderResponse:
        """Remove a document from the index."""
        start = time.monotonic()
        try:
            es = self._get_client()
            result = es.delete(index=index, id=doc_id)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(
                success=result.get("result") == "deleted",
                data={"index": index, "id": doc_id, "result": result.get("result")},
                provider=self.PROVIDER_NAME,
                latency_ms=elapsed,
            )
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc

    def bulk_index(self, index: str, documents: Sequence[Dict[str, Any]]) -> ProviderResponse:
        """Index multiple documents in a single batch.

        Each document **must** contain an ``id`` field used as the
        document ``_id`` in Elasticsearch.
        """
        start = time.monotonic()
        try:
            es = self._get_client()
            from elasticsearch.helpers import bulk as es_bulk
            actions = []
            for doc in documents:
                doc_id = doc.pop("id", None)
                action = {"_index": index, "_source": doc}
                if doc_id:
                    action["_id"] = str(doc_id)
                actions.append(action)
            success_count, errors = es_bulk(es, actions, raise_on_error=False)
            elapsed = (time.monotonic() - start) * 1000
            return ProviderResponse(
                success=len(errors) == 0 if isinstance(errors, list) else True,
                data={"success_count": success_count, "error_count": len(errors) if isinstance(errors, list) else 0, "total": len(actions)},
                provider=self.PROVIDER_NAME,
                latency_ms=elapsed,
            )
        except Exception as exc:
            raise ProviderResponseError(provider_name=self.PROVIDER_NAME, message=str(exc)) from exc
