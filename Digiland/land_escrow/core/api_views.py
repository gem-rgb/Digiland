import json
import uuid
import logging
from decimal import Decimal
from datetime import timedelta

from django.conf import settings
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils.decorators import method_decorator
from django.views import View
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q, F
from django.shortcuts import get_object_or_404

from rest_framework import viewsets, status, generics, filters, permissions
from rest_framework.decorators import api_view, action, permission_classes, throttle_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, IsAdminUser, AllowAny
from rest_framework.pagination import PageNumberPagination

from .models import (
    User, AgentKYCApplication, Transaction, LandParcel, Document,
    AuditLog, PopupAdCampaign, PopupAdEvent, SponsoredAd, AdEngagement,
    LandPromotion, PromotionTier, PromotionPlan, PromotionAnalyticsLog,
    BuyerInterestProfile, BuyerEngagementSignal, SearchQueryLog,
    ParcelView, UserFavorite, FraudScore, VerificationBadge,
    ServiceFee, AnalyticsEvent, RecommendationLog,
    JointBuyerGroup, JointBuyerMember, JointPaymentContribution,
    KYCProfile,
)
from .services.identity import GavaConnectAPI, verify_user_kra_pin
from .services.payment import DarajaAPI
from .serializers import (
    LandPromotionSerializer, PromotionTierSerializer, PromotionPlanSerializer,
    PopupAdCampaignSerializer, PopupAdCampaignListSerializer, PopupAdEventSerializer,
    SponsoredAdSerializer, AdEngagementSerializer,
    BuyerInterestProfileSerializer, BuyerEngagementSignalSerializer, SearchQueryLogSerializer,
    ParcelViewSerializer, UserFavoriteSerializer,
    FraudScoreSerializer, VerificationBadgeSerializer,
    ServiceFeeSerializer, AnalyticsEventSerializer, RecommendationLogSerializer,
    AgentKYCApplicationSerializer, KYCProfileSerializer,
    JointBuyerGroupSerializer, JointBuyerMemberSerializer, JointPaymentContributionSerializer,
    AuditLogSerializer,
    LandParcelListSerializer, TransactionListSerializer,
)

logger = logging.getLogger(__name__)


# ==================== CUSTOM PAGINATION ====================

class StandardPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100


# ==================== MIXINS ====================

class IsSellerOrAgent(permissions.BasePermission):
    """Allow access only to sellers or agents."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role in ['Seller', 'Agent']


class IsAdmin(permissions.BasePermission):
    """Allow access only to admins."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'Admin'


class IsBuyer(permissions.BasePermission):
    """Allow access only to buyers."""
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated and request.user.role == 'Buyer'


# ==================== M-PESA CALLBACK VIEW (PRESERVED) ====================

@method_decorator(csrf_exempt, name='dispatch')
class MpesaCallbackView(View):
    """Handle M-PESA Daraja API callbacks for STK Push and B2C transactions.

    SECURITY: When MPESA_CALLBACK_SECRET is set in environment, validates the
    X-Mpesa-Secret header on incoming callbacks to prevent spoofed payment
    confirmations. If the secret is not configured, a warning is logged but
    the callback is still processed (backward-compatible).
    """

    def _verify_callback_secret(self, request):
        """Verify the M-PESA callback secret header.

        Safaricom Daraja API does not natively sign callbacks, but you can
        configure a callback URL with a query-parameter secret that gets
        echoed back. This method checks for a custom X-Mpesa-Secret header
        when MPESA_CALLBACK_SECRET is configured.

        Returns True if verification passes or is not configured.
        Returns False if verification fails.
        """
        from django.conf import settings
        expected = getattr(settings, 'MPESA_CALLBACK_SECRET', '')
        if not expected:
            # No secret configured — log warning in production
            if not getattr(settings, 'DEBUG', True):
                logger.warning(
                    "MPESA_CALLBACK_SECRET not set — M-PESA callbacks are "
                    "unauthenticated. Configure this in production."
                )
            return True

        provided = request.META.get('HTTP_X_MPESA_SECRET', '')
        if not provided:
            logger.warning("M-PESA callback missing X-Mpesa-Secret header")
            return False

        import hmac
        if not hmac.compare_digest(provided, expected):
            logger.warning("M-PESA callback secret mismatch — possible spoofed callback")
            return False

        return True

    def post(self, request, *args, **kwargs):
        # SECURITY: Verify callback secret if configured
        if not self._verify_callback_secret(request):
            logger.error("M-PESA callback rejected: secret verification failed")
            return JsonResponse({"status": "error", "message": "Unauthorized callback"}, status=403)

        try:
            data = json.loads(request.body)
            logger.info("M-PESA Callback received (secret verified)")

            if 'Body' in data and 'stkCallback' in data['Body']:
                return self.handle_stk_callback(data['Body']['stkCallback'])
            elif 'Result' in data:
                return self.handle_b2c_callback(data['Result'])
            else:
                logger.warning("Unknown M-PESA callback format")
                return JsonResponse({"status": "error", "message": "Unknown callback format"})

        except json.JSONDecodeError:
            logger.error("Invalid JSON in M-PESA callback")
            return JsonResponse({"status": "error", "message": "Invalid JSON"})
        except Exception as e:
            logger.error(f"Error processing M-PESA callback: {str(e)}")
            return JsonResponse({"status": "error", "message": "Internal error"})

    def handle_stk_callback(self, callback_data):
        try:
            result_code = callback_data.get('ResultCode')
            checkout_request_id = callback_data.get('CheckoutRequestID')

            transaction = None
            if checkout_request_id:
                try:
                    transaction = Transaction.objects.get(
                        escrow_reference=f"MPESA-{checkout_request_id}"
                    )
                except Transaction.DoesNotExist:
                    logger.warning(f"No transaction found for CheckoutRequestID: {checkout_request_id}")

            if result_code == 0:
                metadata = callback_data.get('CallbackMetadata', {}).get('Item', [])
                amount = phone = mpesa_receipt = None
                for item in metadata:
                    name = item.get('Name')
                    value = item.get('Value')
                    if name == 'Amount':
                        amount = value
                    elif name == 'PhoneNumber':
                        phone = value
                    elif name == 'MpesaReceiptNumber':
                        mpesa_receipt = value

                logger.info(f"STK Push successful: {mpesa_receipt}, Amount: {amount}, Phone: {phone}")
                if transaction:
                    transaction.status = 'Deposit_Paid'
                    transaction.escrow_reference = f"MPESA-{mpesa_receipt or checkout_request_id}"
                    transaction.save(update_fields=['status', 'escrow_reference'])
                    logger.info(f"Transaction {transaction.id} marked as Deposit_Paid")

                return JsonResponse({"status": "success", "message": "Payment processed successfully"})
            else:
                result_desc = callback_data.get('ResultDesc', 'Transaction failed')
                logger.warning(f"STK Push failed: {result_desc}")
                if transaction:
                    transaction.escrow_reference = f"FAILED-{checkout_request_id}"
                    transaction.save(update_fields=['escrow_reference'])
                return JsonResponse({"status": "failed", "message": result_desc})

        except Exception as e:
            logger.error(f"Error handling STK callback: {str(e)}")
            return JsonResponse({"status": "error", "message": "Callback processing error"})

    def handle_b2c_callback(self, result_data):
        try:
            result_code = result_data.get('ResultCode')
            conversation_id = result_data.get('ConversationID')

            if result_code == 0:
                result_parameters = result_data.get('ResultParameters', {}).get('ResultParameter', [])
                transaction_amount = transaction_receipt = receiver_phone = None
                for param in result_parameters:
                    key = param.get('Key')
                    value = param.get('Value')
                    if key == 'TransactionAmount':
                        transaction_amount = value
                    elif key == 'TransReceipt':
                        transaction_receipt = value
                    elif key == 'ReceiverPartyPublicName':
                        receiver_phone = value

                logger.info(f"B2C successful: {transaction_receipt}, Amount: {transaction_amount}, Receiver: {receiver_phone}")
                return JsonResponse({"status": "success", "message": "B2C payment completed successfully"})
            else:
                result_desc = result_data.get('ResultDesc', 'B2C transaction failed')
                logger.warning(f"B2C failed: {result_desc}")
                return JsonResponse({"status": "failed", "message": result_desc})

        except Exception as e:
            logger.error(f"Error handling B2C callback: {str(e)}")
            return JsonResponse({"status": "error", "message": "B2C callback processing error"})


# ==================== GAVACONNECT VERIFICATION VIEWS (PRESERVED) ====================

@csrf_exempt
@require_http_methods(["POST"])
def verify_kra_pin_view(request):
    """API endpoint to verify KRA PIN.

    When KRA_DB_VALIDATION_ENABLED is False (default), only format validation
    is performed. Enable the flag in production to use GavaConnect/iTax
    database verification as a failover.

    SECURITY: Requires authentication. user_id is derived from the authenticated
    user, NOT from the request body, to prevent IDOR attacks.
    """
    from django.conf import settings
    from rest_framework.permissions import IsAuthenticated
    from rest_framework.decorators import permission_classes as drf_perm

    # SECURITY: Require authentication
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Authentication required"}, status=401)

    try:
        data = json.loads(request.body)
        kra_pin = data.get('kra_pin')
        # SECURITY: Use authenticated user's ID, not body parameter
        user_id = str(request.user.id)

        if not kra_pin:
            return JsonResponse({"status": "error", "message": "KRA PIN is required"})

        # ── Format-only validation (always runs) ──
        import re
        if not re.fullmatch(r'[A-Z]\d{9}[A-Z]', kra_pin.strip().upper()):
            return JsonResponse({
                "status": "error",
                "message": "KRA PIN must be 11 characters: Letter + 9 digits + Letter."
            })

        # ── Database validation — gated behind feature flag ──
        if not getattr(settings, 'KRA_DB_VALIDATION_ENABLED', False):
            logger.info(
                "KRA DB validation disabled — format-only verification for PIN %s****",
                kra_pin[:4],
            )
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    user.is_identity_verified = True
                    user.gavakonect_verification_id = f"GVK-FORMAT-{kra_pin[:4]}****"
                    user.save()
                    logger.info(f"KRA PIN format-verified and user updated: {user.email}")
                except User.DoesNotExist:
                    logger.warning(f"User not found for ID: {user_id}")

            return JsonResponse({
                "status": "success",
                "message": "KRA PIN format validated (database verification disabled)",
                "verification_method": "format_only",
                "verification_details": {
                    "pin_status": "format_valid",
                    "verification_id": f"GVK-FORMAT-{kra_pin[:4]}",
                }
            })

        # ── Production failover: GavaConnect database verification ──
        result = GavaConnectAPI.verify_kra_pin(kra_pin)

        if result.get("status") == "success" and result.get("is_valid"):
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    user.is_identity_verified = True
                    user.gavakonect_verification_id = result.get("verification_id")
                    user.save()
                    if hasattr(user, 'kyc_application'):
                        kyc_app = user.kyc_application
                        kyc_app.kra_pin = kra_pin
                        kyc_app.save()
                    logger.info(f"KRA PIN DB-verified and user updated: {user.email}")
                except User.DoesNotExist:
                    logger.warning(f"User not found for ID: {user_id}")

            return JsonResponse({
                "status": "success",
                "message": "KRA PIN verified successfully",
                "verification_method": "gavaconnect",
                "verification_details": {
                    "taxpayer_name": result.get("taxpayer_name"),
                    "taxpayer_type": result.get("taxpayer_type"),
                    "pin_status": result.get("pin_status"),
                    "response_code": result.get("response_code"),
                    "verification_id": result.get("verification_id"),
                }
            })
        else:
            return JsonResponse({"status": "error", "message": result.get("message", "KRA PIN verification failed")})

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error in KRA PIN verification: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal verification error"})


