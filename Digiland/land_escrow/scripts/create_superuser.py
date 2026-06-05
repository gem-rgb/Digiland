import os, django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import User

if not User.objects.filter(email='admin@example.com').exists():
    User.objects.create_superuser('admin@example.com', 'admin123', role='Admin')
    print("Superuser created: admin@example.com / admin123")
else:
    print("Superuser already exists.")
