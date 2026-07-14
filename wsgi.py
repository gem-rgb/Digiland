"""Repository-root WSGI entry point."""

import os

from django.core.wsgi import get_wsgi_application

from deploy_bootstrap import bootstrap


bootstrap()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "land_escrow.settings")

application = get_wsgi_application()

# Auto-migrate SQLite on Vercel cold-start
if os.environ.get("VERCEL") == "1" and os.environ.get("DATABASE_URL", "").startswith("sqlite"):
    db_path = "/tmp/db.sqlite3"
    marker_path = db_path + ".migrated"
    if not os.path.exists(marker_path):
        try:
            from django.core.management import call_command
            print("Vercel cold start: Running migrations on /tmp/db.sqlite3...")
            call_command("migrate", no_input=True)
            # Create a marker file so we don't migrate again in this container instance
            with open(marker_path, "w") as f:
                f.write("1")
            print("Vercel cold start: Migrations completed successfully.")
        except Exception as e:
            print(f"Failed to auto-migrate on cold start: {e}")

app = application
handler = application
