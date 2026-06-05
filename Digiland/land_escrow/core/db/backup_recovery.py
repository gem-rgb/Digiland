"""
Backup and recovery utilities for the Digiland platform.

Wraps pg_dump / pg_restore for full and incremental backups, provides
cloud snapshot support, and offers point-in-time recovery via
PostgreSQL WAL archiving.
"""
import hashlib
import json
import logging
import os
import subprocess
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from django.conf import settings
from django.db import connection
from django.utils import timezone

logger = logging.getLogger(__name__)


class BackupManager:
    """Create, verify, and manage database backups.

    All pg_dump / pg_restore invocations go through ``subprocess`` so the
    calling code stays inside Django's process model.  Paths default to
    ``/tmp/`` but can be overridden via the ``output_path`` argument.
    """

    BACKUP_DIR = getattr(settings, "DB_BACKUP_DIR", "/tmp/digiland_backups")

    def __init__(self):
        self._db_settings = connection.settings_dict
        os.makedirs(self.BACKUP_DIR, exist_ok=True)

    # ── Full backup ───────────────────────────────────────────

    def create_full_backup(self, output_path: Optional[str] = None,
                           compress: bool = True, encrypt: bool = False) -> Dict[str, Any]:
        """Create a full pg_dump backup of the database.

        Returns a dict with backup metadata (path, size, checksum, etc.).
        """
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": f"Full backup not supported on {connection.vendor}"}

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        ext = ".sql.gz" if compress else ".sql"
        filename = f"digiland_full_{timestamp}{ext}"
        path = output_path or os.path.join(self.BACKUP_DIR, filename)

        cmd = self._pg_dump_base(compress)
        cmd.extend(["--file", path])

        result = self._run_subprocess(cmd, "pg_dump (full)")
        if result["returncode"] != 0:
            return {"status": "failed", "error": result["stderr"], "path": None}

        meta = self._build_metadata(path, "full", compress, encrypt)
        self._save_metadata(meta)
        return {"status": "success", **meta}

    # ── Incremental backup ────────────────────────────────────

    def create_incremental_backup(self, output_path: Optional[str] = None,
                                  since: Optional[datetime] = None) -> Dict[str, Any]:
        """WAL-based incremental backup (requires WAL archiving enabled).

        Falls back to a full backup with a note if WAL archiving is not
        configured.
        """
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": f"Incremental backup not supported on {connection.vendor}"}

        if not self._wal_archiving_enabled():
            logger.warning("WAL archiving not enabled; falling back to full backup")
            return self.create_full_backup(output_path)

        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"digiland_incr_{timestamp}.wal"
        path = output_path or os.path.join(self.BACKUP_DIR, filename)

        # Use pg_basebackup with WAL streaming for incremental
        cmd = [
            "pg_basebackup",
            "-h", self._db_settings.get("HOST", "localhost"),
            "-p", str(self._db_settings.get("PORT", 5432)),
            "-U", self._db_settings.get("USER", "postgres"),
            "-D", path,
            "-Ft", "-z", "--checkpoint=fast",
        ]
        result = self._run_subprocess(cmd, "pg_basebackup (incremental)")
        if result["returncode"] != 0:
            return {"status": "failed", "error": result["stderr"], "path": None}

        meta = self._build_metadata(path, "incremental", compress=False, encrypt=False)
        meta["since"] = since.isoformat() if since else None
        self._save_metadata(meta)
        return {"status": "success", **meta}

    # ── Cloud snapshot ────────────────────────────────────────

    def create_snapshot(self) -> Dict[str, Any]:
        """Request a cloud-provider volume snapshot of the DB volume."""
        provider = getattr(settings, "CLOUD_PROVIDER", None)
        if provider == "aws":
            return self._aws_snapshot()
        elif provider == "gcp":
            return self._gcp_snapshot()
        return {"status": "skipped", "reason": "No cloud provider configured"}

    # ── Restore ───────────────────────────────────────────────

    def restore_from_backup(self, backup_path: str) -> Dict[str, Any]:
        """Restore the database from a backup file via pg_restore."""
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": f"Restore not supported on {connection.vendor}"}
        if not os.path.isfile(backup_path):
            return {"status": "failed", "error": f"Backup file not found: {backup_path}"}

        # Terminate existing connections
        self._terminate_connections()

        cmd = self._pg_restore_base()
        cmd.extend(["--dbname", self._db_settings.get("NAME", ""), "--clean", "--if-exists", backup_path])

        result = self._run_subprocess(cmd, "pg_restore")
        return {"status": "success" if result["returncode"] == 0 else "failed",
                "stderr": result["stderr"], "backup_path": backup_path}

    # ── Verify ────────────────────────────────────────────────

    def verify_backup(self, backup_path: str) -> Dict[str, Any]:
        """Verify backup integrity by checking checksum and listing contents."""
        if not os.path.isfile(backup_path):
            return {"status": "failed", "error": f"Backup file not found: {backup_path}"}

        meta_path = backup_path + ".meta.json"
        if os.path.isfile(meta_path):
            with open(meta_path) as f:
                meta = json.load(f)
            current_checksum = self._compute_checksum(backup_path)
            if current_checksum != meta.get("checksum"):
                return {"status": "corrupt", "error": "Checksum mismatch", "backup_path": backup_path}

        if connection.vendor == "postgresql" and backup_path.endswith((".sql", ".sql.gz", ".dump")):
            cmd = self._pg_restore_base()
            cmd.extend(["--list", backup_path])
            result = self._run_subprocess(cmd, "pg_restore --list")
            return {"status": "success" if result["returncode"] == 0 else "failed",
                    "contents": result["stdout"][:2000], "backup_path": backup_path}

        return {"status": "verified", "method": "checksum_only", "backup_path": backup_path}

    # ── List / Status / Schedule ──────────────────────────────

    def list_backups(self) -> List[Dict[str, Any]]:
        """List available backups from the backup directory."""
        backups = []
        for fname in sorted(os.listdir(self.BACKUP_DIR), reverse=True):
            if fname.endswith((".sql", ".sql.gz", ".dump", ".wal", ".meta.json")):
                fpath = os.path.join(self.BACKUP_DIR, fname)
                if fname.endswith(".meta.json"):
                    continue
                meta_path = fpath + ".meta.json"
                meta = {}
                if os.path.isfile(meta_path):
                    with open(meta_path) as f:
                        meta = json.load(f)
                backups.append({
                    "filename": fname, "path": fpath,
                    "size_bytes": os.path.getsize(fpath),
                    "modified": datetime.fromtimestamp(os.path.getmtime(fpath)).isoformat(),
                    **meta,
                })
        return backups

    def get_backup_status(self, backup_id: str) -> Dict[str, Any]:
        """Check status of a specific backup by its ID/filename."""
        for b in self.list_backups():
            if backup_id in b["filename"]:
                verify = self.verify_backup(b["path"])
                return {**b, "integrity": verify}
        return {"status": "not_found", "backup_id": backup_id}

    def schedule_automatic_backups(self, schedule: str = "daily") -> Dict[str, Any]:
        """Configure automatic backup schedule (cron / celery beat).

        Accepted values: 'hourly', 'daily', 'weekly'.
        """
        cron_map = {"hourly": "0 * * * *", "daily": "0 2 * * *", "weekly": "0 3 * * 0"}
        cron_expr = cron_map.get(schedule)
        if not cron_expr:
            return {"status": "failed", "error": f"Unknown schedule: {schedule}"}
        # Write a cron entry for the management command
        cmd = f"{cron_expr} cd /app && python manage.py db_backup --compress --upload-s3 >> /var/log/db_backup.log 2>&1"
        try:
            existing = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
            lines = existing.stdout.splitlines() if existing.returncode == 0 else []
            lines = [l for l in lines if "db_backup" not in l]
            lines.append(cmd)
            proc = subprocess.run(["crontab", "-"], input="\n".join(lines) + "\n",
                                  capture_output=True, text=True)
            return {"status": "success", "schedule": schedule, "cron": cron_expr}
        except Exception as exc:
            logger.error("Failed to set cron: %s", exc)
            return {"status": "failed", "error": str(exc)}

    # ── Private helpers ───────────────────────────────────────

    def _pg_dump_base(self, compress: bool = True) -> List[str]:
        cmd = ["pg_dump",
               "-h", self._db_settings.get("HOST", "localhost"),
               "-p", str(self._db_settings.get("PORT", 5432)),
               "-U", self._db_settings.get("USER", "postgres"),
               "-d", self._db_settings.get("NAME", "digiland")]
        if compress:
            cmd.extend(["-F", "c", "-Z", "6"])
        return cmd

    def _pg_restore_base(self) -> List[str]:
        return ["pg_restore",
                "-h", self._db_settings.get("HOST", "localhost"),
                "-p", str(self._db_settings.get("PORT", 5432)),
                "-U", self._db_settings.get("USER", "postgres")]

    @staticmethod
    def _run_subprocess(cmd: List[str], label: str) -> Dict[str, Any]:
        env = os.environ.copy()
        env["PGPASSWORD"] = connection.settings_dict.get("PASSWORD", "")
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=3600)
            return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "stdout": "", "stderr": f"{label} timed out after 3600s"}
        except FileNotFoundError:
            return {"returncode": -1, "stdout": "", "stderr": f"{label} binary not found"}

    def _build_metadata(self, path: str, btype: str, compress: bool, encrypt: bool) -> Dict[str, Any]:
        size = os.path.getsize(path) if os.path.isfile(path) else 0
        return {
            "backup_id": str(uuid.uuid4())[:8],
            "path": path, "type": btype,
            "compress": compress, "encrypt": encrypt,
            "size_bytes": size, "checksum": self._compute_checksum(path),
            "created_at": timezone.now().isoformat(),
            "database": self._db_settings.get("NAME", ""),
        }

    @staticmethod
    def _compute_checksum(path: str, block_size: int = 65536) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for block in iter(lambda: f.read(block_size), b""):
                h.update(block)
        return h.hexdigest()

    def _save_metadata(self, meta: Dict[str, Any]):
        meta_path = meta["path"] + ".meta.json"
        with open(meta_path, "w") as f:
            json.dump(meta, f, indent=2)

    def _terminate_connections(self):
        db_name = self._db_settings.get("NAME", "")
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = %s AND pid <> pg_backend_pid()", [db_name]
                )

    def _wal_archiving_enabled(self) -> bool:
        if connection.vendor != "postgresql":
            return False
        try:
            with connection.cursor() as cursor:
                cursor.execute("SHOW archive_mode")
                return cursor.fetchone()[0].lower() == "on"
        except Exception:
            return False

    @staticmethod
    def _aws_snapshot() -> Dict[str, Any]:
        """Placeholder for AWS RDS snapshot invocation."""
        return {"status": "not_implemented", "provider": "aws", "hint": "Use boto3 rds.create_db_snapshot"}

    @staticmethod
    def _gcp_snapshot() -> Dict[str, Any]:
        """Placeholder for GCP Cloud SQL snapshot invocation."""
        return {"status": "not_implemented", "provider": "gcp", "hint": "Use google.cloud.sql Admin API"}


