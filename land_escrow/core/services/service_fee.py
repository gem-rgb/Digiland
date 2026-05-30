"""Service Fee calculation and management"""

from decimal import Decimal
from django.utils import timezone
from core.models import ServiceFee, Transaction


class ServiceFeeService:
    """Manages transparent service fee calculations"""

    FEES = {
        'platform_service': Decimal('0.04'),        # 4% of land price
        'escrow_holding': Decimal('0.02'),          # 2% of land price
        'payment_processing': Decimal('50'),        # Flat KES 50
        'verification': Decimal('10000'),           # Optional, KES 10K
        'due_diligence': Decimal('20000'),          # Optional, KES 20K
    }

    @staticmethod
    def calculate_fees(transaction, include_verification=True, include_due_diligence=False):
        """
        Calculate all fees for a transaction.
        Returns dict with breakdown and totals.
        """
        land_price = transaction.agreed_price
        quantize = Decimal('0.01')

        fees = {
            'land_price': land_price,
            'platform_service_fee': (land_price * ServiceFeeService.FEES['platform_service']).quantize(quantize),
            'escrow_holding_fee': (land_price * ServiceFeeService.FEES['escrow_holding']).quantize(quantize),
            'payment_processing_fee': ServiceFeeService.FEES['payment_processing'].quantize(quantize),
            'verification_fee': (ServiceFeeService.FEES['verification'] if include_verification else Decimal('0')).quantize(quantize),
            'due_diligence_fee': (ServiceFeeService.FEES['due_diligence'] if include_due_diligence else Decimal('0')).quantize(quantize),
        }
        fees['escrow_fee'] = fees['escrow_holding_fee']

        fees['total_fees'] = (
            fees['platform_service_fee'] +
            fees['escrow_holding_fee'] +
            fees['payment_processing_fee'] +
            fees['verification_fee'] +
            fees['due_diligence_fee']
        )

        fees['grand_total'] = (land_price + fees['total_fees']).quantize(quantize)
        fees['total_payable'] = fees['grand_total']

        return fees

    @staticmethod
    def get_fee_explanations():
        """
        Get user-friendly explanations for each fee type.
        Used in UI for education.
        """
        return {
            'platform_service': {
                'label': 'Platform Service Fee',
                'percent': '4%',
                'what': 'Covers platform operations, AI recommendations, buyer discovery features',
                'why': 'Ensures continuous improvement of the marketplace and seller visibility',
            },
            'escrow_holding': {
                'label': 'Escrow Holding Fee',
                'percent': '2%',
                'what': 'Secure fund holding, 7-day buyer validation protection, escrow account management',
                'why': 'Protects both buyer and seller during transaction, prevents fraud',
            },
            'payment_processing': {
                'label': 'Payment Processing Fee',
                'amount': 'KES 50 flat',
                'what': 'Payment gateway transaction costs (Paystack, M-Pesa, KCB)',
                'why': 'Covers payment processor fees for secure fund transfers',
            },
            'verification': {
                'label': 'Verification Fee',
                'amount': 'KES 10,000 (optional)',
                'what': 'Agent land verification costs, document review, compliance checks',
                'why': 'Ensures listing authenticity and protects against fraud',
            },
            'due_diligence': {
                'label': 'Due Diligence Fee',
                'amount': 'KES 20,000 (optional)',
                'what': 'Legal document review, title deed verification, comprehensive due diligence',
                'why': 'Provides additional legal and compliance assurance',
            },
        }

    @staticmethod
    def record_fees_on_transaction(transaction, include_verification=True, include_due_diligence=False, fees_data=None):
        """
        Calculate and record fees for a transaction.
        Creates ServiceFee record.
        """
        fees_data = fees_data or ServiceFeeService.calculate_fees(
            transaction,
            include_verification=include_verification,
            include_due_diligence=include_due_diligence
        )
        escrow_fee = fees_data.get('escrow_fee')
        if escrow_fee is None:
            escrow_fee = fees_data.get('escrow_holding_fee', Decimal('0'))

        service_fee, created = ServiceFee.objects.get_or_create(
            transaction=transaction,
            defaults={
                'platform_fee': fees_data['platform_service_fee'],
                'escrow_fee': escrow_fee,
                'processing_fee': fees_data['payment_processing_fee'],
                'verification_fee': fees_data['verification_fee'],
                'due_diligence_fee': fees_data['due_diligence_fee'],
                'total_fees': fees_data['total_fees'],
                'breakdown': fees_data,
            }
        )

        if not created:
            # Update existing fees
            service_fee.platform_fee = fees_data['platform_service_fee']
            service_fee.escrow_fee = escrow_fee
            service_fee.processing_fee = fees_data['payment_processing_fee']
            service_fee.verification_fee = fees_data['verification_fee']
            service_fee.due_diligence_fee = fees_data['due_diligence_fee']
            service_fee.total_fees = fees_data['total_fees']
            service_fee.breakdown = fees_data
            service_fee.save()

        return service_fee

    @staticmethod
    def get_platform_revenue(days=30):
        """
        Calculate total platform fees collected over time period.
        """
        from django.db.models import Sum
        from datetime import timedelta

        start_date = timezone.now() - timedelta(days=days)

        service_fees = ServiceFee.objects.filter(
            created_at__gte=start_date
        ).aggregate(
            total_platform_fees=Sum('platform_fee'),
            total_escrow_fees=Sum('escrow_fee'),
            total_processing_fees=Sum('processing_fee'),
            total_verification_fees=Sum('verification_fee'),
            total_due_diligence_fees=Sum('due_diligence_fee'),
        )

        platform_fees = service_fees.get('total_platform_fees') or Decimal('0')
        escrow_fees = service_fees.get('total_escrow_fees') or Decimal('0')
        processing_fees = service_fees.get('total_processing_fees') or Decimal('0')
        verification_fees = service_fees.get('total_verification_fees') or Decimal('0')
        due_diligence_fees = service_fees.get('total_due_diligence_fees') or Decimal('0')

        return {
            'platform_fees': platform_fees,
            'escrow_fees': escrow_fees,
            'processing_fees': processing_fees,
            'verification_fees': verification_fees,
            'due_diligence_fees': due_diligence_fees,
            'total': platform_fees + escrow_fees + processing_fees + verification_fees + due_diligence_fees,
        }

    @staticmethod
    def get_monthly_revenue_breakdown(months=12):
        """
        Get fee revenue broken down by month.
        """
        from django.db.models import Sum
        from django.db.models.functions import TruncMonth
        import calendar

        fee_by_month = ServiceFee.objects.filter(
            created_at__isnull=False
        ).annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            total=Sum('total_fees'),
            platform=Sum('platform_fee'),
            escrow=Sum('escrow_fee'),
            processing=Sum('processing_fee'),
            verification=Sum('verification_fee'),
            due_diligence=Sum('due_diligence_fee'),
        ).order_by('month')

        return [{
            'month': str(item['month'].strftime('%Y-%m')) if item['month'] else 'Unknown',
            'platform_fees': item['platform'] or Decimal('0'),
            'escrow_fees': item['escrow'] or Decimal('0'),
            'processing_fees': item['processing'] or Decimal('0'),
            'verification_fees': item['verification'] or Decimal('0'),
            'due_diligence_fees': item['due_diligence'] or Decimal('0'),
            'total_fees': item['total'] or Decimal('0'),
        } for item in fee_by_month]
