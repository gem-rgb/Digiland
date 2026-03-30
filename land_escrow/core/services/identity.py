import requests
import logging
from django.conf import settings
from django.core.exceptions import ValidationError
from .utils import log_api_call

logger = logging.getLogger(__name__)

class GavaConnectAPI:
    """
    GavaConnect API integration for identity verification services.
    Provides KRA PIN verification, ID verification, and business registration checks.
    """
    
    BASE_URL = "https://api.gavaconnect.co.ke/v1"
    
    @classmethod
    def get_headers(cls):
        """Get API headers with authentication"""
        return {
            "Authorization": f"Bearer {settings.GAVACONNECT_API_KEY}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    
    @classmethod
    def verify_kra_pin(cls, kra_pin, id_number=None):
        """
        Verify KRA PIN using GavaConnect API
        
        Args:
            kra_pin: Kenya Revenue Authority PIN
            id_number: Optional National ID number for additional verification
            
        Returns:
            dict: Verification result with status and details
        """
        try:
            url = f"{cls.BASE_URL}/verification/kra-pin"
            payload = {"kra_pin": kra_pin}
            if id_number:
                payload["id_number"] = id_number
            
            log_api_call("GavaConnect KRA PIN Verification", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"KRA PIN verification successful for PIN: {kra_pin[:4]}****")
            return {
                "status": "success",
                "is_valid": result.get("valid", False),
                "business_name": result.get("business_name"),
                "registration_date": result.get("registration_date"),
                "tax_obligations": result.get("tax_obligations"),
                "verification_id": result.get("verification_id")
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GavaConnect KRA PIN verification failed: {str(e)}")
            return {
                "status": "error",
                "message": f"KRA PIN verification service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in KRA PIN verification: {str(e)}")
            return {
                "status": "error", 
                "message": "Internal verification error"
            }
    
    @classmethod
    def verify_id_number(cls, id_number, first_name=None, last_name=None):
        """
        Verify National ID using GavaConnect API
        
        Args:
            id_number: Kenyan National ID number
            first_name: Optional first name for matching
            last_name: Optional last name for matching
            
        Returns:
            dict: Verification result with status and details
        """
        try:
            url = f"{cls.BASE_URL}/verification/id-number"
            payload = {"id_number": id_number}
            if first_name:
                payload["first_name"] = first_name
            if last_name:
                payload["last_name"] = last_name
            
            log_api_call("GavaConnect ID Verification", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"ID verification successful for ID: {id_number[:4]}****")
            
            return {
                "status": "success",
                "is_valid": result.get("valid", False),
                "full_name": result.get("full_name"),
                "date_of_birth": result.get("date_of_birth"),
                "gender": result.get("gender"),
                "district": result.get("district"),
                "county": result.get("county"),
                "verification_id": result.get("verification_id")
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GavaConnect ID verification failed: {str(e)}")
            return {
                "status": "error",
                "message": f"ID verification service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in ID verification: {str(e)}")
            return {
                "status": "error",
                "message": "Internal verification error"
            }
    
    @classmethod
    def verify_business_registration(cls, business_name, registration_number=None):
        """
        Verify business registration using GavaConnect API
        
        Args:
            business_name: Registered business name
            registration_number: Optional business registration number
            
        Returns:
            dict: Verification result with status and details
        """
        try:
            url = f"{cls.BASE_URL}/verification/business-registration"
            payload = {"business_name": business_name}
            if registration_number:
                payload["registration_number"] = registration_number
            
            log_api_call("GavaConnect Business Verification", payload)
            
            response = requests.post(url, json=payload, headers=cls.get_headers(), timeout=30)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"Business verification successful for: {business_name}")
            
            return {
                "status": "success",
                "is_valid": result.get("valid", False),
                "registration_number": result.get("registration_number"),
                "registration_date": result.get("registration_date"),
                "business_type": result.get("business_type"),
                "registered_address": result.get("registered_address"),
                "directors": result.get("directors", []),
                "verification_id": result.get("verification_id")
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"GavaConnect business verification failed: {str(e)}")
            return {
                "status": "error",
                "message": f"Business verification service unavailable: {str(e)}"
            }
        except Exception as e:
            logger.error(f"Unexpected error in business verification: {str(e)}")
            return {
                "status": "error",
                "message": "Internal verification error"
            }

def authenticate_user(id_number, first_name, last_name):
    """
    Enhanced identity verification using GavaConnect API.
    Verifies ID match and returns comprehensive verification data.
    """
    if not hasattr(settings, 'GAVACONNECT_API_KEY') or not settings.GAVACONNECT_API_KEY:
        logger.warning("GavaConnect API key not configured, using mock verification")
        return {
            "status": "success",
            "is_identity_verified": True,
            "gavakonect_verification_id": f"GVK-MOCK-{id_number}",
            "verification_method": "mock"
        }
    
    result = GavaConnectAPI.verify_id_number(id_number, first_name, last_name)
    
    if result["status"] == "success" and result.get("is_valid"):
        return {
            "status": "success",
            "is_identity_verified": True,
            "gavakonect_verification_id": result.get("verification_id"),
            "verification_method": "gavaconnect",
            "verified_details": {
                "full_name": result.get("full_name"),
                "date_of_birth": result.get("date_of_birth"),
                "gender": result.get("gender"),
                "county": result.get("county")
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
    Verify user's KRA PIN for agent KYC verification.
    Updates user's verification status upon successful verification.
    """
    if not hasattr(settings, 'GAVACONNECT_API_KEY') or not settings.GAVACONNECT_API_KEY:
        logger.warning("GavaConnect API key not configured, using mock KRA verification")
        user.is_identity_verified = True
        user.gavakonect_verification_id = f"GVK-KRA-MOCK-{kra_pin[:4]}****"
        user.save()
        return True
    
    result = GavaConnectAPI.verify_kra_pin(kra_pin, user.id_number)
    
    if result["status"] == "success" and result.get("is_valid"):
        user.is_identity_verified = True
        user.gavakonect_verification_id = result.get("verification_id")
        user.save()
        
        logger.info(f"KRA PIN verified successfully for user: {user.email}")
        return True
    else:
        logger.warning(f"KRA PIN verification failed for user: {user.email}")
        return False

def verify_user_identity(user):
    """
    Enhanced identity verification that calls authenticate_user and updates the user.
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
