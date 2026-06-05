import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import User, Message
print(f"Total messages: {Message.objects.count()}")
