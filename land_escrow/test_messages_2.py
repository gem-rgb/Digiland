import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import User, Message
from django.test import RequestFactory
from server.views import clear_message_thread
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.messages.middleware import MessageMiddleware

admin = User.objects.filter(role='Admin').first()
partner = User.objects.exclude(id=admin.id).first()

if admin and partner:
    Message.objects.create(sender=admin, receiver=partner, content="Test msg")
    print(f"Messages between admin and partner: {Message.objects.filter(sender=admin, receiver=partner).count()}")
    
    factory = RequestFactory()
    request = factory.post(f'/messages/thread/{partner.id}/clear/')
    request.user = admin
    
    # Add session and messages middlewares
    middleware = SessionMiddleware(lambda r: None)
    middleware.process_request(request)
    request.session.save()
    
    msg_middleware = MessageMiddleware(lambda r: None)
    msg_middleware.process_request(request)
    
    response = clear_message_thread(request, partner.id)
    print(f"Response status: {response.status_code}")
    print(f"Response url: {response.url}")
    
    remaining = Message.objects.filter(sender=admin, receiver=partner).count()
    print(f"Remaining messages: {remaining}")
else:
    print("Could not find admin or partner")
