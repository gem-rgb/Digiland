"""Service Fee calculation and management"""

from decimal import Decimal
from django.utils import timezone
from core.models import ServiceFee, Transaction


class ServiceFeeService:
    """Manages transparent service fee calculations"""

    FEES = {
        'platform_service': Decimal('0.04'),        # 4% of land price
        'transaction_coordination': Decimal('0.02'), # 2% of land price
        'payment_processing': Decimal('50'),        # Flat KES 50
        'verification': Decimal('15000'),           # Surveyor boundary & beacon verification, KES 15K
        'due_diligence': Decimal('20000'),          # Advocate legal conveyance, KES 20K
    }

    @staticmethod
    def calculate_fees(transaction, include_verification=True, include_due_diligence=False):
        """Calculate separate financial obligations for a transaction.
        
        Strictly separates:
        1. LAND PURCHASE (Buyer -> Seller)
        2. DIGILAND PLATFORM FEE (Buyer/Seller -> DigiLand)
        3. SURVEYOR FEE (Buyer -> Surveyor)
        4. LEGAL CONVEYANCING FEE (Buyer -> Advocate)
        
        NEVER combines these into a single balance payable to DigiLand.
        """
        land_price = transaction.agreed_price or Decimal('0.00')
        quantize = Decimal('0.01')

        coordination_fee = (land_price * ServiceFeeService.FEES['transaction_coordination']).quantize(quantize)
        survey_fee = (ServiceFeeService.FEES['verification'] if include_verification else Decimal('0')).quantize(quantize)
        legal_fee = (ServiceFeeService.FEES['due_diligence'] if include_due_diligence else Decimal('0')).quantize(quantize)
        processing_fee = ServiceFeeService.FEES['payment_processing'].quantize(quantize)

        seller_name = (
            transaction.seller.get_full_name() or transaction.seller.email
            if transaction and transaction.seller else 'Land Seller'
        )

        obligations_schedule = [
            {
                'purpose': 'LAND_PURCHASE',
                'label': 'Land Purchase Consideration',
                'beneficiary': seller_name,
                'beneficiary_type': 'SELLER',
                'amount': float(land_price),
                'currency': 'KES',
                'is_digiland_revenue': False,
                'payee_note': 'Paid directly to seller upon agreed terms',
            },
            {
                'purpose': 'DIGILAND_SERVICE_FEE',
                'label': 'DigiLand Platform Facilitation Fee',
                'beneficiary': 'DigiLand Ltd',
                'beneficiary_type': 'DIGILAND',
                'amount': float(coordination_fee),
                'currency': 'KES',
                'is_digiland_revenue': True,
                'payee_note': 'Paid to DigiLand for platform facilitation and verified audit records',
            },
        ]

        if include_verification:
            obligations_schedule.append({
                'purpose': 'SURVEY_FEE',
                'label': 'Cadastral Boundary & Beacon Survey',
                'beneficiary': 'Licensed Land Surveyor',
                'beneficiary_type': 'SURVEYOR',
                'amount': float(survey_fee),
                'currency': 'KES',
                'is_digiland_revenue': False,
                'payee_note': 'Paid directly to assigned licensed surveyor',
            })

        if include_due_diligence:
            obligations_schedule.append({
                'purpose': 'LEGAL_FEE',
                'label': 'Advocate Conveyancing & Legal Signoff',
                'beneficiary': 'Conveyancing Advocate',
                'beneficiary_type': 'ADVOCATE',
                'amount': float(legal_fee),
                'currency': 'KES',
                'is_digiland_revenue': False,
                'payee_note': 'Paid directly to conveyancing advocate',
            })

        total_third_party_fees = survey_fee + legal_fee + processing_fee
        total_fees = coordination_fee + total_third_party_fees
        total_buyer_obligations = land_price + total_fees

        fees = {
            'land_price': land_price,
            'platform_service_fee': (land_price * ServiceFeeService.FEES['platform_service']).quantize(quantize),
            'coordination_fee': coordination_fee,
            'escrow_holding_fee': coordination_fee, # Backward-compat key
            'escrow_fee': coordination_fee,         # Backward-compat key
            'payment_processing_fee': processing_fee,
            'verification_fee': survey_fee,
            'survey_fee': survey_fee,
            'due_diligence_fee': legal_fee,
            'legal_fee': legal_fee,
            'total_fees': total_fees,
            'digiland_platform_fee_total': coordination_fee,
            'total_buyer_obligations': total_buyer_obligations,
            'grand_total': total_buyer_obligations, # Backward-compat alias for total obligations
            'total_payable': total_buyer_obligations,
            'obligations_schedule': obligations_schedule,
            'non_custodial_notice': 'These represent distinct financial obligations to distinct beneficiaries. DigiLand does not hold land purchase funds in escrow.',
        }

        return fees

    @staticmethod
    def get_fee_explanations():
        """
        Get user-friendly explanations for each fee type.
        Used in UI for education.
        """
        explanations = {
            'platform_service': {
                'label': 'Platform Service Fee',
                'percent': '4%',
                'what': 'Covers platform operations, AI recommendations, buyer discovery features',
                'why': 'Ensures continuous improvement of the marketplace and seller visibility',
            },
            'transaction_coordination': {
                'label': 'Transaction & Verification Coordination Fee',
                'percent': '2%',
                'what': 'Multi-layer parcel verification, document screening, and transaction record management',
                'why': 'Coordinates independent verification checkpoints and traceable transaction records between parties',
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
        # Backward-compatibility alias
        explanations['escrow_holding'] = explanations['transaction_coordination']
        return explanations


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
        platform_fee = fees_data.get('platform_service_fee') or fees_data.get('platform_fee', Decimal('0'))
        coordination_fee = fees_data.get('coordination_fee') or fees_data.get('escrow_fee') or fees_data.get('escrow_holding_fee', Decimal('0'))
        escrow_fee = coordination_fee
        processing_fee = fees_data.get('payment_processing_fee') or fees_data.get('processing_fee', Decimal('0'))
        verification_fee = fees_data.get('verification_fee') or fees_data.get('legal_verification_fee', Decimal('0'))
        due_diligence_fee = fees_data.get('due_diligence_fee', Decimal('0'))
        total_fees = fees_data.get('total_fees', Decimal('0'))

        service_fee, created = ServiceFee.objects.get_or_create(
            transaction=transaction,
            defaults={
                'platform_fee': platform_fee,
                'coordination_fee': coordination_fee,
                'escrow_fee': escrow_fee,
                'processing_fee': processing_fee,
                'verification_fee': verification_fee,
                'due_diligence_fee': due_diligence_fee,
                'total_fees': total_fees,
                'breakdown': fees_data,
            }
        )

        if not created:
            # Update existing fees
            service_fee.platform_fee = platform_fee
            service_fee.coordination_fee = coordination_fee
            service_fee.escrow_fee = escrow_fee
            service_fee.processing_fee = processing_fee
            service_fee.verification_fee = verification_fee
            service_fee.due_diligence_fee = due_diligence_fee
            service_fee.total_fees = total_fees
            service_fee.breakdown = fees_data
            service_fee.save()

        # Sync coordination_fee back to transaction record
        try:
            transaction.coordination_fee = coordination_fee
            transaction.platform_service_fee = platform_fee
            transaction.total_payable = fees_data.get('total_payable', transaction.total_payable)
            transaction.save(update_fields=['coordination_fee', 'platform_service_fee', 'total_payable'])
        except Exception:
            pass

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