@csrf_exempt
@require_http_methods(["POST"])
def verify_identity_view(request):
    """API endpoint to verify user identity using GavaConnect.

    SECURITY: Requires authentication. user_id is derived from the authenticated
    user to prevent IDOR attacks.
    """
    # SECURITY: Require authentication
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Authentication required"}, status=401)

    try:
        data = json.loads(request.body)
        id_number = data.get('id_number')
        first_name = data.get('first_name', '')
        last_name = data.get('last_name', '')
        # SECURITY: Use authenticated user's ID
        user_id = str(request.user.id)

        if not id_number:
            return JsonResponse({"status": "error", "message": "ID number is required"})

        result = GavaConnectAPI.verify_id_number(id_number, first_name, last_name)

        if result.get("status") == "success" and result.get("is_valid"):
            if user_id:
                try:
                    user = User.objects.get(id=user_id)
                    user.is_identity_verified = True
                    user.gavakonect_verification_id = result.get("verification_id")
                    user.save()
                    logger.info(f"Identity verified and user updated: {user.email}")
                except User.DoesNotExist:
                    logger.warning(f"User not found for ID: {user_id}")

            return JsonResponse({
                "status": "success",
                "message": "Identity verified successfully",
                "verification_details": {
                    "full_name": result.get("full_name"),
                    "date_of_birth": result.get("date_of_birth"),
                    "gender": result.get("gender"),
                    "county": result.get("county"),
                    "verification_id": result.get("verification_id"),
                }
            })
        else:
            return JsonResponse({"status": "error", "message": result.get("message", "Identity verification failed")})

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error in identity verification: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal verification error"})


@csrf_exempt
@require_http_methods(["POST"])
def verify_business_view(request):
    """API endpoint to verify business registration using GavaConnect.

    SECURITY: Requires authentication.
    """
    # SECURITY: Require authentication
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Authentication required"}, status=401)
    try:
        data = json.loads(request.body)
        business_name = data.get('business_name')
        registration_number = data.get('registration_number')

        if not business_name:
            return JsonResponse({"status": "error", "message": "Business name is required"})

        result = GavaConnectAPI.verify_business_registration(business_name, registration_number)

        if result.get("status") == "success" and result.get("is_valid"):
            return JsonResponse({
                "status": "success",
                "message": "Business registration verified successfully",
                "verification_details": {
                    "registration_number": result.get("registration_number"),
                    "registration_date": result.get("registration_date"),
                    "business_type": result.get("business_type"),
                    "registered_address": result.get("registered_address"),
                    "directors": result.get("directors", []),
                    "verification_id": result.get("verification_id"),
                }
            })
        else:
            return JsonResponse({"status": "error", "message": result.get("message", "Business verification failed")})

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error in business verification: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal verification error"})


# ==================== M-PESA PAYMENT VIEWS (SECURITY HARDENED) ====================


def _require_auth(request):
    """Helper to enforce authentication on M-PESA endpoints.
    Returns error response if not authenticated, None otherwise.
    """
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({"status": "error", "message": "Authentication required"}, status=401)
    return None


def _require_admin(request):
    """Helper to enforce admin authentication on sensitive M-PESA endpoints.
    Returns error response if not admin, None otherwise.
    """
    auth_err = _require_auth(request)
    if auth_err:
        return auth_err
    if getattr(request.user, 'role', None) != 'Admin':
        return JsonResponse({"status": "error", "message": "Admin access required"}, status=403)
    return None


@csrf_exempt
@require_http_methods(["POST"])
def initiate_mpesa_payment_view(request):
    """API endpoint to initiate M-PESA STK Push payment.

    SECURITY: Requires authentication.
    """
    auth_err = _require_auth(request)
    if auth_err:
        return auth_err
    try:
        data = json.loads(request.body)
        phone_number = data.get('phone_number')
        amount = data.get('amount')
        transaction_id = data.get('transaction_id')

        if not all([phone_number, amount, transaction_id]):
            return JsonResponse({"status": "error", "message": "Phone number, amount, and transaction ID are required"})

        result = DarajaAPI.stk_push(
            phone_number=phone_number,
            amount=amount,
            account_reference=f"ESCROW-{transaction_id}",
            transaction_desc=f"Land escrow payment for transaction {transaction_id}"
        )

        if result.get("status") == "success":
            return JsonResponse({
                "status": "success",
                "message": "M-PESA payment initiated successfully",
                "payment_details": {
                    "checkout_request_id": result.get("checkout_request_id"),
                    "merchant_request_id": result.get("merchant_request_id"),
                    "customer_message": result.get("customer_message"),
                }
            })
        else:
            return JsonResponse({"status": "error", "message": result.get("message", "M-PESA payment initiation failed")})

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error initiating M-PESA payment: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal payment error"})


@csrf_exempt
@require_http_methods(["POST"])
def query_mpesa_status_view(request):
    """API endpoint to query M-PESA STK Push transaction status.

    SECURITY: Requires authentication.
    """
    auth_err = _require_auth(request)
    if auth_err:
        return auth_err
    try:
        data = json.loads(request.body)
        checkout_request_id = data.get('checkout_request_id')
        if not checkout_request_id:
            return JsonResponse({"status": "error", "message": "Checkout request ID is required"})
        result = DarajaAPI.query_stk_status(checkout_request_id)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error querying M-PESA status: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal status query error"})


@csrf_exempt
@require_http_methods(["POST"])
def b2b_payment_view(request):
    """API endpoint to initiate M-PESA B2B payment.

    SECURITY: Requires admin authentication.
    """
    auth_err = _require_admin(request)
    if auth_err:
        return auth_err
    try:
        data = json.loads(request.body)
        receiver_party = data.get('receiver_party')
        amount = data.get('amount')
        command_id = data.get('command_id', 'BusinessPayBill')
        remarks = data.get('remarks', 'B2B Payment')

        if not all([receiver_party, amount]):
            return JsonResponse({"status": "error", "message": "Receiver party and amount are required"})

        result = DarajaAPI.b2b_payment(receiver_party=receiver_party, amount=amount, command_id=command_id, remarks=remarks)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error initiating B2B payment: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal B2B payment error"})


@csrf_exempt
@require_http_methods(["POST"])
def reverse_transaction_view(request):
    """API endpoint to reverse an M-PESA transaction.

    SECURITY: Requires admin authentication.
    """
    auth_err = _require_admin(request)
    if auth_err:
        return auth_err
    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')
        amount = data.get('amount')
        receiver_party = data.get('receiver_party')
        remarks = data.get('remarks', 'Transaction Reversal')

        if not all([transaction_id, amount, receiver_party]):
            return JsonResponse({"status": "error", "message": "Transaction ID, amount, and receiver party are required"})

        result = DarajaAPI.reverse_transaction(transaction_id=transaction_id, amount=amount, receiver_party=receiver_party, remarks=remarks)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error reversing transaction: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal transaction reversal error"})


@csrf_exempt
@require_http_methods(["POST"])
def query_transaction_status_view(request):
    """API endpoint to query M-PESA transaction status.

    SECURITY: Requires authentication.
    """
    auth_err = _require_auth(request)
    if auth_err:
        return auth_err
    try:
        data = json.loads(request.body)
        transaction_id = data.get('transaction_id')
        party_a = data.get('party_a')
        identifier_type = data.get('identifier_type', '4')

        if not all([transaction_id, party_a]):
            return JsonResponse({"status": "error", "message": "Transaction ID and party A are required"})

        result = DarajaAPI.query_transaction_status(transaction_id=transaction_id, party_a=party_a, identifier_type=identifier_type)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error querying transaction status: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal transaction status query error"})


@csrf_exempt
@require_http_methods(["POST"])
def query_account_balance_view(request):
    """API endpoint to query M-PESA account balance.

    SECURITY: Requires admin authentication.
    """
    auth_err = _require_admin(request)
    if auth_err:
        return auth_err
    try:
        data = json.loads(request.body)
        party_a = data.get('party_a')
        identifier_type = data.get('identifier_type', '4')

        if not party_a:
            return JsonResponse({"status": "error", "message": "Party A is required"})

        result = DarajaAPI.query_account_balance(party_a=party_a, identifier_type=identifier_type)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error querying account balance: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal account balance query error"})


@csrf_exempt
@require_http_methods(["POST"])
def simulate_c2b_payment_view(request):
    """API endpoint to simulate C2B payment for testing.

    SECURITY: Requires admin authentication. Only available in sandbox mode.
    """
    auth_err = _require_admin(request)
    if auth_err:
        return auth_err
    try:
        data = json.loads(request.body)
        short_code = data.get('short_code')
        amount = data.get('amount')
        msisdn = data.get('msisdn')
        bill_ref_number = data.get('bill_ref_number')

        if not all([short_code, amount, msisdn, bill_ref_number]):
            return JsonResponse({"status": "error", "message": "Short code, amount, MSISDN, and bill reference number are required"})

        result = DarajaAPI.simulate_c2b_payment(short_code=short_code, amount=amount, msisdn=msisdn, bill_ref_number=bill_ref_number)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error simulating C2B payment: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal C2B simulation error"})


@csrf_exempt
@require_http_methods(["POST"])
def redeem_bonga_points_view(request):
    """API endpoint to redeem Bonga points for payment.

    SECURITY: Requires authentication.
    """
    auth_err = _require_auth(request)
    if auth_err:
        return auth_err
    try:
        data = json.loads(request.body)
        msisdn = data.get('msisdn')
        amount = data.get('amount')
        bonga_points = data.get('bonga_points')
        conversion_rate = data.get('conversion_rate', 0.2)
        short_code = data.get('short_code')
        account_number = data.get('account_number', '')

        if not all([msisdn, amount, bonga_points]):
            return JsonResponse({"status": "error", "message": "MSISDN, amount, and bonga points are required"})

        result = DarajaAPI.redeem_bonga_points(msisdn=msisdn, amount=amount, bonga_points=bonga_points, conversion_rate=conversion_rate, short_code=short_code, account_number=account_number)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error redeeming Bonga points: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal Bonga redemption error"})