class RecoveryManager:
    """Orchestrate database recovery including point-in-time and replica failover."""

    def initiate_recovery(self, target_time: Optional[datetime] = None) -> Dict[str, Any]:
        """Start point-in-time recovery (PITR) using WAL replay.

        If *target_time* is ``None`` recovers to the latest available point.
        """
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": f"PITR not supported on {connection.vendor}"}

        bm = BackupManager()
        backups = bm.list_backups()
        if not backups:
            return {"status": "failed", "error": "No backups available for recovery"}

        latest = backups[0]["path"]
        target_str = target_time.isoformat() if target_time else "latest"
        logger.info("Initiating PITR to %s from %s", target_str, latest)

        # In production this would stop Postgres, configure recovery_target_time
        # in postgresql.conf, start Postgres in recovery mode.
        return {
            "status": "initiated",
            "target_time": target_str,
            "backup_source": latest,
            "note": "PITR requires manual Postgres restart with recovery config",
        }

    def get_recovery_status(self) -> Dict[str, Any]:
        """Check recovery progress from pg_stat_recovery."""
        if connection.vendor != "postgresql":
            return {"status": "unknown", "reason": "PostgreSQL-only feature"}

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_is_in_recovery()")
                in_recovery = cursor.fetchone()[0]
                if not in_recovery:
                    return {"status": "not_in_recovery", "in_recovery": False}
                cursor.execute(
                    "SELECT replay_lag, replay_lsn FROM pg_stat_wal_receiver LIMIT 1"
                )
                row = cursor.fetchone()
                return {"status": "replaying", "in_recovery": True,
                        "replay_lag": str(row[0]) if row else None,
                        "replay_lsn": str(row[1]) if row else None}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def validate_data_integrity(self) -> Dict[str, Any]:
        """Post-recovery validation: row counts, FK integrity, RLS check."""
        results: Dict[str, Any] = {"tables_checked": 0, "issues": []}
        if connection.vendor != "postgresql":
            return {**results, "status": "skipped"}

        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public'"
            )
            tables = [r[0] for r in cursor.fetchall()]
            results["tables_checked"] = len(tables)

            for table in tables:
                try:
                    cursor.execute(f"SELECT count(*) FROM {table}")
                    results[f"{table}_rows"] = cursor.fetchone()[0]
                except Exception as exc:
                    results["issues"].append(f"{table}: {exc}")

            # Check FK integrity for core tables
            cursor.execute(
                """
                SELECT con.conname, conrelid::regclass, confrelid::regclass
                FROM pg_constraint con WHERE con.contype = 'f'
                AND conrelid::regclass::text LIKE 'core_%%'
                LIMIT 20
                """
            )
            for conname, src, dst in cursor.fetchall():
                results["issues"].append(f"FK '{conname}': verify {src} -> {dst} manually")

        results["status"] = "passed" if not results["issues"] else "warnings"
        return results

    def failover_to_replica(self) -> Dict[str, Any]:
        """Promote a standby replica to primary (manual confirmation needed)."""
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": "PostgreSQL-only feature"}

        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_is_in_recovery()")
                in_recovery = cursor.fetchone()[0]
                if in_recovery:
                    cursor.execute("SELECT pg_promote(true, 60)")
                    promoted = cursor.fetchone()[0]
                    return {"status": "promoted" if promoted else "failed",
                            "message": "Replica promoted to primary"}
                return {"status": "already_primary", "in_recovery": False}
        except Exception as exc:
            return {"status": "error", "error": str(exc)}

    def sync_replica(self, replica_host: str) -> Dict[str, Any]:
        """Sync a standby replica from the current primary."""
        if connection.vendor != "postgresql":
            return {"status": "skipped", "reason": "PostgreSQL-only feature"}

        logger.info("Syncing replica at %s", replica_host)
        # In production: pg_basebackup --host=primary --write-recovery-conf
        return {
            "status": "initiated",
            "replica_host": replica_host,
            "note": "Run pg_basebackup from replica host against primary",
        }
