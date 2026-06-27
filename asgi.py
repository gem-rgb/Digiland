"""Repository-root ASGI entry point."""

import os

from django.core.asgi import get_asgi_application

from deploy_bootstrap import bootstrap


bootstrap()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "land_escrow.settings")

application = get_asgi_application()
app = application
handler = application
