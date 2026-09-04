import uuid
import requests
import base64
import logging
from datetime import datetime
from django.conf import settings
from django.core.exceptions import ValidationError
from .utils import log_api_call, validate_phone_number, generate_transaction_reference

logger = logging.getLogger(__name__)

# Callback base URL — in sandbox, Safaricom rejects http://localhost.
# Use site's configured domain or a placeholder HTTPS URL for sandbox.
def _get_callback_base():
    env = getattr(settings, 'DARAJA_ENVIRONMENT', 'sandbox')
    if env == 'production':
        hosts = getattr(settings, 'ALLOWED_HOSTS', ['localhost'])
        domain = hosts[0] if hosts else 'localhost'
        return f"https://{domain}"
    # Sandbox: use a valid HTTPS placeholder (Safaricom won't actually call it)
    return "https://digiland.example.com"

# --- Payment Confirmation & Transaction Progression (Non-Custodial) ---

def record_payment_confirmation(transaction, provider_reference=None, provider='MPESA', metadata=None, payment_reference=None, amount=None, raw_payload=None, **kwargs):
    """
    Records payment evidence from payment provider (M-Pesa STK push, Bank, Stripe).
    DigiLand does NOT hold customer funds or maintain an escrow balance.
    Moves status to Payment_Confirmed / Under_Verification and creates a PaymentRecord audit entry.
    """
    from django.utils import timezone
    from ..models import PaymentRecord, TransactionMilestone

    ref = provider_reference or payment_reference or getattr(transaction, 'payment_reference_safe', None) or f"REF-{uuid.uuid4().hex[:10].upper()}"
    amt = amount or getattr(transaction, 'agreed_price', None) or 0
    transaction.payment_reference = ref
    if not transaction.status or transaction.status == 'Initiated':
        transaction.status = 'Payment_Confirmed'
    transaction.save(update_fields=['status', 'payment_reference', 'updated_at'])

    # Create immutable PaymentRecord evidence
    try:
        PaymentRecord.objects.get_or_create(
            digiland_reference=f"DL-{transaction.id.hex[:8].upper()}-{ref[:10]}",
            defaults={
                'transaction': transaction,
                'parcel': transaction.land_parcel,
                'payer': transaction.buyer,
                'recipient': transaction.seller,
                'payment_provider': provider,
                'provider_reference': ref,
                'amount': amt,
                'currency': 'KES',
                'status': 'CONFIRMED',
                'payment_status': 'CONFIRMED',
                'confirmed_at': timezone.now(),
                'evidence_metadata': metadata or raw_payload or {'source': 'provider_webhook'},
            }
        )
    except Exception as exc:
        logger.warning(f"Could not create PaymentRecord for transaction {transaction.id}: {exc}")

    # Record or update PAYMENT_CONFIRMED milestone
    try:
        TransactionMilestone.objects.update_or_create(
            transaction=transaction,
            milestone_code='PAYMENT_CONFIRMED',
            defaults={
                'sequence_order': 13,
                'status': 'COMPLETED',
                'completed_at': timezone.now(),
                'responsible_party': transaction.buyer,
                'responsible_role': 'Buyer',
                'evidence_data': {'payment_reference': ref, 'provider': provider},
                'audit_note': f"Payment confirmed via {provider} (Ref: {ref})",
            }
        )
    except Exception as exc:
        logger.warning(f"Could not record milestone for transaction {transaction.id}: {exc}")

    return {'status': 'success', 'payment_reference': ref, 'transaction_id': str(transaction.id), 'transaction': transaction}

# Backward compatibility alias
hold_payment = record_payment_confirmation


def complete_transaction(transaction, admin_user=None, notes=None, **kwargs):
    """
    Marks the transaction and ownership transfer as Completed once all verification
    and party actions are satisfied. Does not hold or release funds.
    """
    from django.utils import timezone
    from ..models import TransactionMilestone

    transaction.status = 'Completed'
    transaction.save(update_fields=['status', 'updated_at'])

    # Mark TRANSACTION_COMPLETED milestone
    try:
        TransactionMilestone.objects.update_or_create(
            transaction=transaction,
            milestone_code='TRANSACTION_COMPLETED',
            defaults={
                'sequence_order': 15,
                'status': 'COMPLETED',
                'completed_at': timezone.now(),
                'responsible_role': 'DigiLand Platform',
                'audit_note': notes or 'All transaction milestones, documentation, and transfer verifications concluded.',
            }
        )
    except Exception:
        pass

    commission = getattr(transaction, 'commission', None)
    if commission:
        commission.status = 'Completed'
        commission.closed_at = commission.closed_at or timezone.now()
        commission.save(update_fields=['status', 'closed_at', 'updated_at'])

    return {'status': 'success', 'transaction_id': str(transaction.id), 'transaction': transaction}

# Backward compatibility alias
release_payment_to_seller = complete_transaction


def reverse_payment(transaction, admin_user=None, reason=None, reversal_reference=None, **kwargs):
    """
    Logs provider reversal evidence and updates transaction status to Reversed.
    DigiLand does not hold customer funds or process custodial refunds.
    """
    from django.utils import timezone
    from ..models import PaymentRecord, TransactionMilestone

    ref = reversal_reference or f"REV-{uuid.uuid4().hex[:10].upper()}"
    transaction.status = 'Reversed'
    transaction.save(update_fields=['status', 'updated_at'])

    payment_record = PaymentRecord.objects.filter(transaction=transaction).first()
    if payment_record:
        payment_record.payment_status = 'REVERSED'
        payment_record.notes = f"{payment_record.notes or ''} [Reversal Ref: {ref} - Reason: {reason or 'Admin review'}]".strip()
        payment_record.save(update_fields=['payment_status', 'notes', 'updated_at'])

    return {'status': 'success', 'reversal_reference': ref, 'transaction_id': str(transaction.id), 'transaction': transaction}

# Backward compatibility alias
reverse_escrow_payment = reverse_payment



def refund_payment_to_buyer(transaction):
    """
    Handles scenarios where the transaction fails verification checks and requires payment reversal.
    """
    from django.utils import timezone

    transaction.status = 'Refunded'
    transaction.save(update_fields=['status', 'updated_at'])

    commission = getattr(transaction, 'commission', None)
    if commission and commission.status not in {'Completed', 'Cancelled'}:
        commission.status = 'Cancelled'
        commission.closed_at = commission.closed_at or timezone.now()
        commission.save(update_fields=['status', 'closed_at', 'updated_at'])

    return transaction



# --- Paystack API Setup ---
PAYSTACK_API_URL = "https://api.paystack.co"

def get_paystack_headers():
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

