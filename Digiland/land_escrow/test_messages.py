import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import Message


def main():
    print(f"Total messages: {Message.objects.count()}")


if __name__ == "__main__":
    main()
