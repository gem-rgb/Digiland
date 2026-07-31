from django.test import TestCase, Client
from django.urls import reverse
from core.models import User, LandParcel, Transaction
from django.utils import timezone

class LawyerSellerWorkflowTests(TestCase):
    def setUp(self):
        # Create Seller, Agent, Lawyer, Buyer, and Admin
        self.seller = User.objects.create_user(
            email='seller@test.com',
            password='password123',
            role='Seller',
            is_onboarded=True,
            is_active=True
        )
        self.agent = User.objects.create_user(
            email='agent@test.com',
            password='password123',
            role='Agent',
            is_onboarded=True,
            is_active=True,
            is_identity_verified=True
        )
        self.lawyer = User.objects.create_user(
            email='lawyer@test.com',
            password='password123',
            role='Lawyer',
            is_onboarded=True,
            is_active=True
        )
        self.buyer = User.objects.create_user(
            email='buyer@test.com',
            password='password123',
            role='Buyer',
            is_onboarded=True,
            is_active=True
        )
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='password123',
            role='Admin',
            is_onboarded=True,
            is_active=True
        )

        # Create Land Parcel
        self.parcel = LandParcel.objects.create(
            parcel_number='12345_abc',
            county='Nairobi',
            constituency='Dagoretti North',
            ward='Kilimani',
            land_size=0.5,
            asking_price=5000000.00,
            verification_status='Pending',
            listed_by=self.seller
        )

        # Create Transaction
        self.transaction = Transaction.objects.create(
            buyer=self.buyer,
            seller=self.seller,
            land_parcel=self.parcel,
            agreed_price=4500000.00,
            status='Initiated'
        )

    def test_seller_can_upload_and_edit_parcel(self):
        client = Client()
        client.login(email='seller@test.com', password='password123')

        # Edit parcel
        edit_url = reverse('frontend:parcel_edit', args=[self.parcel.parcel_number])
        response = client.post(edit_url, {
            'parcel_number': self.parcel.parcel_number,
            'county': 'Mombasa',
            'constituency': 'Changamwe',
            'ward': 'Chaani',
            'land_size': '0.7',
            'asking_price': '4800000.00',
            'lowest_negotiable_price': '4000000.00',
            'registered_owner_id': '12345678',
            'land_use_type': 'Residential'
        })
        self.assertEqual(response.status_code, 302)
        self.parcel.refresh_from_db()
        self.assertEqual(self.parcel.county, 'Mombasa')
        self.assertEqual(float(self.parcel.asking_price), 4800000.00)

    def test_unauthorized_user_cannot_edit_parcel(self):
        client = Client()
        client.login(email='buyer@test.com', password='password123')

        # Buyer attempts to edit seller's parcel
        edit_url = reverse('frontend:parcel_edit', args=[self.parcel.parcel_number])
        response = client.post(edit_url, {
            'county': 'Mombasa',
        })
        self.assertEqual(response.status_code, 302)
        self.parcel.refresh_from_db()
        self.assertNotEqual(self.parcel.county, 'Mombasa')

    def test_agent_verify_and_reject_parcel(self):
        client = Client()
        client.login(email='agent@test.com', password='password123')

        # Reject/flag as fraudulent
        reject_url = reverse('frontend:agent_verify_parcel', args=[self.parcel.parcel_number])
        response = client.post(reject_url, {'action': 'reject'})
        self.assertEqual(response.status_code, 302)
        self.parcel.refresh_from_db()
        self.assertEqual(self.parcel.verification_status, 'Fraudulent')

    def test_lawyer_can_access_dashboard_and_sign(self):
        client = Client()
        client.login(email='lawyer@test.com', password='password123')

        # Dashboard access
        dashboard_url = reverse('frontend:agent_dashboard')
        response = client.get(dashboard_url)
        self.assertEqual(response.status_code, 200)

        # Sign contract POST
        sign_url = reverse('frontend:sign_contract', args=[self.transaction.id])
        response = client.post(sign_url, {
            'lawyer_signature_data': 'data:image/png;base64,lawyersignature',
            'lawyer_name': 'Advocate Kamau',
            'lawyer_lsk_number': 'P.105/12345/20'
        })
        self.assertEqual(response.status_code, 302)
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.lawyer_name, 'Advocate Kamau')
        self.assertEqual(self.transaction.lawyer_lsk_number, 'P.105/12345/20')
        self.assertIsNotNone(self.transaction.lawyer_signature)
        self.assertIsNotNone(self.transaction.lawyer_signed_at)

    def test_marketplace_redirect_and_search(self):
        client = Client()
        # Check /marketplace redirects to /parcels/ preserving query params
        resp = client.get('/marketplace/?q=Nairobi')
        self.assertIn(resp.status_code, [301, 302])
        self.assertEqual(resp.headers['Location'], '/parcels/?q=Nairobi')

        # Check searching parcel list works
        resp = client.get(reverse('frontend:parcel_list') + '?q=Dagoretti')
        self.assertEqual(resp.status_code, 200)

    def test_dual_signature_document_access(self):
        client = Client()
        # Seller requests/authorizes document access
        client.login(email='seller@test.com', password='password123')
        req_url = reverse('frontend:request_document_access', args=[self.parcel.parcel_number])
        resp = client.post(req_url, {'seller_pin': '123456'})
        self.assertEqual(resp.status_code, 302)

        # Lawyer confirms access
        client.login(email='lawyer@test.com', password='password123')
        conf_url = reverse('frontend:confirm_document_access', args=[self.parcel.parcel_number])
        resp = client.post(conf_url, {'accessor_pin': '654321'})
        self.assertEqual(resp.status_code, 302)

        from core.models import DocumentAccessGrant
        grant = DocumentAccessGrant.objects.filter(parcel=self.parcel, access_granted=True).first()
        self.assertIsNotNone(grant)
        self.assertTrue(grant.is_valid)

    def test_lawyer_post_transaction_tasks(self):
        client = Client()
        client.login(email='lawyer@test.com', password='password123')
        tasks_url = reverse('frontend:lawyer_post_transaction_tasks', args=[self.transaction.id])
        
        # GET initializes tasks
        resp = client.get(tasks_url)
        self.assertEqual(resp.status_code, 200)

        # POST updates a task
        resp = client.post(tasks_url, {
            'task_key': 'lodge_caution',
            'is_completed': 'true',
            'reference_number': 'REG/CAUTION/2026/99',
            'notes': 'Caution lodged at Nairobi Registry'
        })
        self.assertEqual(resp.status_code, 302)

        from core.models import LawyerPostTransactionTask
        task = LawyerPostTransactionTask.objects.get(transaction=self.transaction, task_key='lodge_caution')
        self.assertTrue(task.is_completed)
        self.assertEqual(task.reference_number, 'REG/CAUTION/2026/99')

    def test_seller_dashboard_access(self):
        client = Client()
        client.login(email='seller@test.com', password='password123')
        seller_url = reverse('frontend:seller_dashboard')
        resp = client.get(seller_url)
        self.assertEqual(resp.status_code, 200)


