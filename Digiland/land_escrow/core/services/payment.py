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

# --- Shared Escrow Logic ---
def hold_payment(transaction):
    """
    Logic to park the funds. Moves status to Deposit_Paid.
    """
    transaction.status = 'Deposit_Paid'
    transaction.save()
    return transaction

def release_payment_to_seller(transaction):
    """
    Logic to clear the transaction. Moves status to Completed.
    """
    from django.utils import timezone

    transaction.status = 'Completed'
    transaction.save(update_fields=['status', 'updated_at'])

    commission = getattr(transaction, 'commission', None)
    if commission:
        commission.status = 'Completed'
        commission.closed_at = commission.closed_at or timezone.now()
        commission.save(update_fields=['status', 'closed_at', 'updated_at'])

    return transaction

def refund_payment_to_buyer(transaction):
    """
    Handles scenarios where the transaction fails fraud check and needs refund.
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
    Provides STK Push, B2C, and transaction status query capabilities.
    """
    
    BASE_URL = "https://sandbox.safaricom.co.ke"  # Use production URL in live environment
    
    @classmethod
    def get_access_token(cls):
        """
        Get OAuth access token from Daraja API
        """
        try:
            url = f"{cls.BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
            consumer_key = settings.DARAJA_CONSUMER_KEY
            consumer_secret = settings.DARAJA_CONSUMER_SECRET
            
            if not consumer_key or not consumer_secret:
                logger.error("Daraja consumer key or secret not configured")
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
            
            if access_token:
                logger.info("Successfully obtained Daraja access token")
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
            
            url = f"{cls.BASE_URL}/mpesa/stkpush/v1/processrequest"
            
            if not callback_url:
                callback_url = f"{_get_callback_base()}/api/v1/mpesa/callback"
            
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
            url = f"{cls.BASE_URL}/mpesa/stkpushquery/v1/query"
            
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
            logger.error(f"Unexpected error in STK status query: {str(e)}")
            return {
                "status": "error",
                "message": "Internal status query error"
            }
    
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

# --- Enhanced M-PESA Functions ---
def mpesa_stk_push(phone, amount, transaction_id):
    """
    Enhanced M-PESA STK Push using Daraja API
    """
    if not all([hasattr(settings, 'DARAJA_CONSUMER_KEY'), 
                hasattr(settings, 'DARAJA_CONSUMER_SECRET'),
                hasattr(settings, 'DARAJA_SHORTCODE'),
                hasattr(settings, 'DARAJA_PASSKEY')]):
        logger.warning("Daraja API not fully configured, using mock implementation")
        return {
            "status": True,
            "gateway": "MPESA",
            "message": f"STK Push sent successfully to {phone}",
            "CheckoutRequestID": f"ws_CO_{uuid.uuid4().hex[:10]}"
        }
    
    account_reference = f"ESCROW-{transaction_id}"
    transaction_desc = f"Land escrow payment for transaction {transaction_id}"
    
    result = DarajaAPI.stk_push(
        phone_number=phone,
        amount=amount,
        account_reference=account_reference,
        transaction_desc=transaction_desc
    )
    
    return result

def mpesa_query_status(checkout_request_id):
    """
    Enhanced M-PESA status query using Daraja API
    """
    if not all([hasattr(settings, 'DARAJA_CONSUMER_KEY'), 
                hasattr(settings, 'DARAJA_CONSUMER_SECRET')]):
        return {"status": "Complete", "ResultCode": "0"}
    
    result = DarajaAPI.query_stk_status(checkout_request_id)
    return result

def mpesa_b2c_transfer(phone, amount, transaction_id):
    """
    Enhanced M-PESA B2C transfer using Daraja API
    """
    if not all([hasattr(settings, 'DARAJA_CONSUMER_KEY'), 
                hasattr(settings, 'DARAJA_CONSUMER_SECRET'),
                hasattr(settings, 'DARAJA_INITIATOR_NAME'),
                hasattr(settings, 'DARAJA_INITIATOR_PASSWORD')]):
        logger.warning("Daraja B2C API not fully configured, using mock implementation")
        return {
            "status": True,
            "gateway": "MPESA",
            "message": f"B2C Transfer to {phone} initiated successfully",
            "ConversationID": f"AG_{uuid.uuid4().hex[:10]}"
        }
    
    remarks = f"Escrow payout for transaction {transaction_id}"
    result = DarajaAPI.b2c_payment(
        phone_number=phone,
        amount=amount,
        remarks=remarks
    )
    
    return result

def reverse_escrow_payment(transaction, reason="Payment reversal"):
    """
    Reverse an escrow payment back to the buyer
    
    Args:
        transaction: Transaction object to reverse
        reason: Reason for reversal
        
    Returns:
        dict: Reversal result
    """
    try:
        if not all([hasattr(settings, 'DARAJA_CONSUMER_KEY'), 
                    hasattr(settings, 'DARAJA_CONSUMER_SECRET'),
                    hasattr(settings, 'DARAJA_INITIATOR_NAME'),
                    hasattr(settings, 'DARAJA_INITIATOR_PASSWORD')]):
            logger.warning("Daraja reversal API not fully configured, using mock implementation")
            return {
                "status": True,
                "message": "Mock reversal completed successfully",
                "reversal_reference": f"MOCK-REV-{uuid.uuid4().hex[:12].upper()}"
            }
        
        # Get the original payment details from transaction
        # This would typically be stored in a Payment model or similar
        original_amount = transaction.agreed_price
        buyer_phone = transaction.buyer.phone_number
        transaction_ref = transaction.escrow_reference or str(transaction.id)
        
        # Initiate reversal via Daraja API
        result = DarajaAPI.reverse_transaction(
            transaction_id=transaction_ref,
            amount=original_amount,
            receiver_party=buyer_phone,
            remarks=reason
        )
        
        if result.get("status") == "success":
            logger.info(f"Payment reversal initiated for transaction {transaction.id}")
            return {
                "status": "success",
                "message": "Payment reversal initiated successfully",
                "reversal_reference": result.get("conversation_id"),
                "amount": original_amount,
                "recipient": buyer_phone
            }
        else:
            logger.error(f"Payment reversal failed for transaction {transaction.id}: {result}")
            return {
                "status": "error",
                "message": result.get("message", "Payment reversal failed"),
                "error_details": result
            }
            
    except Exception as e:
        logger.error(f"Unexpected error in payment reversal: {str(e)}")
        return {
            "status": "error",
            "message": f"Internal reversal error: {str(e)}"
        }

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
        'escrow_fee': fees['escrow_fee'],
        'escrow_holding_fee': fees['escrow_holding_fee'],
        'processing_fee': fees['payment_processing_fee'],
        'payment_processing_fee': fees['payment_processing_fee'],
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
