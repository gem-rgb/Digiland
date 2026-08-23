from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


ROOT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = ROOT_DIR / "Digiland" / "land_escrow"


def bootstrap() -> Path:
    """Load local environment files and expose the Django project on sys.path."""
    if not PROJECT_DIR.exists():
        raise RuntimeError(f"Expected Django project at {PROJECT_DIR}")

    for env_path in (
        ROOT_DIR / ".env",
        PROJECT_DIR / ".env",
        PROJECT_DIR / ".env.local",
    ):
        if env_path.exists():
            load_dotenv(env_path, override=False)

    # Vercel environment: redirect SQLite to writable /tmp directory
    if os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV"):
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url or db_url.startswith("sqlite"):
            os.environ["DATABASE_URL"] = "sqlite:////tmp/db.sqlite3"

    project_path = str(PROJECT_DIR)
    if project_path not in sys.path:
        sys.path.insert(0, project_path)

    init_django_app()
    return PROJECT_DIR


_BOOTSTRAP_DONE = False
_MARKER_FILE = Path("/tmp/.digiland_bootstrapped") if (os.environ.get("VERCEL") or os.environ.get("VERCEL_ENV")) else None


def init_django_app() -> None:
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return

    # Skip database operations if running build / check commands
    if any(cmd in sys.argv for cmd in ("collectstatic", "makemigrations", "check", "test")):
        return

    try:
        import django
        from django.conf import settings
        if not settings.configured:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "land_escrow.settings")
            django.setup()

        from django.core.management import call_command
        from django.contrib.sites.models import Site
        from core.models import User
        from allauth.account.models import EmailAddress

        # Apply any pending migrations on database during container cold start
        try:
            call_command("migrate", interactive=False, verbosity=0)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).warning("Bootstrap migrate failed: %s", exc)

        site, _ = Site.objects.get_or_create(id=1, defaults={"domain": "digiland-six.vercel.app", "name": "Digiland"})
        if site.domain != "digiland-six.vercel.app":
            site.domain = "digiland-six.vercel.app"
            site.name = "Digiland"
            site.save(update_fields=["domain", "name"])

        # Provision Admin account if not present
        admin_email = "karanitaitumu@gmail.com"
        admin_user, admin_created = User.objects.get_or_create(
            email=admin_email,
            defaults={
                "first_name": "Karani",
                "last_name": "Taitumu",
                "role": "Admin",
                "is_staff": True,
                "is_superuser": True,
                "is_email_verified": True,
                "is_identity_verified": True,
                "is_onboarded": True,
            }
        )
        if admin_created:
            admin_user.set_password("AdminDigiland2026!")
            admin_user.save()
            EmailAddress.objects.update_or_create(user=admin_user, email=admin_email, defaults={"verified": True, "primary": True})

        # Provision Seller account if not present
        seller_email = "seller_demo@example.com"
        seller_user, seller_created = User.objects.get_or_create(
            email=seller_email,
            defaults={
                "first_name": "Demo",
                "last_name": "Seller",
                "role": "Seller",
                "is_email_verified": True,
                "is_identity_verified": True,
                "is_onboarded": True,
            }
        )
        if seller_created:
            seller_user.set_password("SellerDigiland2026!")
            seller_user.save()
            EmailAddress.objects.update_or_create(user=seller_user, email=seller_email, defaults={"verified": True, "primary": True})

        # Provision legalhusla Seller account if not present
        legal_email = "legalhusla@gmail.com"
        legal_user, legal_created = User.objects.get_or_create(
            email=legal_email,
            defaults={
                "first_name": "Legal",
                "last_name": "Husla",
                "role": "Seller",
                "is_email_verified": True,
                "is_identity_verified": True,
                "is_onboarded": True,
            }
        )
        if legal_created:
            legal_user.set_password("LegalHusla2026!")
            legal_user.save()
            EmailAddress.objects.update_or_create(user=legal_user, email=legal_email, defaults={"verified": True, "primary": True})

        _BOOTSTRAP_DONE = True
        if _MARKER_FILE:
            try:
                _MARKER_FILE.write_text("1")
            except Exception:
                pass

    except Exception as exc:
        print(f"[deploy_bootstrap] DB init exception: {exc}")


