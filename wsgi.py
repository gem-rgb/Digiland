"""Repository-root WSGI entry point."""

import os

from django.core.wsgi import get_wsgi_application

from deploy_bootstrap import bootstrap


bootstrap()
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "land_escrow.settings")

application = get_wsgi_application()
app = application
handler = application
