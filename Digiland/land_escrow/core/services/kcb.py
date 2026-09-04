"""
KCB Bank API Integration Service

Handles fund transfers, balance inquiries, and transaction status checks
via KCB's Open Banking API gateway, similar to the existing M-Pesa integration.

In sandbox/dev mode, API calls are simulated with mock responses.
"""
import logging
import uuid
import requests
from django.conf import settings

logger = logging.getLogger(__name__)

# KCB API Endpoints (configurable via settings)
KCB_BASE_URL = getattr(settings, 'KCB_API_BASE_URL', 'https://uat.bfrg.co.ke:8443/api')
KCB_CLIENT_ID = getattr(settings, 'KCB_CLIENT_ID', '')
KCB_CLIENT_SECRET = getattr(settings, 'KCB_CLIENT_SECRET', '')
KCB_SANDBOX = getattr(settings, 'KCB_SANDBOX', True)


def _get_access_token():
    """Authenticate with KCB OAuth2 gateway and return a bearer token."""
    if KCB_SANDBOX:
        return 'sandbox-mock-token'

    try:
        response = requests.post(
            f'{KCB_BASE_URL}/token',
            data={'grant_type': 'client_credentials'},
            auth=(KCB_CLIENT_ID, KCB_CLIENT_SECRET),
            timeout=15,
        )
        response.raise_for_status()
        return response.json().get('access_token')
    except Exception as exc:
        logger.error('KCB token error: %s', exc)
        return None


def initiate_fund_transfer(*, source_account, destination_account, amount, reference, narration='Digiland Direct Settlement'):
    """
    Initiate a fund transfer between transaction parties (direct settlement).
    DigiLand does NOT take custody of land purchase funds or maintain an escrow balance.

    Returns dict with keys: status, reference, message
    """
    if KCB_SANDBOX:
        mock_ref = f"KCB-{uuid.uuid4().hex[:10].upper()}"
        logger.info(
            'KCB SANDBOX transfer: %s -> %s, KES %s, ref=%s',
            source_account, destination_account, amount, mock_ref
        )
        return {
            'status': 'success',
            'reference': mock_ref,
            'message': f'Sandbox transfer of KES {amount:,.2f} initiated. Reference: {mock_ref}',
            'transaction_id': mock_ref,
        }

    token = _get_access_token()
    if not token:
        return {'status': 'error', 'message': 'Could not authenticate with KCB gateway.'}

    try:
        payload = {
            'companyCode': getattr(settings, 'KCB_COMPANY_CODE', ''),
            'transactionType': 'FT',
            'debitAccount': source_account,
            'creditAccount': destination_account,
            'debitAmount': str(amount),
            'debitCurrency': 'KES',
            'transactionReference': reference,
            'narration': narration,
        }
        headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        response = requests.post(
            f'{KCB_BASE_URL}/fundstransfer',
            json=payload,
            headers=headers,
            timeout=30,
        )
        data = response.json()

        if response.status_code == 200 and data.get('status') == '000':
            return {
                'status': 'success',
                'reference': data.get('transactionReference', reference),
                'message': data.get('message', 'Transfer initiated successfully.'),
                'transaction_id': data.get('transactionId', ''),
            }
        else:
            return {
                'status': 'error',
                'message': data.get('message', 'Transfer failed.'),
            }
    except Exception as exc:
        logger.error('KCB transfer error: %s', exc)
        return {'status': 'error', 'message': str(exc)}


def check_account_balance(account_number):
    """Query the balance of a KCB account."""
    if KCB_SANDBOX:
        return {
            'status': 'success',
            'balance': 500000.00,
            'currency': 'KES',
            'account': account_number,
        }

    token = _get_access_token()
    if not token:
        return {'status': 'error', 'message': 'Could not authenticate with KCB gateway.'}

    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(
            f'{KCB_BASE_URL}/accounts/{account_number}/balance',
            headers=headers,
            timeout=15,
        )
        data = response.json()
        return {
            'status': 'success',
            'balance': float(data.get('availableBalance', 0)),
            'currency': data.get('currency', 'KES'),
            'account': account_number,
        }
    except Exception as exc:
        logger.error('KCB balance error: %s', exc)
        return {'status': 'error', 'message': str(exc)}


def check_transaction_status(transaction_reference):
    """Query the status of a KCB transaction by its reference."""
    if KCB_SANDBOX:
        return {
            'status': 'success',
            'transaction_status': 'completed',
            'reference': transaction_reference,
            'message': 'Sandbox: Transaction completed successfully.',
        }

    token = _get_access_token()
    if not token:
        return {'status': 'error', 'message': 'Could not authenticate with KCB gateway.'}

    try:
        headers = {'Authorization': f'Bearer {token}'}
        response = requests.get(
            f'{KCB_BASE_URL}/transactions/{transaction_reference}/status',
            headers=headers,
            timeout=15,
        )
        data = response.json()
        return {
            'status': 'success',
            'transaction_status': data.get('transactionStatus', 'unknown'),
            'reference': transaction_reference,
            'message': data.get('message', ''),
        }
    except Exception as exc:
        logger.error('KCB status error: %s', exc)
        return {'status': 'error', 'message': str(exc)}


def initiate_b2c_payout(*, destination_account, amount, reference, beneficiary_name='', narration='Digiland Fee Settlement'):
    """
    Platform operational settlement (service fee disbursement to surveyors/advocates).
    DigiLand does NOT disburse seller land purchase balances from platform custody.
    """
    platform_account = getattr(settings, 'KCB_PLATFORM_ACCOUNT', 'DIGILAND-OPS-001')
    return initiate_fund_transfer(
        source_account=platform_account,
        destination_account=destination_account,
        amount=amount,
        reference=reference,
        narration=narration,
    )