@csrf_exempt
@require_http_methods(["POST"])
def calculate_bonga_points_view(request):
    """API endpoint to calculate monetary value of Bonga points.

    SECURITY: Requires authentication.
    """
    auth_err = _require_auth(request)
    if auth_err:
        return auth_err
    try:
        data = json.loads(request.body)
        points = data.get('points')
        if not points:
            return JsonResponse({"status": "error", "message": "Points are required"})
        result = DarajaAPI.calculate_bonga_points(points)
        return JsonResponse(result)
    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid JSON"})
    except Exception as e:
        logger.error(f"Error calculating Bonga points: {str(e)}")
        return JsonResponse({"status": "error", "message": "Internal Bonga calculation error"})


@require_http_methods(["GET"])
def check_checkout_status_view(request):
    """Frontend polling endpoint to check if an STK Push payment was completed.

    SECURITY: Requires authentication and ownership of the transaction.
    """
    # SECURITY: Require authentication
    if not request.user or not request.user.is_authenticated:
        return JsonResponse({"payment_status": "error", "message": "Authentication required"})

    checkout_request_id = request.GET.get('checkout_request_id', '')
    transaction_id = request.GET.get('transaction_id', '')

    if not transaction_id:
        return JsonResponse({"payment_status": "error", "message": "Transaction ID required"})

    try:
        transaction = Transaction.objects.get(id=transaction_id)
    except Transaction.DoesNotExist:
        return JsonResponse({"payment_status": "error", "message": "Transaction not found"})

    # SECURITY: Verify user is a transaction participant
    user = request.user
    if (user != transaction.buyer and user != transaction.seller and
            user != transaction.agent and getattr(user, 'role', None) != 'Admin'):
        return JsonResponse({"payment_status": "error", "message": "Not authorized"})

    if transaction.status == 'Deposit_Paid':
        return JsonResponse({
            "payment_status": "completed",
            "message": "Payment confirmed!",
            "escrow_reference": transaction.escrow_reference,
            "mpesa_receipt": transaction.escrow_reference.replace("MPESA-", "") if transaction.escrow_reference else "",
        })

    if transaction.escrow_reference and transaction.escrow_reference.startswith("FAILED-"):
        return JsonResponse({"payment_status": "failed", "message": "Payment was declined or cancelled."})

    if checkout_request_id:
        try:
            result = DarajaAPI.query_stk_status(checkout_request_id)
            if result.get('status') == 'success' and result.get('result_code') == '0':
                transaction.status = 'Deposit_Paid'
                transaction.escrow_reference = f"MPESA-{checkout_request_id}"
                transaction.save(update_fields=['status', 'escrow_reference'])
                return JsonResponse({"payment_status": "completed", "message": "Payment confirmed via status query!", "escrow_reference": transaction.escrow_reference})
            elif result.get('status') == 'error' and 'cancelled' in str(result.get('message', '')).lower():
                transaction.escrow_reference = f"FAILED-{checkout_request_id}"
                transaction.save(update_fields=['escrow_reference'])
                return JsonResponse({"payment_status": "failed", "message": result.get('message', 'Payment was cancelled.')})
        except Exception as e:
            logger.error(f"Error querying STK status: {str(e)}")

    return JsonResponse({"payment_status": "pending", "message": "Waiting for payment confirmation..."})


