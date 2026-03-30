# Identity Service
def authenticate_user(id_number, first_name, last_name):
    """
    Mock integration with GavaKonect.
    Verifies ID match.
    """
    return {
        "status": "success",
        "is_identity_verified": True,
        "gavakonect_verification_id": f"GVK-{id_number}"
    }

def verify_user_identity(user):
    """
    Calls authenticate_user and updates the is_identity_verified flag.
    For the mock, assumes user has valid first/last name or defaults.
    """
    first_name = user.first_name or "Test"
    last_name = user.last_name or "User"
    
    result = authenticate_user(user.id_number, first_name, last_name)
    
    if result.get('is_identity_verified'):
        user.is_identity_verified = True
        user.gavakonect_verification_id = result.get('gavakonect_verification_id')
        user.save()
        return True
    return False
