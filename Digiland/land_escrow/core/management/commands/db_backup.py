"""
Management command: db_backup

Create full or incremental database backups with optional compression,
encryption, and S3 upload.

Usage:
    python manage.py db_backup
    python manage.py db_backup --output /tmp/backup.sql.gz
    python manage.py db_backup --compress --encrypt --upload-s3
    python manage.py db_backup --incremental --since 2026-01-01
"""
import logging

from django.core.management.base import BaseCommand, CommandError

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = (
        "Create a database backup (full or incremental) with optional "
        "compression, encryption, and S3 upload."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            type=str,
            default=None,
            help="Output file path for the backup (default: auto-generated in /tmp/)",
        )
        parser.add_argument(
            "--compress",
            action="store_true",
            default=True,
            help="Enable gzip compression (default: True)",
        )
        parser.add_argument(
            "--no-compress",
            action="store_false",
            dest="compress",
            help="Disable compression",
        )
        parser.add_argument(
            "--encrypt",
            action="store_true",
            default=False,
            help="Encrypt the backup with AES-256 (requires BACKUP_ENCRYPTION_KEY)",
        )
        parser.add_argument(
            "--upload-s3",
            action="store_true",
            default=False,
            help="Upload the completed backup to S3 (requires boto3)",
        )
        parser.add_argument(
            "--incremental",
            action="store_true",
            default=False,
            help="Create an incremental (WAL-based) backup instead of full",
        )
        parser.add_argument(
            "--since",
            type=str,
            default=None,
            help="Timestamp for incremental backup start (ISO 8601 format)",
        )
        parser.add_argument(
            "--schedule",
            type=str,
            choices=["hourly", "daily", "weekly"],
            default=None,
            help="Set up an automatic backup schedule instead of running immediately",
        )
        parser.add_argument(
            "--verify",
            action="store_true",
            default=False,
            help="Verify backup integrity after creation",
        )

    def handle(self, *args, **options):
        from core.db.backup_recovery import BackupManager

        bm = BackupManager()

        # ── Schedule mode ─────────────────────────────────────
        if options["schedule"]:
            self.stdout.write(f"Setting up {options['schedule']} automatic backups…")
            result = bm.schedule_automatic_backups(options["schedule"])
            if result["status"] == "success":
                self.stdout.write(self.style.SUCCESS(
                    f"Automatic {options['schedule']} backup schedule configured."
                ))
            else:
                raise CommandError(f"Failed to set schedule: {result.get('error')}")
            return

        # ── Immediate backup ──────────────────────────────────
        self.stdout.write("Starting database backup…")

        if options["incremental"]:
            result = self._incremental_backup(bm, options)
        else:
            result = self._full_backup(bm, options)

        if result.get("status") not in ("success",):
            raise CommandError(f"Backup failed: {result.get('error', result)}")

        self.stdout.write(self.style.SUCCESS(
            f"Backup created: {result.get('path', 'N/A')}"
        ))
        self.stdout.write(f"  Size: {result.get('size_bytes', 0):,} bytes")
        self.stdout.write(f"  Checksum: {result.get('checksum', 'N/A')[:16]}…")
        self.stdout.write(f"  Type: {result.get('type', 'full')}")

        # ── Verify ────────────────────────────────────────────
        if options["verify"]:
            self.stdout.write("Verifying backup integrity…")
            verify_result = bm.verify_backup(result["path"])
            if verify_result.get("status") in ("success", "verified"):
                self.stdout.write(self.style.SUCCESS("Backup integrity verified."))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Backup verification: {verify_result.get('status')} — "
                    f"{verify_result.get('error', 'see details above')}"
                ))

        # ── Encrypt ───────────────────────────────────────────
        if options["encrypt"]:
            encrypt_result = self._encrypt_backup(result["path"])
            if encrypt_result["status"] == "success":
                self.stdout.write(self.style.SUCCESS(
                    f"Backup encrypted: {encrypt_result['path']}"
                ))
            else:
                self.stdout.write(self.style.WARNING(
                    f"Encryption skipped: {encrypt_result.get('error')}"
                ))

        # ── Upload to S3 ──────────────────────────────────────
        if options["upload_s3"]:
            upload_result = self._upload_to_s3(result["path"])
            if upload_result["status"] == "success":
                self.stdout.write(self.style.SUCCESS(
                    f"Backup uploaded to S3: {upload_result.get('s3_key')}"
                ))
            else:
                raise CommandError(f"S3 upload failed: {upload_result.get('error')}")

    # ── Private helpers ───────────────────────────────────────

    @staticmethod
    def _full_backup(bm: BackupManager, options) -> dict:
        return bm.create_full_backup(
            output_path=options.get("output"),
            compress=options.get("compress", True),
            encrypt=options.get("encrypt", False),
        )

    @staticmethod
    def _incremental_backup(bm: BackupManager, options) -> dict:
        from datetime import datetime
        since = None
        if options.get("since"):
            try:
                since = datetime.fromisoformat(options["since"])
            except ValueError:
                raise CommandError(f"Invalid --since timestamp: {options['since']}")
        return bm.create_incremental_backup(
            output_path=options.get("output"),
            since=since,
        )

    @staticmethod
    def _encrypt_backup(path: str) -> dict:
        """AES-256-CBC encryption of the backup file."""
        import os
        from django.conf import settings

        key = getattr(settings, "BACKUP_ENCRYPTION_KEY", None)
        if not key:
            return {"status": "skipped", "error": "BACKUP_ENCRYPTION_KEY not set in settings"}

        encrypted_path = path + ".enc"
        try:
            import subprocess
            proc = subprocess.run(
                [
                    "openssl", "enc", "-aes-256-cbc",
                    "-salt", "-in", path,
                    "-out", encrypted_path,
                    "-pass", f"pass:{key}",
                ],
                capture_output=True, text=True, timeout=600,
            )
            if proc.returncode == 0:
                return {"status": "success", "path": encrypted_path}
            return {"status": "failed", "error": proc.stderr}
        except FileNotFoundError:
            return {"status": "skipped", "error": "openssl not found on PATH"}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    @staticmethod
    def _upload_to_s3(path: str) -> dict:
        """Upload backup file to S3 via boto3."""
        try:
            import boto3
            from django.conf import settings
        except ImportError:
            return {"status": "failed", "error": "boto3 not installed — run pip install boto3"}

        bucket = getattr(settings, "BACKUP_S3_BUCKET", None)
        if not bucket:
            return {"status": "failed", "error": "BACKUP_S3_BUCKET not set in settings"}

        try:
            import os
            s3 = boto3.client("s3")
            s3_key = f"db-backups/{os.path.basename(path)}"
            s3.upload_file(path, bucket, s3_key)
            return {"status": "success", "s3_key": s3_key, "bucket": bucket}
        except Exception as exc:
            return {"status": "failed", "error": str(exc)}
