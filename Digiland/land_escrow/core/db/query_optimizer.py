"""
Query optimization utilities for the Digiland platform.

Analyzes Django querysets for N+1 problems, missing indexes, and
performance issues. Provides automatic optimization via select_related /
prefetch_related and EXPLAIN ANALYZE integration.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any

from django.db import connection, models
from django.db.models import QuerySet

logger = logging.getLogger(__name__)


@dataclass
class QueryAnalysisResult:
    """Holds the result of analysing a single queryset."""

    has_n_plus_one: bool = False
    n_plus_one_relations: List[str] = field(default_factory=list)
    missing_indexes: List[str] = field(default_factory=list)
    full_table_scans: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    estimated_cost: Optional[float] = None
    execution_time_ms: Optional[float] = None
    raw_explain: Optional[str] = None


@dataclass
class IndexSuggestion:
    """Represents a suggested index for a model."""

    model_name: str
    table_name: str
    columns: List[str]
    index_type: str = "btree"  # btree, gin, gist, hash
    reason: str = ""
    estimated_impact: str = "medium"  # low, medium, high
    create_sql: str = ""


class SlowQueryLog(models.Model):
    """Stores slow query data for analysis and alerting.

    Persisted in the database so that operations teams can review
    historical slow-query trends without relying on external log
    aggregation.
    """

    query_hash = models.CharField(max_length=64, db_index=True)
    query_sql = models.TextField()
    execution_time_ms = models.FloatField(help_text="Query duration in milliseconds")
    rows_examined = models.BigIntegerField(default=0)
    rows_returned = models.BigIntegerField(default=0)
    query_source = models.CharField(max_length=255, blank=True, help_text="View/URL that triggered this query")
    database_vendor = models.CharField(max_length=30, default="postgresql")
    tenant_id = models.UUIDField(db_index=True, null=True, blank=True)
    captured_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-execution_time_ms"]
        indexes = [
            models.Index(fields=["query_hash", "captured_at"], name="idx_sql_hash_captured"),
            models.Index(fields=["execution_time_ms"], name="idx_sql_exec_time"),
        ]

    def __str__(self):
        return f"SlowQuery({self.query_hash[:8]}… {self.execution_time_ms:.1f}ms)"


class QueryOptimizer:
    """Analyzes, diagnoses, and optimises Django querysets.

    Usage::

        optimizer = QueryOptimizer()
        result = optimizer.analyze_queryset(Transaction.objects.all())
        optimized = optimizer.optimize_queryset(Transaction.objects.all())
    """

    SLOW_THRESHOLD_MS = 200

    # ── Analysis ──────────────────────────────────────────────

    def analyze_query(self, queryset: QuerySet) -> QueryAnalysisResult:
        """Analyze a Django queryset for N+1, missing indexes, etc."""
        result = QueryAnalysisResult()
        model = queryset.model

        # 1. Detect N+1 via FK / M2M traversal without select/prefetch
        self._detect_n_plus_one(queryset, result)

        # 2. Run EXPLAIN ANALYZE (PostgreSQL only)
        if connection.vendor == "postgresql":
            explain_result = self.explain_query(queryset)
            result.raw_explain = explain_result
            self._parse_explain(explain_result, result)

        # 3. Check for missing indexes on filter / order columns
        self._check_missing_indexes(model, queryset.query, result)

        return result

    # ── Index Suggestions ─────────────────────────────────────

    def suggest_indexes(self, model: type) -> List[IndexSuggestion]:
        """Suggest indexes based on query patterns for *model*."""
        suggestions: List[IndexSuggestion] = []
        if connection.vendor != "postgresql":
            logger.info("Index suggestions are PostgreSQL-only; skipping on %s", connection.vendor)
            return suggestions

        table = model._meta.db_table
        with connection.cursor() as cursor:
            # Find columns frequently used in filters but lacking an index
            cursor.execute(
                """
                SELECT attname, n_distinct
                FROM pg_stats
                WHERE tablename = %s AND n_distinct > 0.1
                ORDER BY n_distinct DESC
                """,
                [table],
            )
            for col_name, n_distinct in cursor.fetchall():
                cursor.execute(
                    """
                    SELECT 1 FROM pg_indexes
                    WHERE tablename = %s AND indexdef LIKE %s LIMIT 1
                    """,
                    [table, f"%{col_name}%"],
                )
                if not cursor.fetchone():
                    suggestions.append(
                        IndexSuggestion(
                            model_name=model.__name__,
                            table_name=table,
                            columns=[col_name],
                            reason=f"Column '{col_name}' has high cardinality ({n_distinct:.2f}) but no index",
                            estimated_impact="high",
                            create_sql=f"CREATE INDEX idx_{table}_{col_name} ON {table} ({col_name});",
                        )
                    )
        return suggestions

    # ── Auto-optimisation ─────────────────────────────────────

    def optimize_queryset(self, queryset: QuerySet) -> QuerySet:
        """Apply select_related / prefetch_related automatically."""
        model = queryset.model
        fk_fields, m2m_fields = [], []

        for f in model._meta.get_fields():
            if hasattr(f, "related_model") and f.related_model is not None:
                if f.many_to_one or f.one_to_one:
                    fk_fields.append(f.name)
                elif f.one_to_many or f.many_to_many:
                    m2m_fields.append(f.name)

        if fk_fields:
            queryset = queryset.select_related(*fk_fields)
        if m2m_fields:
            queryset = queryset.prefetch_related(*m2m_fields)
        return queryset

    # ── EXPLAIN ANALYZE ───────────────────────────────────────

    def explain_query(self, queryset: QuerySet) -> Optional[str]:
        """Run EXPLAIN ANALYZE and return results (PostgreSQL only)."""
        if connection.vendor != "postgresql":
            logger.warning("EXPLAIN ANALYZE is PostgreSQL-only; skipping on %s", connection.vendor)
            return None
        try:
            sql, params = queryset.query.sql_with_params()
            with connection.cursor() as cursor:
                cursor.execute(f"EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT) {sql}", params)
                rows = cursor.fetchall()
            return "\n".join(r[0] for r in rows)
        except Exception as exc:
            logger.error("EXPLAIN ANALYZE failed: %s", exc)
            return None

    # ── Slow Query Log ────────────────────────────────────────

    def get_slow_queries(self, limit: int = 20) -> List[SlowQueryLog]:
        """Return the most recent slow query log entries."""
        return SlowQueryLog.objects.all()[:limit]

    def get_query_stats(self) -> Dict[str, Any]:
        """Aggregate query performance statistics."""
        stats: Dict[str, Any] = {"total_slow_queries": 0, "avg_execution_time_ms": 0.0,
                                  "top_queries": [], "by_source": {}}
        try:
            qs = SlowQueryLog.objects.all()
            stats["total_slow_queries"] = qs.count()
            if stats["total_slow_queries"] > 0:
                from django.db.models import Avg
                agg = qs.aggregate(avg=Avg("execution_time_ms"))
                stats["avg_execution_time_ms"] = round(agg["avg"] or 0, 2)
                stats["top_queries"] = list(
                    qs.values("query_hash", "query_sql", "execution_time_ms")[:5]
                )
        except Exception as exc:
            logger.error("Failed to compute query stats: %s", exc)
        return stats

    # ── Private helpers ───────────────────────────────────────

    @staticmethod
    def _detect_n_plus_one(queryset: QuerySet, result: QueryAnalysisResult):
        """Flag FK lookups that would cause N+1 queries."""
        model = queryset.model
        existing_select = set(queryset.query.select_related or [])
        existing_prefetch = {p.prefetch_lookup for p in queryset._prefetch_related_lookups} \
            if hasattr(queryset, "_prefetch_related_lookups") and queryset._prefetch_related_lookups else set()

        for f in model._meta.get_fields():
            if hasattr(f, "related_model") and f.related_model:
                if f.many_to_one or f.one_to_one:
                    if f.name not in existing_select:
                        result.has_n_plus_one = True
                        result.n_plus_one_relations.append(f.name)
                        result.suggestions.append(
                            f"Use select_related('{f.name}') to avoid N+1 on {model.__name__}.{f.name}"
                        )
                elif f.one_to_many or f.many_to_many:
                    if f.name not in existing_prefetch:
                        result.has_n_plus_one = True
                        result.n_plus_one_relations.append(f.name)
                        result.suggestions.append(
                            f"Use prefetch_related('{f.name}') to avoid N+1 on {model.__name__}.{f.name}"
                        )

    def _parse_explain(self, explain_text: Optional[str], result: QueryAnalysisResult):
        """Extract cost and scan info from EXPLAIN output."""
        if not explain_text:
            return
        for line in explain_text.splitlines():
            if "Seq Scan" in line:
                table = self._extract_table(line)
                result.full_table_scans.append(table)
                result.suggestions.append(f"Sequential scan detected on '{table}' — consider adding an index")
            if "cost=" in line and result.estimated_cost is None:
                try:
                    cost_part = line.split("cost=")[1].split("..")[1]
                    result.estimated_cost = float(cost_part.split(" ")[0])
                except (IndexError, ValueError):
                    pass
            if "actual time=" in line and result.execution_time_ms is None:
                try:
                    time_part = line.split("actual time=")[1].split("..")[1]
                    result.execution_time_ms = float(time_part.split(".")[0])
                except (IndexError, ValueError):
                    pass

    @staticmethod
    def _extract_table(line: str) -> str:
        """Best-effort extraction of a table name from an EXPLAIN line."""
        for token in line.split():
            if token.startswith("core_") or token.startswith("tenants_"):
                return token
        return "unknown"

    @staticmethod
    def _check_missing_indexes(model, query_obj, result: QueryAnalysisResult):
        """Check whether filter/order columns have supporting indexes."""
        if connection.vendor != "postgresql":
            return
        existing = set()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT indexname FROM pg_indexes WHERE tablename = %s",
                [model._meta.db_table],
            )
            existing = {r[0] for r in cursor.fetchall()}

        # Simplified: check where clause columns
        try:
            where_cols = [c.lstrip("-") for c in getattr(query_obj, "_where_cols", [])]
            for col in where_cols:
                idx_name = f"idx_{model._meta.db_table}_{col}"
                if idx_name not in existing:
                    result.missing_indexes.append(col)
                    result.suggestions.append(f"Consider adding an index on {model.__name__}.{col}")
        except Exception:
            pass
