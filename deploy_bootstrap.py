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
    if os.environ.get("VERCEL") == "1":
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url or db_url.startswith("sqlite"):
            os.environ["DATABASE_URL"] = "sqlite:////tmp/db.sqlite3"

    project_path = str(PROJECT_DIR)
    if project_path not in sys.path:
        sys.path.insert(0, project_path)

    init_django_app()
    return PROJECT_DIR


def init_django_app() -> None:
    try:
        import django
        from django.conf import settings
        if not settings.configured:
            os.environ.setdefault("DJANGO_SETTINGS_MODULE", "land_escrow.settings")
            django.setup()

        from django.core.management import call_command
        from django.contrib.sites.models import Site
        from core.models import User

        call_command("migrate", interactive=False, verbosity=0)

        site, _ = Site.objects.get_or_create(id=1, defaults={"domain": "digiland-six.vercel.app", "name": "Digiland"})
        if site.domain != "digiland-six.vercel.app":
            site.domain = "digiland-six.vercel.app"
            site.name = "Digiland"
            site.save()

        # Provision Admin account for karanitaitumu@gmail.com
        admin_email = "karanitaitumu@gmail.com"
        admin_user, _created = User.objects.get_or_create(
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
        admin_user.set_password("AdminDigiland2026!")
        admin_user.role = "Admin"
        admin_user.is_staff = True
        admin_user.is_superuser = True
        admin_user.is_onboarded = True
        admin_user.save()

    except Exception as exc:
        print(f"[deploy_bootstrap] DB init exception: {exc}")

