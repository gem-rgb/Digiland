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

        # Provision Admin account (Karani & dedicated admin)
        for admin_email, first, last in [
            ("karanitaitumu@gmail.com", "Karani", "Taitumu"),
            ("admin@digiland.co.ke", "Digiland", "Administrator"),
        ]:
            admin_user, _ = User.objects.get_or_create(
                email=admin_email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": "Admin",
                    "is_staff": True,
                    "is_superuser": True,
                    "is_active": True,
                    "is_email_verified": True,
                    "is_identity_verified": True,
                    "is_onboarded": True,
                }
            )
            admin_user.role = "Admin"
            admin_user.is_staff = True
            admin_user.is_superuser = True
            admin_user.is_active = True
            admin_user.is_email_verified = True
            admin_user.is_identity_verified = True
            admin_user.is_onboarded = True
            admin_user.set_password("AdminDigiland2026!")
            admin_user.save()
            EmailAddress.objects.update_or_create(user=admin_user, email=admin_email, defaults={"verified": True, "primary": True})

        # Provision Seller accounts
        for seller_email, first, last, pwd in [
            ("seller_demo@example.com", "Demo", "Seller", "SellerDigiland2026!"),
            ("legalhusla@gmail.com", "Legal", "Husla", "LegalHusla2026!"),
        ]:
            seller_user, _ = User.objects.get_or_create(
                email=seller_email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": "Seller",
                    "is_staff": False,
                    "is_superuser": False,
                    "is_active": True,
                    "is_email_verified": True,
                    "is_identity_verified": True,
                    "is_onboarded": True,
                }
            )
            seller_user.role = "Seller"
            seller_user.is_staff = False
            seller_user.is_superuser = False
            seller_user.is_active = True
            seller_user.is_email_verified = True
            seller_user.is_identity_verified = True
            seller_user.is_onboarded = True
            seller_user.set_password(pwd)
            seller_user.save()
            EmailAddress.objects.update_or_create(user=seller_user, email=seller_email, defaults={"verified": True, "primary": True})

        # Provision Buyer account
        buyer_email = "buyer_demo@example.com"
        buyer_user, _ = User.objects.get_or_create(
            email=buyer_email,
            defaults={
                "first_name": "Demo",
                "last_name": "Buyer",
                "role": "Buyer",
                "is_staff": False,
                "is_superuser": False,
                "is_active": True,
                "is_email_verified": True,
                "is_identity_verified": True,
                "is_onboarded": True,
            }
        )
        buyer_user.role = "Buyer"
        buyer_user.is_staff = False
        buyer_user.is_superuser = False
        buyer_user.is_active = True
        buyer_user.is_email_verified = True
        buyer_user.is_identity_verified = True
        buyer_user.is_onboarded = True
        buyer_user.set_password("BuyerDigiland2026!")
        buyer_user.save()
        EmailAddress.objects.update_or_create(user=buyer_user, email=buyer_email, defaults={"verified": True, "primary": True})

        # Provision EARB Agent accounts
        for agent_email, first, last in [
            ("agent_demo@example.com", "David", "Agent"),
            ("agent@digiland.co.ke", "Field", "Agent"),
        ]:
            agent_user, _ = User.objects.get_or_create(
                email=agent_email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": "Agent",
                    "is_staff": False,
                    "is_superuser": False,
                    "is_active": True,
                    "is_email_verified": True,
                    "is_identity_verified": True,
                    "is_onboarded": True,
                    "agent_county": "Nairobi",
                    "agent_constituency": "Dagoretti North",
                }
            )
            agent_user.role = "Agent"
            agent_user.is_staff = False
            agent_user.is_superuser = False
            agent_user.is_active = True
            agent_user.is_email_verified = True
            agent_user.is_identity_verified = True
            agent_user.is_onboarded = True
            agent_user.set_password("AgentDigiland2026!")
            agent_user.save()
            EmailAddress.objects.update_or_create(user=agent_user, email=agent_email, defaults={"verified": True, "primary": True})

        # Provision LSK Advocate/Lawyer accounts
        for lawyer_email, first, last in [
            ("lawyer_demo@example.com", "Sarah", "Lawyer"),
            ("lawyer@digiland.co.ke", "LSK", "Advocate"),
        ]:
            lawyer_user, _ = User.objects.get_or_create(
                email=lawyer_email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": "Lawyer",
                    "is_staff": False,
                    "is_superuser": False,
                    "is_active": True,
                    "is_email_verified": True,
                    "is_identity_verified": True,
                    "is_onboarded": True,
                }
            )
            lawyer_user.role = "Lawyer"
            lawyer_user.is_staff = False
            lawyer_user.is_superuser = False
            lawyer_user.is_active = True
            lawyer_user.is_email_verified = True
            lawyer_user.is_identity_verified = True
            lawyer_user.is_onboarded = True
            lawyer_user.set_password("LawyerDigiland2026!")
            lawyer_user.save()
            EmailAddress.objects.update_or_create(user=lawyer_user, email=lawyer_email, defaults={"verified": True, "primary": True})

        # Provision Licensed Surveyor accounts
        for surveyor_email, first, last in [
            ("surveyor_demo@example.com", "Jane", "Surveyor"),
            ("surveyor@digiland.co.ke", "Licensed", "Surveyor"),
        ]:
            surveyor_user, _ = User.objects.get_or_create(
                email=surveyor_email,
                defaults={
                    "first_name": first,
                    "last_name": last,
                    "role": "Surveyor",
                    "is_staff": False,
                    "is_superuser": False,
                    "is_active": True,
                    "is_email_verified": True,
                    "is_identity_verified": True,
                    "is_onboarded": True,
                    "surveyor_license_number": "ISLK-4092/2026",
                    "surveyor_firm": "Geospatial Surveys Kenya Ltd",
                    "surveyor_county": "Nairobi & Kiambu",
                    "is_surveyor_verified": True,
                }
            )
            surveyor_user.role = "Surveyor"
            surveyor_user.is_staff = False
            surveyor_user.is_superuser = False
            surveyor_user.is_active = True
            surveyor_user.is_email_verified = True
            surveyor_user.is_identity_verified = True
            surveyor_user.is_onboarded = True
            surveyor_user.surveyor_license_number = "ISLK-4092/2026"
            surveyor_user.surveyor_firm = "Geospatial Surveys Kenya Ltd"
            surveyor_user.surveyor_county = "Nairobi & Kiambu"
            surveyor_user.is_surveyor_verified = True
            surveyor_user.set_password("SurveyorDigiland2026!")
            surveyor_user.save()
            EmailAddress.objects.update_or_create(user=surveyor_user, email=surveyor_email, defaults={"verified": True, "primary": True})

        _BOOTSTRAP_DONE = True
        if _MARKER_FILE:
            try:
                _MARKER_FILE.write_text("1")
            except Exception:
                pass

    except Exception as exc:
        print(f"[deploy_bootstrap] DB init exception: {exc}")


