"""
Payment Reconciliation Service for DigiLand (Non-Custodial Architecture).

Provides comprehensive reconciliation, traceability, and audit reporting
for all confirmed payments, ensuring clear separation between:
1. Land Purchase Funds
2. DigiLand Platform/Service Fees
3. Professional Service Fees
4. Payment Records
5. Transaction Status

DigiLand is not an escrow provider and does not hold customer funds.
"""

from decimal import Decimal
import logging
from django.db.models import Q, Sum, Count
from django.utils import timezone
from core.models import PaymentRecord, Transaction, RefundRecord, LandParcel, User, AuditLog

logger = logging.getLogger(__name__)


class PaymentReconciliationService:
    """Reconciliation and audit ledger for DigiLand payments."""

    @staticmethod
    def get_transaction_reconciliation(transaction):
        """
        Produce a full payment reconciliation ledger for a transaction.
        Maps all payment intents and confirmed receipts against agreed amounts.
        """
        payments = PaymentRecord.objects.filter(transaction=transaction).order_by('created_at')
        refunds = RefundRecord.objects.filter(transaction=transaction).order_by('created_at')

        confirmed_payments = payments.filter(status__in=['PAYMENT_CONFIRMED', 'CONFIRMED'])
        
        # Categorized confirmed amounts
        land_funds_confirmed = confirmed_payments.filter(purpose='LAND_PURCHASE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        service_fees_confirmed = confirmed_payments.filter(purpose='DIGILAND_SERVICE_FEE').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        professional_fees_confirmed = confirmed_payments.filter(
            purpose__in=['SURVEY_FEE', 'LEGAL_FEE', 'INSPECTION_FEE']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_confirmed = confirmed_payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        total_refunded = refunds.filter(status='REFUND_CONFIRMED').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Outstanding balances
        land_price = getattr(transaction, 'agreed_price', Decimal('0.00')) or Decimal('0.00')
        platform_fee = getattr(transaction, 'coordination_fee_safe', Decimal('0.00')) or Decimal('0.00')

        return {
            'transaction_id': str(transaction.id),
            'transaction_reference': getattr(transaction, 'transaction_reference', None) or f"DL-TXN-{str(transaction.id)[:8]}",
            'status': transaction.status,
            'buyer_email': transaction.buyer.email if transaction.buyer else None,
            'seller_email': transaction.seller.email if transaction.seller else None,
            'parcel_number': transaction.land_parcel.parcel_number if transaction.land_parcel else None,
            'financials': {
                'agreed_land_price': float(land_price),
                'platform_coordination_fee': float(platform_fee),
                'total_payable': float(getattr(transaction, 'total_payable', land_price + platform_fee) or (land_price + platform_fee)),
                'land_funds_confirmed': float(land_funds_confirmed),
                'service_fees_confirmed': float(service_fees_confirmed),
                'professional_fees_confirmed': float(professional_fees_confirmed),
                'total_confirmed_received': float(total_confirmed),
                'total_refunded': float(total_refunded),
                'net_reconciled': float(total_confirmed - total_refunded),
                'is_fully_paid': land_funds_confirmed >= land_price,
            },
            'payments': [
                {
                    'id': str(p.id),
                    'digiland_reference': p.digiland_reference,
                    'purpose': p.purpose,
                    'purpose_label': p.get_purpose_display(),
                    'payment_type': getattr(p, 'payment_type', 'DIRECT_SETTLEMENT'),
                    'beneficiary': p.beneficiary,
                    'beneficiary_name': getattr(p, 'beneficiary_name', ''),
                    'beneficiary_type': getattr(p, 'beneficiary_type', 'SELLER'),
                    'provider': p.payment_provider,
                    'provider_reference': p.provider_reference,
                    'amount': float(p.amount),
                    'currency': p.currency,
                    'status': p.status,
                    'status_label': p.get_status_display(),
                    'initiated_at': p.initiated_at.isoformat() if p.initiated_at else None,
                    'confirmed_at': p.confirmed_at.isoformat() if p.confirmed_at else None,
                }
                for p in payments
            ],
            'refunds': [
                {
                    'id': str(r.id),
                    'refund_reference': r.refund_reference,
                    'amount': float(r.amount),
                    'currency': r.currency,
                    'status': r.status,
                    'status_label': r.get_status_display(),
                    'reason': r.reason,
                    'provider_reversal_reference': r.provider_reversal_reference,
                    'created_at': r.created_at.isoformat(),
                }
                for r in refunds
            ],
        }

    @staticmethod
    def search_payments(
        transaction_ref=None,
        provider_receipt=None,
        buyer_email=None,
        seller_email=None,
        parcel_number=None,
        amount_min=None,
        amount_max=None,
        status=None,
        purpose=None,
        start_date=None,
        end_date=None,
        limit=100
    ):
        """
        Search payment records across all parameters requested in the reconciliation layer.
        """
        qs = PaymentRecord.objects.select_related('transaction', 'payer', 'recipient', 'parcel').all()

        if transaction_ref:
            qs = qs.filter(
                Q(transaction__transaction_reference__icontains=transaction_ref) |
                Q(transaction__id__icontains=transaction_ref) |
                Q(digiland_reference__icontains=transaction_ref)
            )

        if provider_receipt:
            qs = qs.filter(
                Q(provider_reference__icontains=provider_receipt) |
                Q(checkout_request_reference__icontains=provider_receipt)
            )

        if buyer_email:
            qs = qs.filter(payer__email__icontains=buyer_email)

        if seller_email:
            qs = qs.filter(recipient__email__icontains=seller_email)

        if parcel_number:
            qs = qs.filter(parcel__parcel_number__icontains=parcel_number)

        if amount_min is not None:
            try:
                qs = qs.filter(amount__gte=Decimal(str(amount_min)))
            except Exception:
                pass

        if amount_max is not None:
            try:
                qs = qs.filter(amount__lte=Decimal(str(amount_max)))
            except Exception:
                pass

        if status:
            # Match either new status or legacy alias
            if status == 'CONFIRMED':
                qs = qs.filter(status__in=['PAYMENT_CONFIRMED', 'CONFIRMED'])
            elif status == 'FAILED':
                qs = qs.filter(status__in=['PAYMENT_FAILED', 'FAILED'])
            elif status == 'PENDING':
                qs = qs.filter(status__in=['PAYMENT_PENDING', 'PAYMENT_INITIATED', 'CUSTOMER_ACTION_REQUIRED', 'PAYMENT_PROCESSING', 'INITIATED'])
            else:
                qs = qs.filter(status__iexact=status)

        if purpose:
            qs = qs.filter(purpose=purpose)

        if start_date:
            qs = qs.filter(created_at__gte=start_date)

        if end_date:
            qs = qs.filter(created_at__lte=end_date)

        return qs.order_by('-created_at')[:limit]

    @staticmethod
    def get_reconciliation_summary():
        """
        Compute platform-wide reconciliation summary metrics for executive/admin dashboards.
        Zero escrow balances or funds held.
        """
        now = timezone.now()
        thirty_days_ago = now - timezone.timedelta(days=30)

        # Payment metrics
        confirmed_qs = PaymentRecord.objects.filter(status__in=['PAYMENT_CONFIRMED', 'CONFIRMED'])
        pending_qs = PaymentRecord.objects.filter(
            status__in=['CREATED', 'PAYMENT_PENDING', 'PAYMENT_INITIATED', 'CUSTOMER_ACTION_REQUIRED', 'PAYMENT_PROCESSING', 'INITIATED']
        )
        failed_qs = PaymentRecord.objects.filter(status__in=['PAYMENT_FAILED', 'FAILED', 'PAYMENT_CANCELLED', 'PAYMENT_EXPIRED'])

        confirmed_volume = confirmed_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        confirmed_count = confirmed_qs.count()
        pending_count = pending_qs.count()
        failed_count = failed_qs.count()

        # Categorized confirmed amounts
        land_transaction_value = confirmed_qs.filter(
            Q(purpose='LAND_PURCHASE') | Q(payment_purpose='LAND_PURCHASE')
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        service_revenue = confirmed_qs.filter(
            Q(purpose='DIGILAND_SERVICE_FEE') | Q(payment_purpose='DIGILAND_SERVICE_FEE')
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        professional_fees = confirmed_qs.filter(
            Q(purpose__in=['SURVEY_FEE', 'LEGAL_FEE', 'INSPECTION_FEE', 'ADDITIONAL_DUE_DILIGENCE_FEE']) |
            Q(payment_purpose__in=['SURVEY_FEE', 'LEGAL_FEE', 'INSPECTION_FEE', 'ADDITIONAL_DUE_DILIGENCE_FEE'])
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        total_confirmed = confirmed_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        total_refunded = RefundRecord.objects.filter(status='REFUND_CONFIRMED').aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Refunds metrics
        refunds_qs = RefundRecord.objects.all()
        confirmed_refunds_qs = refunds_qs.filter(status='REFUND_CONFIRMED')
        refunds_count = refunds_qs.count()
        refunds_volume = confirmed_refunds_qs.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')

        # Transactions metrics
        total_txns = Transaction.objects.count()
        completed_txns = Transaction.objects.filter(status='Completed').count()
        active_txns = Transaction.objects.filter(status__in=['Initiated', 'Payment_Confirmed', 'Under_Verification']).count()
        disputed_txns = Transaction.objects.filter(status='Disputed').count()

        # Parcels verification
        total_parcels = LandParcel.objects.count()
        verified_parcels = LandParcel.objects.filter(verification_status='Verified').count()
        verification_rate = (verified_parcels / total_parcels * 100) if total_parcels > 0 else 0.0

        return {
            'metrics': {
                # 4 DISTINCT METRICS (Section 14)
                'land_transaction_value_kes': float(land_transaction_value),
                'digiland_revenue_kes': float(service_revenue),
                'professional_services_value_kes': float(professional_fees),
                'total_payment_volume_kes': float(total_confirmed),

                # Supporting operational metrics
                'confirmed_payments_count': confirmed_count,
                'confirmed_payments_volume_kes': float(total_confirmed),
                'pending_payments_count': pending_count,
                'failed_payments_count': failed_count,
                'refunds_count': refunds_count,
                'refunds_volume_kes': float(refunds_volume),
                'digiland_service_revenue_kes': float(service_revenue),
                'land_gmv_kes': float(land_transaction_value),
                'total_transaction_volume': total_txns,
                'completed_transactions_count': completed_txns,
                'active_transactions_count': active_txns,
                'open_disputes_count': disputed_txns,
                'verification_completion_pct': round(verification_rate, 1),
            },
            'reconciliation_timestamp': now.isoformat(),
        }
