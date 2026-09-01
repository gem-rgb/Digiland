from decimal import Decimal
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from core.models import (
    LandParcel,
    Transaction,
    PaymentRecord,
    ParcelTrustProfile,
    TransactionMilestone,
    DisputeCase,
    ServiceFee,
)
from core.services.payment import (
    record_payment_confirmation,
    complete_transaction,
    reverse_payment,
)
from core.services.service_fee import ServiceFeeService


User = get_user_model()


class NonCustodialArchitectureTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email='seller_test@example.com',
            password='password123',
            role='Seller',
        )
        self.buyer = User.objects.create_user(
            email='buyer_test@example.com',
            password='password123',
            role='Buyer',
        )
        self.admin = User.objects.create_superuser(
            email='admin_test@example.com',
            password='password123',
        )

        self.parcel = LandParcel.objects.create(
            listed_by=self.seller,
            parcel_number='NAI-TEST-001',
            county='Nairobi',
            constituency='Westlands',
            ward='Parklands',
            land_size=Decimal('0.5'),
            land_use_type='Commercial',
            registered_owner_id='ID-12345678',
            asking_price=Decimal('5000000.00'),
            verification_status='Verified',
        )
        self.transaction = Transaction.objects.create(
            land_parcel=self.parcel,
            buyer=self.buyer,
            seller=self.seller,
            agreed_price=Decimal('5000000.00'),
            status='Initiated',
        )


    def test_trust_profile_creation(self):
        """ParcelTrustProfile correctly attaches and records risk metrics."""
        profile = ParcelTrustProfile.objects.create(
            parcel=self.parcel,
            seller_identity_verified=True,
            title_document_reviewed=True,
            risk_rating='LOW',
        )
        self.assertTrue(profile.seller_identity_verified)
        self.assertTrue(profile.title_document_reviewed)
        self.assertEqual(profile.risk_rating, 'LOW')
        self.assertEqual(str(profile), f"Trust Profile for {self.parcel.parcel_number} (LOW)")

    def test_service_fee_is_coordination_fee_not_escrow_holding(self):
        """Service fee is designated as Transaction & Verification Coordination Fee."""
        fees = ServiceFeeService.calculate_fees(self.transaction)
        self.assertIn('coordination_fee', fees)
        self.assertEqual(fees['coordination_fee'], Decimal('100000.00'))  # 2% of 5,000,000
        
        explanations = ServiceFeeService.get_fee_explanations()
        self.assertIn('transaction_coordination', explanations)
        self.assertEqual(explanations['transaction_coordination']['label'], 'Transaction & Verification Coordination Fee')


    def test_record_payment_confirmation_creates_payment_record(self):
        """Payment confirmation creates immutable PaymentRecord without holding funds."""
        result = record_payment_confirmation(
            transaction=self.transaction,
            payment_reference='MPESA-CONFIRM-9988',
            provider='M-Pesa STK',
            amount=Decimal('5000000.00'),
            raw_payload={'receipt': 'MPESA-CONFIRM-9988', 'status': 'Success'},
        )
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['payment_reference'], 'MPESA-CONFIRM-9988')
        
        # Verify transaction status updated
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'Payment_Confirmed')
        self.assertEqual(self.transaction.payment_reference_safe, 'MPESA-CONFIRM-9988')
        
        # Verify PaymentRecord created
        record = PaymentRecord.objects.get(transaction=self.transaction)
        self.assertEqual(record.payment_status, 'CONFIRMED')
        self.assertEqual(record.provider_reference, 'MPESA-CONFIRM-9988')
        self.assertEqual(record.amount, Decimal('5000000.00'))
        
        # Verify TransactionMilestone created
        milestone = TransactionMilestone.objects.filter(
            transaction=self.transaction,
            milestone_code='PAYMENT_CONFIRMED',
        ).first()
        self.assertIsNotNone(milestone)
        self.assertEqual(milestone.status, 'COMPLETED')

    def test_complete_transaction_advances_without_custodial_release(self):
        """complete_transaction concludes verifications and marks transaction completed."""
        record_payment_confirmation(
            transaction=self.transaction,
            payment_reference='MPESA-CONFIRM-9988',
            amount=Decimal('5000000.00'),
        )
        
        result = complete_transaction(
            transaction=self.transaction,
            admin_user=self.admin,
            notes='All conveyancing and title deed verifications verified.',
        )
        self.assertEqual(result['status'], 'success')
        
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'Completed')
        
        # Verify completion milestone
        milestone = TransactionMilestone.objects.filter(
            transaction=self.transaction,
            milestone_code='TRANSACTION_COMPLETED',
        ).first()
        self.assertIsNotNone(milestone)
        self.assertEqual(milestone.status, 'COMPLETED')

    def test_reverse_payment_logs_audit_record(self):
        """reverse_payment logs provider reversal evidence without claiming custodial refunds."""
        record_payment_confirmation(
            transaction=self.transaction,
            payment_reference='MPESA-CONFIRM-9988',
            amount=Decimal('5000000.00'),
        )
        
        result = reverse_payment(
            transaction=self.transaction,
            admin_user=self.admin,
            reason='Title survey encumbrance flagged by advocate.',
            reversal_reference='REV-009922',
        )
        self.assertEqual(result['status'], 'success')
        
        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, 'Reversed')
        
        # Verify PaymentRecord status is REVERSED
        record = PaymentRecord.objects.get(transaction=self.transaction)
        self.assertEqual(record.payment_status, 'REVERSED')
        self.assertIn('REV-009922', record.notes)


    def test_dispute_case_creation(self):
        """Dispute cases are logged against transaction without escrow freezing claims."""
        case = DisputeCase.objects.create(
            case_number='CASE-TEST-001',
            transaction=self.transaction,
            opened_by=self.buyer,
            claim_summary='Boundary beacon dispute detected during survey.',
            status='DISPUTE_OPENED',
        )
        self.assertEqual(case.status, 'DISPUTE_OPENED')
        self.assertEqual(case.transaction, self.transaction)
        self.assertIn('CASE-TEST-001', str(case))

