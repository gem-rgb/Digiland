"""
Management command: db_optimize

Run database optimization tasks including VACUUM, ANALYZE, REINDEX,
index suggestions, and dead-tuple cleanup.

Usage:
    python manage.py db_optimize
    python manage.py db_optimize --vacuum --analyze
    python manage.py db_optimize --reindex --table core_landparcel
    python manage.py db_optimize --suggest-indexes
    python manage.py db_optimize --clean-dead-tuples --min-dead 1000
"""
import logging
from typing import Dict, Any, List

from django.core.management.base import BaseCommand
from django.db import connection

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Run database optimization tasks: VACUUM, ANALYZE, REINDEX, "
        "suggest indexes, and clean dead tuples."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--vacuum",
            action="store_true",
            default=False,
            help="Run VACUUM on all user tables",
        )
        parser.add_argument(
            "--vacuum-full",
            action="store_true",
            default=False,
            help="Run VACUUM FULL (reclaims all space, locks tables)",
        )
        parser.add_argument(
            "--analyze",
            action="store_true",
            default=False,
            help="Run ANALYZE to update statistics",
        )
        parser.add_argument(
            "--reindex",
            action="store_true",
            default=False,
            help="Rebuild all indexes (REINDEX DATABASE)",
        )
        parser.add_argument(
            "--table",
            type=str,
            default=None,
            help="Limit VACUUM/ANALYZE/REINDEX to a specific table",
        )
        parser.add_argument(
            "--suggest-indexes",
            action="store_true",
            default=False,
            help="Analyze query patterns and suggest new indexes",
        )
        parser.add_argument(
            "--clean-dead-tuples",
            action="store_true",
            default=False,
            help="VACUUM tables with high dead-tuple counts",
        )
        parser.add_argument(
            "--min-dead",
            type=int,
            default=5000,
            help="Minimum dead tuples threshold for --clean-dead-tuples (default: 5000)",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Show what would be done without executing",
        )
        parser.add_argument(
            "--all",
            action="store_true",
            default=False,
            dest="run_all",
            help="Run vacuum, analyze, clean-dead-tuples, and suggest-indexes",
        )

    def handle(self, *args, **options):
        if connection.vendor != "postgresql":
            self.stdout.write(self.style.WARNING(
                f"Most optimizations require PostgreSQL. Current: {connection.vendor}. "
                f"Running limited optimizations."
            ))

        # If no specific option chosen and not --all, run a safe default set
        if not any([
            options["vacuum"], options["vacuum_full"], options["analyze"],
            options["reindex"], options["suggest_indexes"],
            options["clean_dead_tuples"], options["run_all"],
        ]):
            options["run_all"] = True

        if options["run_all"]:
            options["vacuum"] = True
            options["analyze"] = True
            options["clean_dead_tuples"] = True
            options["suggest_indexes"] = True

        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY RUN — no changes will be made\n"))

        results: Dict[str, Any] = {}

        if options["vacuum"] or options["vacuum_full"]:
            results["vacuum"] = self._run_vacuum(options)

        if options["analyze"]:
            results["analyze"] = self._run_analyze(options)

        if options["reindex"]:
            results["reindex"] = self._run_reindex(options)

        if options["clean_dead_tuples"]:
            results["dead_tuples"] = self._clean_dead_tuples(options)

        if options["suggest_indexes"]:
            results["index_suggestions"] = self._suggest_indexes(options)

        # ── Summary ───────────────────────────────────────────
        self.stdout.write(f"\n{'='*50}")
        self.stdout.write(self.style.SUCCESS("Optimization complete."))
        for task, result in results.items():
            status = result.get("status", "unknown")
            icon = "✅" if status == "success" else "⚠️" if status == "warning" else "❌"
            self.stdout.write(f"  {icon} {task}: {status}")

    # ── VACUUM ────────────────────────────────────────────────

    def _run_vacuum(self, options) -> Dict[str, Any]:
        """Run VACUUM or VACUUM FULL on tables."""
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": "PostgreSQL-only"}

        tables = self._get_tables(options.get("table"))
        vacuum_type = "VACUUM FULL" if options["vacuum_full"] else "VACUUM"

        if options["vacuum_full"]:
            self.stdout.write(self.style.WARNING(
                "  VACUUM FULL will lock tables — this may cause downtime!"
            ))

        results_by_table = {}
        for table in tables:
            sql = f"{vacuum_type} {table}"
            if options["dry_run"]:
                self.stdout.write(f"  [DRY RUN] {sql}")
                results_by_table[table] = "dry_run"
                continue

            try:
                self.stdout.write(f"  Running: {sql}")
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                results_by_table[table] = "ok"
                self.stdout.write(self.style.SUCCESS(f"    ✅ {table}"))
            except Exception as exc:
                results_by_table[table] = f"error: {exc}"
                self.stdout.write(self.style.ERROR(f"    ❌ {table}: {exc}"))

        return {"status": "success", "tables": results_by_table}

    # ── ANALYZE ───────────────────────────────────────────────

    def _run_analyze(self, options) -> Dict[str, Any]:
        """Run ANALYZE to update planner statistics."""
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": "PostgreSQL-only"}

        tables = self._get_tables(options.get("table"))
        results_by_table = {}

        for table in tables:
            sql = f"ANALYZE {table}"
            if options["dry_run"]:
                self.stdout.write(f"  [DRY RUN] {sql}")
                results_by_table[table] = "dry_run"
                continue

            try:
                self.stdout.write(f"  Running: {sql}")
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                results_by_table[table] = "ok"
                self.stdout.write(self.style.SUCCESS(f"    ✅ {table}"))
            except Exception as exc:
                results_by_table[table] = f"error: {exc}"
                self.stdout.write(self.style.ERROR(f"    ❌ {table}: {exc}"))

        return {"status": "success", "tables": results_by_table}

    # ── REINDEX ───────────────────────────────────────────────

    def _run_reindex(self, options) -> Dict[str, Any]:
        """Rebuild indexes to eliminate bloat."""
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": "PostgreSQL-only"}

        if options["dry_run"]:
            target = options.get("table") or "entire database"
            self.stdout.write(f"  [DRY RUN] REINDEX on {target}")
            return {"status": "dry_run"}

        self.stdout.write(self.style.WARNING(
            "  REINDEX will lock tables — consider REINDEX CONCURRENTLY on PG 12+"
        ))

        try:
            if options.get("table"):
                sql = f"REINDEX TABLE {options['table']}"
            else:
                db_name = connection.settings_dict.get("NAME", "digiland")
                sql = f"REINDEX DATABASE {db_name}"

            self.stdout.write(f"  Running: {sql}")
            with connection.cursor() as cursor:
                cursor.execute(sql)
            return {"status": "success", "command": sql}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    # ── Dead tuple cleanup ────────────────────────────────────

    def _clean_dead_tuples(self, options) -> Dict[str, Any]:
        """VACUUM tables with high dead-tuple counts."""
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": "PostgreSQL-only"}

        min_dead = options.get("min_dead", 5000)
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT relname, n_dead_tup, n_live_tup
                FROM pg_stat_user_tables
                WHERE n_dead_tup > %s
                ORDER BY n_dead_tup DESC
                """,
                [min_dead],
            )
            bloated = cursor.fetchall()

        if not bloated:
            self.stdout.write("  No tables with significant dead tuples found.")
            return {"status": "success", "tables_cleaned": 0}

        self.stdout.write(f"  Found {len(bloated)} table(s) with > {min_dead} dead tuples:")
        for table, dead, live in bloated:
            pct = round(100 * dead / live, 1) if live else 0
            self.stdout.write(f"    {table}: {dead:,} dead / {live:,} live ({pct}%)")

        cleaned = 0
        for table, dead, live in bloated:
            sql = f"VACUUM {table}"
            if options["dry_run"]:
                self.stdout.write(f"  [DRY RUN] {sql}")
                continue
            try:
                with connection.cursor() as cursor:
                    cursor.execute(sql)
                cleaned += 1
                self.stdout.write(self.style.SUCCESS(f"    ✅ Vacuumed {table}"))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f"    ❌ Failed to vacuum {table}: {exc}"))

        return {"status": "success", "tables_cleaned": cleaned, "candidates": len(bloated)}

    # ── Index suggestions ─────────────────────────────────────

    def _suggest_indexes(self, options) -> Dict[str, Any]:
        """Analyze models and suggest missing indexes."""
        from core.db.query_optimizer import QueryOptimizer
        from django.apps import apps

        optimizer = QueryOptimizer()
        all_suggestions = []

        for model in apps.get_models():
            try:
                suggestions = optimizer.suggest_indexes(model)
                all_suggestions.extend(suggestions)
            except Exception as exc:
                logger.debug("Index suggestion failed for %s: %s", model.__name__, exc)

        if not all_suggestions:
            self.stdout.write("  No index suggestions — your schema looks good!")
            return {"status": "success", "suggestions": 0}

        self.stdout.write(f"\n  📊 {len(all_suggestions)} index suggestion(s):")
        self.stdout.write(f"  {'-'*50}")
        for sug in all_suggestions:
            self.stdout.write(f"    Table: {sug.table_name}")
            self.stdout.write(f"    Columns: {', '.join(sug.columns)}")
            self.stdout.write(f"    Impact: {sug.estimated_impact}")
            self.stdout.write(f"    Reason: {sug.reason}")
            if sug.create_sql:
                self.stdout.write(f"    SQL: {sug.create_sql}")
            self.stdout.write("")

        return {"status": "success", "suggestions": len(all_suggestions),
                "details": [{"table": s.table_name, "columns": s.columns,
                             "sql": s.create_sql, "impact": s.estimated_impact}
                            for s in all_suggestions]}

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _get_tables(specific_table=None) -> List[str]:
        """Get list of tables to operate on."""
        if specific_table:
            return [specific_table]
        with connection.cursor() as cursor:
            if connection.vendor == "postgresql":
                cursor.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
                )
            else:
                cursor.execute(
                    "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%%'"
                )
            return [r[0] for r in cursor.fetchall()]
