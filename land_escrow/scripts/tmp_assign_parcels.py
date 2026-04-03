import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import LandParcel, User

# Find any user with Admin role or just the first user
admin_user = User.objects.filter(role='Admin').first()
if not admin_user:
    admin_user = User.objects.first()

if admin_user:
    orphans = LandParcel.objects.filter(listed_by__isnull=True)
    count = orphans.count()
    orphans.update(listed_by=admin_user)
    print(f"Assigned {count} orphaned parcels to user {admin_user.email}")
else:
    print("No users found to assign orphaned parcels to.")