# ==================== STRIPE PAYMENT VIEWS ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stripe_create_payment_intent(request):
    """
    POST /api/v1/payments/stripe/create/ — Create a Stripe PaymentIntent.
    Body: { "transaction_id": "uuid", "amount": 100000 }
    """
    try:
        import stripe
        from django.conf import settings

        stripe.api_key = settings.STRIPE_SECRET_KEY
        data = request.data
        transaction_id = data.get('transaction_id')
        amount = data.get('amount')

        if not transaction_id or not amount:
            return Response({"error": "transaction_id and amount are required"}, status=status.HTTP_400_BAD_REQUEST)

        try:
            transaction = Transaction.objects.get(id=transaction_id)
        except Transaction.DoesNotExist:
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

        # Verify user is the buyer
        if transaction.buyer != request.user and transaction.seller != request.user:
            return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

        # Stripe expects amount in cents
        amount_cents = int(Decimal(str(amount)) * 100)

        intent = stripe.PaymentIntent.create(
            amount=amount_cents,
            currency='kes',
            metadata={
                'transaction_id': str(transaction_id),
                'user_id': str(request.user.id),
                'user_email': request.user.email,
            },
        )

        return Response({
            'client_secret': intent.client_secret,
            'payment_intent_id': intent.id,
            'amount': amount,
            'currency': 'kes',
        })
    except ImportError:
        return Response({"error": "Stripe is not configured"}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    except Exception as e:
        logger.error(f"Stripe PaymentIntent creation error: {str(e)}")
        return Response({"error": "Payment initiation failed"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook_view(request):
    """
    POST /api/v1/payments/stripe/webhook/ — Handle Stripe webhook events.
    Verifies the webhook signature for security.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        import stripe
        from django.conf import settings

        stripe.api_key = settings.STRIPE_SECRET_KEY
        webhook_secret = settings.STRIPE_WEBHOOK_SECRET

        if not webhook_secret:
            # SECURITY: No fallback — reject webhook if secret is not configured
            logger.error("STRIPE_WEBHOOK_SECRET not configured — rejecting webhook request")
            return JsonResponse({"error": "Webhook not configured"}, status=503)

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
        except stripe.error.SignatureVerificationError as e:
            logger.error("Stripe webhook signature verification failed: %s", str(e))
            return JsonResponse({"error": "Invalid signature"}, status=400)

        event_type = event.get('type', '')

        if event_type == 'payment_intent.succeeded':
            payment_intent = event['data']['object']
            transaction_id = payment_intent.get('metadata', {}).get('transaction_id')

            if transaction_id:
                try:
                    transaction = Transaction.objects.get(id=transaction_id)
                    transaction.status = 'Deposit_Paid'
                    transaction.escrow_reference = f"STRIPE-{payment_intent['id']}"
                    transaction.save(update_fields=['status', 'escrow_reference'])
                    logger.info(f"Stripe payment succeeded for transaction {transaction_id}")

                    AuditLog.objects.create(
                        user=transaction.buyer,
                        action=f"Stripe payment confirmed for transaction {transaction_id}",
                        metadata={'payment_intent_id': payment_intent['id'], 'amount': payment_intent.get('amount')},
                    )
                except Transaction.DoesNotExist:
                    logger.error(f"Transaction not found for Stripe payment: {transaction_id}")

        elif event_type == 'payment_intent.payment_failed':
            payment_intent = event['data']['object']
            transaction_id = payment_intent.get('metadata', {}).get('transaction_id')
            logger.warning(f"Stripe payment failed for transaction {transaction_id}")

        return JsonResponse({"status": "success"})

    except ImportError:
        return JsonResponse({"error": "Stripe not configured"}, status=503)
    except Exception as e:
        logger.error(f"Stripe webhook error: {str(e)}")
        return JsonResponse({"error": "Webhook processing failed"}, status=400)


# ==================== PROMOTION ENDPOINTS ====================

class LandPromotionViewSet(viewsets.ModelViewSet):
    """
    CRUD for land parcel promotions (boosted listings).

    list:     GET  /api/v1/promotions/
    create:   POST /api/v1/promotions/
    retrieve: GET  /api/v1/promotions/{id}/
    update:   PATCH /api/v1/promotions/{id}/
    cancel:   POST /api/v1/promotions/{id}/cancel/
    """
    serializer_class = LandPromotionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    filterset_fields = ['tier', 'billing_model', 'is_active', 'payment_status']
    ordering_fields = ['-start_date']

    def get_queryset(self):
        return LandPromotion.objects.filter(created_by=self.request.user).select_related('parcel')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='cancel')
    def cancel(self, request, pk=None):
        """Cancel an active promotion."""
        promotion = self.get_object()
        if not promotion.is_active:
            return Response({"error": "Promotion is already inactive"}, status=status.HTTP_400_BAD_REQUEST)

        promotion.is_active = False
        promotion.end_date = timezone.now().date()
        promotion.save(update_fields=['is_active', 'end_date'])

        AuditLog.objects.create(
            user=request.user,
            action=f"Promotion {promotion.id} cancelled",
            metadata={'parcel_id': str(promotion.parcel_id), 'tier': promotion.tier},
        )
        return Response({"message": "Promotion cancelled", "promotion": LandPromotionSerializer(promotion).data})


class PromotionTierListView(generics.ListAPIView):
    """GET /api/v1/promotion-tiers/ — List available tiers."""
    queryset = PromotionTier.objects.filter(active=True)
    serializer_class = PromotionTierSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = None


class PromotionPlanCreateView(generics.CreateAPIView):
    """POST /api/v1/promotion-plans/ — Create or update seller plan."""
    serializer_class = PromotionPlanSerializer
    permission_classes = [IsAuthenticated, IsSellerOrAgent]

    def perform_create(self, serializer):
        # If the seller already has a plan, update it instead
        existing = PromotionPlan.objects.filter(seller=self.request.user).first()
        if existing:
            existing.tier = serializer.validated_data['tier']
            existing.auto_renew = serializer.validated_data.get('auto_renew', True)
            existing.status = 'Active'
            existing.end_date = timezone.now() + timedelta(days=30)
            existing.save()
            self.instance = existing
        else:
            serializer.save(seller=self.request.user)

    def create(self, request, *args, **kwargs):
        existing = PromotionPlan.objects.filter(seller=request.user).first()
        if existing:
            serializer = self.get_serializer(existing, data=request.data, partial=True)
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_200_OK)

        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(serializer.data, status=status.HTTP_201_CREATED)


class PromotionPlanMineView(generics.RetrieveAPIView):
    """GET /api/v1/promotion-plans/mine/ — Get current user's plan."""
    serializer_class = PromotionPlanSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        return get_object_or_404(PromotionPlan, seller=self.request.user)


# ==================== RECOMMENDATION ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def recommendations_feed(request):
    """
    GET /api/v1/recommendations/ — Personalized feed for the buyer.
    Uses the full RecommendationEngine with content-based, collaborative,
    geo-spatial, and hybrid algorithms.
    """
    from .services.recommendation import RecommendationEngine

    user = request.user
    feed = RecommendationEngine.build_recommendation_feed(user)

    # Serialize each section
    def serialize_section(parcels_qs):
        if not parcels_qs or not parcels_qs.exists():
            return []
        serializer = LandParcelListSerializer(parcels_qs, many=True, context={'request': request})
        return serializer.data

    return Response({
        'recommended': serialize_section(feed.get('recommended', [])),
        'popular': serialize_section(feed.get('popular', [])),
        'recently_viewed': serialize_section(feed.get('recently_viewed', [])),
        'recently_viewed_similar': serialize_section(feed.get('recently_viewed_similar', [])),
        'hot_deals': serialize_section(feed.get('hot_deals', [])),
        'trending': serialize_section(feed.get('trending', [])),
        'people_also_viewed': serialize_section(feed.get('people_also_viewed', [])),
        'sponsored_listings': serialize_section(feed.get('sponsored_listings', [])),
        'buyer_category': feed.get('buyer_category', ''),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def popular_listings(request):
    """
    GET /api/v1/recommendations/popular/ — Popular listings by views and favorites.
    """
    parcels = LandParcel.objects.filter(
        verification_status='Verified',
        asking_price__isnull=False,
    ).annotate(
        view_count=Count('views'),
        fav_count=Count('favorited_by'),
    ).order_by('-fav_count', '-view_count')

    paginator = StandardPagination()
    page = paginator.paginate_queryset(parcels, request)
    serializer = LandParcelListSerializer(page, many=True, context={'request': request})
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def trending_listings(request):
    """
    GET /api/v1/recommendations/trending/ — Trending listings (recent engagement spike).
    """
    since = timezone.now() - timedelta(days=7)
    parcels = LandParcel.objects.filter(
        verification_status='Verified',
        asking_price__isnull=False,
    ).annotate(
        recent_views=Count('views', filter=Q(views__viewed_at__gte=since)),
        recent_favs=Count('favorited_by', filter=Q(favorited_by__saved_at__gte=since)),
    ).order_by('-recent_favs', '-recent_views')

    paginator = StandardPagination()
    page = paginator.paginate_queryset(parcels, request)
    serializer = LandParcelListSerializer(page, many=True, context={'request': request})
    return paginator.get_paginated_response(serializer.data)


@api_view(['GET'])
@permission_classes([AllowAny])
def sponsored_listings(request):
    """
    GET /api/v1/recommendations/sponsored/ — Sponsored/promoted listings.
    """
    parcels = LandParcel.objects.filter(
        verification_status='Verified',
        promotions__is_active=True,
        asking_price__isnull=False,
    ).distinct().select_related('listed_by')

    paginator = StandardPagination()
    page = paginator.paginate_queryset(parcels, request)
    serializer = LandParcelListSerializer(page, many=True, context={'request': request})
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def track_parcel_view(request):
    """
    POST /api/v1/recommendations/track-view/ — Track a parcel view.
    Body: { "parcel_id": "uuid" }
    """
    parcel_id = request.data.get('parcel_id')
    if not parcel_id:
        return Response({"error": "parcel_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        parcel = LandParcel.objects.get(id=parcel_id)
    except LandParcel.DoesNotExist:
        return Response({"error": "Parcel not found"}, status=status.HTTP_404_NOT_FOUND)

    ParcelView.objects.create(user=request.user, parcel=parcel)

    # Also record an analytics event
    AnalyticsEvent.objects.create(
        parcel=parcel,
        user=request.user,
        event_type='View',
        metadata={'source': 'track_view'},
    )

    return Response({"message": "View tracked"}, status=status.HTTP_201_CREATED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def track_favorite(request):
    """
    POST /api/v1/recommendations/track-favorite/ — Track a favorite.
    Body: { "parcel_id": "uuid", "action": "add"|"remove" }
    """
    parcel_id = request.data.get('parcel_id')
    action = request.data.get('action', 'add')

    if not parcel_id:
        return Response({"error": "parcel_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        parcel = LandParcel.objects.get(id=parcel_id)
    except LandParcel.DoesNotExist:
        return Response({"error": "Parcel not found"}, status=status.HTTP_404_NOT_FOUND)

    if action == 'add':
        fav, created = UserFavorite.objects.get_or_create(user=request.user, parcel=parcel)
        AnalyticsEvent.objects.create(parcel=parcel, user=request.user, event_type='Save', metadata={'action': 'add'})
        return Response({"message": "Favorite added", "created": created}, status=status.HTTP_201_CREATED if created else status.HTTP_200_OK)
    else:
        deleted, _ = UserFavorite.objects.filter(user=request.user, parcel=parcel).delete()
        return Response({"message": "Favorite removed", "deleted": deleted}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def track_search_query(request):
    """
    POST /api/v1/recommendations/track-search/ — Track a search query.
    Body: { "query": "...", "filters": {...} }
    """
    query = request.data.get('query', '')
    filters_data = request.data.get('filters', {})

    if not query:
        return Response({"error": "query is required"}, status=status.HTTP_400_BAD_REQUEST)

    SearchQueryLog.objects.create(
        user=request.user,
        query=query,
        filters=filters_data,
    )

    return Response({"message": "Search tracked"}, status=status.HTTP_201_CREATED)


class BuyerInterestProfileView(generics.RetrieveUpdateAPIView):
    """
    GET/PUT /api/v1/buyer-profile/ — Get or update buyer interest profile.
    """
    serializer_class = BuyerInterestProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        profile, _ = BuyerInterestProfile.objects.get_or_create(
            user=self.request.user,
            defaults={'category': 'Residential'}
        )
        return profile


# ==================== POPUP AD ENDPOINTS ====================

class PopupAdCampaignViewSet(viewsets.ModelViewSet):
    """
    CRUD for popup ad campaigns.

    list:     GET  /api/v1/popup-campaigns/
    create:   POST /api/v1/popup-campaigns/
    retrieve: GET  /api/v1/popup-campaigns/{id}/
    update:   PATCH /api/v1/popup-campaigns/{id}/
    activate: POST /api/v1/popup-campaigns/{id}/activate/
    pause:    POST /api/v1/popup-campaigns/{id}/pause/
    dashboard: GET /api/v1/popup-campaigns/dashboard/
    """
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_serializer_class(self):
        if self.action == 'list':
            return PopupAdCampaignListSerializer
        return PopupAdCampaignSerializer

    def get_queryset(self):
        return PopupAdCampaign.objects.filter(created_by=self.request.user).select_related('parcel')

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        """Activate a draft/paused campaign."""
        campaign = self.get_object()
        if campaign.status not in ['Draft', 'Paused']:
            return Response({"error": f"Cannot activate campaign in {campaign.status} status"}, status=status.HTTP_400_BAD_REQUEST)

        campaign.status = 'Active'
        campaign.save(update_fields=['status', 'updated_at'])

        AuditLog.objects.create(
            user=request.user,
            action=f"Popup campaign {campaign.id} activated",
            metadata={'campaign_name': campaign.campaign_name},
        )
        return Response({"message": "Campaign activated", "campaign": PopupAdCampaignSerializer(campaign, context={'request': request}).data})

    @action(detail=True, methods=['post'], url_path='pause')
    def pause(self, request, pk=None):
        """Pause an active campaign."""
        campaign = self.get_object()
        if campaign.status != 'Active':
            return Response({"error": f"Cannot pause campaign in {campaign.status} status"}, status=status.HTTP_400_BAD_REQUEST)

        campaign.status = 'Paused'
        campaign.save(update_fields=['status', 'updated_at'])

        AuditLog.objects.create(
            user=request.user,
            action=f"Popup campaign {campaign.id} paused",
            metadata={'campaign_name': campaign.campaign_name},
        )
        return Response({"message": "Campaign paused", "campaign": PopupAdCampaignSerializer(campaign, context={'request': request}).data})

    @action(detail=False, methods=['get'], url_path='dashboard')
    def dashboard(self, request):
        """Seller promotions dashboard with aggregate stats."""
        campaigns = self.get_queryset()
        active = campaigns.filter(status='Active')
        total_spent = campaigns.aggregate(total=Sum('spent_amount'))['total'] or Decimal('0.00')
        total_impressions = campaigns.aggregate(total=Sum('impressions_count'))['total'] or 0
        total_clicks = campaigns.aggregate(total=Sum('clicks_count'))['total'] or 0
        total_leads = campaigns.aggregate(total=Sum('leads_count'))['total'] or 0

        return Response({
            'total_campaigns': campaigns.count(),
            'active_campaigns': active.count(),
            'total_spent': str(total_spent),
            'total_impressions': total_impressions,
            'total_clicks': total_clicks,
            'total_leads': total_leads,
            'avg_ctr': round(total_clicks / total_impressions * 100, 2) if total_impressions > 0 else 0,
            'recent_campaigns': PopupAdCampaignListSerializer(campaigns[:5], many=True, context={'request': request}).data,
        })


@api_view(['GET'])
@permission_classes([AllowAny])
def popup_ads_for_page(request):
    """
    GET /api/v1/popup-ads/ — Get popup ads relevant to the current page context.
    Query params: page_context, county, session_key
    """
    page_context = request.query_params.get('page_context', '')
    county = request.query_params.get('county', '')
    session_key = request.query_params.get('session_key', '')

    campaigns = PopupAdCampaign.objects.filter(
        status='Active',
        payment_status='Paid',
    ).select_related('parcel')

    if county:
        campaigns = campaigns.filter(
            Q(target_counties__contains=[county]) | Q(target_counties=[])
        )

    # Order by priority bid and quality score
    campaigns = campaigns.order_by('-priority_bid', '-quality_score')[:5]

    serializer = PopupAdCampaignSerializer(campaigns, many=True, context={'request': request})
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([AllowAny])
def record_popup_ad_event(request, pk=None):
    """
    POST /api/v1/popup-ads/{id}/event/ — Record a popup ad event.
    Body: { "event_type": "Impression"|"Click"|"Lead"|"Dismissed", ... }
    """
    try:
        campaign = PopupAdCampaign.objects.get(id=pk)
    except PopupAdCampaign.DoesNotExist:
        return Response({"error": "Campaign not found"}, status=status.HTTP_404_NOT_FOUND)

    event_type = request.data.get('event_type')
    if event_type not in dict(PopupAdEvent.EVENT_CHOICES).keys():
        return Response({"error": "Invalid event_type"}, status=status.HTTP_400_BAD_REQUEST)

    event_data = {
        'campaign': campaign.id,
        'event_type': event_type,
        'placement_area': request.data.get('placement_area', ''),
        'session_key': request.data.get('session_key', ''),
        'page_context': request.data.get('page_context', ''),
        'buyer_category': request.data.get('buyer_category', ''),
        'county_context': request.data.get('county_context', ''),
        'intent_score': request.data.get('intent_score', 0),
        'relevance_score': request.data.get('relevance_score', 0),
        'dwell_seconds': request.data.get('dwell_seconds', 0),
        'metadata': request.data.get('metadata', {}),
    }

    if request.user.is_authenticated:
        event_data['user'] = request.user.id

    serializer = PopupAdEventSerializer(data=event_data)
    serializer.is_valid(raise_exception=True)
    event = serializer.save()

    # Update campaign counters
    if event_type == 'Impression':
        campaign.impressions_count = F('impressions_count') + 1
    elif event_type == 'Click':
        campaign.clicks_count = F('clicks_count') + 1
    elif event_type == 'Lead':
        campaign.leads_count = F('leads_count') + 1
    elif event_type == 'Dismissed':
        campaign.dismissals_count = F('dismissals_count') + 1

    campaign.save(update_fields=[
        'impressions_count', 'clicks_count', 'leads_count', 'dismissals_count'
    ])

    return Response(PopupAdEventSerializer(event).data, status=status.HTTP_201_CREATED)


# ==================== SPONSORED ADS ENDPOINTS ====================

class SponsoredAdViewSet(viewsets.ModelViewSet):
    """
    CRUD for sponsored ads.

    list:        GET  /api/v1/sponsored-ads/
    create:      POST /api/v1/sponsored-ads/
    retrieve:    GET  /api/v1/sponsored-ads/{id}/
    activate:    POST /api/v1/sponsored-ads/{id}/activate/
    pause:       POST /api/v1/sponsored-ads/{id}/pause/
    end:         POST /api/v1/sponsored-ads/{id}/end/
    performance: GET  /api/v1/sponsored-ads/{id}/performance/
    """
    serializer_class = SponsoredAdSerializer
    permission_classes = [IsAuthenticated, IsSellerOrAgent]
    pagination_class = StandardPagination
    filterset_fields = ['status', 'billing_model', 'tier']

    def get_queryset(self):
        return SponsoredAd.objects.filter(seller=self.request.user).select_related('parcel')

    def perform_create(self, serializer):
        serializer.save(seller=self.request.user)

    @action(detail=True, methods=['post'], url_path='activate')
    def activate(self, request, pk=None):
        """Activate a draft/scheduled ad."""
        ad = self.get_object()
        if ad.status not in ['Draft', 'Scheduled', 'Paused']:
            return Response({"error": f"Cannot activate ad in {ad.status} status"}, status=status.HTTP_400_BAD_REQUEST)

        ad.status = 'Active'
        if not ad.starts_at:
            ad.starts_at = timezone.now()
        ad.save(update_fields=['status', 'starts_at', 'updated_at'])

        AuditLog.objects.create(
            user=request.user,
            action=f"Sponsored ad {ad.id} activated",
            metadata={'parcel_id': str(ad.parcel_id), 'billing_model': ad.billing_model},
        )
        return Response({"message": "Ad activated", "ad": SponsoredAdSerializer(ad, context={'request': request}).data})

    @action(detail=True, methods=['post'], url_path='pause')
    def pause(self, request, pk=None):
        """Pause an active ad."""
        ad = self.get_object()
        if ad.status != 'Active':
            return Response({"error": f"Cannot pause ad in {ad.status} status"}, status=status.HTTP_400_BAD_REQUEST)

        ad.status = 'Paused'
        ad.save(update_fields=['status', 'updated_at'])
        return Response({"message": "Ad paused", "ad": SponsoredAdSerializer(ad, context={'request': request}).data})

    @action(detail=True, methods=['post'], url_path='end')
    def end(self, request, pk=None):
        """End an ad campaign."""
        ad = self.get_object()
        if ad.status in ['Ended', 'Rejected']:
            return Response({"error": f"Cannot end ad in {ad.status} status"}, status=status.HTTP_400_BAD_REQUEST)

        ad.status = 'Ended'
        ad.ends_at = timezone.now()
        ad.save(update_fields=['status', 'ends_at', 'updated_at'])
        return Response({"message": "Ad ended", "ad": SponsoredAdSerializer(ad, context={'request': request}).data})

    @action(detail=True, methods=['get'], url_path='performance')
    def performance(self, request, pk=None):
        """Get performance metrics for a sponsored ad."""
        ad = self.get_object()
        engagements = AdEngagement.objects.filter(ad=ad)

        total_impressions = engagements.filter(event_type='Impression').count()
        total_clicks = engagements.filter(event_type='Click').count()
        total_saves = engagements.filter(event_type='Save').count()
        total_inquiries = engagements.filter(event_type='Inquiry').count()
        total_shares = engagements.filter(event_type='Share').count()

        ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
        budget_remaining = (ad.budget_total or Decimal('0')) - ad.budget_spent

        return Response({
            'ad_id': str(ad.id),
            'status': ad.status,
            'billing_model': ad.billing_model,
            'budget_total': str(ad.budget_total or Decimal('0')),
            'budget_spent': str(ad.budget_spent),
            'budget_remaining': str(budget_remaining),
            'impressions': total_impressions,
            'clicks': total_clicks,
            'saves': total_saves,
            'inquiries': total_inquiries,
            'shares': total_shares,
            'ctr': round(ctr, 2),
            'is_active': ad.is_active,
        })


# ==================== SERVICE FEE ENDPOINTS ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def calculate_service_fees(request):
    """
    POST /api/v1/service-fees/calculate/ — Calculate fees for a transaction.
    Body: { "transaction_id": "uuid" } or { "amount": 100000, "include_legal_verification": false, "include_due_diligence": false }
    """
    transaction_id = request.data.get('transaction_id')
    amount = request.data.get('amount')
    include_legal = request.data.get('include_legal_verification', False)
    include_dd = request.data.get('include_due_diligence', False)

    if transaction_id:
        try:
            tx = Transaction.objects.get(id=transaction_id)
            amount = tx.agreed_price
            include_legal = tx.include_legal_verification
            include_dd = tx.include_due_diligence
        except Transaction.DoesNotExist:
            return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

    if not amount:
        return Response({"error": "amount or transaction_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    amount = Decimal(str(amount))

    # Fee calculations
    platform_fee = amount * Decimal('0.04')       # 4% platform fee
    escrow_fee = amount * Decimal('0.02')          # 2% escrow holding fee
    processing_fee = Decimal('500.00')              # Flat KES 500 processing fee
    verification_fee = Decimal('5000.00') if include_legal else Decimal('0.00')
    due_diligence_fee = Decimal('3000.00') if include_dd else Decimal('0.00')

    total_fees = platform_fee + escrow_fee + processing_fee + verification_fee + due_diligence_fee

    breakdown = {
        'platform_fee': {'amount': str(platform_fee), 'rate': '4%', 'description': 'Platform service fee'},
        'escrow_fee': {'amount': str(escrow_fee), 'rate': '2%', 'description': 'Escrow holding fee'},
        'processing_fee': {'amount': str(processing_fee), 'rate': 'flat', 'description': 'Payment processing fee'},
        'verification_fee': {'amount': str(verification_fee), 'description': 'Legal verification fee (optional)'},
        'due_diligence_fee': {'amount': str(due_diligence_fee), 'description': 'Due diligence fee (optional)'},
    }

    return Response({
        'principal': str(amount),
        'platform_fee': str(platform_fee),
        'escrow_fee': str(escrow_fee),
        'processing_fee': str(processing_fee),
        'verification_fee': str(verification_fee),
        'due_diligence_fee': str(due_diligence_fee),
        'total_fees': str(total_fees),
        'total_payable': str(amount + total_fees),
        'breakdown': breakdown,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def fee_explanations(request):
    """GET /api/v1/service-fees/explanations/ — Get fee explanations."""
    return Response({
        'fees': [
            {'name': 'Platform Service Fee', 'rate': '4%', 'description': 'Charged on every transaction for platform maintenance and support.'},
            {'name': 'Escrow Holding Fee', 'rate': '2%', 'description': 'Covers the cost of securely holding funds in escrow during the transaction.'},
            {'name': 'Payment Processing Fee', 'rate': 'Flat KES 500', 'description': 'Covers M-Pesa/Paystack processing costs.'},
            {'name': 'Legal Verification Fee', 'rate': 'KES 5,000', 'description': 'Optional. Covers legal verification of land documents by a qualified advocate.'},
            {'name': 'Due Diligence Fee', 'rate': 'KES 3,000', 'description': 'Optional. Covers comprehensive background checks and land search verification.'},
        ],
        'disclaimer': 'All fees are inclusive of VAT where applicable. Fees are deducted before disbursement to seller.',
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def transaction_service_fees(request, transaction_id):
    """GET /api/v1/service-fees/{transaction_id}/ — Get recorded fees for a transaction.
    
    SECURITY: Only transaction participants or admins can view fees.
    """
    try:
        service_fee = ServiceFee.objects.get(transaction_id=transaction_id)
    except ServiceFee.DoesNotExist:
        return Response({"error": "Service fees not found for this transaction"}, status=status.HTTP_404_NOT_FOUND)

    # SECURITY: Ownership check
    txn = service_fee.transaction
    user = request.user
    if (user != txn.buyer and user != txn.seller and
            (txn.agent is None or user != txn.agent) and user.role != 'Admin'):
        return Response({"error": "Not authorized"}, status=status.HTTP_403_FORBIDDEN)

    serializer = ServiceFeeSerializer(service_fee)
    return Response(serializer.data)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_revenue(request):
    """GET /api/v1/admin/revenue/ — Admin revenue analytics."""
    total_fees = ServiceFee.objects.aggregate(
        total_platform=Sum('platform_fee'),
        total_escrow=Sum('escrow_fee'),
        total_processing=Sum('processing_fee'),
        total_verification=Sum('verification_fee'),
        total_dd=Sum('due_diligence_fee'),
        total_all=Sum('total_fees'),
    )

    total_transactions = ServiceFee.objects.count()

    # Promotion revenue
    promo_revenue = LandPromotion.objects.filter(payment_status='Paid').aggregate(
        total=Sum('price_paid')
    )['total'] or Decimal('0.00')

    # Popup ad revenue
    popup_revenue = PopupAdCampaign.objects.filter(payment_status='Paid').aggregate(
        total=Sum('spent_amount')
    )['total'] or Decimal('0.00')

    # Sponsored ad revenue
    sponsored_revenue = SponsoredAd.objects.aggregate(
        total=Sum('budget_spent')
    )['total'] or Decimal('0.00')

    return Response({
        'service_fees': {
            'platform_fee': str(total_fees['total_platform'] or Decimal('0.00')),
            'escrow_fee': str(total_fees['total_escrow'] or Decimal('0.00')),
            'processing_fee': str(total_fees['total_processing'] or Decimal('0.00')),
            'verification_fee': str(total_fees['total_verification'] or Decimal('0.00')),
            'due_diligence_fee': str(total_fees['total_dd'] or Decimal('0.00')),
            'total': str(total_fees['total_all'] or Decimal('0.00')),
            'transaction_count': total_transactions,
        },
        'promotion_revenue': str(promo_revenue),
        'popup_ad_revenue': str(popup_revenue),
        'sponsored_ad_revenue': str(sponsored_revenue),
        'total_revenue': str(
            (total_fees['total_all'] or Decimal('0.00')) +
            promo_revenue + popup_revenue + sponsored_revenue
        ),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_revenue_monthly(request):
    """GET /api/v1/admin/revenue/monthly/ — Monthly revenue breakdown."""
    from django.db.models.functions import TruncMonth

    monthly = ServiceFee.objects.annotate(
        month=TruncMonth('created_at')
    ).values('month').annotate(
        total_platform=Sum('platform_fee'),
        total_escrow=Sum('escrow_fee'),
        total_processing=Sum('processing_fee'),
        total=Sum('total_fees'),
        count=Count('id'),
    ).order_by('-month')

    return Response({
        'monthly_breakdown': [
            {
                'month': entry['month'].strftime('%Y-%m') if entry['month'] else None,
                'platform_fee': str(entry['total_platform'] or Decimal('0.00')),
                'escrow_fee': str(entry['total_escrow'] or Decimal('0.00')),
                'processing_fee': str(entry['total_processing'] or Decimal('0.00')),
                'total': str(entry['total'] or Decimal('0.00')),
                'transaction_count': entry['count'],
            }
            for entry in monthly
        ]
    })


# ==================== ANALYTICS ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def parcel_analytics(request, pk):
    """GET /api/v1/analytics/parcel/{id}/ — Parcel analytics."""
    try:
        parcel = LandParcel.objects.get(id=pk)
    except LandParcel.DoesNotExist:
        return Response({"error": "Parcel not found"}, status=status.HTTP_404_NOT_FOUND)

    # View stats
    total_views = ParcelView.objects.filter(parcel=parcel).count()
    views_last_7d = ParcelView.objects.filter(
        parcel=parcel, viewed_at__gte=timezone.now() - timedelta(days=7)
    ).count()
    views_last_30d = ParcelView.objects.filter(
        parcel=parcel, viewed_at__gte=timezone.now() - timedelta(days=30)
    ).count()

    # Favorite stats
    total_favs = UserFavorite.objects.filter(parcel=parcel).count()

    # Engagement signals
    engagement_stats = BuyerEngagementSignal.objects.filter(parcel=parcel).values(
        'signal_type'
    ).annotate(count=Count('id'))

    # Analytics events
    event_stats = AnalyticsEvent.objects.filter(parcel=parcel).values(
        'event_type'
    ).annotate(count=Count('id'))

    # Promotion stats
    active_promotions = LandPromotion.objects.filter(parcel=parcel, is_active=True).count()

    # Badges
    badges = VerificationBadge.objects.filter(parcel=parcel, revoked=False)

    return Response({
        'parcel_id': str(parcel.id),
        'parcel_number': parcel.parcel_number,
        'views': {
            'total': total_views,
            'last_7_days': views_last_7d,
            'last_30_days': views_last_30d,
        },
        'favorites': total_favs,
        'engagement_signals': {e['signal_type']: e['count'] for e in engagement_stats},
        'analytics_events': {e['event_type']: e['count'] for e in event_stats},
        'active_promotions': active_promotions,
        'verification_badges': VerificationBadgeSerializer(badges, many=True).data,
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsSellerOrAgent])
def seller_ad_performance(request):
    """GET /api/v1/analytics/seller/ads/ — Seller ad performance."""
    user = request.user

    # Sponsored ads
    sponsored = SponsoredAd.objects.filter(seller=user)
    sponsored_data = []
    for ad in sponsored:
        engagements = AdEngagement.objects.filter(ad=ad)
        sponsored_data.append({
            'ad_id': str(ad.id),
            'parcel_number': ad.parcel.parcel_number,
            'status': ad.status,
            'billing_model': ad.billing_model,
            'budget_total': str(ad.budget_total or Decimal('0')),
            'budget_spent': str(ad.budget_spent),
            'impressions': engagements.filter(event_type='Impression').count(),
            'clicks': engagements.filter(event_type='Click').count(),
            'inquiries': engagements.filter(event_type='Inquiry').count(),
        })

    # Popup campaigns
    popup_campaigns = PopupAdCampaign.objects.filter(created_by=user)
    popup_data = PopupAdCampaignListSerializer(popup_campaigns, many=True, context={'request': request}).data

    # Land promotions
    land_promos = LandPromotion.objects.filter(created_by=user, is_active=True)
    promo_data = LandPromotionSerializer(land_promos, many=True).data

    return Response({
        'sponsored_ads': sponsored_data,
        'popup_campaigns': popup_data,
        'land_promotions': promo_data,
        'total_campaigns': len(sponsored_data) + len(popup_data) + len(promo_data),
    })


@api_view(['GET'])
@permission_classes([AllowAny])
def trending_locations(request):
    """GET /api/v1/analytics/trending/ — Trending locations."""
    since = timezone.now() - timedelta(days=30)

    trending = LandParcel.objects.filter(
        verification_status='Verified',
    ).annotate(
        recent_views=Count('views', filter=Q(views__viewed_at__gte=since)),
        recent_favs=Count('favorited_by', filter=Q(favorited_by__saved_at__gte=since)),
    ).values('county').annotate(
        parcel_count=Count('id'),
        total_views=Sum('recent_views'),
        total_favs=Sum('recent_favs'),
    ).order_by('-total_views', '-total_favs')[:20]

    return Response({
        'trending_locations': list(trending),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def recommendation_performance(request):
    """GET /api/v1/analytics/recommendations/ — Recommendation performance."""
    total_recs = RecommendationLog.objects.count()
    clicked_recs = RecommendationLog.objects.filter(clicked=True).count()
    saved_recs = RecommendationLog.objects.filter(saved=True).count()
    inquired_recs = RecommendationLog.objects.filter(inquired=True).count()

    # By algorithm type
    by_algorithm = RecommendationLog.objects.values('algorithm_type').annotate(
        total=Count('id'),
        clicked=Count('id', filter=Q(clicked=True)),
        saved=Count('id', filter=Q(saved=True)),
        inquired=Count('id', filter=Q(inquired=True)),
        avg_score=Avg('score'),
    ).order_by('-total')

    return Response({
        'overall': {
            'total_recommendations': total_recs,
            'clicks': clicked_recs,
            'saves': saved_recs,
            'inquiries': inquired_recs,
            'click_rate': round(clicked_recs / total_recs * 100, 2) if total_recs > 0 else 0,
            'save_rate': round(saved_recs / total_recs * 100, 2) if total_recs > 0 else 0,
        },
        'by_algorithm': list(by_algorithm),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def buyer_segment_analytics(request):
    """GET /api/v1/analytics/buyer-segments/ — Buyer segment analytics."""
    segments = BuyerInterestProfile.objects.values('category').annotate(
        count=Count('id'),
        avg_budget_min=Avg('budget_min'),
        avg_budget_max=Avg('budget_max'),
    ).order_by('-count')

    return Response({
        'buyer_segments': list(segments),
        'total_profiles': BuyerInterestProfile.objects.count(),
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def platform_revenue(request):
    """GET /api/v1/analytics/platform-revenue/ — Platform revenue."""
    return admin_revenue(request)


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def admin_dashboard(request):
    """GET /api/v1/admin/dashboard/ — Admin analytics dashboard."""
    # User stats
    user_stats = User.objects.values('role').annotate(count=Count('id'))
    total_users = User.objects.count()

    # Transaction stats
    tx_stats = Transaction.objects.values('status').annotate(count=Count('id'))
    total_volume = Transaction.objects.aggregate(
        total=Sum('agreed_price')
    )['total'] or Decimal('0.00')

    # Parcel stats
    parcel_stats = LandParcel.objects.values('verification_status').annotate(count=Count('id'))

    # Active promotions
    active_promos = LandPromotion.objects.filter(is_active=True).count()
    active_popup_campaigns = PopupAdCampaign.objects.filter(status='Active').count()
    active_sponsored_ads = SponsoredAd.objects.filter(status='Active').count()

    # Revenue
    total_revenue = ServiceFee.objects.aggregate(total=Sum('total_fees'))['total'] or Decimal('0.00')

    # Fraud
    high_risk_count = FraudScore.objects.filter(score__gte=50).count()
    flagged_count = FraudScore.objects.filter(flagged_for_review=True).count()

    return Response({
        'users': {
            'total': total_users,
            'by_role': {u['role']: u['count'] for u in user_stats},
        },
        'transactions': {
            'by_status': {t['status']: t['count'] for t in tx_stats},
            'total_volume': str(total_volume),
        },
        'parcels': {
            'by_status': {p['verification_status']: p['count'] for p in parcel_stats},
        },
        'promotions': {
            'active_land_promotions': active_promos,
            'active_popup_campaigns': active_popup_campaigns,
            'active_sponsored_ads': active_sponsored_ads,
        },
        'revenue': {
            'total_service_fees': str(total_revenue),
        },
        'fraud': {
            'high_risk_users': high_risk_count,
            'flagged_users': flagged_count,
        },
    })


# ==================== FRAUD ENDPOINTS ====================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_fraud_score(request, pk):
    """GET /api/v1/fraud/user/{id}/score/ — Get user fraud score.
    
    SECURITY: Users can only view their own fraud score. Admins can view any user's score.
    """
    # SECURITY: Ownership check — only self or admin
    if str(request.user.id) != str(pk) and request.user.role != 'Admin':
        return Response({"error": "Not authorized to view this fraud score."}, status=status.HTTP_403_FORBIDDEN)
    
    try:
        fraud = FraudScore.objects.get(user_id=pk)
    except FraudScore.DoesNotExist:
        # Auto-calculate on the fly
        user = get_object_or_404(User, id=pk)
        fraud = _calculate_fraud_score(user)

    serializer = FraudScoreSerializer(fraud)
    return Response(serializer.data)


def _calculate_fraud_score(user):
    """Calculate and update fraud score for a user."""
    score = 0
    risk_factors = []

    # Check for unverified identity
    if not user.is_identity_verified:
        score += 15
        risk_factors.append('unverified_identity')

    # Check for multiple parcels with same owner ID
    parcel_count = LandParcel.objects.filter(listed_by=user).count()
    if parcel_count > 10:
        score += 10
        risk_factors.append('high_listing_count')

    # Check for disputed transactions
    disputed_count = Transaction.objects.filter(
        Q(seller=user) | Q(buyer=user),
        status='Disputed'
    ).count()
    if disputed_count > 0:
        score += 20
        risk_factors.append('disputed_transactions')

    # Check KYC status
    if hasattr(user, 'kyc_profile'):
        if user.kyc_profile.status == 'FLAGGED_FOR_REVIEW':
            score += 30
            risk_factors.append('kyc_flagged')
        elif user.kyc_profile.status == 'LOCKED':
            score += 50
            risk_factors.append('kyc_locked')

    score = min(score, 100)

    fraud, _ = FraudScore.objects.update_or_create(
        user=user,
        defaults={'score': score, 'risk_factors': risk_factors},
    )
    return fraud


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def check_duplicate_listings(request, pk):
    """GET /api/v1/fraud/parcel/{id}/duplicates/ — Check for duplicate listings."""
    try:
        parcel = LandParcel.objects.get(id=pk)
    except LandParcel.DoesNotExist:
        return Response({"error": "Parcel not found"}, status=status.HTTP_404_NOT_FOUND)

    # Find potential duplicates: same county, similar size, similar price
    duplicates = LandParcel.objects.filter(
        county=parcel.county,
        land_use_type=parcel.land_use_type,
        asking_price__gte=parcel.asking_price * Decimal('0.9') if parcel.asking_price else None,
        asking_price__lte=parcel.asking_price * Decimal('1.1') if parcel.asking_price else None,
    ).exclude(id=parcel.id)

    if parcel.asking_price is None:
        duplicates = LandParcel.objects.none()

    return Response({
        'parcel_id': str(parcel.id),
        'parcel_number': parcel.parcel_number,
        'potential_duplicates_count': duplicates.count(),
        'potential_duplicates': [
            {
                'id': str(d.id),
                'parcel_number': d.parcel_number,
                'county': d.county,
                'asking_price': str(d.asking_price),
                'land_size': str(d.land_size),
                'listed_by': d.listed_by.email if d.listed_by else None,
            }
            for d in duplicates[:10]
        ],
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def flag_user_for_review(request):
    """POST /api/v1/fraud/flag/ — Flag user for review."""
    user_id = request.data.get('user_id')
    reason = request.data.get('reason', '')

    if not user_id:
        return Response({"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        target_user = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return Response({"error": "User not found"}, status=status.HTTP_404_NOT_FOUND)

    fraud, _ = FraudScore.objects.get_or_create(
        user=target_user,
        defaults={'score': 0, 'risk_factors': []},
    )
    fraud.flagged_for_review = True
    fraud.review_notes = reason
    fraud.save(update_fields=['flagged_for_review', 'review_notes'])

    AuditLog.objects.create(
        user=request.user,
        action=f"User {target_user.email} flagged for review",
        metadata={'reason': reason, 'flagged_by': request.user.email},
    )

    return Response({"message": "User flagged for review", "fraud_score": FraudScoreSerializer(fraud).data})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def high_risk_users(request):
    """GET /api/v1/admin/fraud/high-risk/ — High risk users."""
    high_risk = FraudScore.objects.filter(score__gte=50).select_related('user').order_by('-score')
    serializer = FraudScoreSerializer(high_risk, many=True)
    return Response({'high_risk_users': serializer.data, 'count': high_risk.count()})


@api_view(['GET'])
@permission_classes([IsAuthenticated, IsAdmin])
def flagged_users(request):
    """GET /api/v1/admin/fraud/flagged/ — Flagged users."""
    flagged = FraudScore.objects.filter(flagged_for_review=True).select_related('user').order_by('-score')
    serializer = FraudScoreSerializer(flagged, many=True)
    return Response({'flagged_users': serializer.data, 'count': flagged.count()})


@api_view(['POST'])
@permission_classes([IsAuthenticated, IsAdmin])
def approve_flagged_user(request, pk):
    """POST /api/v1/admin/fraud/{id}/approve/ — Approve/clear a flagged user."""
    try:
        fraud = FraudScore.objects.get(id=pk)
    except FraudScore.DoesNotExist:
        return Response({"error": "Fraud score record not found"}, status=status.HTTP_404_NOT_FOUND)

    action_type = request.data.get('action', 'clear')  # 'clear' or 'escalate'

    if action_type == 'clear':
        fraud.flagged_for_review = False
        fraud.score = max(0, fraud.score - 20)
        fraud.review_notes = request.data.get('notes', 'Cleared by admin')
    elif action_type == 'escalate':
        fraud.score = min(100, fraud.score + 20)
        fraud.review_notes = request.data.get('notes', 'Escalated by admin')

    fraud.reviewed_by = request.user
    fraud.save()

    AuditLog.objects.create(
        user=request.user,
        action=f"Fraud review for user {fraud.user.email}: {action_type}",
        metadata={'fraud_score_id': str(fraud.id), 'action': action_type, 'new_score': fraud.score},
    )

    return Response({"message": f"User {action_type}ed", "fraud_score": FraudScoreSerializer(fraud).data})


# ==================== STRIPE PAYMENT ENDPOINTS ====================

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def stripe_create_payment_intent(request):
    """
    POST /api/v1/payments/stripe/create/ — Create Stripe payment intent.
    Body: { "transaction_id": "uuid" }
    """
    transaction_id = request.data.get('transaction_id')
    if not transaction_id:
        return Response({"error": "transaction_id is required"}, status=status.HTTP_400_BAD_REQUEST)

    try:
        transaction = Transaction.objects.get(id=transaction_id)
    except Transaction.DoesNotExist:
        return Response({"error": "Transaction not found"}, status=status.HTTP_404_NOT_FOUND)

    # In production, this would call the Stripe API
    # For now, return a mock payment intent
    import uuid as _uuid
    mock_intent_id = f"pi_{_uuid.uuid4().hex[:24]}"
    mock_client_secret = f"{mock_intent_id}_secret_{_uuid.uuid4().hex[:16]}"

    # Calculate total amount in cents (Stripe uses smallest currency unit)
    total_amount = int(transaction.total_payable * 100) if transaction.total_payable else int(transaction.agreed_price * 100)

    return Response({
        'id': mock_intent_id,
        'client_secret': mock_client_secret,
        'amount': total_amount,
        'currency': 'kes',
        'status': 'requires_payment_method',
        'transaction_id': str(transaction.id),
        'metadata': {
            'transaction_id': str(transaction.id),
            'buyer_email': transaction.buyer.email,
            'parcel_number': transaction.land_parcel.parcel_number,
        },
    })


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook_view(request):
    """
    POST /api/v1/payments/stripe/webhook/ — Stripe webhook handler.
    """
    payload = request.body
    sig_header = request.META.get('HTTP_STRIPE_SIGNATURE', '')

    try:
        data = json.loads(payload)
        event_type = data.get('type', '')

        logger.info(f"Stripe webhook received: {event_type}")

        if event_type == 'payment_intent.succeeded':
            intent = data.get('data', {}).get('object', {})
            transaction_id = intent.get('metadata', {}).get('transaction_id')

            if transaction_id:
                try:
                    transaction = Transaction.objects.get(id=transaction_id)
                    transaction.status = 'Deposit_Paid'
                    transaction.escrow_reference = f"STRIPE-{intent.get('id', '')}"
                    transaction.save(update_fields=['status', 'escrow_reference'])

                    AuditLog.objects.create(
                        user=transaction.buyer,
                        action=f'Stripe payment confirmed for transaction {transaction.id}',
                        metadata={
                            'transaction_id': str(transaction.id),
                            'stripe_intent_id': intent.get('id'),
                            'amount': intent.get('amount'),
                        },
                    )
                except Transaction.DoesNotExist:
                    logger.error(f"Transaction not found for Stripe payment: {transaction_id}")

        elif event_type == 'payment_intent.payment_failed':
            intent = data.get('data', {}).get('object', {})
            transaction_id = intent.get('metadata', {}).get('transaction_id')
            if transaction_id:
                try:
                    transaction = Transaction.objects.get(id=transaction_id)
                    transaction.escrow_reference = f"FAILED-STRIPE-{intent.get('id', '')}"
                    transaction.save(update_fields=['escrow_reference'])
                except Transaction.DoesNotExist:
                    pass

        return JsonResponse({"status": "success", "received": True})

    except json.JSONDecodeError:
        return JsonResponse({"status": "error", "message": "Invalid payload"}, status=400)
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        return JsonResponse({"status": "error", "message": "Webhook processing error"}, status=500)


# ==================== KYC ENDPOINTS ====================

class AgentKYCApplicationViewSet(viewsets.ModelViewSet):
    """Agent KYC application endpoints."""
    serializer_class = AgentKYCApplicationSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = AgentKYCApplication.objects.select_related('agent')
        if self.request.user.role != 'Admin':
            qs = qs.filter(agent=self.request.user)
        return qs

    def perform_create(self, serializer):
        serializer.save(agent=self.request.user, kyc_submitted=True)

    @action(detail=True, methods=['post'], url_path='approve', permission_classes=[IsAuthenticated, IsAdmin])
    def approve(self, request, pk=None):
        application = self.get_object()
        application.status = 'Approved'
        application.reviewed_at = timezone.now()
        application.save(update_fields=['status', 'reviewed_at'])

        # Update user identity verification
        application.agent.is_identity_verified = True
        application.agent.save(update_fields=['is_identity_verified'])

        AuditLog.objects.create(
            user=request.user,
            action=f"KYC application approved for {application.agent.email}",
            metadata={'application_id': str(application.id)},
        )
        return Response({"message": "KYC application approved", "application": AgentKYCApplicationSerializer(application).data})

    @action(detail=True, methods=['post'], url_path='reject', permission_classes=[IsAuthenticated, IsAdmin])
    def reject(self, request, pk=None):
        application = self.get_object()
        reason = request.data.get('reason', '')
        application.status = 'Rejected'
        application.reviewed_at = timezone.now()
        application.save(update_fields=['status', 'reviewed_at'])

        AuditLog.objects.create(
            user=request.user,
            action=f"KYC application rejected for {application.agent.email}",
            metadata={'application_id': str(application.id), 'reason': reason},
        )
        return Response({"message": "KYC application rejected"})


class KYCProfileViewSet(viewsets.ModelViewSet):
    """KYC profile management (admin/staff)."""
    serializer_class = KYCProfileSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardPagination
    filterset_fields = ['status']

    def get_queryset(self):
        return KYCProfile.objects.select_related('user')


# ==================== JOINT BUYER ENDPOINTS ====================

class JointBuyerGroupViewSet(viewsets.ModelViewSet):
    """Joint buyer group management."""
    serializer_class = JointBuyerGroupSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        qs = JointBuyerGroup.objects.select_related('leader').prefetch_related('members')
        if self.request.user.role == 'Admin':
            return qs
        return qs.filter(leader=self.request.user)

    def perform_create(self, serializer):
        serializer.save(leader=self.request.user)


class JointBuyerMemberViewSet(viewsets.ModelViewSet):
    """Joint buyer member management."""
    serializer_class = JointBuyerMemberSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination

    def get_queryset(self):
        return JointBuyerMember.objects.filter(
            group__leader=self.request.user
        ).select_related('group')


class JointPaymentContributionViewSet(viewsets.ModelViewSet):
    """Joint payment contribution tracking."""
    serializer_class = JointPaymentContributionSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = StandardPagination
    filterset_fields = ['status', 'payment_channel']

    def get_queryset(self):
        return JointPaymentContribution.objects.filter(
            transaction__buyer=self.request.user
        ).select_related('transaction', 'member')


# ==================== AUDIT LOG ENDPOINTS ====================

class AuditLogListView(generics.ListAPIView):
    """GET /api/v1/audit-logs/ — List audit logs (admin only)."""
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsAdmin]
    pagination_class = StandardPagination
    filterset_fields = ['user', 'action']
    ordering_fields = ['-timestamp']

    def get_queryset(self):
        return AuditLog.objects.select_related('user').order_by('-timestamp')



# ==================== PRICE PREDICTION ENDPOINTS ====================

from rest_framework.throttling import AnonRateThrottle, UserRateThrottle


class PricePredictionAnonThrottle(AnonRateThrottle):
    """Throttle for anonymous users on price prediction: 10/min."""
    rate = '10/min'


class PricePredictionUserThrottle(UserRateThrottle):
    """Throttle for authenticated users on price prediction: 30/min."""
    rate = '30/min'


def _get_confidence_label(r2_score):
    """Derive a human-readable confidence label from the model R² score."""
    if r2_score >= 0.85:
        return 'High Confidence'
    elif r2_score >= 0.70:
        return 'Moderate Confidence'
    elif r2_score >= 0.50:
        return 'Low Confidence'
    else:
        return 'Very Low Confidence'


def _get_market_position(price_per_acre):
    """Derive a market position label from the predicted price per acre."""
    if price_per_acre >= 100_000_000:
        return 'Premium zone'
    elif price_per_acre >= 20_000_000:
        return 'High-value zone'
    elif price_per_acre >= 5_000_000:
        return 'Mid-market zone'
    elif price_per_acre >= 1_000_000:
        return 'Emerging zone'
    else:
        return 'Rural / remote zone'


@api_view(['GET', 'POST'])
@permission_classes([AllowAny])
@throttle_classes([PricePredictionAnonThrottle, PricePredictionUserThrottle])
def price_prediction_api(request):
    if not getattr(settings, 'ENABLE_AI_PRICE_PREDICTION', False):
        return Response({
            'error': 'AI features are disabled for this rollout.',
            'error_code': 'SERVICE_UNAVAILABLE'
        }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    from .services.price_prediction import (
        predict_price, get_model_info, get_fallback_prediction,
        get_constituencies_for_county, get_towns_for_constituency,
        get_location_catalog,
        resolve_location,
        KENYA_COUNTIES, LAND_USE_TYPES, PLOT_GRADES, KENYA_LOCATIONS, MODEL_VERSION,
    )

    # ── GET: Return model metadata, reference data, or cascading location data ──
    if request.method == 'GET':
        action = request.query_params.get('action', '')

        if action == 'locations':
            query = request.query_params.get('query', '').strip()
            try:
                limit = int(request.query_params.get('limit', 60))
            except (TypeError, ValueError):
                limit = 60

            locations = get_location_catalog(query=query, limit=limit)
            return Response({
                'query': query,
                'count': len(locations),
                'locations': locations,
            })

        # ── Cascading location data ──
        if action == 'constituencies':
            county = request.query_params.get('county', '').strip()
            county, _, _ = resolve_location(county)
            if not county or county not in KENYA_COUNTIES:
                return Response({
                    'error': f'Invalid county. Valid counties: {", ".join(sorted(KENYA_LOCATIONS.keys())[:10])}...',
                    'error_code': 'INVALID_COUNTY',
                }, status=status.HTTP_400_BAD_REQUEST)
            constituencies = get_constituencies_for_county(county)
            return Response({
                'county': county,
                'constituencies': constituencies,
            })

        if action == 'towns':
            county = request.query_params.get('county', '').strip()
            constituency = request.query_params.get('constituency', '').strip()
            county, constituency, _ = resolve_location(county, constituency)
            if not county or county not in KENYA_COUNTIES:
                return Response({
                    'error': 'Invalid county.',
                    'error_code': 'INVALID_COUNTY',
                }, status=status.HTTP_400_BAD_REQUEST)
            towns = get_towns_for_constituency(county, constituency)
            return Response({
                'county': county,
                'constituency': constituency,
                'towns': towns,
            })

        # ── Default GET: Model info + counties ──
        metadata = get_model_info()
        return Response({
            'model_info': {
                'n_records': metadata.get('n_records', 0),
                'n_counties': metadata.get('n_counties', 0),
                'n_towns': metadata.get('n_towns', 0),
                'algorithm': f'Ensemble (RF+GB), v{MODEL_VERSION}',
                'cv_r2_mean': metadata.get('cv_r2_mean', 0),
                'cv_r2_mean_rf': metadata.get('cv_r2_mean_rf', 0),
                'cv_r2_mean_gb': metadata.get('cv_r2_mean_gb', 0),
            },
            'counties': KENYA_COUNTIES,
            'land_use_types': LAND_USE_TYPES,
            'plot_grades': PLOT_GRADES,
        })

    # ── POST: Run prediction ──
    data = request.data

    # ── Input validation ──
    errors = {}

    raw_county = str(data.get('county', '')).strip()
    raw_constituency = str(data.get('constituency', '')).strip()
    raw_town = str(data.get('town', '')).strip()

    county, constituency, town = resolve_location(raw_county, raw_constituency, raw_town)
    county = county or raw_county
    constituency = constituency or raw_constituency
    town = town or raw_town

    if not raw_county:
        errors['county'] = 'County is required.'
    if not county:
        errors['county'] = 'County is required.'
    elif county not in KENYA_COUNTIES:
        errors['county'] = f'Unknown county. Must be one of the {len(KENYA_COUNTIES)} Kenyan counties.'

    if not constituency and county:
        constituency = county  # Default to county name

    if not town:
        town = constituency  # Default town to constituency

    land_use = str(data.get('land_use', '')).strip().title()
    if not land_use:
        errors['land_use'] = 'Land use type is required.'
    elif land_use not in LAND_USE_TYPES:
        errors['land_use'] = f'Invalid land use. Must be one of: {", ".join(LAND_USE_TYPES)}.'

    size_acres = data.get('size_acres')
    if size_acres is None:
        errors['size_acres'] = 'Size in acres is required.'
    else:
        try:
            size_acres = float(size_acres)
            if size_acres <= 0:
                errors['size_acres'] = 'Size must be greater than 0.'
            elif size_acres > 10000:
                errors['size_acres'] = 'Size must be 10,000 acres or less.'
        except (TypeError, ValueError):
            errors['size_acres'] = 'Size must be a valid number.'

    def _coerce_request_bool(value, default=True):
        if value is None:
            return default
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        normalized = str(value).strip().lower()
        if not normalized:
            return default
        return normalized in {'1', 'true', 't', 'yes', 'y', 'on'}

    has_road_access = _coerce_request_bool(data.get('has_road_access', True))
    has_water = _coerce_request_bool(data.get('has_water', True))
    has_electricity = _coerce_request_bool(data.get('has_electricity', True))

    # New optional fields
    proximity_to_tarmac_km = data.get('proximity_to_tarmac_km')
    if proximity_to_tarmac_km is not None:
        try:
            proximity_to_tarmac_km = float(proximity_to_tarmac_km)
            if proximity_to_tarmac_km < 0 or proximity_to_tarmac_km > 50:
                errors['proximity_to_tarmac_km'] = 'Must be between 0 and 50 km.'
        except (TypeError, ValueError):
            errors['proximity_to_tarmac_km'] = 'Must be a valid number.'

    proximity_to_school_km = data.get('proximity_to_school_km')
    if proximity_to_school_km is not None:
        try:
            proximity_to_school_km = float(proximity_to_school_km)
            if proximity_to_school_km < 0 or proximity_to_school_km > 50:
                errors['proximity_to_school_km'] = 'Must be between 0 and 50 km.'
        except (TypeError, ValueError):
            errors['proximity_to_school_km'] = 'Must be a valid number.'

    proximity_to_hospital_km = data.get('proximity_to_hospital_km')
    if proximity_to_hospital_km is not None:
        try:
            proximity_to_hospital_km = float(proximity_to_hospital_km)
            if proximity_to_hospital_km < 0 or proximity_to_hospital_km > 50:
                errors['proximity_to_hospital_km'] = 'Must be between 0 and 50 km.'
        except (TypeError, ValueError):
            errors['proximity_to_hospital_km'] = 'Must be a valid number.'

    plot_grade = str(data.get('plot_grade', '')).strip().upper()
    if plot_grade and plot_grade not in PLOT_GRADES:
        errors['plot_grade'] = f'Invalid plot grade. Must be one of: {", ".join(PLOT_GRADES)}.'

    if errors:
        return Response({'errors': errors, 'error_code': 'VALIDATION_ERROR'}, status=status.HTTP_400_BAD_REQUEST)

    # ── Run prediction ──
    try:
        result = predict_price(
            county=county,
            constituency=constituency,
            land_use=land_use,
            size_acres=size_acres,
            has_road_access=has_road_access,
            has_water=has_water,
            has_electricity=has_electricity,
            town=town,
            proximity_to_tarmac_km=proximity_to_tarmac_km,
            proximity_to_school_km=proximity_to_school_km,
            proximity_to_hospital_km=proximity_to_hospital_km,
            plot_grade=plot_grade or 'C',
        )
    except Exception as exc:
        logger.error(f'Price prediction error: {exc}')
        # Try fallback prediction
        try:
            result = get_fallback_prediction(county, land_use, size_acres)
        except Exception:
            return Response(
                {'error': 'Prediction service unavailable. Please try again later.',
                 'error_code': 'SERVICE_UNAVAILABLE'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

    # ── Handle model-unavailable case ──
    if 'error' in result:
        error_msg = result['error']
        if 'not available' in error_msg.lower() or 'train' in error_msg.lower():
            # Try fallback
            try:
                result = get_fallback_prediction(county, land_use, size_acres)
            except Exception:
                return Response(
                    {'error': 'Price prediction model is not available. Please contact support.',
                     'error_code': 'MODEL_UNAVAILABLE'},
                    status=status.HTTP_503_SERVICE_UNAVAILABLE,
                )
        else:
            # Unknown location / encoding error → 422
            return Response(
                {'error': f'Could not generate prediction: {error_msg}',
                 'error_code': 'PREDICTION_FAILED'},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )

    # ── Enrich response with confidence label and market position ──
    r2_score = result.get('model_accuracy', 0)
    if isinstance(r2_score, float) and r2_score < 1:
        # R² is stored as 0-1 fraction; convert to percentage for display
        model_accuracy_pct = f'{r2_score * 100:.1f}%'
    elif isinstance(r2_score, (int, float)):
        model_accuracy_pct = f'{r2_score:.1f}%'
    else:
        model_accuracy_pct = 'N/A'

    result['model_accuracy'] = model_accuracy_pct
    result['confidence_label'] = _get_confidence_label(r2_score if isinstance(r2_score, float) else 0)
    result['market_position'] = _get_market_position(result.get('price_per_acre', 0))
    result['model_version'] = result.get('model_version', MODEL_VERSION)
    result['prediction_id'] = result.get('prediction_id', '')

    return Response(result, status=status.HTTP_200_OK)


@api_view(['GET'])
@permission_classes([AllowAny])
def auth_me_api(request):
    """GET /api/auth/me/
    Returns authenticated user's details.
    """
    if not request.user.is_authenticated:
        return Response({
            "authenticated": False,
            "role": None,
            "is_onboarded": False,
        }, status=status.HTTP_200_OK)
    return Response({
        "authenticated": True,
        "role": request.user.role.lower() if request.user.role else None,
        "is_onboarded": getattr(request.user, 'is_onboarded', False),
    }, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def onboarding_select_role_api(request):
    """POST /api/onboarding/select-role/
    Saves user role and marks onboarding as completed.
    """
    role = request.data.get('role', '').lower().strip()
    if role not in ['buyer', 'seller']:
        return Response({'error': 'Invalid role. Choose buyer or seller.'}, status=status.HTTP_400_BAD_REQUEST)

    user = request.user
    user.role = 'Buyer' if role == 'buyer' else 'Seller'
    user.is_onboarded = True
    user.save(update_fields=['role', 'is_onboarded'])

    return Response({
        "authenticated": True,
        "role": user.role.lower(),
        "is_onboarded": user.is_onboarded,
    }, status=status.HTTP_200_OK)
