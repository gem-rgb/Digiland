import uuid
import requests
import base64
import logging
from datetime import datetime
from django.conf import settings
from django.core.exceptions import ValidationError
from .utils import log_api_call, validate_phone_number, generate_transaction_reference

logger = logging.getLogger(__name__)

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
    transaction.status = 'Completed'
    transaction.save()
    return transaction

def refund_payment_to_buyer(transaction):
    """
    Handles scenarios where the transaction fails fraud check and needs refund.
    """
    transaction.status = 'Refunded'
    transaction.save()
    return transaction


# --- Paystack API Setup ---
PAYSTACK_API_URL = "https://api.paystack.co"

def get_paystack_headers():
    return {
        "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
        "Content-Type": "application/json"
    }

def paystack_initialize(email, amount, reference):
    payload = {
        "email": email,
        "amount": int(float(amount) * 100),
        "reference": reference,
        "callback_url": "http://127.0.0.1:8000/api/v1/payments/callback"
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
            url = f"{cls.BASE_URL}/oauth/v1/generate"
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
                callback_url = f"http://127.0.0.1:8000/api/v1/mpesa/callback"
            
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
                "QueueTimeOutURL": f"http://127.0.0.1:8000/api/v1/mpesa/b2c/timeout",
                "ResultURL": f"http://127.0.0.1:8000/api/v1/mpesa/b2c/result",
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
