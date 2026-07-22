from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from core.models import LandParcel, Transaction, User
from core.services.commission import (
    accept_commission,
    close_commission,
    complete_site_visit,
    create_commission,
    find_nearby_agents,
    lawyer_verdict,
    review_documents,
    schedule_site_visit,
    submit_to_lawyer,
)


class PurchaseCommissionWorkflowTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email='seller@test.com',
            password='password123',
            role='Seller',
            is_active=True,
            is_onboarded=True,
        )
        self.buyer = User.objects.create_user(
            email='buyer@test.com',
            password='password123',
            role='Buyer',
            is_active=True,
            is_onboarded=True,
        )
        self.agent = User.objects.create_user(
            email='agent@test.com',
            password='password123',
            role='Agent',
            is_active=True,
            is_onboarded=True,
            is_identity_verified=True,
            agent_county='Nairobi',
            agent_constituency='Dagoretti North',
        )
        self.other_agent = User.objects.create_user(
            email='agent-2@test.com',
            password='password123',
            role='Agent',
            is_active=True,
            is_onboarded=True,
            is_identity_verified=True,
            agent_county='Mombasa',
            agent_constituency='Changamwe',
        )
        self.lawyer = User.objects.create_user(
            email='lawyer@test.com',
            password='password123',
            role='Lawyer',
            is_active=True,
            is_onboarded=True,
            is_identity_verified=True,
        )
        self.parcel = LandParcel.objects.create(
            parcel_number='NBO-001',
            county='Nairobi',
            constituency='Dagoretti North',
            ward='Kilimani',
            land_size=0.5,
            registered_owner_id='12345678',
            asking_price='5000000.00',
            verification_status='Verified',
            listed_by=self.seller,
        )

    def test_commission_lifecycle_reaches_transaction_at_closing(self):
        commission = create_commission(self.buyer, self.parcel)
        self.assertEqual(commission.status, 'Open')
        self.assertEqual(commission.target_county, 'Nairobi')
        self.assertEqual(commission.target_constituency, 'Dagoretti North')

        accept_commission(self.agent, commission)
        commission.refresh_from_db()
        self.assertEqual(commission.status, 'Accepted')
        self.assertEqual(commission.accepted_by_id, self.agent.id)

        review_documents(commission, self.agent, note='Parcel documents are present.')
        commission.refresh_from_db()
        self.assertTrue(commission.documents_reviewed)
        self.assertEqual(commission.status, 'Documents_Review')

        submit_to_lawyer(commission, self.agent, lawyer=self.lawyer, note='Forwarding to legal review.')
        commission.refresh_from_db()
        self.assertEqual(commission.status, 'Lawyer_Verification')
        self.assertEqual(commission.assigned_lawyer_id, self.lawyer.id)

        lawyer_verdict(commission, self.lawyer, verified=True, note='Verified by advocate.')
        commission.refresh_from_db()
        self.assertEqual(commission.status, 'Site_Visit_Scheduled')
        self.assertTrue(commission.lawyer_verified)

        visit_date = timezone.now() + timedelta(days=1)
        schedule_site_visit(commission, self.agent, visit_date=visit_date, location='Main gate', notes='Buyer to attend.')
        commission.refresh_from_db()
        self.assertEqual(commission.status, 'Site_Visit_Scheduled')
        self.assertEqual(commission.site_visit_location, 'Main gate')

        complete_site_visit(commission, self.agent, notes='Site visit completed.')
        commission.refresh_from_db()
        self.assertTrue(commission.site_visit_complete)
        self.assertEqual(commission.status, 'Site_Visit_Complete')

        locked_commission, transaction = close_commission(commission, self.agent)
        self.assertEqual(locked_commission.status, 'Closing')
        self.assertIsNotNone(transaction)
        self.assertEqual(transaction.status, 'Under_Verification')
        self.assertEqual(transaction.buyer_id, self.buyer.id)
        self.assertEqual(transaction.seller_id, self.seller.id)

        commission.refresh_from_db()
        self.assertEqual(commission.transaction_id, transaction.id)
        self.assertEqual(Transaction.objects.count(), 1)

    def test_duplicate_active_commission_is_blocked(self):
        create_commission(self.buyer, self.parcel)
        with self.assertRaises(ValidationError):
            create_commission(self.buyer, self.parcel)

    def test_find_nearby_agents_prefers_exact_region(self):
        agents = list(find_nearby_agents('Nairobi', 'Dagoretti North'))
        self.assertIn(self.agent, agents)
        self.assertNotIn(self.other_agent, agents)
