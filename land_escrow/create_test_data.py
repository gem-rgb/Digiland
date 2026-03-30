#!/usr/bin/env python
"""
Create test data for agent dashboard
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import User, LandParcel, Transaction, Message
from decimal import Decimal

def create_test_data():
    print("=== Creating Test Data for Agent Dashboard ===")
    
    try:
        agent = User.objects.get(email='tatetricky@gmail.com')
        print(f"✅ Found agent: {agent.email}")
    except User.DoesNotExist:
        print("❌ Agent not found")
        return
    
    # Create test parcels assigned to agent
    print("\n📦 Creating test parcels...")
    parcels_data = [
        {
            'parcel_number': 'TEST-001',
            'ward': 'Test Ward 1',
            'county': 'Test County',
            'land_size': 2.5,
            'verification_status': 'Pending'
        },
        {
            'parcel_number': 'TEST-002', 
            'ward': 'Test Ward 2',
            'county': 'Test County',
            'land_size': 1.8,
            'verification_status': 'Pending'
        },
        {
            'parcel_number': 'TEST-003',
            'ward': 'Test Ward 3', 
            'county': 'Test County',
            'land_size': 3.2,
            'verification_status': 'Verified'
        }
    ]
    
    for parcel_data in parcels_data:
        parcel, created = LandParcel.objects.get_or_create(
            parcel_number=parcel_data['parcel_number'],
            defaults={
                **parcel_data,
                'assigned_agent': agent,
                'listed_by': agent,  # Agent is also the seller for test
                'asking_price': Decimal('1000000'),
                'ardhisasa_last_synced': '2026-03-30 10:00:00'
            }
        )
        if created:
            print(f"  ✅ Created parcel: {parcel.parcel_number}")
        else:
            print(f"  ⚠️  Parcel already exists: {parcel.parcel_number}")
    
    # Create test transactions
    print("\n💰 Creating test transactions...")
    
    # Create test buyer
    buyer, buyer_created = User.objects.get_or_create(
        email='testbuyer@example.com',
        defaults={
            'role': 'Buyer',
            'is_active': True,
            'is_identity_verified': True,
            'phone_number': '+254700000001',
            'id_number': '12345678'
        }
    )
    
    for parcel in LandParcel.objects.filter(assigned_agent=agent)[:2]:
        tx, created = Transaction.objects.get_or_create(
            land_parcel=parcel,
            buyer=buyer,
            seller=agent,
            defaults={
                'agreed_price': Decimal('1500000'),
                'status': 'Under_Verification',
                'contract_agreed': True,
                'buyer_signature': 'test_signature_buyer',
                'seller_signature': 'test_signature_seller'
            }
        )
        if created:
            print(f"  ✅ Created transaction for parcel: {parcel.parcel_number}")
        else:
            print(f"  ⚠️  Transaction already exists for parcel: {parcel.parcel_number}")
    
    # Create test messages
    print("\n💬 Creating test messages...")
    messages_data = [
        {
            'sender': buyer,
            'content': 'Hello, I am interested in purchasing this parcel. Can we schedule a viewing?'
        },
        {
            'sender': buyer,
            'content': 'I have submitted my documents for verification. Please let me know the next steps.'
        },
        {
            'sender': buyer,
            'content': 'Thank you for your assistance with the land transfer process.'
        }
    ]
    
    for msg_data in messages_data:
        msg, created = Message.objects.get_or_create(
            receiver=agent,
            sender=msg_data['sender'],
            content=msg_data['content'],
            defaults={'is_read': False}
        )
        if created:
            print(f"  ✅ Created message from {msg.sender.email}")
        else:
            print(f"  ⚠️  Message already exists")
    
    # Create pending users for approval
    print("\n👥 Creating test users for approval...")
    users_data = [
        {
            'email': 'testbuyer2@example.com',
            'role': 'Buyer',
            'phone_number': '+254700000002',
            'id_number': '87654321'
        },
        {
            'email': 'testseller@example.com',
            'role': 'Seller', 
            'phone_number': '+254700000003',
            'id_number': '11223344'
        }
    ]
    
    for user_data in users_data:
        user, created = User.objects.get_or_create(
            email=user_data['email'],
            defaults={
                **user_data,
                'is_active': True,
                'is_identity_verified': False
            }
        )
        if created:
            print(f"  ✅ Created pending user: {user.email} ({user.role})")
        else:
            print(f"  ⚠️  User already exists: {user.email}")
    
    print("\n🎉 Test data creation completed!")
    
    # Verify data
    print("\n📊 Verification:")
    parcels = LandParcel.objects.filter(assigned_agent=agent, verification_status='Pending')
    print(f"  - Assigned pending parcels: {parcels.count()}")
    
    transactions = Transaction.objects.filter(
        contract_agreed=True,
        status__in=['Deposit_Paid', 'Under_Verification']
    ).filter(
        land_parcel__assigned_agent=agent
    )
    print(f"  - Pending transactions: {transactions.count()}")
    
    messages = Message.objects.filter(receiver=agent, is_read=False)
    print(f"  - Unread messages: {messages.count()}")
    
    pending_users = User.objects.filter(
        role__in=['Buyer', 'Seller'], 
        is_identity_verified=False, 
        is_active=True
    )
    print(f"  - Pending user approvals: {pending_users.count()}")

if __name__ == "__main__":
    create_test_data()
