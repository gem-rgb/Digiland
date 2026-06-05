"""
Management command: db_health_check

Comprehensive database health check covering replication status,
connection pool, slow queries, index usage, table bloat, and
vacuum status.

Usage:
    python manage.py db_health_check
    python manage.py db_health_check --verbose
    python manage.py db_health_check --check replication,indexes
    python manage.py db_health_check --json
"""
import json
import logging
from typing import Dict, Any, List

from django.core.management.base import BaseCommand
from django.db import connection

logger = logging.getLogger(__name__)

AVAILABLE_CHECKS = [
    "replication", "connections", "slow_queries",
    "indexes", "bloat", "vacuum", "rls",
]


class Command(BaseCommand):
    help = "Run a comprehensive database health check."

    def add_arguments(self, parser):
        parser.add_argument(
            "--check",
            type=str,
            default=None,
            help=(
                f"Comma-separated list of checks to run. "
                f"Available: {', '.join(AVAILABLE_CHECKS)}"
            ),
        )
        parser.add_argument(
            "--verbose",
            action="store_true",
            default=False,
            help="Show detailed output for each check",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            default=False,
            dest="json_output",
            help="Output results as JSON",
        )
        parser.add_argument(
            "--warning-threshold",
            type=int,
            default=80,
            help="Percentage threshold for connection-usage warnings (default: 80)",
        )

    def handle(self, *args, **options):
        checks = self._resolve_checks(options.get("check"))
        results: Dict[str, Any] = {"database_vendor": connection.vendor, "checks": {}}
        issues_count = 0

        if connection.vendor != "postgresql":
            self.stdout.write(self.style.WARNING(
                f"Full health checks require PostgreSQL. Current: {connection.vendor}"
            ))
            results["limited_mode"] = True

        for check_name in checks:
            handler = getattr(self, f"_check_{check_name}", None)
            if handler is None:
                self.stdout.write(self.style.WARNING(f"Unknown check: {check_name}"))
                continue

            if options["verbose"]:
                self.stdout.write(f"\n{'='*60}")
                self.stdout.write(f"  Running: {check_name}")
                self.stdout.write(f"{'='*60}")

            result = handler(options)
            results["checks"][check_name] = result
            issues_count += len(result.get("issues", []))

            if options["verbose"]:
                self._print_check_result(check_name, result)
            else:
                status_icon = "✅" if result.get("status") == "healthy" else "⚠️" if result.get("issues") else "✅"
                self.stdout.write(f"  {status_icon} {check_name}: {result.get('status', 'unknown')}")

        # ── Summary ───────────────────────────────────────────
        if options["json_output"]:
            self.stdout.write(json.dumps(results, indent=2, default=str))
            return

        self.stdout.write(f"\n{'='*60}")
        if issues_count == 0:
            self.stdout.write(self.style.SUCCESS(
                f"  Database health: ALL CHECKS PASSED ({len(checks)} checks)"
            ))
        else:
            self.stdout.write(self.style.WARNING(
                f"  Database health: {issues_count} issue(s) found across {len(checks)} checks"
            ))
        self.stdout.write(f"{'='*60}")

    # ── Check implementations ─────────────────────────────────

    def _check_replication(self, options) -> Dict[str, Any]:
        """Check replication status and lag."""
        result: Dict[str, Any] = {"status": "healthy", "issues": []}
        if connection.vendor != "postgresql":
            result["status"] = "skipped"
            result["note"] = "PostgreSQL-only"
            return result

        from core.db.ha_config import HighAvailabilityManager
        ha = HighAvailabilityManager()
        lag_info = ha.check_replication_lag()
        result["details"] = lag_info

        if lag_info.get("status") == "primary":
            replicas = lag_info.get("replicas", [])
            result["replica_count"] = len(replicas)
            for r in replicas:
                lag_bytes = r.get("lag_bytes", 0)
                if lag_bytes and lag_bytes > 10_000_000:  # > 10MB
                    result["issues"].append(
                        f"Replica {r['host']} lag: {lag_bytes:,} bytes"
                    )
            if not replicas:
                result["issues"].append("No replicas configured — no HA redundancy")
        elif lag_info.get("lag_seconds", 0) > 60:
            result["issues"].append(
                f"Replication lag: {lag_info['lag_seconds']:.1f}s (> 60s threshold)"
            )

        if result["issues"]:
            result["status"] = "warning"
        return result

    def _check_connections(self, options) -> Dict[str, Any]:
        """Check connection pool and usage."""
        result: Dict[str, Any] = {"status": "healthy", "issues": []}
        if connection.vendor != "postgresql":
            result["status"] = "skipped"
            return result

        threshold = options.get("warning_threshold", 80)
        with connection.cursor() as cursor:
            cursor.execute("SELECT count(*) FROM pg_stat_activity")
            active = cursor.fetchone()[0]
            cursor.execute("SHOW max_connections")
            max_conn = int(cursor.fetchone()[0])
            usage_pct = round(active / max_conn * 100, 1) if max_conn else 0

            result["active_connections"] = active
            result["max_connections"] = max_conn
            result["usage_percent"] = usage_pct

            # Breakdown by state
            cursor.execute(
                "SELECT state, count(*) FROM pg_stat_activity GROUP BY state"
            )
            result["by_state"] = {row[0]: row[1] for row in cursor.fetchall()}

            if usage_pct > threshold:
                result["issues"].append(
                    f"Connection usage {usage_pct}% exceeds {threshold}% threshold"
                )
                result["status"] = "warning"

            # Idle-in-transaction connections
            cursor.execute(
                "SELECT count(*) FROM pg_stat_activity "
                "WHERE state = 'idle in transaction' AND query_start < now() - interval '5 minutes'"
            )
            idle_xact = cursor.fetchone()[0]
            if idle_xact > 0:
                result["issues"].append(
                    f"{idle_xact} connections idle in transaction > 5min"
                )
                result["status"] = "warning"

        return result

    def _check_slow_queries(self, options) -> Dict[str, Any]:
        """Check for slow queries."""
        result: Dict[str, Any] = {"status": "healthy", "issues": []}
        try:
            from core.db.query_optimizer import QueryOptimizer
            optimizer = QueryOptimizer()
            stats = optimizer.get_query_stats()
            result["total_slow_queries"] = stats.get("total_slow_queries", 0)
            result["avg_execution_time_ms"] = stats.get("avg_execution_time_ms", 0)

            if stats.get("total_slow_queries", 0) > 100:
                result["issues"].append(
                    f"High slow-query count: {stats['total_slow_queries']}"
                )
                result["status"] = "warning"
        except Exception as exc:
            result["status"] = "error"
            result["issues"].append(f"Could not query slow query log: {exc}")
        return result

    def _check_indexes(self, options) -> Dict[str, Any]:
        """Check index usage and find unused/duplicate indexes."""
        result: Dict[str, Any] = {"status": "healthy", "issues": [],
                                   "unused_indexes": [], "duplicate_indexes": []}
        if connection.vendor != "postgresql":
            result["status"] = "skipped"
            return result

        with connection.cursor() as cursor:
            # Unused indexes
            cursor.execute(
                """
                SELECT schemaname, relname, indexrelname, idx_scan
                FROM pg_stat_user_indexes
                WHERE idx_scan = 0 AND schemaname = 'public'
                ORDER BY pg_relation_size(indexrelid) DESC
                LIMIT 20
                """
            )
            unused = cursor.fetchall()
            result["unused_indexes"] = [
                {"table": r[1], "index": r[2], "scans": r[3]} for r in unused
            ]
            if len(unused) > 10:
                result["issues"].append(
                    f"{len(unused)} unused indexes found (wasting disk & write bandwidth)"
                )
                result["status"] = "warning"

            # Duplicate indexes
            cursor.execute(
                """
                SELECT pg_get_indexdef(idx1.oid), pg_get_indexdef(idx2.oid),
                       idx1.indexrelid::regclass, idx2.indexrelid::regclass
                FROM pg_index idx1
                JOIN pg_index idx2 ON idx1.indrelid = idx2.indrelid
                    AND idx1.indexrelid < idx2.indexrelid
                    AND idx1.indkey = idx2.indkey
                LIMIT 10
                """
            )
            dups = cursor.fetchall()
            result["duplicate_indexes"] = [
                {"index1": str(r[2]), "index2": str(r[3])} for r in dups
            ]
            if dups:
                result["issues"].append(
                    f"{len(dups)} duplicate index pair(s) found"
                )

        return result

    def _check_bloat(self, options) -> Dict[str, Any]:
        """Check table and index bloat."""
        result: Dict[str, Any] = {"status": "healthy", "issues": [],
                                   "bloated_tables": []}
        if connection.vendor != "postgresql":
            result["status"] = "skipped"
            return result

        with connection.cursor() as cursor:
            # Simplified bloat estimate using dead tuples
            cursor.execute(
                """
                SELECT relname, n_dead_tup, n_live_tup,
                       CASE WHEN n_live_tup > 0
                            THEN round(100.0 * n_dead_tup / n_live_tup, 2)
                            ELSE 0 END AS bloat_pct
                FROM pg_stat_user_tables
                WHERE n_dead_tup > 1000
                ORDER BY n_dead_tup DESC
                LIMIT 20
                """
            )
            bloated = cursor.fetchall()
            result["bloated_tables"] = [
                {"table": r[0], "dead_tuples": r[1], "live_tuples": r[2], "bloat_pct": r[3]}
                for r in bloated
            ]
            severely_bloated = [t for t in result["bloated_tables"] if t["bloat_pct"] > 50]
            if severely_bloated:
                result["issues"].append(
                    f"{len(severely_bloated)} table(s) with >50% bloat — VACUUM recommended"
                )
                result["status"] = "warning"
        return result

    def _check_vacuum(self, options) -> Dict[str, Any]:
        """Check vacuum and autovacuum status."""
        result: Dict[str, Any] = {"status": "healthy", "issues": []}
        if connection.vendor != "postgresql":
            result["status"] = "skipped"
            return result

        with connection.cursor() as cursor:
            cursor.execute("SHOW autovacuum")
            autovacuum = cursor.fetchone()[0]
            result["autovacuum_enabled"] = autovacuum == "on"

            if autovacuum != "on":
                result["issues"].append("Autovacuum is DISABLED — this can cause bloat and performance issues")
                result["status"] = "warning"

            # Last vacuum times
            cursor.execute(
                """
                SELECT relname, last_vacuum, last_autovacuum, last_analyze, last_autoanalyze
                FROM pg_stat_user_tables
                WHERE last_autovacuum IS NOT NULL OR last_vacuum IS NOT NULL
                ORDER BY GREATEST(last_vacuum, last_autovacuum) DESC NULLS LAST
                LIMIT 10
                """
            )
            result["recent_vacuums"] = [
                {"table": r[0], "last_vacuum": str(r[1]), "last_autovacuum": str(r[2]),
                 "last_analyze": str(r[3]), "last_autoanalyze": str(r[4])}
                for r in cursor.fetchall()
            ]

            # Tables never vacuumed
            cursor.execute(
                """
                SELECT count(*) FROM pg_stat_user_tables
                WHERE last_vacuum IS NULL AND last_autovacuum IS NULL
                """
            )
            never_vacuumed = cursor.fetchone()[0]
            if never_vacuumed > 0:
                result["issues"].append(f"{never_vacuumed} table(s) have never been vacuumed")
        return result

    def _check_rls(self, options) -> Dict[str, Any]:
        """Check Row-Level Security policies."""
        result: Dict[str, Any] = {"status": "healthy", "issues": []}
        if connection.vendor != "postgresql":
            result["status"] = "skipped"
            return result

        import importlib
        rls_migration = importlib.import_module("core.migrations.0028_enable_rls")
        TENANT_SCOPED_TABLES = rls_migration.TENANT_SCOPED_TABLES

        with connection.cursor() as cursor:
            tables_without_rls = []
            for table in TENANT_SCOPED_TABLES:
                cursor.execute(
                    "SELECT relrowsecurity FROM pg_class WHERE relname = %s",
                    [table],
                )
                row = cursor.fetchone()
                if not row or not row[0]:
                    tables_without_rls.append(table)

            if tables_without_rls:
                result["issues"].append(
                    f"RLS not enabled on {len(tables_without_rls)} table(s): "
                    f"{', '.join(tables_without_rls[:5])}"
                )
                result["status"] = "warning"
            result["tables_without_rls"] = tables_without_rls
        return result

    # ── Helpers ───────────────────────────────────────────────

    @staticmethod
    def _resolve_checks(check_arg):
        if check_arg:
            requested = [c.strip() for c in check_arg.split(",")]
            return [c for c in requested if c in AVAILABLE_CHECKS]
        return AVAILABLE_CHECKS

    def _print_check_result(self, name: str, result: Dict[str, Any]):
        """Print detailed check output."""
        status = result.get("status", "unknown")
        if status == "healthy":
            self.stdout.write(self.style.SUCCESS(f"  Status: {status}"))
        else:
            self.stdout.write(self.style.WARNING(f"  Status: {status}"))

        for key, value in result.items():
            if key in ("status", "issues"):
                continue
            if isinstance(value, (dict, list)):
                self.stdout.write(f"  {key}: {json.dumps(value, indent=4, default=str)[:500]}")
            else:
                self.stdout.write(f"  {key}: {value}")

        for issue in result.get("issues", []):
            self.stdout.write(self.style.WARNING(f"  ⚠️  {issue}"))
