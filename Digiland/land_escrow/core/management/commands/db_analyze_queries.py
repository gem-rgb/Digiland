"""
Management command: db_analyze_queries

Analyze query performance: detect slow queries, N+1 problems,
missing indexes, and run EXPLAIN ANALYZE on query plans.

Usage:
    python manage.py db_analyze_queries
    python manage.py db_analyze_queries --model core.Transaction
    python manage.py db_analyze_queries --slow-queries --limit 50
    python manage.py db_analyze_queries --detect-n1
    python manage.py db_analyze_queries --explain --model core.LandParcel
    python manage.py db_analyze_queries --missing-indexes
"""
import logging
from typing import Dict, Any, List

from django.core.management.base import BaseCommand, CommandError
from django.db import connection
from django.apps import apps

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Analyze query performance: slow queries, N+1 detection, "
        "missing indexes, and EXPLAIN ANALYZE."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--model",
            type=str,
            default=None,
            help="Model to analyze (e.g., core.Transaction)",
        )
        parser.add_argument(
            "--slow-queries",
            action="store_true",
            default=False,
            help="Show slow query log entries from pg_stat_statements",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=20,
            help="Number of slow queries to show (default: 20)",
        )
        parser.add_argument(
            "--detect-n1",
            action="store_true",
            default=False,
            help="Detect N+1 query patterns across all models",
        )
        parser.add_argument(
            "--explain",
            action="store_true",
            default=False,
            help="Run EXPLAIN ANALYZE on the model's default queryset",
        )
        parser.add_argument(
            "--missing-indexes",
            action="store_true",
            default=False,
            help="Find columns used in queries without supporting indexes",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            default=False,
            dest="run_all",
            help="Run all analyses",
        )
        parser.add_argument(
            "--min-duration-ms",
            type=float,
            default=100.0,
            help="Minimum duration (ms) for a query to be considered slow (default: 100)",
        )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write(self.style.WARNING(
                f"Full analysis requires PostgreSQL. Current: {connection.vendor}. "
                f"Some checks will be skipped."
            ))

        # Default to all analyses if none specified
        if not any([
            options["slow_queries"], options["detect_n1"],
            options["explain"], options["missing_indexes"],
            options["run_all"],
        ]):
            options["run_all"] = True

        if options["run_all"]:
            options["slow_queries"] = True
            options["detect_n1"] = True
            options["missing_indexes"] = True

        results: Dict[str, Any] = {}

        if options["slow_queries"]:
            results["slow_queries"] = self._analyze_slow_queries(options)

        if options["detect_n1"]:
            results["n_plus_one"] = self._detect_n_plus_one(options)

        if options["explain"]:
            results["explain"] = self._run_explain(options)

        if options["missing_indexes"]:
            results["missing_indexes"] = self._find_missing_indexes(options)

        # ── Summary ───────────────────────────────────────────
        self.stdout.write(f"\n{'='*60}")
        self.stdout.write(self.style.SUCCESS("Query analysis complete."))
        total_issues = sum(len(r.get("issues", [])) for r in results.values())
        if total_issues:
            self.stdout.write(self.style.WARNING(
                f"  {total_issues} issue(s) found across {len(results)} analyses"
            ))
        else:
            self.stdout.write(self.style.SUCCESS("  No issues found."))
        self.stdout.write(f"{'='*60}")

    # ── Slow queries ──────────────────────────────────────────

    def _analyze_slow_queries(self, options) -> Dict[str, Any]:
        """Retrieve and display slow queries."""
        result: Dict[str, Any] = {"status": "healthy", "issues": [], "queries": []}
        limit = options.get("limit", 20)

        self.stdout.write("\n📊 Slow Query Analysis")
        self.stdout.write("-" * 50)

        # Try pg_stat_statements first
        if connection.vendor == "postgresql":
            pg_stat_available = self._check_pg_stat_statements()
            if pg_stat_available:
                queries = self._get_pg_stat_statements(limit)
                result["queries"] = queries

                for q in queries[:5]:
                    self.stdout.write(
                        f"  Query: {q.get('query', '')[:80]}…"
                    )
                    self.stdout.write(
                        f"    Mean time: {q.get('mean_exec_time_ms', 0):.1f}ms | "
                        f"Calls: {q.get('calls', 0)} | "
                        f"Total time: {q.get('total_exec_time_ms', 0):.0f}ms"
                    )

                if queries:
                    slow_count = len([
                        q for q in queries
                        if q.get("mean_exec_time_ms", 0) > options.get("min_duration_ms", 100)
                    ])
                    if slow_count:
                        result["issues"].append(f"{slow_count} queries exceed {options.get('min_duration_ms', 100)}ms threshold")
                        result["status"] = "warning"
            else:
                self.stdout.write(self.style.WARNING(
                    "  pg_stat_statements extension not available. "
                    "Enable with: CREATE EXTENSION pg_stat_statements;"
                ))

        # Also check our SlowQueryLog model
        try:
            from core.db.query_optimizer import QueryOptimizer
            optimizer = QueryOptimizer()
            slow_entries = optimizer.get_slow_queries(limit=limit)
            if slow_entries:
                self.stdout.write(f"\n  SlowQueryLog entries: {len(slow_entries)}")
                for entry in slow_entries[:5]:
                    self.stdout.write(
                        f"    {entry.execution_time_ms:.1f}ms — "
                        f"{entry.query_sql[:60]}…"
                    )
        except Exception:
            pass

        return result

    # ── N+1 detection ─────────────────────────────────────────

    def _detect_n_plus_one(self, options) -> Dict[str, Any]:
        """Detect N+1 query patterns across models."""
        result: Dict[str, Any] = {"status": "healthy", "issues": [], "models": []}

        self.stdout.write("\n🔍 N+1 Query Detection")
        self.stdout.write("-" * 50)

        from core.db.query_optimizer import QueryOptimizer
        optimizer = QueryOptimizer()

        models_to_check = self._get_models(options.get("model"))
        total_n_plus_one = 0

        for model in models_to_check:
            try:
                qs = model.objects.all()[:1]  # Small queryset for analysis
                analysis = optimizer.analyze_query(qs)

                model_info = {
                    "model": model.__name__,
                    "has_n_plus_one": analysis.has_n_plus_one,
                    "relations": analysis.n_plus_one_relations,
                    "suggestions": analysis.suggestions[:3],
                }
                result["models"].append(model_info)

                if analysis.has_n_plus_one:
                    total_n_plus_one += len(analysis.n_plus_one_relations)
                    self.stdout.write(self.style.WARNING(
                        f"  ⚠️  {model.__name__}: {len(analysis.n_plus_one_relations)} "
                        f"N+1 relation(s): {', '.join(analysis.n_plus_one_relations)}"
                    ))
                    for sug in analysis.suggestions[:2]:
                        self.stdout.write(f"      → {sug}")
                else:
                    self.stdout.write(f"  ✅ {model.__name__}: No N+1 issues")

            except Exception as exc:
                logger.debug("N+1 check failed for %s: %s", model.__name__, exc)

        if total_n_plus_one:
            result["status"] = "warning"
            result["issues"].append(f"Found {total_n_plus_one} potential N+1 relation(s) across models")
        return result

    # ── EXPLAIN ANALYZE ───────────────────────────────────────

    def _run_explain(self, options) -> Dict[str, Any]:
        """Run EXPLAIN ANALYZE on a model's queryset."""
        result: Dict[str, Any] = {"status": "healthy", "issues": []}

        model_label = options.get("model")
        if not model_label:
            return {"status": "error", "issues": ["--model is required for --explain"]}

        model = self._resolve_model(model_label)
        if not model:
            raise CommandError(f"Model not found: {model_label}")

        self.stdout.write(f"\n🧪 EXPLAIN ANALYZE: {model.__name__}")
        self.stdout.write("-" * 50)

        from core.db.query_optimizer import QueryOptimizer
        optimizer = QueryOptimizer()

        qs = model.objects.all()[:100]
        explain = optimizer.explain_query(qs)

        if explain:
            self.stdout.write(explain[:2000])
            result["explain_output"] = explain[:2000]

            # Check for sequential scans
            if "Seq Scan" in explain:
                result["issues"].append("Sequential scan detected — consider adding an index")
                result["status"] = "warning"

            # Extract execution time
            for line in explain.splitlines():
                if "Execution Time" in line:
                    self.stdout.write(self.style.SUCCESS(f"  {line.strip()}"))
        else:
            self.stdout.write("  EXPLAIN ANALYZE not available (PostgreSQL-only)")
            result["status"] = "skipped"

        return result

    # ── Missing indexes ───────────────────────────────────────

    def _find_missing_indexes(self, options) -> Dict[str, Any]:
        """Find columns used in queries without supporting indexes."""
        result: Dict[str, Any] = {"status": "healthy", "issues": [], "suggestions": []}

        self.stdout.write("\n📇 Missing Index Analysis")
        self.stdout.write("-" * 50)

        if connection.vendor != "postgresql":
            self.stdout.write("  Skipped — PostgreSQL-only feature")
            result["status"] = "skipped"
            return result

        from core.db.query_optimizer import QueryOptimizer
        optimizer = QueryOptimizer()

        models_to_check = self._get_models(options.get("model"))
        all_suggestions = []

        for model in models_to_check:
            try:
                suggestions = optimizer.suggest_indexes(model)
                all_suggestions.extend(suggestions)
            except Exception as exc:
                logger.debug("Index suggestion failed for %s: %s", model.__name__, exc)

        if all_suggestions:
            self.stdout.write(f"  Found {len(all_suggestions)} index suggestion(s):")
            for sug in all_suggestions[:10]:
                self.stdout.write(
                    f"    📌 {sug.table_name}.{', '.join(sug.columns)} "
                    f"({sug.index_type}) — {sug.reason}"
                )
                if sug.create_sql:
                    self.stdout.write(f"       {sug.create_sql}")
                all_suggestions_dict = {
                    "table": sug.table_name, "columns": sug.columns,
                    "type": sug.index_type, "impact": sug.estimated_impact,
                    "sql": sug.create_sql,
                }
                result["suggestions"].append(all_suggestions_dict)

            result["issues"].append(f"{len(all_suggestions)} missing index(es) detected")
            result["status"] = "warning"
        else:
            self.stdout.write("  ✅ No missing indexes detected")

        return result

    # ── Private helpers ───────────────────────────────────────

    @staticmethod
    def _check_pg_stat_statements() -> bool:
        """Check if pg_stat_statements extension is available."""
        if connection.vendor != "postgresql":
            return False
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pg_stat_statements')"
                )
                return cursor.fetchone()[0]
        except Exception:
            return False

    @staticmethod
    def _get_pg_stat_statements(limit: int) -> List[Dict[str, Any]]:
        """Get slow queries from pg_stat_statements."""
        try:
            with connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT query, calls, total_exec_time, mean_exec_time,
                           min_exec_time, max_exec_time, rows
                    FROM pg_stat_statements
                    ORDER BY mean_exec_time DESC
                    LIMIT %s
                    """,
                    [limit],
                )
                return [
                    {
                        "query": row[0][:200],
                        "calls": row[1],
                        "total_exec_time_ms": round(row[2], 2),
                        "mean_exec_time_ms": round(row[3], 2),
                        "min_exec_time_ms": round(row[4], 2),
                        "max_exec_time_ms": round(row[5], 2),
                        "rows": row[6],
                    }
                    for row in cursor.fetchall()
                ]
        except Exception:
            return []

    @staticmethod
    def _get_models(model_label=None):
        """Get list of Django models to analyze."""
        if model_label:
            model = Command._resolve_model(model_label)
            return [model] if model else []
        return [m for m in apps.get_models() if m._meta.app_label == "core"]

    @staticmethod
    def _resolve_model(label: str):
        """Resolve 'app.Model' string to a model class."""
        try:
            app_label, model_name = label.split(".")
            return apps.get_model(app_label, model_name)
        except (ValueError, LookupError):
            return None
