"""
Management command: db_restore

Restore the database from a backup file with optional point-in-time
recovery and integrity verification.

Usage:
    python manage.py db_restore --backup-path /tmp/digiland_full_20260603.sql.gz
    python manage.py db_restore --backup-path /tmp/backup.sql.gz --target-time "2026-06-03 14:30:00"
    python manage.py db_restore --backup-path /tmp/backup.sql.gz --verify-only
"""
import logging

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Restore the database from a backup file. Supports point-in-time "
        "recovery and pre-restore integrity verification."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--backup-path",
            type=str,
            required=True,
            help="Path to the backup file to restore from",
        )
        parser.add_argument(
            "--target-time",
            type=str,
            default=None,
            help=(
                "Point-in-time recovery target (ISO 8601 format). "
                "Requires WAL archiving to be enabled."
            ),
        )
        parser.add_argument(
            "--verify-only",
            action="store_true",
            default=False,
            help="Verify the backup integrity without actually restoring",
        )
        parser.add_argument(
            "--skip-backup",
            action="store_true",
            default=False,
            help="Skip creating a pre-restore safety backup (NOT recommended)",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Force restore without confirmation prompt (use with caution)",
        )
        parser.add_argument(
            "--validate-after",
            action="store_true",
            default=False,
            help="Run data-integrity validation after restore completes",
        )

    def handle(self, *args, **options):
        from core.db.backup_recovery import BackupManager, RecoveryManager

        backup_path = options["backup_path"]
        bm = BackupManager()
        rm = RecoveryManager()

        # ── Verify only ───────────────────────────────────────
        if options["verify_only"]:
            self.stdout.write(f"Verifying backup: {backup_path}")
            result = bm.verify_backup(backup_path)
            if result.get("status") in ("success", "verified"):
                self.stdout.write(self.style.SUCCESS(
                    f"Backup integrity: {result['status']}"
                ))
                if result.get("contents"):
                    self.stdout.write(f"Contents preview:\n{result['contents'][:500]}")
            elif result.get("status") == "corrupt":
                raise CommandError("Backup is CORRUPT — checksum mismatch!")
            else:
                self.stdout.write(self.style.WARNING(
                    f"Verification result: {result.get('status')} — {result.get('error')}"
                ))
            return

        # ── Pre-flight checks ─────────────────────────────────
        import os
        if not os.path.isfile(backup_path):
            raise CommandError(f"Backup file not found: {backup_path}")

        # Verify backup before proceeding
        self.stdout.write("Verifying backup integrity before restore…")
        verify = bm.verify_backup(backup_path)
        if verify.get("status") == "corrupt":
            raise CommandError("Backup is corrupt — aborting restore")

        # ── Confirmation ──────────────────────────────────────
        if not options["force"]:
            self.stdout.write(self.style.WARNING(
                "\n  ⚠️  WARNING: This will OVERWRITE the current database!\n"
                f"  Backup: {backup_path}\n"
            ))
            confirm = input("Type 'yes' to proceed with restore: ")
            if confirm.strip().lower() != "yes":
                self.stdout.write("Restore cancelled.")
                return

        # ── Safety backup ─────────────────────────────────────
        if not options["skip_backup"]:
            self.stdout.write("Creating safety backup before restore…")
            safety = bm.create_full_backup()
            if safety.get("status") == "success":
                self.stdout.write(self.style.SUCCESS(
                    f"Safety backup: {safety.get('path')}"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Safety backup failed: {safety.get('error')} — continuing anyway"
                ))

        # ── Point-in-time recovery ────────────────────────────
        if options["target_time"]:
            self._pitr_restore(rm, options)
            return

        # ── Standard restore ──────────────────────────────────
        self.stdout.write(f"Restoring from: {backup_path}")
        result = bm.restore_from_backup(backup_path)

        if result.get("status") == "success":
            self.stdout.write(self.style.SUCCESS("Database restored successfully."))
        elif result.get("status") == "skipped":
            self.stdout.write(self.style.WARNING(
                f"Restore skipped: {result.get('reason')}"
            ))
        else:
            raise CommandError(
                f"Restore failed: {result.get('error', result.get('stderr', 'unknown'))}"
            )

        # ── Post-restore validation ───────────────────────────
        if options["validate_after"]:
            self.stdout.write("Running post-restore data integrity validation…")
            integrity = rm.validate_data_integrity()
            self._display_integrity(integrity)

    # ── Private helpers ───────────────────────────────────────

    def _pitr_restore(self, rm: RecoveryManager, options):
        """Handle point-in-time recovery."""
        from datetime import datetime

        target_time = None
        if options["target_time"]:
            try:
                target_time = datetime.fromisoformat(options["target_time"])
            except ValueError:
                raise CommandError(
                    f"Invalid --target-time format: {options['target_time']}"
                )

        self.stdout.write(f"Initiating point-in-time recovery to: {options['target_time']}")
        result = rm.initiate_recovery(target_time=target_time)

        if result.get("status") == "initiated":
            self.stdout.write(self.style.SUCCESS(
                "PITR initiated. Manual steps required:"
            ))
            self.stdout.write(f"  Target time: {result.get('target_time')}")
            self.stdout.write(f"  Backup source: {result.get('backup_source')}")
            self.stdout.write(f"  Note: {result.get('note')}")
        elif result.get("status") == "skipped":
            self.stdout.write(self.style.WARNING(
                f"PITR skipped: {result.get('reason')}"
            ))
        else:
            raise CommandError(f"PITR failed: {result.get('error')}")

    def _display_integrity(self, integrity: dict):
        """Display integrity check results."""
        status = integrity.get("status", "unknown")
        tables = integrity.get("tables_checked", 0)

        if status in ("passed", "success"):
            self.stdout.write(self.style.SUCCESS(
                f"Integrity check PASSED ({tables} tables checked)"
            ))
        elif status == "warnings":
            self.stdout.write(self.style.WARNING(
                f"Integrity check: WARNINGS ({tables} tables checked)"
            ))
            for issue in integrity.get("issues", []):
                self.stdout.write(f"  ⚠️  {issue}")
        else:
            self.stdout.write(self.style.ERROR(
                f"Integrity check: {status} ({tables} tables checked)"
            ))
