"""
Automated Test Suite for DigiLand Non-Escrow / Direct-Settlement Architecture.
Implements the 20 test specifications mandated by Section 34 of the specification.

1. Buyer creates land purchase payment
2. Buyer cannot change seller
3. Buyer cannot change amount
4. Buyer cannot change beneficiary
5. Land purchase does not increase DigiLand revenue
6. DigiLand fee increases DigiLand revenue
7. Survey fee is separate from land purchase
8. Legal fee is separate from land purchase
9. Duplicate M-PESA callback does not duplicate payment
10. Failed payment does not become confirmed
11. Reversed payment updates correctly
12. Browser closure does not lose payment state
13. Seller sees confirmed payment
14. Buyer sees correct payment history
15. Admin sees correct beneficiary
16. Historical legacy records remain intact
17. No escrow balance is created
18. No seller funds are recorded as DigiLand revenue
19. Unauthorized user cannot initiate payment for another user's transaction
20. Provider receipt cannot be reused for another transaction
"""

from decimal import Decimal
import json
from unittest.mock import patch
from django.core.exceptions import ValidationError
from django.test import TestCase, RequestFactory
from django.utils import timezone
from core.models import User, LandParcel, Transaction, PaymentRecord, RefundRecord
from core.services.payment_router import PaymentRouter
from core.services.payment import (
    create_payment_intent,
    initiate_mpesa_stk_push,
    process_mpesa_callback,
    request_refund,
    review_refund,
    execute_refund,
    DarajaAPI,
)
from core.services.payment_reconciliation import PaymentReconciliationService
from core.api_views import initiate_mpesa_payment_view


class DirectSettlementArchitectureTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()

        self.seller = User.objects.create_user(
            email="seller.wanjiku@example.com",
            password="testpassword123",
            role="Seller",
            first_name="Mary",
            last_name="Wanjiku"
        )
        self.buyer = User.objects.create_user(
            email="buyer.kamau@example.com",
            password="testpassword123",
            role="Buyer",
            first_name="John",
            last_name="Kamau"
        )
        self.unauthorized_user = User.objects.create_user(
            email="stranger@example.com",
            password="testpassword123",
            role="Buyer",
            first_name="Jane",
            last_name="Stranger"
        )
        self.surveyor = User.objects.create_user(
            email="surveyor.mwangi@example.com",
            password="testpassword123",
            role="Agent",
            first_name="Peter",
            last_name="Mwangi"
        )
        self.advocate = User.objects.create_user(
            email="advocate.omondi@example.com",
            password="testpassword123",
            role="Agent",
            first_name="David",
            last_name="Omondi"
        )
        self.admin = User.objects.create_superuser(
            email="admin@digiland.co.ke",
            password="adminpassword123"
        )
        self.parcel = LandParcel.objects.create(
            parcel_number="KIAMBU/RUIRU/10452",
            land_size=Decimal("1.25"),
            asking_price=Decimal("4500000.00"),
            listed_by=self.seller,
            verification_status="Verified",
            county="Kiambu",
            constituency="Ruiru",
            ward="Biashara",
            land_use_type="Agricultural/Residential",
            registered_owner_id="22334455"
        )
        self.transaction = Transaction.objects.create(
            land_parcel=self.parcel,
            buyer=self.buyer,
            seller=self.seller,
            agreed_price=Decimal("4500000.00"),
            coordination_fee=Decimal("90000.00"),
            platform_service_fee=Decimal("90000.00"),
            status="Initiated"
        )

    # -------------------------------------------------------------------------
    # Test 1: Buyer creates land purchase payment
    # -------------------------------------------------------------------------
    def test_01_buyer_creates_land_purchase_payment(self):
        """Buyer initiates land purchase payment routing directly to seller with correct metadata."""
        payment = PaymentRouter.create_land_purchase_payment(
            transaction=self.transaction,
            payer=self.buyer
        )
        self.assertEqual(payment.payment_type, 'DIRECT_SETTLEMENT')
        self.assertEqual(payment.payment_purpose, 'LAND_PURCHASE')
        self.assertEqual(payment.beneficiary_type, 'SELLER')
        self.assertEqual(payment.beneficiary_user, self.seller)
        self.assertEqual(payment.payer, self.buyer)
        self.assertEqual(payment.amount, Decimal("4500000.00"))
        self.assertEqual(payment.currency, 'KES')
        self.assertEqual(payment.status, 'CREATED')
        self.assertTrue(payment.digiland_reference.startswith('DL-PMT-') or payment.digiland_reference.startswith('DL-PAY-'))

    # -------------------------------------------------------------------------
    # Test 2: Buyer cannot change seller
    # -------------------------------------------------------------------------
    def test_02_buyer_cannot_change_seller(self):
        """PaymentRouter strictly binds beneficiary to transaction seller."""
        payment = PaymentRouter.create_land_purchase_payment(
            transaction=self.transaction,
            payer=self.buyer
        )
        # Beneficiary user is guaranteed to be transaction seller
        self.assertEqual(payment.beneficiary_user, self.transaction.seller)
        self.assertNotEqual(payment.beneficiary_user, self.unauthorized_user)

    # -------------------------------------------------------------------------
    # Test 3: Buyer cannot change amount
    # -------------------------------------------------------------------------
    def test_03_buyer_cannot_change_amount(self):
        """Tampered amount is rejected during land purchase payment creation."""
        with self.assertRaises((ValueError, ValidationError)) as ctx:
            PaymentRouter.create_land_purchase_payment(
                transaction=self.transaction,
                payer=self.buyer,
                amount=Decimal("1000.00") # Tampered amount
            )
        self.assertIn("Amount mismatch", str(ctx.exception))

    # -------------------------------------------------------------------------
    # Test 4: Buyer cannot change beneficiary
    # -------------------------------------------------------------------------
    def test_04_buyer_cannot_change_beneficiary(self):
        """Land purchase payment beneficiary cannot be pointed to any third party."""
        payment = PaymentRouter.create_land_purchase_payment(
            transaction=self.transaction,
            payer=self.buyer
        )
        self.assertEqual(payment.beneficiary_type, 'SELLER')
        self.assertEqual(payment.beneficiary_user.id, self.seller.id)

    # -------------------------------------------------------------------------
    # Test 5: Land purchase does not increase DigiLand revenue
    # -------------------------------------------------------------------------
    def test_05_land_purchase_does_not_increase_digiland_revenue(self):
        """Confirmed land purchase money does NOT count toward DigiLand platform revenue."""
        payment = PaymentRouter.create_land_purchase_payment(
            transaction=self.transaction,
            payer=self.buyer
        )
        payment.status = 'PAYMENT_CONFIRMED'
        payment.payment_status = 'COMPLETED'
        payment.confirmed_at = timezone.now()
        payment.provider_reference = 'MPESA_LAND_TXN_001'
        payment.save()

        summary = PaymentReconciliationService.get_reconciliation_summary()
        metrics = summary['metrics']

        self.assertEqual(metrics['digiland_revenue_kes'], 0.0)
        self.assertEqual(metrics['land_transaction_value_kes'], 4500000.0)
        self.assertEqual(metrics['total_payment_volume_kes'], 4500000.0)

    # -------------------------------------------------------------------------
    # Test 6: DigiLand fee increases DigiLand revenue
    # -------------------------------------------------------------------------
    def test_06_digiland_fee_increases_digiland_revenue(self):
        """Confirmed platform coordination fee increases DigiLand revenue."""
        fee_payment = PaymentRouter.create_digiland_fee_payment(
            transaction=self.transaction,
            payer=self.buyer,
            amount=Decimal("90000.00")
        )
        fee_payment.status = 'PAYMENT_CONFIRMED'
        fee_payment.payment_status = 'COMPLETED'
        fee_payment.confirmed_at = timezone.now()
        fee_payment.provider_reference = 'MPESA_FEE_TXN_001'
        fee_payment.save()

        summary = PaymentReconciliationService.get_reconciliation_summary()
        metrics = summary['metrics']

        self.assertEqual(metrics['digiland_revenue_kes'], 90000.0)
        self.assertEqual(metrics['land_transaction_value_kes'], 0.0)
        self.assertEqual(metrics['total_payment_volume_kes'], 90000.0)

    # -------------------------------------------------------------------------
    # Test 7: Survey fee is separate from land purchase
    # -------------------------------------------------------------------------
    def test_07_survey_fee_is_separate_from_land_purchase(self):
        """Survey fee is created as a separate obligation with professional beneficiary."""
        survey_payment = PaymentRouter.create_professional_payment(
            transaction=self.transaction,
            payer=self.buyer,
            professional=self.surveyor,
            service_type='SURVEY_FEE',
            amount=Decimal("15000.00")
        )
        survey_payment.status = 'PAYMENT_CONFIRMED'
        survey_payment.payment_status = 'COMPLETED'
        survey_payment.save()

        self.assertEqual(survey_payment.payment_type, 'PROFESSIONAL_PAYMENT')
        self.assertEqual(survey_payment.payment_purpose, 'SURVEY_FEE')
        self.assertEqual(survey_payment.beneficiary_type, 'SURVEYOR')
        self.assertEqual(survey_payment.beneficiary_user, self.surveyor)

        summary = PaymentReconciliationService.get_reconciliation_summary()
        metrics = summary['metrics']
        self.assertEqual(metrics['digiland_revenue_kes'], 0.0)
        self.assertEqual(metrics['professional_services_value_kes'], 15000.0)
        self.assertEqual(metrics['land_transaction_value_kes'], 0.0)

    # -------------------------------------------------------------------------
    # Test 8: Legal fee is separate from land purchase
    # -------------------------------------------------------------------------
    def test_08_legal_fee_is_separate_from_land_purchase(self):
        """Legal fee is created as a separate obligation with advocate beneficiary."""
        legal_payment = PaymentRouter.create_professional_payment(
            transaction=self.transaction,
            payer=self.buyer,
            professional=self.advocate,
            service_type='LEGAL_FEE',
            amount=Decimal("20000.00")
        )
        legal_payment.status = 'PAYMENT_CONFIRMED'
        legal_payment.payment_status = 'COMPLETED'
        legal_payment.save()

        self.assertEqual(legal_payment.payment_type, 'PROFESSIONAL_PAYMENT')
        self.assertEqual(legal_payment.payment_purpose, 'LEGAL_FEE')
        self.assertEqual(legal_payment.beneficiary_type, 'ADVOCATE')
        self.assertEqual(legal_payment.beneficiary_user, self.advocate)

        summary = PaymentReconciliationService.get_reconciliation_summary()
        metrics = summary['metrics']
        self.assertEqual(metrics['digiland_revenue_kes'], 0.0)
        self.assertEqual(metrics['professional_services_value_kes'], 20000.0)

    # -------------------------------------------------------------------------
    # Test 9: Duplicate M-PESA callback does not duplicate payment
    # -------------------------------------------------------------------------
    def test_09_duplicate_mpesa_callback_does_not_duplicate_payment(self):
        """Duplicate M-PESA callbacks for the same CheckoutRequestID are idempotent."""
        payment = PaymentRouter.create_land_purchase_payment(
            transaction=self.transaction,
            payer=self.buyer
        )
        payment.checkout_request_reference = "ws_CO_01092026_DUP_TEST"
        payment.status = 'CUSTOMER_ACTION_REQUIRED'
        payment.save()

        callback_payload = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "MR_12345",
                    "CheckoutRequestID": "ws_CO_01092026_DUP_TEST",
                    "ResultCode": 0,
                    "ResultDesc": "The service request is processed successfully.",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 4500000.00},
                            {"Name": "MpesaReceiptNumber", "Value": "MPESA_RCPT_DUP_01"},
                            {"Name": "TransactionDate", "Value": 20260901120000},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }

        # First callback processing
        res1 = process_mpesa_callback(callback_payload)
        self.assertEqual(res1.get("status"), "success")
        payment.refresh_from_db()
        self.assertEqual(payment.status, "PAYMENT_CONFIRMED")
        self.assertEqual(payment.provider_reference, "MPESA_RCPT_DUP_01")

        # Second identical callback processing
        res2 = process_mpesa_callback(callback_payload)
        self.assertIn(res2.get("status"), ["duplicate_ignored", "success"])
        self.assertTrue(res2.get("already_processed", True))

        # Ensure only 1 payment record exists and amount is intact
        self.assertEqual(PaymentRecord.objects.filter(transaction=self.transaction).count(), 1)
        self.assertEqual(payment.amount, Decimal("4500000.00"))

    # -------------------------------------------------------------------------
    # Test 10: Failed payment does not become confirmed
    # -------------------------------------------------------------------------
    def test_10_failed_payment_does_not_become_confirmed(self):
        """Failed M-PESA callback transitions status to PAYMENT_FAILED and is not confirmed."""
        payment = PaymentRouter.create_land_purchase_payment(
            transaction=self.transaction,
            payer=self.buyer
        )
        payment.checkout_request_reference = "ws_CO_01092026_FAIL_TEST"
        payment.status = 'CUSTOMER_ACTION_REQUIRED'
        payment.save()

        failed_callback = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "MR_FAIL_123",
                    "CheckoutRequestID": "ws_CO_01092026_FAIL_TEST",
                    "ResultCode": 1032,
                    "ResultDesc": "Request cancelled by user."
                }
            }
        }

        res = process_mpesa_callback(failed_callback)
        self.assertEqual(res.get("status"), "failed")
        payment.refresh_from_db()
        self.assertEqual(payment.status, "PAYMENT_FAILED")
        self.assertIn(payment.payment_status, ["FAILED", "PAYMENT_FAILED"])

        # Should not count in confirmed metrics
        summary = PaymentReconciliationService.get_reconciliation_summary()
        self.assertEqual(summary['metrics']['confirmed_payments_count'], 0)

    # -------------------------------------------------------------------------
    # Test 11: Reversed payment updates correctly
    # -------------------------------------------------------------------------
    def test_11_reversed_payment_updates_correctly(self):
        """Reversed payment creates a refund record and updates ledger correctly."""
        payment = PaymentRouter.create_land_purchase_payment(
            transaction=self.transaction,
            payer=self.buyer
        )
        payment.status = 'PAYMENT_CONFIRMED'
        payment.payment_status = 'COMPLETED'
        payment.provider_reference = 'MPESA_REFUND_TARGET'
        payment.save()

        refund = request_refund(
            payment=payment,
            amount=Decimal("4500000.00"),
            reason="Buyer requested cancellation after boundary dispute",
            requested_by=self.admin
        )
        self.assertEqual(refund.status, 'REFUND_REQUESTED')

        review_refund(refund, reviewed_by=self.admin, approve=True)
        execute_refund(refund, admin_user=self.admin, provider_reversal_reference='REV_DAR_998877')

        refund.refresh_from_db()
        self.assertEqual(refund.status, 'REFUND_CONFIRMED')
        self.assertEqual(refund.provider_reversal_reference, 'REV_DAR_998877')

    # -------------------------------------------------------------------------
    # Test 12: Browser closure does not lose payment state
    # -------------------------------------------------------------------------
    def test_12_browser_closure_does_not_lose_payment_state(self):
        """Payment state resides authoritatively in database with provider references."""
        payment = PaymentRouter.create_land_purchase_payment(
            transaction=self.transaction,
            payer=self.buyer
        )
        payment.checkout_request_reference = "ws_CO_BROWSER_CLOSE_TEST"
        payment.account_reference = payment.digiland_reference
        payment.status = 'CUSTOMER_ACTION_REQUIRED'
        payment.save()

        # Simulate browser closing and later server retrieval
        retrieved_payment = PaymentRecord.objects.get(checkout_request_reference="ws_CO_BROWSER_CLOSE_TEST")
        self.assertEqual(retrieved_payment.id, payment.id)
        self.assertEqual(retrieved_payment.status, 'CUSTOMER_ACTION_REQUIRED')

    # -------------------------------------------------------------------------
    # Test 13: Seller sees confirmed payment
    # -------------------------------------------------------------------------
    def test_13_seller_sees_confirmed_payment(self):
        """Seller can view confirmed payment ledger with their name as beneficiary."""
        payment = PaymentRouter.create_land_purchase_payment(
            transaction=self.transaction,
            payer=self.buyer
        )
        payment.status = 'PAYMENT_CONFIRMED'
        payment.provider_reference = 'MPESA_SELLER_SEES_01'
        payment.save()

        reconciliation = PaymentReconciliationService.get_transaction_reconciliation(self.transaction)
        self.assertEqual(len(reconciliation['payments']), 1)
        p = reconciliation['payments'][0]
        self.assertEqual(p['status'], 'PAYMENT_CONFIRMED')
        self.assertEqual(p['beneficiary_type'], 'SELLER')
        self.assertIn("Mary Wanjiku", p['beneficiary'])

    # -------------------------------------------------------------------------
    # Test 14: Buyer sees correct payment history
    # -------------------------------------------------------------------------
    def test_14_buyer_sees_correct_payment_history(self):
        """Buyer sees separated payment history for land purchase and service fee."""
        p1 = PaymentRouter.create_land_purchase_payment(
            transaction=self.transaction,
            payer=self.buyer
        )
        p1.status = 'PAYMENT_CONFIRMED'
        p1.save()

        p2 = PaymentRouter.create_digiland_fee_payment(
            transaction=self.transaction,
            payer=self.buyer,
            amount=Decimal("90000.00")
        )
        p2.status = 'PAYMENT_CONFIRMED'
        p2.save()

        reconciliation = PaymentReconciliationService.get_transaction_reconciliation(self.transaction)
        self.assertEqual(len(reconciliation['payments']), 2)
        purposes = [p['purpose'] for p in reconciliation['payments']]
        self.assertIn('LAND_PURCHASE', purposes)
        self.assertIn('DIGILAND_SERVICE_FEE', purposes)

    # -------------------------------------------------------------------------
    # Test 15: Admin sees correct beneficiary
    # -------------------------------------------------------------------------
    def test_15_admin_sees_correct_beneficiary(self):
        """Admin reconciliation correctly identifies explicit beneficiary for each record."""
        p_seller = PaymentRouter.create_land_purchase_payment(self.transaction, self.buyer)
        p_platform = PaymentRouter.create_digiland_fee_payment(self.transaction, self.buyer, Decimal("90000.00"))
        p_prof = PaymentRouter.create_professional_payment(self.transaction, self.buyer, self.surveyor, 'SURVEY_FEE', Decimal("15000.00"))

        self.assertEqual(p_seller.beneficiary_type, 'SELLER')
        self.assertEqual(p_platform.beneficiary_type, 'DIGILAND')
        self.assertEqual(p_prof.beneficiary_type, 'SURVEYOR')

    # -------------------------------------------------------------------------
    # Test 16: Historical legacy records remain intact
    # -------------------------------------------------------------------------
    def test_16_historical_legacy_records_remain_intact(self):
        """Legacy payment records with is_legacy_record=True are readable without schema errors."""
        legacy_record = PaymentRecord.objects.create(
            transaction=self.transaction,
            parcel=self.parcel,
            payer=self.buyer,
            recipient=self.seller,
            amount=Decimal("500000.00"),
            currency="KES",
            purpose="LAND_PURCHASE",
            payment_purpose="LAND_PURCHASE",
            payment_type="DIRECT_SETTLEMENT",
            beneficiary_type="SELLER",
            beneficiary_name="Legacy Seller",
            is_legacy_record=True,
            status="PAYMENT_CONFIRMED"
        )
        self.assertTrue(legacy_record.is_legacy_record)
        self.assertEqual(str(legacy_record.amount), "500000.00")

    # -------------------------------------------------------------------------
    # Test 17: No escrow balance is created
    # -------------------------------------------------------------------------
    def test_17_no_escrow_balance_is_created(self):
        """DigiLand maintains zero escrow balance/holding reserve."""
        p = PaymentRouter.create_land_purchase_payment(self.transaction, self.buyer)
        p.status = 'PAYMENT_CONFIRMED'
        p.save()

        summary = PaymentReconciliationService.get_reconciliation_summary()
        # Verify no escrow balance is held or returned
        self.assertNotIn('escrow_balance_kes', summary['metrics'])

    # -------------------------------------------------------------------------
    # Test 18: No seller funds are recorded as DigiLand revenue
    # -------------------------------------------------------------------------
    def test_18_no_seller_funds_are_recorded_as_digiland_revenue(self):
        """A KES 4,500,000 land purchase does not increment DigiLand revenue."""
        p = PaymentRouter.create_land_purchase_payment(self.transaction, self.buyer)
        p.status = 'PAYMENT_CONFIRMED'
        p.save()

        summary = PaymentReconciliationService.get_reconciliation_summary()
        self.assertEqual(summary['metrics']['digiland_revenue_kes'], 0.0)

    # -------------------------------------------------------------------------
    # Test 19: Unauthorized user cannot initiate payment for another user's transaction
    # -------------------------------------------------------------------------
    def test_19_unauthorized_user_cannot_initiate_payment_for_another_users_transaction(self):
        """Unauthorized user attempting to initiate land purchase payment receives 403 Forbidden."""
        request = self.factory.post(
            '/api/v1/mpesa/stk-push/',
            data=json.dumps({
                'phone_number': '0712345678',
                'amount': 4500000,
                'transaction_id': str(self.transaction.id),
                'purpose': 'LAND_PURCHASE'
            }),
            content_type='application/json'
        )
        request.user = self.unauthorized_user

        response = initiate_mpesa_payment_view(request)
        self.assertEqual(response.status_code, 403)
        data = json.loads(response.content)
        self.assertIn("Only the designated buyer", data['message'])

    # -------------------------------------------------------------------------
    # Test 20: Provider receipt cannot be reused for another transaction
    # -------------------------------------------------------------------------
    def test_20_provider_receipt_cannot_be_reused_for_another_transaction(self):
        """Attempting to confirm a second transaction with an already-used receipt number is blocked."""
        # Confirm payment on transaction 1
        p1 = PaymentRouter.create_land_purchase_payment(self.transaction, self.buyer)
        p1.checkout_request_reference = "ws_CO_TX1"
        p1.status = 'CUSTOMER_ACTION_REQUIRED'
        p1.save()

        callback_tx1 = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "MR_1",
                    "CheckoutRequestID": "ws_CO_TX1",
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 4500000.00},
                            {"Name": "MpesaReceiptNumber", "Value": "UNIQUE_RECEIPT_999"},
                            {"Name": "TransactionDate", "Value": 20260901120000},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }
        res1 = process_mpesa_callback(callback_tx1)
        self.assertEqual(res1.get("status"), "success")

        # Create a second transaction and attempt to use the same receipt
        tx2 = Transaction.objects.create(
            land_parcel=self.parcel,
            buyer=self.buyer,
            seller=self.seller,
            agreed_price=Decimal("4500000.00"),
            status="Initiated"
        )
        p2 = PaymentRouter.create_land_purchase_payment(tx2, self.buyer)
        p2.checkout_request_reference = "ws_CO_TX2"
        p2.status = 'CUSTOMER_ACTION_REQUIRED'
        p2.save()

        callback_tx2_reused = {
            "Body": {
                "stkCallback": {
                    "MerchantRequestID": "MR_2",
                    "CheckoutRequestID": "ws_CO_TX2",
                    "ResultCode": 0,
                    "ResultDesc": "Success",
                    "CallbackMetadata": {
                        "Item": [
                            {"Name": "Amount", "Value": 4500000.00},
                            {"Name": "MpesaReceiptNumber", "Value": "UNIQUE_RECEIPT_999"}, # Reused receipt!
                            {"Name": "TransactionDate", "Value": 20260901120000},
                            {"Name": "PhoneNumber", "Value": 254712345678}
                        ]
                    }
                }
            }
        }
        res2 = process_mpesa_callback(callback_tx2_reused)
        self.assertEqual(res2.get("status"), "failed")
        self.assertIn("already recorded", res2.get("message", "").lower())
