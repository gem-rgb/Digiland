from decimal import Decimal
from unittest.mock import patch
from django.test import TestCase
from django.utils import timezone
from core.models import User, LandParcel, Transaction, PaymentRecord, RefundRecord, TransactionMilestone
from core.services.payment import (
    create_payment_intent,
    initiate_mpesa_stk_push,
    process_mpesa_callback,
    query_payment_status,
    request_refund,
    review_refund,
    execute_refund,
    DarajaAPI,
)
from core.services.payment_reconciliation import PaymentReconciliationService


class MpesaPaymentArchitectureTests(TestCase):
    def setUp(self):
        self.seller = User.objects.create_user(
            email="seller@example.com",
            password="testpassword123",
            role="Seller"
        )
        self.buyer = User.objects.create_user(
            email="buyer@example.com",
            password="testpassword123",
            role="Buyer"
        )
        self.admin = User.objects.create_superuser(
            email="admin@example.com",
            password="adminpassword123"
        )
        self.parcel = LandParcel.objects.create(
            parcel_number="NAIROBI/BLOCK100/999",
            land_size=Decimal("0.5"),
            asking_price=Decimal("1500000.00"),
            listed_by=self.seller,
            verification_status="Verified",
            county="Nairobi",
            constituency="Westlands",
            ward="Parklands",
            land_use_type="Residential",
            registered_owner_id="12345678"
        )
        self.transaction = Transaction.objects.create(
            land_parcel=self.parcel,
            buyer=self.buyer,
            seller=self.seller,
            agreed_price=Decimal("1500000.00"),
            status="Initiated"
        )

    def test_01_transaction_reference_auto_generation(self):
        """Transaction generates unique DL-TXN-YYYY-XXXXXX reference upon creation."""
        self.assertIsNotNone(self.transaction.transaction_reference)
        self.assertTrue(self.transaction.transaction_reference.startswith("DL-TXN-"))
        parts = self.transaction.transaction_reference.split("-")
        self.assertEqual(len(parts), 4)
        self.assertEqual(parts[0], "DL")
        self.assertEqual(parts[1], "TXN")
        self.assertEqual(parts[2], str(timezone.now().year))
        self.assertEqual(len(parts[3]), 6)

    def test_02_payment_intent_purpose_separation(self):
        """Payment intents clearly distinguish Land Purchase, Platform Fees, and Professional Fees."""
        # 1. Land purchase intent
        payment_land = create_payment_intent(
            transaction=self.transaction,
            payer=self.buyer,
            amount=Decimal("1500000.00"),
            purpose="LAND_PURCHASE"
        )
        self.assertEqual(payment_land.purpose, "LAND_PURCHASE")
        self.assertEqual(payment_land.status, "CREATED")
        self.assertEqual(payment_land.recipient, self.seller)

        # 2. Platform service fee intent
        payment_fee = create_payment_intent(
            transaction=self.transaction,
            payer=self.buyer,
            amount=Decimal("30000.00"),
            purpose="DIGILAND_SERVICE_FEE"
        )
        self.assertEqual(payment_fee.purpose, "DIGILAND_SERVICE_FEE")
        self.assertEqual(payment_fee.status, "CREATED")
        self.assertIsNone(payment_fee.recipient)

        # 3. Professional surveyor fee intent
        payment_survey = create_payment_intent(
            transaction=self.transaction,
            payer=self.buyer,
            amount=Decimal("25000.00"),
            purpose="SURVEY_FEE"
        )
        self.assertEqual(payment_survey.purpose, "SURVEY_FEE")
        self.assertEqual(payment_survey.status, "CREATED")

    @patch.object(DarajaAPI, 'stk_push')
    def test_03_initiate_mpesa_stk_push(self, mock_stk):
        """STK push sets checkout request reference and moves payment state to CUSTOMER_ACTION_REQUIRED."""
        mock_stk.return_value = {
            "status": "success",
            "ResponseCode": "0",
            "checkout_request_id": "ws_CO_TEST_12345678",
            "merchant_request_id": "MR_TEST_9999",
            "customer_message": "Success. Request accepted for processing"
        }

        payment = create_payment_intent(
            transaction=self.transaction,
            payer=self.buyer,
            amount=Decimal("1500000.00"),
            purpose="LAND_PURCHASE"
        )

        res = initiate_mpesa_stk_push(payment, "254712345678")
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["checkout_request_id"], "ws_CO_TEST_12345678")

        payment.refresh_from_db()
        self.assertEqual(payment.status, "CUSTOMER_ACTION_REQUIRED")
        self.assertEqual(payment.checkout_request_reference, "ws_CO_TEST_12345678")
        self.assertIsNotNone(payment.initiated_at)

    def test_04_mpesa_callback_confirmation_and_idempotency(self):
        """Callback confirms payment, verifies amount, advances transaction, and is strictly idempotent."""
        payment = create_payment_intent(
            transaction=self.transaction,
            payer=self.buyer,
            amount=Decimal("1500000.00"),
            purpose="LAND_PURCHASE"
        )
        payment.status = "CUSTOMER_ACTION_REQUIRED"
        payment.checkout_request_reference = "ws_CO_CALLBACK_TEST_001"
        payment.save()

        callback_data = {
            "CheckoutRequestID": "ws_CO_CALLBACK_TEST_001",
            "ResultCode": 0,
            "ResultDesc": "The service request is processed successfully.",
            "CallbackMetadata": {
                "Item": [
                    {"Name": "Amount", "Value": 1500000.00},
                    {"Name": "MpesaReceiptNumber", "Value": "QGH789KLMN"},
                    {"Name": "TransactionDate", "Value": 20260901170000},
                    {"Name": "PhoneNumber", "Value": 254712345678}
                ]
            }
        }

        # First call: Confirmation
        res1 = process_mpesa_callback(callback_data)
        self.assertEqual(res1["status"], "success")
        self.assertEqual(res1["receipt"], "QGH789KLMN")

        payment.refresh_from_db()
        self.assertEqual(payment.status, "PAYMENT_CONFIRMED")
        self.assertEqual(payment.provider_reference, "QGH789KLMN")
        self.assertIsNotNone(payment.confirmed_at)

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, "Payment_Confirmed")
        self.assertEqual(self.transaction.payment_reference, "QGH789KLMN")

        # Verify milestone 13
        milestone = TransactionMilestone.objects.filter(
            transaction=self.transaction,
            milestone_code="PAYMENT_CONFIRMED"
        ).first()
        self.assertIsNotNone(milestone)
        self.assertEqual(milestone.status, "COMPLETED")

        # Second call: Idempotent duplicate check
        res2 = process_mpesa_callback(callback_data)
        self.assertEqual(res2["status"], "duplicate_ignored")

    def test_05_underpayment_detection(self):
        """Rejects confirmation if callback amount is less than expected payment amount."""
        payment = create_payment_intent(
            transaction=self.transaction,
            payer=self.buyer,
            amount=Decimal("1500000.00"),
            purpose="LAND_PURCHASE"
        )
        payment.status = "CUSTOMER_ACTION_REQUIRED"
        payment.checkout_request_reference = "ws_CO_UNDERPAY_TEST"
        payment.save()

        underpay_callback = {
            "CheckoutRequestID": "ws_CO_UNDERPAY_TEST",
            "ResultCode": 0,
            "ResultDesc": "Success",
            "CallbackMetadata": {
                "Item": [
                    {"Name": "Amount", "Value": 50000.00},  # Underpaid
                    {"Name": "MpesaReceiptNumber", "Value": "UNDERPAY001"},
                    {"Name": "PhoneNumber", "Value": 254712345678}
                ]
            }
        }

        res = process_mpesa_callback(underpay_callback)
        self.assertEqual(res["status"], "failed")
        self.assertIn("Underpayment", res["message"])

        payment.refresh_from_db()
        self.assertEqual(payment.status, "PAYMENT_FAILED")
        self.assertIn("Underpayment", payment.failure_reason)

    def test_06_browser_closure_authoritative_status_polling(self):
        """Authoritative status query retrieves state after customer authorization."""
        payment = create_payment_intent(
            transaction=self.transaction,
            payer=self.buyer,
            amount=Decimal("1500000.00"),
            purpose="LAND_PURCHASE"
        )
        payment.status = "PAYMENT_CONFIRMED"
        payment.provider_reference = "MPESA-RECOVERED-123"
        payment.confirmed_at = timezone.now()
        payment.save()

        status_res = query_payment_status(str(payment.id))
        self.assertEqual(status_res["status"], "success")
        self.assertTrue(status_res["is_confirmed"])
        self.assertEqual(status_res["provider_reference"], "MPESA-RECOVERED-123")

    def test_07_payment_reconciliation_service_and_search(self):
        """Reconciliation service provides complete traceability and summary metrics."""
        payment = create_payment_intent(
            transaction=self.transaction,
            payer=self.buyer,
            amount=Decimal("1500000.00"),
            purpose="LAND_PURCHASE"
        )
        payment.status = "PAYMENT_CONFIRMED"
        payment.provider_reference = "REC-SEARCH-999"
        payment.confirmed_at = timezone.now()
        payment.save()

        # Search by transaction reference
        results = PaymentReconciliationService.search_payments(
            transaction_ref=self.transaction.transaction_reference
        )
        self.assertTrue(len(results) >= 1)
        self.assertEqual(results[0].provider_reference, "REC-SEARCH-999")

        # Search by receipt
        receipt_results = PaymentReconciliationService.search_payments(
            provider_receipt="REC-SEARCH-999"
        )
        self.assertEqual(len(receipt_results), 1)

        # Ledger breakdown
        ledger = PaymentReconciliationService.get_transaction_reconciliation(self.transaction)
        self.assertEqual(ledger["transaction_reference"], self.transaction.transaction_reference)
        self.assertEqual(ledger["financials"]["land_funds_confirmed"], 1500000.0)
        self.assertTrue(ledger["financials"]["is_fully_paid"])

        # Platform summary metrics
        summary = PaymentReconciliationService.get_reconciliation_summary()
        self.assertTrue(summary["metrics"]["confirmed_payments_count"] >= 1)
        self.assertTrue(summary["metrics"]["land_gmv_kes"] >= 1500000.0)

    def test_08_refund_lifecycle_state_machine(self):
        """Refund workflow moves through requested, review/approved, and confirmed reversal."""
        payment = create_payment_intent(
            transaction=self.transaction,
            payer=self.buyer,
            amount=Decimal("1500000.00"),
            purpose="LAND_PURCHASE"
        )
        payment.status = "PAYMENT_CONFIRMED"
        payment.provider_reference = "CONFIRMED-BEFORE-REFUND"
        payment.save()

        # 1. Request refund
        refund = request_refund(payment, requested_by=self.buyer, reason="Survey boundary mismatch")
        self.assertEqual(refund.status, "REFUND_REQUESTED")
        self.assertTrue(refund.refund_reference.startswith("DL-RFD-"))

        # 2. Review refund
        review_refund(refund, reviewed_by=self.admin, approve=True, notes="Verified valid claim")
        refund.refresh_from_db()
        self.assertEqual(refund.status, "REFUND_APPROVED")
        self.assertEqual(refund.reviewed_by, self.admin)

        # 3. Execute refund
        exec_res = execute_refund(refund, admin_user=self.admin, provider_reversal_reference="REV-SBN-777")
        self.assertEqual(exec_res["status"], "success")

        refund.refresh_from_db()
        self.assertEqual(refund.status, "REFUND_CONFIRMED")
        self.assertEqual(refund.provider_reversal_reference, "REV-SBN-777")

        payment.refresh_from_db()
        self.assertEqual(payment.status, "PAYMENT_REVERSED")

        self.transaction.refresh_from_db()
        self.assertEqual(self.transaction.status, "Reversed")