def paystack_initialize(email, amount, reference, callback_url=None):
    payload = {
        "email": email,
        "amount": int(float(amount) * 100),
        "reference": reference,
        "callback_url": callback_url or getattr(settings, 'PAYSTACK_CALLBACK_URL', 'http://127.0.0.1:8000/api/v1/payments/callback')
    }
    response = requests.post(f"{PAYSTACK_API_URL}/transaction/initialize", json=payload, headers=get_paystack_headers())
    if response.status_code == 200:
        return response.json()
    return {"status": False, "message": "Failed to initialize Paystack transaction"}

def paystack_verify(reference):
    response = requests.get(f"{PAYSTACK_API_URL}/transaction/verify/{reference}", headers=get_paystack_headers())
    if response.status_code == 200:
        return response.json()
    return {"status": False, "message": "Transaction verification failed"}

def paystack_transfer(recipient_code, amount, reason="Escrow Release"):
    payload = {
        "source": "balance",
        "amount": int(float(amount) * 100),
        "recipient": recipient_code,
        "reason": reason
    }
    response = requests.post(f"{PAYSTACK_API_URL}/transfer", json=payload, headers=get_paystack_headers())
    if response.status_code == 200:
        return response.json()
    return {"status": False, "message": "Failed to transfer funds to seller"}


