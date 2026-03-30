import uuid
import requests
from django.conf import settings

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


# --- M-PESA Daraja Configuration (Mocked) ---
def mpesa_stk_push(phone, amount, transaction_id):
    """
    Mocks M-PESA Safaricom STK Push Call
    """
    return {
        "status": True,
        "gateway": "MPESA",
        "message": f"STK Push sent successfully to {phone}",
        "CheckoutRequestID": f"ws_CO_{uuid.uuid4().hex[:10]}"
    }

def mpesa_query_status(checkout_request_id):
    return {"status": "Complete", "ResultCode": "0"}

def mpesa_b2c_transfer(phone, amount, transaction_id):
    """
    Mocks M-PESA B2C API Call to payout seller
    """
    return {
        "status": True,
        "gateway": "MPESA",
        "message": f"B2C Transfer to {phone} initiated successfully",
        "ConversationID": f"AG_{uuid.uuid4().hex[:10]}"
    }
