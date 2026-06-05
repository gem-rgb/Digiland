#!/usr/bin/env python
"""
Create test agent ratings
"""
import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from core.models import User, AgentRating

def create_test_ratings():
    print("=== Creating Test Agent Ratings ===")
    
    try:
        agent = User.objects.get(email='tatetricky@gmail.com')
        print(f"✅ Found agent: {agent.email}")
    except User.DoesNotExist:
        print("❌ Agent not found")
        return
    
    # Create some test ratings
    ratings_data = [
        {
            'rating': 5,
            'review': 'Excellent performance! Very professional and efficient in processing land parcels. Great communication with clients.'
        },
        {
            'rating': 4,
            'review': 'Good work overall. Timely completion of assigned tasks and thorough documentation.'
        },
        {
            'rating': 3,
            'review': 'Satisfactory performance. Completed tasks adequately but could improve response time.'
        }
    ]
    
    for rating_data in ratings_data:
        # Create a test admin user for rating
        admin_user, created = User.objects.get_or_create(
            email='admin@digiland.com',
            defaults={
                'role': 'Admin',
                'is_active': True,
                'is_identity_verified': True
            }
        )
        
        rating, rating_created = AgentRating.objects.get_or_create(
            agent=agent,
            rated_by=admin_user,
            rating=rating_data['rating'],
            review=rating_data['review'],
            defaults={
                'created_at': f'2026-03-{30 - len(ratings_data):02d}'
            }
        )
        
        if rating_created:
            print(f"  ✅ Created {rating_data['rating']}-star rating")
        else:
            print(f"  ⚠️  {rating_data['rating']}-star rating already exists")
    
    print(f"\n📊 Final Rating Summary:")
    print(f"  - Total ratings: {AgentRating.objects.filter(agent=agent).count()}")
    print(f"  - Average rating: {agent.average_rating}")
    print(f"  - Tasks completed: {agent.total_tasks_completed}")

if __name__ == "__main__":
    create_test_ratings()
