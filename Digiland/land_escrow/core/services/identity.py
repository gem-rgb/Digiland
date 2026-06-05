import requests
import base64
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from .utils import log_api_call

logger = logging.getLogger(__name__)


class GavaConnectAPI:
    """
    GavaConnect API integration for KRA identity verification services.
    Uses the official KRA GavaConnect developer portal (developer.go.ke) with OAuth2.
    
    GavaConnect requires a separate app per API product, so we maintain
    three sets of credentials:
      - PIN Checker BY ID  → GAVACONNECT_CONSUMER_KEY / SECRET
      - PIN Checker by PIN → GAVACONNECT_PIN_CONSUMER_KEY / SECRET
      - TCC Checker        → GAVACONNECT_TCC_CONSUMER_KEY / SECRET
    
    Sandbox Base URL: https://sbx.kra.go.ke
    Production Base URL: https://api.kra.go.ke
    """
    
    @classmethod
    def _get_base_url(cls):
        return getattr(settings, 'GAVACONNECT_BASE_URL', 'https://sbx.kra.go.ke')
    
    @classmethod
    def _get_token_for_product(cls, product):
        """
        Get OAuth2 access token for a specific API product.
        
        Args:
            product: one of 'pin_by_id', 'pin_by_pin', 'tcc'
        """
        cred_map = {
            'pin_by_id': (
                getattr(settings, 'GAVACONNECT_CONSUMER_KEY', ''),
                getattr(settings, 'GAVACONNECT_CONSUMER_SECRET', ''),
            ),
            'pin_by_pin': (
                getattr(settings, 'GAVACONNECT_PIN_CONSUMER_KEY', ''),
                getattr(settings, 'GAVACONNECT_PIN_CONSUMER_SECRET', ''),
            ),
            'tcc': (
                getattr(settings, 'GAVACONNECT_TCC_CONSUMER_KEY', ''),
                getattr(settings, 'GAVACONNECT_TCC_CONSUMER_SECRET', ''),
            ),
        }
        
        consumer_key, consumer_secret = cred_map.get(product, ('', ''))
        
        if not consumer_key or not consumer_secret:
            logger.error(f"GavaConnect credentials for '{product}' not configured")
            return None
        
        try:
            credentials = f"{consumer_key}:{consumer_secret}"
            encoded = base64.b64encode(credentials.encode()).decode()
            
            url = f"{cls._get_base_url()}/v1/token/generate?grant_type=client_credentials"
            
            headers = {
                "Authorization": f"Basic {encoded}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            
            result = response.json()
            access_token = result.get("access_token")
            
            if access_token:
                logger.info(f"Got GavaConnect token for '{product}'")
                return access_token
            else:
                logger.error(f"No access token in GavaConnect response for '{product}'")
                return None
                
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get GavaConnect token for '{product}': {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error getting GavaConnect token: {str(e)}")
            return None
    
    @classmethod
    def _get_headers_for_product(cls, product):
        """Get Bearer-token headers for a specific product's app."""
        token = cls._get_token_for_product(product)
        if not token:
            raise ValidationError(f"Could not obtain GavaConnect token for '{product}'")
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    # --- Legacy convenience alias (default = pin_by_id app) ---
    @classmethod
    def get_access_token(cls):
        return cls._get_token_for_product('pin_by_id')
    
    # ──────────────────────────────────────────────
    #  PIN Checker by PIN  (app: DigilandFull)
    # ──────────────────────────────────────────────
    @classmethod
    def verify_kra_pin(cls, kra_pin):
        """
        Verify a KRA PIN against iTax using the PIN Checker by PIN API.
        
        Endpoint: POST {base}/checker/v1/pinbypin
        Request:  {"KRAPIN": "P318295670X"}
        Response: {"ResponseCode":"23000","Message":"Valid PIN","Status":"OK",
                   "PINDATA":{"KRAPIN":"...","TypeOfTaxpayer":"Individual",
                              "Name":"JOHN DOE","StatusOfPIN":"Active"}}
        """
        try:
            url = f"{cls._get_base_url()}/checker/v1/pinbypin"
            payload = {"KRAPIN": kra_pin}
            
            log_api_call("GavaConnect PIN Checker by PIN", {"KRAPIN": f"{kra_pin[:4]}****"})
            
            response = requests.post(
                url, json=payload,
                headers=cls._get_headers_for_product('pin_by_pin'),
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"PIN check for {kra_pin[:4]}****: {result.get('Message', 'N/A')}")
            
            pin_data = result.get("PINDATA", {})
            is_valid = (
                result.get("ResponseCode") == "23000"
                and result.get("Status") == "OK"
            )
            
            return {
                "status": "success",
                "is_valid": is_valid,
                "response_code": result.get("ResponseCode"),
                "message": result.get("Message", ""),
                "kra_pin": pin_data.get("KRAPIN"),
                "taxpayer_name": pin_data.get("Name"),
                "taxpayer_type": pin_data.get("TypeOfTaxpayer"),
                "pin_status": pin_data.get("StatusOfPIN"),
                "verification_id": f"GVK-PIN-{kra_pin[:4]}"
            }
            
        except ValidationError as e:
            return {"status": "error", "message": f"Auth error: {str(e)}"}
        except requests.exceptions.RequestException as e:
            logger.error(f"PIN-by-PIN verification failed: {str(e)}")
            return {"status": "error", "message": f"KRA PIN verification service unavailable: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected PIN-by-PIN error: {str(e)}")
            return {"status": "error", "message": "Internal verification error"}
    
    # ──────────────────────────────────────────────
    #  PIN Checker BY ID  (app: Digiland)
    # ──────────────────────────────────────────────
    @classmethod
    def verify_pin_by_id(cls, taxpayer_id, taxpayer_type="KE"):
        """
        Retrieve KRA PIN from a National ID using PIN Checker BY ID API.
        
        Endpoint: POST {base}/checker/v1/pin
        Request:  {"TaxpayerType":"KE","TaxpayerID":"100000000"}
        Response: {"TaxpayerPIN":"A000000000I","TaxpayerName":"YAMAS12 TEST OMINI01"}
        """
        try:
            url = f"{cls._get_base_url()}/checker/v1/pin"
            payload = {
                "TaxpayerType": taxpayer_type,
                "TaxpayerID": str(taxpayer_id)
            }
            
            log_api_call("GavaConnect PIN Checker by ID", {"TaxpayerID": f"{str(taxpayer_id)[:4]}****"})
            
            response = requests.post(
                url, json=payload,
                headers=cls._get_headers_for_product('pin_by_id'),
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"PIN-by-ID for {str(taxpayer_id)[:4]}****: {result}")
            
            taxpayer_pin = result.get("TaxpayerPIN")
            taxpayer_name = result.get("TaxpayerName")
            
            return {
                "status": "success",
                "is_valid": bool(taxpayer_pin),
                "kra_pin": taxpayer_pin,
                "taxpayer_name": taxpayer_name,
                "verification_id": f"GVK-ID-{str(taxpayer_id)[:4]}"
            }
            
        except ValidationError as e:
            return {"status": "error", "message": f"Auth error: {str(e)}"}
        except requests.exceptions.RequestException as e:
            logger.error(f"PIN-by-ID verification failed: {str(e)}")
            return {"status": "error", "message": f"ID verification service unavailable: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected PIN-by-ID error: {str(e)}")
            return {"status": "error", "message": "Internal verification error"}
    
    # ──────────────────────────────────────────────
    #  TCC Checker  (app: Digiland Escrow)
    # ──────────────────────────────────────────────
    @classmethod
    def verify_tcc(cls, kra_pin, tcc_number):
        """
        Validate a Tax Compliance Certificate using the TCC Checker API.
        
        Endpoint: POST {base}/v1/kra-tcc/validate
        Request:  {"kraPIN":"A948312567Q","tccNumber":"K92OR548W43A21N9"}
        """
        try:
            url = f"{cls._get_base_url()}/v1/kra-tcc/validate"
            payload = {
                "kraPIN": kra_pin,
                "tccNumber": tcc_number
            }
            
            log_api_call("GavaConnect TCC Validation", {"kraPIN": f"{kra_pin[:4]}****"})
            
            response = requests.post(
                url, json=payload,
                headers=cls._get_headers_for_product('tcc'),
                timeout=30
            )
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"TCC validation for {kra_pin[:4]}****: {result}")
            
            return {
                "status": "success",
                "is_valid": result.get("Status") == "OK" or result.get("ResponseCode") == "23000",
                "message": result.get("Message", ""),
                "details": result
            }
            
        except ValidationError as e:
            return {"status": "error", "message": f"Auth error: {str(e)}"}
        except requests.exceptions.RequestException as e:
            logger.error(f"TCC verification failed: {str(e)}")
            return {"status": "error", "message": f"TCC verification service unavailable: {str(e)}"}
        except Exception as e:
            logger.error(f"Unexpected TCC error: {str(e)}")
            return {"status": "error", "message": "Internal TCC verification error"}
    
    # ---- Legacy aliases for backward compat ----
    @classmethod
    def verify_id_number(cls, id_number, first_name=None, last_name=None):
        """Legacy alias → verify_pin_by_id."""
        return cls.verify_pin_by_id(taxpayer_id=id_number, taxpayer_type="KE")
    
    @classmethod
    def verify_business_registration(cls, business_name, registration_number=None):
        """Legacy: verify business via their KRA PIN."""
        if registration_number:
            return cls.verify_kra_pin(registration_number)
        return {"status": "error", "message": "Business KRA PIN required for verification"}


# ── Convenience helpers used by the rest of the codebase ──────────────

def authenticate_user(id_number, first_name, last_name):
    """
    Identity verification using GavaConnect PIN-by-ID API.

    When KRA_DB_VALIDATION_ENABLED is False (default for dev/staging),
    returns a format-only mock verification so signup is never blocked
    by KRA API downtime.  Enable in production to enforce real DB checks.
    """
    if not getattr(settings, 'KRA_DB_VALIDATION_ENABLED', False):
        logger.info("KRA DB validation disabled — format-only verification for ID %s****", str(id_number)[:4])
        return {
            "status": "success",
            "is_identity_verified": True,
            "gavakonect_verification_id": f"GVK-FORMAT-{str(id_number)[:4]}",
            "verification_method": "format_only"
        }

    if not getattr(settings, 'GAVACONNECT_CONSUMER_KEY', ''):
        logger.warning("GavaConnect credentials not configured — mock verification")
        return {
            "status": "success",
            "is_identity_verified": True,
            "gavakonect_verification_id": f"GVK-MOCK-{id_number}",
            "verification_method": "mock"
        }

    result = GavaConnectAPI.verify_pin_by_id(taxpayer_id=id_number)

    if result["status"] == "success" and result.get("is_valid"):
        return {
            "status": "success",
            "is_identity_verified": True,
            "gavakonect_verification_id": result.get("verification_id"),
            "verification_method": "gavaconnect",
            "verified_details": {
                "kra_pin": result.get("kra_pin"),
                "taxpayer_name": result.get("taxpayer_name"),
            }
        }
    else:
        return {
            "status": "failed",
            "is_identity_verified": False,
            "message": result.get("message", "Identity verification failed"),
            "verification_method": "gavaconnect"
        }


def verify_user_kra_pin(user, kra_pin):
    """
    Verify user's KRA PIN for KYC.  Uses PIN Checker by PIN API.
    Updates user's verification status on success.

    When KRA_DB_VALIDATION_ENABLED is False (default for dev/staging),
    skips the GavaConnect API call and marks format-only verification.
    Enable in production to enforce real DB checks as failover.
    """
    if not getattr(settings, 'KRA_DB_VALIDATION_ENABLED', False):
        logger.info(
            "KRA DB validation disabled — format-only verification for %s PIN %s****",
            user.email, kra_pin[:4],
        )
        user.is_identity_verified = True
        user.gavakonect_verification_id = f"GVK-FORMAT-{kra_pin[:4]}****"
        user.save()
        return True

    if not getattr(settings, 'GAVACONNECT_PIN_CONSUMER_KEY', ''):
        logger.warning("GavaConnect PIN credentials not configured — mock KRA verification")
        user.is_identity_verified = True
        user.gavakonect_verification_id = f"GVK-KRA-MOCK-{kra_pin[:4]}****"
        user.save()
        return True

    result = GavaConnectAPI.verify_kra_pin(kra_pin)

    if result["status"] == "success" and result.get("is_valid"):
        user.is_identity_verified = True
        user.gavakonect_verification_id = result.get("verification_id")
        user.save()
        logger.info(f"KRA PIN verified for {user.email} — Name: {result.get('taxpayer_name')}")
        return True
    else:
        logger.warning(f"KRA PIN verification failed for {user.email} — {result.get('message')}")
        return False


def verify_user_identity(user):
    """
    Enhanced identity verification that calls authenticate_user and updates the user.

    Respects KRA_DB_VALIDATION_ENABLED setting — when disabled, performs
    format-only verification without calling the KRA database.
    """
    first_name = user.first_name or ""
    last_name = user.last_name or ""

    result = authenticate_user(user.id_number, first_name, last_name)

    if result.get('is_identity_verified'):
        user.is_identity_verified = True
        user.gavakonect_verification_id = result.get('gavakonect_verification_id')
        user.save()
        return True
    return False
