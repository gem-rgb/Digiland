import logging
import json
from datetime import datetime
from django.conf import settings

logger = logging.getLogger(__name__)

def log_api_call(service_name, payload, response=None):
    """
    Log external API calls for monitoring and debugging
    
    Args:
        service_name: Name of the external service (e.g., "GavaConnect KRA PIN Verification")
        payload: Request payload (dict)
        response: Optional response data
    """
    log_data = {
        "timestamp": datetime.now().isoformat(),
        "service": service_name,
        "request": payload,
        "response": response
    }
    
    if hasattr(settings, 'DEBUG') and settings.DEBUG:
        logger.info(f"API Call - {service_name}: {json.dumps(log_data, indent=2)}")
    else:
        logger.info(f"API Call - {service_name}: {service_name} processed")

def mask_sensitive_data(data, sensitive_fields=['pin', 'password', 'secret', 'key']):
    """
    Mask sensitive data in logs
    
    Args:
        data: Dictionary containing potentially sensitive data
        sensitive_fields: List of field names to mask
        
    Returns:
        dict: Data with sensitive fields masked
    """
    if not isinstance(data, dict):
        return data
    
    masked_data = {}
    for key, value in data.items():
        key_lower = key.lower()
        if any(field in key_lower for field in sensitive_fields):
            if isinstance(value, str) and len(value) > 4:
                masked_data[key] = value[:2] + '*' * (len(value) - 4) + value[-2:]
            else:
                masked_data[key] = '*' * len(str(value))
        elif isinstance(value, dict):
            masked_data[key] = mask_sensitive_data(value, sensitive_fields)
        else:
            masked_data[key] = value
    
    return masked_data

def validate_phone_number(phone):
    """
    Validate and format Kenyan phone number
    
    Args:
        phone: Phone number string
        
    Returns:
        str: Formatted phone number or None if invalid
    """
    if not phone:
        return None
    
    # Remove spaces, dashes, and parentheses
    phone = ''.join(c for c in phone if c.isdigit())
    
    # Check if it's a valid Kenyan number
    if phone.startswith('254') and len(phone) == 12:
        return phone
    elif phone.startswith('07') and len(phone) == 10:
        return '254' + phone[1:]
    elif phone.startswith('01') and len(phone) == 10:
        return '254' + phone[1:]
    
    return None

def format_kra_pin(kra_pin):
    """
    Validate and format KRA PIN
    
    Args:
        kra_pin: KRA PIN string
        
    Returns:
        str: Formatted KRA PIN or None if invalid
    """
    if not kra_pin:
        return None
    
    # Remove spaces and convert to uppercase
    kra_pin = kra_pin.replace(' ', '').upper()
    
    # Basic validation - KRA PINs are typically alphanumeric and 9-11 characters
    if len(kra_pin) >= 9 and len(kra_pin) <= 11 and kra_pin.replace('K', '').replace('P', '').replace('A', '').isalnum():
        return kra_pin
    
    return None

def generate_transaction_reference(prefix='TXN'):
    """
    Generate unique transaction reference
    
    Args:
        prefix: Prefix for the reference
        
    Returns:
        str: Unique transaction reference
    """
    import uuid
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    unique_id = str(uuid.uuid4())[:8].upper()
    return f"{prefix}{timestamp}{unique_id}"
