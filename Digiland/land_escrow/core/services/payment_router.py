"""Payment Routing Abstraction for DigiLand Non-Custodial Direct Settlement Architecture.

Strictly separates:
1. LAND PURCHASE MONEY (Buyer -> Seller; DIRECT_SETTLEMENT)
2. DIGILAND SERVICE FEES (Buyer/Seller -> DigiLand; PLATFORM_COLLECTION)
3. PROFESSIONAL SERVICE FEES (Buyer -> Professional Provider; PROFESSIONAL_PAYMENT)

DigiLand NEVER takes custody of land purchase funds and NEVER creates an internal escrow balance.
"""

from decimal import Decimal
import logging
from typing import Dict, Any, Optional
from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.utils import timezone
from core.models import User, Transaction, LandParcel, PaymentRecord

logger = logging.getLogger(__name__)


class PaymentRouter:
    """Authoritative routing layer that determines payer, beneficiary, purpose, amount, 

    route, and provider parameters for every financial event in DigiLand.
    """

    ROUTES = {
        'DIRECT_SETTLEMENT': 'Direct Buyer-to-Seller Settlement',
        'PLATFORM_COLLECTION': 'DigiLand Platform Revenue Collection',
        'PROFESSIONAL_PAYMENT': 'Direct Buyer-to-Professional Payment',
    }

    PURPOSES = {
        'LAND_PURCHASE': 'Land Purchase Consideration',
        'DIGILAND_SERVICE_FEE': 'DigiLand Platform Coordination Fee',
        'SURVEY_FEE': 'Surveyor Boundary & Beacon Verification Fee',
        'LEGAL_FEE': 'Advocate Conveyancing & Legal Signoff Fee',
        'INSPECTION_FEE': 'Field Inspection Agent Fee',
        'ADDITIONAL_DUE_DILIGENCE_FEE': 'Specialist Due Diligence Fee',
        'OTHER': 'Other Approved Professional Fee',
    }

    @classmethod
    def create_land_purchase_payment(
        cls,
        transaction: Transaction,
        payer: User,
        amount: Optional[Decimal] = None,
        provider: str = 'MPESA',
        notes: Optional[str] = None
    ) -> PaymentRecord:
        """Creates a Land Purchase payment intent.
        
        FLOW A: BUYER -> SELLER
        - Beneficiary: Seller (explicitly bound to transaction.seller)
        - Payer: Buyer (enforces payer == transaction.buyer)
        - Amount: Agreed land price (backend authoritative; cannot be modified by buyer)
        - Purpose: LAND_PURCHASE
        - Route: DIRECT_SETTLEMENT
        
        This money is NOT DigiLand revenue and is NEVER held by DigiLand.
        """
        if payer != transaction.buyer:
            logger.warning(f"Unauthorized payment creation attempt by {payer} on transaction {transaction.transaction_reference}")
            raise PermissionDenied("Only the designated buyer can initiate the land purchase payment.")

        seller = transaction.seller
        if not seller:
            raise ValidationError("Transaction has no designated seller.")

        # Backend authoritative amount: Agreed purchase price
        payment_amount = transaction.agreed_price
        if amount is not None and Decimal(str(amount)) != payment_amount:
            logger.warning(f"Attempted amount tampering for transaction {transaction.transaction_reference}: requested {amount}, agreed {payment_amount}")
            raise ValidationError(f"Amount mismatch. Land purchase payment must exactly equal agreed price: KES {payment_amount:,.2f}")

        seller_name = seller.get_full_name() or seller.email

        payment = PaymentRecord.objects.create(
            transaction=transaction,
            parcel=transaction.land_parcel,
            payer=payer,
            recipient=seller,
            beneficiary_user=seller,
            beneficiary_name=f"{seller_name} (Seller)",
            beneficiary_type='SELLER',
            payment_type='DIRECT_SETTLEMENT',
            payment_purpose='LAND_PURCHASE',
            purpose='LAND_PURCHASE',
            amount=payment_amount,
            currency='KES',
            payment_provider=provider,
            status='CREATED',
            notes=notes or f"Land purchase payment for {transaction.land_parcel.parcel_number if transaction.land_parcel else 'Parcel'} to Seller {seller_name}"
        )

        logger.info(
            f"Created LAND_PURCHASE payment {payment.digiland_reference} for {transaction.transaction_reference}: "
            f"Buyer {payer.email} -> Seller {seller.email} (KES {payment.amount:,.2f})"
        )
        return payment

    @classmethod
    def create_digiland_fee_payment(
        cls,
        transaction: Transaction,
        payer: User,
        amount: Optional[Decimal] = None,
        provider: str = 'MPESA',
        notes: Optional[str] = None
    ) -> PaymentRecord:
        """Creates a DigiLand Platform Service Fee payment intent.
        
        FLOW B: BUYER/SELLER -> DIGILAND
        - Beneficiary: DigiLand Ltd
        - Purpose: DIGILAND_SERVICE_FEE
        - Route: PLATFORM_COLLECTION
        
        This payment IS DigiLand revenue and is collected directly to DigiLand's shortcode.
        """
        # Determine standard fee (2% coordination fee or transaction.coordination_fee)
        default_fee = getattr(transaction, 'coordination_fee', None)
        if not default_fee or default_fee <= 0:
            if transaction.agreed_price:
                default_fee = (transaction.agreed_price * Decimal('0.02')).quantize(Decimal('0.01'))
            else:
                default_fee = Decimal('25000.00')

        payment_amount = Decimal(str(amount)) if amount is not None else default_fee

        payment = PaymentRecord.objects.create(
            transaction=transaction,
            parcel=transaction.land_parcel,
            payer=payer,
            recipient=None,
            beneficiary_user=None,
            beneficiary_name='DigiLand Ltd',
            beneficiary_type='DIGILAND',
            payment_type='PLATFORM_COLLECTION',
            payment_purpose='DIGILAND_SERVICE_FEE',
            purpose='DIGILAND_SERVICE_FEE',
            amount=payment_amount,
            currency='KES',
            payment_provider=provider,
            status='CREATED',
            notes=notes or f"DigiLand platform coordination fee for {transaction.transaction_reference}"
        )

        logger.info(
            f"Created DIGILAND_SERVICE_FEE payment {payment.digiland_reference} for {transaction.transaction_reference}: "
            f"Payer {payer.email} -> DigiLand (KES {payment.amount:,.2f})"
        )
        return payment

    @classmethod
    def create_professional_payment(
        cls,
        transaction: Transaction,
        payer: User,
        professional: User,
        service_type: str,
        amount: Decimal,
        provider: str = 'MPESA',
        notes: Optional[str] = None
    ) -> PaymentRecord:
        """Creates a Professional Service Fee payment intent.
        
        FLOW C: BUYER -> PROFESSIONAL SERVICE PROVIDER
        - Beneficiary: Assigned Professional (Surveyor / Advocate / Field Agent)
        - Payer: Buyer
        - Purpose: SURVEY_FEE / LEGAL_FEE / INSPECTION_FEE
        - Route: PROFESSIONAL_DIRECT_PAYMENT
        
        DigiLand does NOT take custody of the professional's money.
        """
        service_upper = service_type.upper()
        if 'SURVEY' in service_upper:
            purpose = 'SURVEY_FEE'
            ben_type = 'SURVEYOR'
            role_label = 'Licensed Surveyor'
        elif 'LEGAL' in service_upper or 'ADVOCATE' in service_upper or 'CONVEY' in service_upper:
            purpose = 'LEGAL_FEE'
            ben_type = 'ADVOCATE'
            role_label = 'Conveyancing Advocate'
        elif 'INSPECT' in service_upper or 'AGENT' in service_upper:
            purpose = 'INSPECTION_FEE'
            ben_type = 'FIELD_AGENT'
            role_label = 'Inspection Agent'
        else:
            purpose = 'ADDITIONAL_DUE_DILIGENCE_FEE'
            ben_type = 'OTHER'
            role_label = 'Service Provider'

        prof_name = professional.get_full_name() or professional.email
        payment_amount = Decimal(str(amount))

        payment = PaymentRecord.objects.create(
            transaction=transaction,
            parcel=transaction.land_parcel,
            payer=payer,
            recipient=professional,
            beneficiary_user=professional,
            beneficiary_name=f"{prof_name} ({role_label})",
            beneficiary_type=ben_type,
            payment_type='PROFESSIONAL_PAYMENT',
            payment_purpose=purpose,
            purpose=purpose,
            service_type=service_type,
            amount=payment_amount,
            currency='KES',
            payment_provider=provider,
            status='CREATED',
            notes=notes or f"Professional service payment ({service_type}) for {transaction.transaction_reference} to {prof_name}"
        )

        logger.info(
            f"Created PROFESSIONAL_PAYMENT {payment.digiland_reference} for {transaction.transaction_reference}: "
            f"Buyer {payer.email} -> {role_label} {prof_name} (KES {payment.amount:,.2f})"
        )
        return payment

    @classmethod
    def get_route_settlement_instructions(cls, payment: PaymentRecord) -> Dict[str, Any]:
        """Returns direct settlement instructions and metadata based on payment routing.
        
        Ensures the UI displays accurate non-custodial copy and never suggests DigiLand
        is collecting land purchase funds.
        """
        tx_ref = payment.transaction.transaction_reference if payment.transaction else payment.digiland_reference

        if payment.payment_type == 'DIRECT_SETTLEMENT':
            seller = payment.beneficiary_user or (payment.transaction.seller if payment.transaction else None)
            seller_phone = getattr(seller, 'phone_number', '') if seller else ''
            seller_name = payment.beneficiary_name or 'Seller'
            
            return {
                'route': 'DIRECT_SETTLEMENT',
                'title': 'Direct Land Purchase Settlement',
                'description': 'Payment is made directly from the buyer to the verified land seller. DigiLand does not hold customer funds.',
                'beneficiary_name': seller_name,
                'beneficiary_type': 'SELLER',
                'amount': float(payment.amount),
                'currency': payment.currency,
                'transaction_reference': tx_ref,
                'provider': payment.payment_provider,
                'safari_product_requirement': 'Safaricom Marketplace / Split Payment API or Direct Seller Merchant Till C2B',
                'direct_payment_details': {
                    'payee': seller_name,
                    'reference_to_quote': tx_ref,
                    'phone_number': seller_phone,
                    'payment_method': 'M-PESA / Bank RTGS Transfer',
                },
                'non_custodial_notice': (
                    "DigiLand facilitates and records verified payment evidence. "
                    "DigiLand does not operate an escrow service or hold seller purchase funds."
                )
            }

        elif payment.payment_type == 'PLATFORM_COLLECTION':
            return {
                'route': 'PLATFORM_COLLECTION',
                'title': 'DigiLand Platform Facilitation Fee',
                'description': 'Platform technology, AI document analysis, and transaction coordination fee paid directly to DigiLand.',
                'beneficiary_name': 'DigiLand Ltd',
                'beneficiary_type': 'DIGILAND',
                'amount': float(payment.amount),
                'currency': payment.currency,
                'transaction_reference': tx_ref,
                'provider': payment.payment_provider,
                'paybill': getattr(settings, 'DARAJA_SHORTCODE', ''),
                'account_reference': payment.digiland_reference,
                'non_custodial_notice': "DigiLand service fee for digital conveyancing platform facilitation."
            }

        else: # PROFESSIONAL_PAYMENT
            return {
                'route': 'PROFESSIONAL_PAYMENT',
                'title': f"Professional Service: {payment.service_type or payment.get_payment_purpose_display()}",
                'description': 'Direct payment to the independent licensed professional. DigiLand does not take custody of professional fees.',
                'beneficiary_name': payment.beneficiary_name,
                'beneficiary_type': payment.beneficiary_type,
                'amount': float(payment.amount),
                'currency': payment.currency,
                'transaction_reference': tx_ref,
                'provider': payment.payment_provider,
                'non_custodial_notice': "Direct professional engagement payment."
            }