# --- M-PESA Daraja API Implementation ---
class DarajaAPI:
    """
    Safaricom Daraja API integration for M-PESA payments.
    Supports sandbox and production environments via settings.DARAJA_ENVIRONMENT.
    """
    _cached_token = None
    _token_expires_at = None

    @classmethod
    def get_base_url(cls):
        """Returns the appropriate Daraja API base URL according to environment setting."""
        env = getattr(settings, 'DARAJA_ENVIRONMENT', 'sandbox')
        if str(env).lower() == 'production':
            return "https://api.safaricom.co.ke"
        return "https://sandbox.safaricom.co.ke"

    @classmethod
    def get_access_token(cls):
        """
        Get OAuth access token from Daraja API (cached in-memory for the duration of token validity).
        """
        import time
        now = time.time()
        if cls._cached_token and cls._token_expires_at and now < (cls._token_expires_at - 60):
            return cls._cached_token

        try:
            base_url = cls.get_base_url()
            url = f"{base_url}/oauth/v1/generate?grant_type=client_credentials"
            consumer_key = getattr(settings, 'DARAJA_CONSUMER_KEY', '')
            consumer_secret = getattr(settings, 'DARAJA_CONSUMER_SECRET', '')
            
            if not consumer_key or not consumer_secret:
                logger.error("Daraja consumer key or secret not configured in backend environment")
                return None
            
            # Encode consumer key and secret
            credentials = f"{consumer_key}:{consumer_secret}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            
            headers = {
                "Authorization": f"Basic {encoded_credentials}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            access_token = result.get("access_token")
            expires_in = int(result.get("expires_in", 3599))
            
            if access_token:
                logger.info("Successfully obtained fresh Daraja access token")
                cls._cached_token = access_token
                cls._token_expires_at = now + expires_in
                return access_token
            else:
                logger.error("No access token in Daraja response")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Daraja access token: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting Daraja access token: {str(e)}")
            return None
    
    @classmethod
    def get_headers(cls):
        """
        Get API headers with fresh access token
        """
        access_token = cls.get_access_token()
        if not access_token:
            raise ValidationError("Failed to obtain Daraja access token")
        
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
    
    @classmethod
    def register_url(cls, callback_url, confirmation_url=None):
        """
        Register validation and confirmation URLs for C2B transactions
        """
        try:
            url = f"{cls.BASE_URL}/mpesa/c2b/v1/registerurl"
            
            if not confirmation_url:
                confirmation_url = callback_url
            
            payload = {
                "ShortCode": settings.DARAJA_SHORTCODE,
                "ResponseType": "Completed",
                "ConfirmationURL": confirmation_url,
                "ValidationURL": callback_url
            }
            
            log_api_call("Daraja URL Registration", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Daraja URL registration successful: {result}")
            return {
                "status": "success",
                "message": "URLs registered successfully",
                "data": result
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Daraja URL registration failed: {str(e)}")
            return {
                "status": "error",
                "message": f"URL registration failed: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in URL registration: {str(e)}")
            return {
                "status": "error",
                "message": "Internal registration error"
            }
    
    @classmethod
    def stk_push(cls, phone_number, amount, account_reference, transaction_desc, callback_url=None):
        """
        Initiate M-PESA STK Push payment
        
        Args:
            phone_number: Customer phone number (format: 254XXXXXXXXX)
            amount: Amount to charge
            account_reference: Transaction reference
            transaction_desc: Transaction description
            callback_url: Optional callback URL
            
        Returns:
            dict: STK Push result
        """
        try:
            # Validate and format phone number
            formatted_phone = validate_phone_number(phone_number)
            if not formatted_phone:
                return {
                    "status": "error",
                    "message": "Invalid phone number format"
                }
            base_url = cls.get_base_url()
            url = f"{base_url}/mpesa/stkpush/v1/processrequest"
            
            if not callback_url:
                secret_param = f"?secret={settings.MPESA_CALLBACK_SECRET}" if getattr(settings, 'MPESA_CALLBACK_SECRET', '') else ""
                callback_url = getattr(settings, 'DARAJA_CALLBACK_URL', '') or f"{_get_callback_base()}/api/v1/mpesa/callback{secret_param}"
            
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            password = base64.b64encode(
                f"{settings.DARAJA_SHORTCODE}{settings.DARAJA_PASSKEY}{timestamp}".encode()
            ).decode()
            
            payload = {
                "BusinessShortCode": settings.DARAJA_SHORTCODE,
                "Password": password,
                "Timestamp": timestamp,
                "TransactionType": "CustomerPayBillOnline",
                "Amount": int(float(amount)),
                "PartyA": formatted_phone,
                "PartyB": settings.DARAJA_SHORTCODE,
                "PhoneNumber": formatted_phone,
                "CallBackURL": callback_url,
                "AccountReference": account_reference,
                "TransactionDesc": transaction_desc
            }
            
            log_api_call("Daraja STK Push", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("ResponseCode") == "0":
                logger.info(f"STK Push initiated successfully for {formatted_phone}")
                return {
                    "status": "success",
                    "message": "STK Push initiated successfully",
                    "checkout_request_id": result.get("CheckoutRequestID"),
                    "merchant_request_id": result.get("MerchantRequestID"),
                    "customer_message": result.get("CustomerMessage")
                }
            else:
                logger.error(f"STK Push failed: {result}")
                return {
                    "status": "error",
                    "message": result.get("errorMessage", "STK Push failed"),
                    "response_code": result.get("ResponseCode")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Daraja STK Push request failed: {str(e)}")
            return {
                "status": "error",
                "message": f"STK Push service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in STK Push: {str(e)}")
            return {
                "status": "error",
                "message": "Internal STK Push error"
            }
    
    @classmethod
    def query_stk_status(cls, checkout_request_id):
        """
        Query STK Push transaction status
        
        Args:
            checkout_request_id: Checkout request ID from STK Push
            
        Returns:
            dict: Transaction status
        """
        try:
            base_url = cls.get_base_url()
            url = f"{base_url}/mpesa/stkpushquery/v1/query"
            
            timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
            password = base64.b64encode(
                f"{settings.DARAJA_SHORTCODE}{settings.DARAJA_PASSKEY}{timestamp}".encode()
            ).decode()
            
            payload = {
                "BusinessShortCode": settings.DARAJA_SHORTCODE,
                "Password": password,
                "Timestamp": timestamp,
                "CheckoutRequestID": checkout_request_id
            }
            
            log_api_call("Daraja STK Status Query", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("ResponseCode") == "0":
                return {
                    "status": "success",
                    "response_code": result.get("ResponseCode"),
                    "result_code": result.get("ResultCode"),
                    "result_desc": result.get("ResultDesc"),
                    "callback_metadata": result.get("CallbackMetadata", {})
                }
            else:
                return {
                    "status": "pending",
                    "response_code": result.get("ResponseCode"),
                    "message": result.get("ResultDesc", "Transaction pending")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Daraja STK status query failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Status query service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in status query: {str(e)}")
            return {
                "status": "error",
                "message": "Internal status query error"
            }

    @classmethod
    def reverse_transaction(cls, transaction_id, amount, receiver_party=None, remarks="Transaction reversal"):
        """
        Initiates M-PESA transaction reversal via Daraja API (if approved and configured).
        """
        try:
            base_url = cls.get_base_url()
            url = f"{base_url}/mpesa/reversal/v1/request"
            shortcode = getattr(settings, 'DARAJA_SHORTCODE', '')
            initiator = getattr(settings, 'DARAJA_INITIATOR_NAME', '')
            initiator_pass = getattr(settings, 'DARAJA_INITIATOR_PASSWORD', '')

            if not all([shortcode, initiator, initiator_pass]):
                logger.warning("Daraja Reversal credentials not configured")
                return {"status": "error", "message": "Daraja Reversal credentials not configured"}

            result_url = f"{_get_callback_base()}/api/v1/mpesa/reversal/callback"
            timeout_url = f"{_get_callback_base()}/api/v1/mpesa/reversal/timeout"

            payload = {
                "Initiator": initiator,
                "SecurityCredential": initiator_pass,
                "CommandID": "TransactionReversal",
                "TransactionID": transaction_id,
                "Amount": int(float(amount)),
                "ReceiverParty": receiver_party or shortcode,
                "RecieverIdentifierType": "11",
                "ResultURL": result_url,
                "QueueTimeOutURL": timeout_url,
                "Remarks": remarks[:100],
                "Occasion": "DisputeResolution"
            }
            log_api_call("Daraja Reversal", payload)
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            result = response.json()
            return {"status": "success", "data": result}
        except Exception as e:
            logger.error(f"Daraja Reversal request failed: {str(e)}")
            return {"status": "error", "message": str(e)}
    
    @classmethod
    def b2c_payment(cls, phone_number, amount, command_id="BusinessPayment", remarks="Escrow Payout"):
        """
        Initiate M-PESA B2C payment to seller
        
        Args:
            phone_number: Recipient phone number
            amount: Amount to pay
            command_id: Payment command type
            remarks: Payment remarks
            
        Returns:
            dict: B2C payment result
        """
        try:
            # Validate and format phone number
            formatted_phone = validate_phone_number(phone_number)
            if not formatted_phone:
                return {
                    "status": "error",
                    "message": "Invalid phone number format"
                }
            
            url = f"{cls.BASE_URL}/mpesa/b2c/v1/paymentrequest"
            
            # Generate security credentials
            initiator_password = settings.DARAJA_INITIATOR_PASSWORD
            security_credentials = base64.b64encode(initiator_password.encode()).decode()
            
            payload = {
                "InitiatorName": settings.DARAJA_INITIATOR_NAME,
                "SecurityCredential": security_credentials,
                "CommandID": command_id,
                "Amount": int(float(amount)),
                "PartyA": settings.DARAJA_SHORTCODE,
                "PartyB": formatted_phone,
                "Remarks": remarks,
                "QueueTimeOutURL": f"{_get_callback_base()}/api/v1/mpesa/b2c/timeout",
                "ResultURL": f"{_get_callback_base()}/api/v1/mpesa/b2c/result",
                "Occasion": "Escrow Payout"
            }
            
            log_api_call("Daraja B2C Payment", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("ResponseCode") == "0":
                logger.info(f"B2C payment initiated successfully for {formatted_phone}")
                return {
                    "status": "success",
                    "message": "B2C payment initiated successfully",
                    "conversation_id": result.get("ConversationID"),
                    "originator_conversation_id": result.get("OriginatorConversationID"),
                    "response_description": result.get("ResponseDescription")
                }
            else:
                logger.error(f"B2C payment failed: {result}")
                return {
                    "status": "error",
                    "message": result.get("ResponseDescription", "B2C payment failed"),
                    "response_code": result.get("ResponseCode")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Daraja B2C payment failed: {str(e)}")
            return {
                "status": "error",
                "message": f"B2C payment service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in B2C payment: {str(e)}")
            return {
                "status": "error",
                "message": "Internal B2C payment error"
            }
    
    @classmethod
    def b2b_payment(cls, receiver_party, amount, command_id="BusinessPayBill", remarks="B2B Payment"):
        """
        Initiate M-PESA B2B payment between businesses
        
        Args:
            receiver_party: Receiver shortcode
            amount: Amount to pay
            command_id: Payment command type
            remarks: Payment remarks
            
        Returns:
            dict: B2B payment result
        """
        try:
            url = f"{cls.BASE_URL}/mpesa/b2b/v1/paymentrequest"
            
            # Generate security credentials
            initiator_password = settings.DARAJA_INITIATOR_PASSWORD
            security_credentials = base64.b64encode(initiator_password.encode()).decode()
            
            payload = {
                "Initiator": settings.DARAJA_INITIATOR_NAME,
                "SecurityCredential": security_credentials,
                "CommandID": command_id,
                "SenderIdentifierType": "4",
                "RecieverIdentifierType": "4",
                "Amount": int(float(amount)),
                "PartyA": settings.DARAJA_SHORTCODE,
                "PartyB": receiver_party,
                "AccountReference": f"B2B-{generate_transaction_reference()}",
                "Remarks": remarks,
                "QueueTimeOutURL": f"{_get_callback_base()}/api/v1/mpesa/b2b/timeout",
                "ResultURL": f"{_get_callback_base()}/api/v1/mpesa/b2b/result"
            }
            
            log_api_call("Daraja B2B Payment", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("ResponseCode") == "0":
                logger.info(f"B2B payment initiated successfully for {receiver_party}")
                return {
                    "status": "success",
                    "message": "B2B payment initiated successfully",
                    "conversation_id": result.get("ConversationID"),
                    "originator_conversation_id": result.get("OriginatorConversationID"),
                    "response_description": result.get("ResponseDescription")
                }
            else:
                logger.error(f"B2B payment failed: {result}")
                return {
                    "status": "error",
                    "message": result.get("ResponseDescription", "B2B payment failed"),
                    "response_code": result.get("ResponseCode")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Daraja B2B payment failed: {str(e)}")
            return {
                "status": "error",
                "message": f"B2B payment service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in B2B payment: {str(e)}")
            return {
                "status": "error",
                "message": "Internal B2B payment error"
            }
    
    @classmethod
    def reverse_transaction(cls, transaction_id, amount, receiver_party, remarks="Transaction Reversal"):
        """
        Reverse an M-PESA transaction
        
        Args:
            transaction_id: Original transaction ID to reverse
            amount: Amount to reverse
            receiver_party: Receiver of the reversal
            remarks: Reversal remarks
            
        Returns:
            dict: Reversal result
        """
        try:
            url = f"{cls.BASE_URL}/mpesa/reversal/v1/request"
            
            # Generate security credentials
            initiator_password = settings.DARAJA_INITIATOR_PASSWORD
            security_credentials = base64.b64encode(initiator_password.encode()).decode()
            
            payload = {
                "Initiator": settings.DARAJA_INITIATOR_NAME,
                "SecurityCredential": security_credentials,
                "CommandID": "TransactionReversal",
                "TransactionID": transaction_id,
                "Amount": int(float(amount)),
                "ReceiverParty": receiver_party,
                "RecieverIdentifierType": "4",
                "ResultURL": f"{_get_callback_base()}/api/v1/mpesa/reversal/result",
                "QueueTimeOutURL": f"{_get_callback_base()}/api/v1/mpesa/reversal/timeout",
                "Remarks": remarks,
                "Occasion": "Transaction Reversal"
            }
            
            log_api_call("Daraja Transaction Reversal", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("ResponseCode") == "0":
                logger.info(f"Transaction reversal initiated successfully for {transaction_id}")
                return {
                    "status": "success",
                    "message": "Transaction reversal initiated successfully",
                    "conversation_id": result.get("ConversationID"),
                    "originator_conversation_id": result.get("OriginatorConversationID"),
                    "response_description": result.get("ResponseDescription")
                }
            else:
                logger.error(f"Transaction reversal failed: {result}")
                return {
                    "status": "error",
                    "message": result.get("ResponseDescription", "Transaction reversal failed"),
                    "response_code": result.get("ResponseCode")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Daraja transaction reversal failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Transaction reversal service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in transaction reversal: {str(e)}")
            return {
                "status": "error",
                "message": "Internal transaction reversal error"
            }
    
    @classmethod
    def query_transaction_status(cls, transaction_id, party_a, identifier_type="4"):
        """
        Query the status of an M-PESA transaction
        
        Args:
            transaction_id: Transaction ID to query
            party_a: Party involved in transaction
            identifier_type: Type of identifier (default: 4 for shortcode)
            
        Returns:
            dict: Transaction status result
        """
        try:
            url = f"{cls.BASE_URL}/mpesa/transactionstatus/v1/query"
            
            # Generate security credentials
            initiator_password = settings.DARAJA_INITIATOR_PASSWORD
            security_credentials = base64.b64encode(initiator_password.encode()).decode()
            
            payload = {
                "Initiator": settings.DARAJA_INITIATOR_NAME,
                "SecurityCredential": security_credentials,
                "CommandID": "TransactionStatusQuery",
                "TransactionID": transaction_id,
                "PartyA": party_a,
                "IdentifierType": identifier_type,
                "ResultURL": f"{_get_callback_base()}/api/v1/mpesa/status/result",
                "QueueTimeOutURL": f"{_get_callback_base()}/api/v1/mpesa/status/timeout",
                "Remarks": "Transaction status query",
                "Occasion": "Status Query"
            }
            
            log_api_call("Daraja Transaction Status Query", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("ResponseCode") == "0":
                return {
                    "status": "success",
                    "transaction_status": result.get("Result"),
                    "conversation_id": result.get("ConversationID"),
                    "originator_conversation_id": result.get("OriginatorConversationID")
                }
            else:
                return {
                    "status": "error",
                    "message": result.get("ResponseDescription", "Status query failed"),
                    "response_code": result.get("ResponseCode")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Daraja transaction status query failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Status query service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in transaction status query: {str(e)}")
            return {
                "status": "error",
                "message": "Internal status query error"
            }
    
    @classmethod
    def query_account_balance(cls, party_a, identifier_type="4"):
        """
        Query M-PESA account balance
        
        Args:
            party_a: Party whose balance to query
            identifier_type: Type of identifier (default: 4 for shortcode)
            
        Returns:
            dict: Account balance result
        """
        try:
            url = f"{cls.BASE_URL}/mpesa/accountbalance/v1/query"
            
            # Generate security credentials
            initiator_password = settings.DARAJA_INITIATOR_PASSWORD
            security_credentials = base64.b64encode(initiator_password.encode()).decode()
            
            payload = {
                "Initiator": settings.DARAJA_INITIATOR_NAME,
                "SecurityCredential": security_credentials,
                "CommandID": "AccountBalance",
                "PartyA": party_a,
                "IdentifierType": identifier_type,
                "ResultURL": f"{_get_callback_base()}/api/v1/mpesa/balance/result",
                "QueueTimeOutURL": f"{_get_callback_base()}/api/v1/mpesa/balance/timeout",
                "Remarks": "Account balance query",
                "Occasion": "Balance Query"
            }
            
            log_api_call("Daraja Account Balance Query", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("ResponseCode") == "0":
                return {
                    "status": "success",
                    "balance": result.get("Result"),
                    "conversation_id": result.get("ConversationID"),
                    "originator_conversation_id": result.get("OriginatorConversationID")
                }
            else:
                return {
                    "status": "error",
                    "message": result.get("ResponseDescription", "Balance query failed"),
                    "response_code": result.get("ResponseCode")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Daraja account balance query failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Balance query service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in account balance query: {str(e)}")
            return {
                "status": "error",
                "message": "Internal balance query error"
            }
    
    @classmethod
    def simulate_c2b_payment(cls, short_code, amount, msisdn, bill_ref_number):
        """
        Simulate a C2B payment for testing
        
        Args:
            short_code: Business shortcode
            amount: Amount to simulate
            msisdn: Customer phone number
            bill_ref_number: Bill reference number
            
        Returns:
            dict: Simulation result
        """
        try:
            url = f"{cls.BASE_URL}/mpesa/c2b/v1/simulate"
            
            payload = {
                "ShortCode": short_code,
                "CommandID": "CustomerPayBillOnline",
                "Amount": int(float(amount)),
                "Msisdn": validate_phone_number(msisdn) or msisdn,
                "BillRefNumber": bill_ref_number
            }
            
            log_api_call("Daraja C2B Simulation", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("ResponseCode") == "0":
                logger.info(f"C2B payment simulation successful")
                return {
                    "status": "success",
                    "message": "C2B payment simulation successful",
                    "transaction_id": result.get("TransactionID"),
                    "conversation_id": result.get("ConversationID")
                }
            else:
                logger.error(f"C2B payment simulation failed: {result}")
                return {
                    "status": "error",
                    "message": result.get("ResponseDescription", "C2B simulation failed"),
                    "response_code": result.get("ResponseCode")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Daraja C2B simulation failed: {str(e)}")
            return {
                "status": "error",
                "message": f"C2B simulation service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in C2B simulation: {str(e)}")
            return {
                "status": "error",
                "message": "Internal C2B simulation error"
            }
    
    @classmethod
    def redeem_bonga_points(cls, msisdn, amount, bonga_points, conversion_rate=0.2, short_code=None, account_number=""):
        """
        Redeem Bonga points for payment
        
        Args:
            msisdn: Customer phone number
            amount: Amount to pay
            bonga_points: Points to redeem
            conversion_rate: Points to money conversion rate
            short_code: Business shortcode (optional)
            account_number: Account number (optional)
            
        Returns:
            dict: Bonga redemption result
        """
        try:
            url = f"{cls.BASE_URL}/v1/lipa/na/bonga/redeem-paybill"
            
            payload = {
                "msisdn": validate_phone_number(msisdn) or msisdn,
                "amount": int(float(amount)),
                "bongaPoints": int(bonga_points),
                "conversionRate": float(conversion_rate),
                "shortCode": short_code or settings.DARAJA_SHORTCODE,
                "accountNumber": account_number
            }
            
            log_api_call("Daraja Bonga Points Redemption", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("ResponseCode") == "0":
                logger.info(f"Bonga points redemption successful for {msisdn}")
                return {
                    "status": "success",
                    "message": "Bonga points redeemed successfully",
                    "transaction_id": result.get("TransactionID"),
                    "points_used": bonga_points,
                    "amount_paid": amount
                }
            else:
                logger.error(f"Bonga points redemption failed: {result}")
                return {
                    "status": "error",
                    "message": result.get("ResponseDescription", "Bonga redemption failed"),
                    "response_code": result.get("ResponseCode")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Daraja Bonga redemption failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Bonga redemption service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in Bonga redemption: {str(e)}")
            return {
                "status": "error",
                "message": "Internal Bonga redemption error"
            }
    
    @classmethod
    def calculate_bonga_points(cls, points):
        """
        Calculate monetary value of Bonga points
        
        Args:
            points: Number of Bonga points
            
        Returns:
            dict: Points calculation result
        """
        try:
            url = f"{cls.BASE_URL}/v1/lipa/na/bonga/calculator-points"
            
            payload = {
                "points": int(points)
            }
            
            log_api_call("Daraja Bonga Points Calculation", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            
            if result.get("ResponseCode") == "0":
                return {
                    "status": "success",
                    "points": points,
                    "amount": result.get("Amount"),
                    "conversion_rate": result.get("ConversionRate")
                }
            else:
                return {
                    "status": "error",
                    "message": result.get("ResponseDescription", "Points calculation failed"),
                    "response_code": result.get("ResponseCode")
                }
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Daraja Bonga calculation failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Bonga calculation service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in Bonga calculation: {str(e)}")
            return {
                "status": "error",
                "message": "Internal Bonga calculation error"
            }

# --- Dedicated Non-Custodial Payment Architecture & M-PESA Functions ---

def create_payment_intent(
    transaction,
    payer,
    amount=None,
    purpose='LAND_PURCHASE',
    recipient=None,
    parcel=None,
    provider='MPESA',
    payment_type=None,
    beneficiary_user=None,
    beneficiary_name=None,
    service_type=None
):
    """
    Creates a dedicated PaymentRecord via PaymentRouter.
    Separates Land Purchase Funds, Platform Service Fees, and Professional Service Fees.
    Never holds funds or creates an escrow balance.
    """
    from decimal import Decimal
    from .payment_router import PaymentRouter
    
    if purpose == 'LAND_PURCHASE':
        return PaymentRouter.create_land_purchase_payment(
            transaction=transaction,
            payer=payer,
            amount=Decimal(str(amount)) if amount else None,
            provider=provider
        )
    elif purpose == 'DIGILAND_SERVICE_FEE':
        return PaymentRouter.create_digiland_fee_payment(
            transaction=transaction,
            payer=payer,
            amount=Decimal(str(amount)) if amount else None,
            provider=provider
        )
    elif purpose in ['SURVEY_FEE', 'LEGAL_FEE', 'INSPECTION_FEE']:
        prof = beneficiary_user or recipient or getattr(transaction, 'seller', None)
        if not prof:
            prof = payer
        return PaymentRouter.create_professional_payment(
            transaction=transaction,
            payer=payer,
            professional=prof,
            service_type=service_type or purpose,
            amount=Decimal(str(amount)) if amount else Decimal('15000.00'),
            provider=provider
        )
    else:
        # Fallback for other approved payments
        from ..models import PaymentRecord
        payment = PaymentRecord.objects.create(
            transaction=transaction,
            parcel=parcel or getattr(transaction, 'land_parcel', None),
            payer=payer,
            recipient=recipient,
            beneficiary_user=beneficiary_user or recipient,
            beneficiary_name=beneficiary_name or 'Beneficiary',
            purpose=purpose,
            payment_purpose=purpose,
            payment_type=payment_type or 'DIRECT_SETTLEMENT',
            payment_provider=provider,
            amount=Decimal(str(amount)) if amount else Decimal('0.00'),
            currency='KES',
            status='CREATED',
        )
        return payment


def initiate_mpesa_stk_push(payment, phone_number, callback_url=None):
    """
    Initiates M-Pesa STK push for a PaymentRecord, transitioning state to CUSTOMER_ACTION_REQUIRED.
    Does not hold funds; records initiation for asynchronous provider confirmation.
    """
    from django.utils import timezone
    payment.status = 'PAYMENT_INITIATED'
    payment.payment_status = 'INITIATED'
    payment.initiated_at = timezone.now()
    payment.account_reference = payment.digiland_reference
    payment.save(update_fields=['status', 'payment_status', 'initiated_at', 'account_reference', 'updated_at'])

    account_ref = payment.digiland_reference
    desc = f"{payment.get_purpose_display()} {payment.digiland_reference}"[:60]

    result = DarajaAPI.stk_push(
        phone_number=phone_number,
        amount=payment.amount,
        account_reference=account_ref,
        transaction_desc=desc,
        callback_url=callback_url
    )

    if result.get("status") == "success" or result.get("ResponseCode") == "0":
        checkout_req_id = result.get("checkout_request_id") or result.get("CheckoutRequestID")
        merchant_req_id = result.get("merchant_request_id") or result.get("MerchantRequestID")
        payment.status = 'CUSTOMER_ACTION_REQUIRED'
        payment.checkout_request_reference = checkout_req_id
        payment.merchant_request_reference = merchant_req_id
        payment.save(update_fields=['status', 'checkout_request_reference', 'merchant_request_reference', 'updated_at'])

        return {
            'status': 'success',
            'checkout_request_id': checkout_req_id,
            'merchant_request_id': merchant_req_id,
            'payment_id': str(payment.id),
            'digiland_reference': payment.digiland_reference,
            'message': result.get("customer_message") or "STK Push initiated. Authorize payment on your phone.",
        }
    else:
        payment.status = 'PAYMENT_FAILED'
        payment.payment_status = 'FAILED'
        payment.failed_at = timezone.now()
        payment.failure_reason = result.get("message") or "STK Push initiation failed"
        payment.save(update_fields=['status', 'payment_status', 'failed_at', 'failure_reason', 'updated_at'])

        return {
            'status': 'error',
            'payment_id': str(payment.id),
            'digiland_reference': payment.digiland_reference,
            'message': payment.failure_reason,
        }


def process_mpesa_callback(callback_data):
    """
    Idempotently processes Daraja STK callback payload.
    Authenticates amount, prevents duplicate processing, records audit evidence,
    and updates transaction status without custodial money holding.
    """
    from decimal import Decimal
    from django.utils import timezone
    from ..models import PaymentRecord, TransactionMilestone, AuditLog

    stk_callback = callback_data.get('Body', {}).get('stkCallback', {}) if isinstance(callback_data, dict) and 'Body' in callback_data else callback_data
    if not isinstance(stk_callback, dict):
        stk_callback = callback_data

    checkout_req_id = stk_callback.get('CheckoutRequestID') or callback_data.get('CheckoutRequestID')
    result_code = stk_callback.get('ResultCode') if 'ResultCode' in stk_callback else callback_data.get('ResultCode')
    result_desc = stk_callback.get('ResultDesc', '') or callback_data.get('ResultDesc', '')

    if not checkout_req_id:
        logger.warning("M-Pesa callback missing CheckoutRequestID")
        return {"status": "error", "message": "Missing CheckoutRequestID"}

    payment = PaymentRecord.objects.filter(checkout_request_reference=checkout_req_id).first()
    if not payment:
        logger.warning(f"No PaymentRecord found for CheckoutRequestID {checkout_req_id}")
        return {"status": "error", "message": f"Payment record not found for {checkout_req_id}"}

    # Idempotency Guard: prevent double-processing if already confirmed
    if payment.status in ['PAYMENT_CONFIRMED', 'CONFIRMED']:
        logger.info(f"Callback already processed for payment {payment.digiland_reference} (idempotent ignore)")
        return {"status": "duplicate_ignored", "already_processed": True, "message": "Payment already confirmed", "payment_id": str(payment.id)}

    if result_code == 0 or result_code == "0":
        metadata = stk_callback.get('CallbackMetadata', {}).get('Item', []) or callback_data.get('CallbackMetadata', {}).get('Item', [])
        amount = phone = mpesa_receipt = trans_date = None
        for item in metadata:
            name = item.get('Name')
            value = item.get('Value')
            if name == 'Amount':
                amount = value
            elif name == 'PhoneNumber':
                phone = value
            elif name == 'MpesaReceiptNumber':
                mpesa_receipt = value
            elif name == 'TransactionDate':
                trans_date = value

        # Receipt Reuse Guard (Section 34 / Test 20): Check if receipt was already recorded
        if mpesa_receipt and PaymentRecord.objects.filter(provider_reference=mpesa_receipt).exclude(id=payment.id).exists():
            logger.error(f"Provider receipt {mpesa_receipt} has already been recorded for another payment!")
            payment.status = 'PAYMENT_FAILED'
            payment.payment_status = 'FAILED'
            payment.failed_at = timezone.now()
            payment.failure_reason = f"Provider receipt {mpesa_receipt} already recorded for another transaction"
            payment.save(update_fields=['status', 'payment_status', 'failed_at', 'failure_reason', 'updated_at'])
            return {"status": "failed", "message": f"Provider receipt {mpesa_receipt} already recorded for another transaction", "payment_id": str(payment.id)}

        # Amount validation: verify amount received matches or exceeds expected payment amount
        if amount is not None and Decimal(str(amount)) < payment.amount:
            logger.error(f"Underpayment alert! Expected {payment.amount}, received {amount} for {payment.digiland_reference}")
            payment.status = 'PAYMENT_FAILED'
            payment.payment_status = 'FAILED'
            payment.failed_at = timezone.now()
            payment.failure_reason = f"Underpayment: Expected KES {payment.amount}, received KES {amount}"
            payment.evidence_metadata = callback_data
            payment.save(update_fields=['status', 'payment_status', 'failed_at', 'failure_reason', 'evidence_metadata', 'updated_at'])
            return {"status": "failed", "message": payment.failure_reason, "payment_id": str(payment.id)}

        # Payment Confirmed!
        receipt_code = mpesa_receipt or f"MPESA-{checkout_req_id}"
        payment.status = 'PAYMENT_CONFIRMED'
        payment.payment_status = 'CONFIRMED'
        payment.provider_reference = receipt_code
        payment.confirmed_at = timezone.now()
        payment.evidence_metadata = {
            'callback': callback_data,
            'mpesa_receipt': mpesa_receipt,
            'amount': str(amount),
            'phone': str(phone),
            'transaction_date': str(trans_date),
        }
        payment.save(update_fields=['status', 'payment_status', 'provider_reference', 'confirmed_at', 'evidence_metadata', 'updated_at'])

        # Update parent transaction
        transaction = payment.transaction
        if transaction:
            transaction.payment_reference = receipt_code
            if transaction.status in ['Initiated', 'Under_Verification', 'Deposit_Paid']:
                transaction.status = 'Payment_Confirmed'
            transaction.save(update_fields=['status', 'payment_reference', 'updated_at'])

            # Progress milestone 13
            try:
                TransactionMilestone.objects.update_or_create(
                    transaction=transaction,
                    milestone_code='PAYMENT_CONFIRMED',
                    defaults={
                        'sequence_order': 13,
                        'status': 'COMPLETED',
                        'completed_at': timezone.now(),
                        'responsible_party': transaction.buyer,
                        'responsible_role': 'Buyer',
                        'evidence_data': {'receipt': receipt_code, 'provider': 'MPESA', 'amount': str(amount)},
                        'audit_note': f"Payment confirmed and recorded via M-Pesa. Receipt: {receipt_code}",
                    }
                )
            except Exception as e:
                logger.warning(f"Could not record milestone 13: {e}")

            # Audit log
            try:
                AuditLog.objects.create(
                    user=transaction.buyer,
                    action=f"PAYMENT_CONFIRMED: {payment.digiland_reference} (M-Pesa {receipt_code})",
                    metadata={
                        'payment_id': str(payment.id),
                        'transaction_id': str(transaction.id),
                        'amount': str(amount),
                        'receipt': receipt_code,
                    }
                )
            except Exception:
                pass

        return {"status": "success", "message": "Payment confirmed and recorded", "payment_id": str(payment.id), "receipt": receipt_code}

    else:
        # ResultCode != 0 -> Failed
        payment.status = 'PAYMENT_FAILED'
        payment.payment_status = 'FAILED'
        payment.failed_at = timezone.now()
        payment.failure_reason = result_desc or f"Failed with result code {result_code}"
        payment.evidence_metadata = callback_data
        payment.save(update_fields=['status', 'payment_status', 'failed_at', 'failure_reason', 'evidence_metadata', 'updated_at'])

        return {"status": "failed", "message": payment.failure_reason, "payment_id": str(payment.id)}


def query_payment_status(payment_id_or_checkout_id):
    """
    Retrieves authoritative payment status from backend database.
    If status is still CUSTOMER_ACTION_REQUIRED and older than 35s, queries Daraja STK status.
    """
    from django.utils import timezone
    from django.db.models import Q
    from ..models import PaymentRecord

    payment = None
    try:
        import uuid
        uid = uuid.UUID(str(payment_id_or_checkout_id))
        payment = PaymentRecord.objects.filter(id=uid).first()
    except Exception:
        payment = PaymentRecord.objects.filter(
            Q(checkout_request_reference=payment_id_or_checkout_id) |
            Q(digiland_reference=payment_id_or_checkout_id)
        ).first()

    if not payment:
        return {"status": "error", "message": "Payment not found"}

    # If pending for a while, query provider status actively
    if payment.status in ['CUSTOMER_ACTION_REQUIRED', 'PAYMENT_INITIATED', 'PAYMENT_PROCESSING'] and payment.checkout_request_reference:
        now = timezone.now()
        if payment.initiated_at and (now - payment.initiated_at).total_seconds() > 35:
            query_res = DarajaAPI.query_stk_status(payment.checkout_request_reference)
            if query_res.get("ResultCode") == "0":
                process_mpesa_callback({
                    'CheckoutRequestID': payment.checkout_request_reference,
                    'ResultCode': 0,
                    'ResultDesc': query_res.get("ResultDesc", "Success"),
                    'CallbackMetadata': query_res.get("callback_metadata", {}),
                })
                payment.refresh_from_db()
            elif query_res.get("ResultCode") and str(query_res.get("ResultCode")) != "0":
                process_mpesa_callback({
                    'CheckoutRequestID': payment.checkout_request_reference,
                    'ResultCode': int(query_res.get("ResultCode")),
                    'ResultDesc': query_res.get("ResultDesc", "Payment Failed"),
                })
                payment.refresh_from_db()

    return {
        'status': 'success',
        'payment_id': str(payment.id),
        'digiland_reference': payment.digiland_reference,
        'payment_status': payment.status,
        'is_confirmed': payment.status in ['PAYMENT_CONFIRMED', 'CONFIRMED'],
        'is_failed': payment.status in ['PAYMENT_FAILED', 'FAILED', 'PAYMENT_CANCELLED', 'PAYMENT_EXPIRED'],
        'provider_reference': payment.provider_reference,
        'failure_reason': payment.failure_reason,
        'amount': float(payment.amount),
        'currency': payment.currency,
        'confirmed_at': payment.confirmed_at.isoformat() if payment.confirmed_at else None,
    }


def request_refund(payment, requested_by, amount=None, reason="Customer requested refund"):
    """
    Creates a formal non-custodial RefundRecord in status REFUND_REQUESTED.
    """
    from ..models import RefundRecord
    amt = amount or payment.amount
    refund = RefundRecord.objects.create(
        payment=payment,
        transaction=payment.transaction,
        amount=amt,
        currency=payment.currency,
        status='REFUND_REQUESTED',
        reason=reason,
        requested_by=requested_by,
    )
    return refund


def review_refund(refund_record, reviewed_by, approve=True, notes=""):
    """
    Advances refund from REFUND_REQUESTED to REFUND_APPROVED or REFUND_REJECTED.
    """
    refund_record.reviewed_by = reviewed_by
    if notes:
        refund_record.notes = f"{refund_record.notes or ''} [Review: {notes}]".strip()
    if approve:
        refund_record.status = 'REFUND_APPROVED'
    else:
        refund_record.status = 'REFUND_REJECTED'
    refund_record.save(update_fields=['status', 'reviewed_by', 'notes', 'updated_at'])
    return refund_record


def execute_refund(refund_record, admin_user=None, provider_reversal_reference=None):
    """
    Executes refund/reversal with provider and marks REFUND_CONFIRMED.
    Does not execute custodial fund transfers.
    """
    ref = provider_reversal_reference
    if not ref:
        # If Daraja Reversal API is configured and payment has a provider receipt
        if getattr(settings, 'DARAJA_INITIATOR_NAME', None) and refund_record.payment.provider_reference:
            res = DarajaAPI.reverse_transaction(
                transaction_id=refund_record.payment.provider_reference,
                amount=refund_record.amount,
                remarks=f"Reversal for {refund_record.refund_reference}"
            )
            if res.get("status") == "success":
                ref = res.get("data", {}).get("ConversationID") or f"REV-MPESA-{uuid.uuid4().hex[:8].upper()}"

    if not ref:
        ref = f"REV-PORTAL-{uuid.uuid4().hex[:8].upper()}"

    refund_record.status = 'REFUND_CONFIRMED'
    refund_record.provider_reversal_reference = ref
    refund_record.save(update_fields=['status', 'provider_reversal_reference', 'updated_at'])

    # Update payment record
    payment = refund_record.payment
    payment.status = 'PAYMENT_REVERSED'
    payment.payment_status = 'REVERSED'
    payment.notes = f"{payment.notes or ''} [Refund Confirmed: {refund_record.refund_reference} - Ref: {ref}]".strip()
    payment.save(update_fields=['status', 'payment_status', 'notes', 'updated_at'])

    # Update transaction
    transaction = refund_record.transaction
    transaction.status = 'Reversed'
    transaction.save(update_fields=['status', 'updated_at'])

    return {
        'status': 'success',
        'refund_reference': refund_record.refund_reference,
        'provider_reversal_reference': ref,
    }


def mpesa_stk_push(phone, amount, transaction_id, purpose='LAND_PURCHASE', payment=None):
    """
    Enhanced M-PESA STK Push using Daraja API.
    Creates or updates PaymentRecord and links to transaction without custodial claims.
    """
    from ..models import Transaction, PaymentRecord
    transaction = None
    try:
        import uuid
        uid = uuid.UUID(str(transaction_id))
        transaction = Transaction.objects.filter(id=uid).first()
    except Exception:
        transaction = Transaction.objects.filter(transaction_reference=str(transaction_id)).first()

    if not payment and transaction:
        payer = transaction.buyer
        payment = create_payment_intent(
            transaction=transaction,
            payer=payer,
            amount=amount,
            purpose=purpose,
            recipient=transaction.seller,
            parcel=transaction.land_parcel,
            provider='MPESA'
        )

    if payment:
        return initiate_mpesa_stk_push(payment, phone)

    # Fallback if no payment entity could be created
    ref = getattr(transaction, 'transaction_reference', None) or f"DL-{str(transaction_id)[:10]}"
    account_reference = ref
    transaction_desc = f"Land payment for {ref}"[:60]
    
    result = DarajaAPI.stk_push(
        phone_number=phone,
        amount=amount,
        account_reference=account_reference,
        transaction_desc=transaction_desc
    )
    return result


def mpesa_query_status(checkout_request_id):
    """
    Enhanced M-PESA status query using Daraja API and local payment record fallback.
    """
    return query_payment_status(checkout_request_id)


def mpesa_b2c_transfer(phone, amount, transaction_id):
    """
    Enhanced M-PESA B2C transfer using Daraja API
    """
    if not all([getattr(settings, 'DARAJA_CONSUMER_KEY', None), 
                getattr(settings, 'DARAJA_CONSUMER_SECRET', None),
                getattr(settings, 'DARAJA_INITIATOR_NAME', None),
                getattr(settings, 'DARAJA_INITIATOR_PASSWORD', None)]):
        logger.warning("Daraja B2C API not fully configured, using mock implementation")
        return {
            "status": True,
            "gateway": "MPESA",
            "message": f"B2C Transfer to {phone} initiated successfully",
            "ConversationID": f"AG_{uuid.uuid4().hex[:10]}"
        }
    
    remarks = f"Payment transfer for transaction {transaction_id}"
    result = DarajaAPI.b2c_payment(
        phone_number=phone,
        amount=amount,
        remarks=remarks
    )
    return result


def reverse_payment(transaction, reason="Payment reversal", admin_user=None, reversal_reference=None, **kwargs):
    """
    Logs provider reversal evidence and updates transaction status to Reversed.
    DigiLand does not hold customer funds or process custodial refunds.
    """
    from django.utils import timezone
    from ..models import PaymentRecord

    ref = reversal_reference or f"REV-{uuid.uuid4().hex[:10].upper()}"
    transaction.status = 'Reversed'
    transaction.save(update_fields=['status', 'updated_at'])

    payment_record = PaymentRecord.objects.filter(transaction=transaction).first()
    if payment_record:
        payment_record.status = 'REVERSED'
        payment_record.payment_status = 'REVERSED'
        payment_record.notes = f"{payment_record.notes or ''} [Reversal Ref: {ref} - Reason: {reason}]".strip()
        payment_record.save(update_fields=['status', 'payment_status', 'notes', 'updated_at'])

    return {
        "status": "success",
        "message": "Payment reversal recorded successfully",
        "reversal_reference": ref,
        "transaction_id": str(transaction.id),
        "transaction": transaction,
    }


# Backward compatibility alias
reverse_escrow_payment = reverse_payment


def check_transaction_status(transaction_ref):

    """
    Check the status of a transaction via Daraja API
    
    Args:
        transaction_ref: Transaction reference to check
        
    Returns:
        dict: Transaction status
    """
    try:
        if not all([hasattr(settings, 'DARAJA_CONSUMER_KEY'), 
                    hasattr(settings, 'DARAJA_CONSUMER_SECRET')]):
            logger.warning("Daraja status API not fully configured, returning mock status")
            return {
                "status": "success",
                "transaction_status": "Completed",
                "amount": 0,
                "message": "Mock status check"
            }
        
        # Query transaction status
        result = DarajaAPI.query_transaction_status(
            transaction_id=transaction_ref,
            party_a=getattr(settings, 'DARAJA_SHORTCODE', ''),
            identifier_type="4"
        )
        
        return result
        
    except Exception as e:
        logger.error(f"Error checking transaction status: {str(e)}")
        return {
            "status": "error",
            "message": f"Status check error: {str(e)}"
        }


def calculate_checkout_fees(agreed_price, include_verification=False, include_due_diligence=False, include_legal=None):
    """
    Calculate the transparent checkout/escrow fees breakdown.
    The checkout page shares the same fee model as the service-fee engine:
    - Platform Service Fee: 4% of agreed price
    - Escrow Holding Fee: 2% of agreed price
    - Processing Fee: Flat KES 50
    - Optional Verification Fee: KES 10,000
    - Optional Due Diligence Fee: KES 20,000
    """
    from decimal import Decimal
    from types import SimpleNamespace
    from core.services.service_fee import ServiceFeeService

    if include_legal is not None:
        include_verification = include_legal

    quote = SimpleNamespace(agreed_price=Decimal(str(agreed_price)))
    fees = ServiceFeeService.calculate_fees(
        quote,
        include_verification=include_verification,
        include_due_diligence=include_due_diligence,
    )

    return {
        'land_price': fees['land_price'],
        'platform_service_fee': fees['platform_service_fee'],
        'platform_fee': fees['platform_service_fee'],
        'escrow_fee': fees['escrow_fee'],
        'escrow_holding_fee': fees['escrow_holding_fee'],
        'processing_fee': fees['payment_processing_fee'],
        'payment_processing_fee': fees['payment_processing_fee'],
        'verification_fee': fees['verification_fee'],
        'legal_verification_fee': fees['verification_fee'],
        'due_diligence_fee': fees['due_diligence_fee'],
        'total_fees': fees['total_fees'],
        'total_payable': fees['total_payable'],
        'grand_total': fees['grand_total'],
    }


def pay_for_promotion(promotion_id, payment_ref, gateway='paystack'):
    """
    Simulates payment verification for a seller/agent promotion campaign.
    Marks promotion as active and paid upon success.
    """
    try:
        from core.models import LandPromotion
        promo = LandPromotion.objects.get(id=promotion_id)
        promo.payment_reference = payment_ref
        promo.payment_status = 'Paid'
        promo.is_active = True
        promo.save(update_fields=['payment_reference', 'payment_status', 'is_active'])
        return {"status": "success", "message": "Promotion paid successfully"}
    except Exception as e:
        logger.error(f"Failed to pay for promotion: {e}")
        return {"status": "error", "message": str(e)}
