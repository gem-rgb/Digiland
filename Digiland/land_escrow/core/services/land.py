# Land Registry Service
def fetch_parcel_details(parcel_number):
    """
    Mock ArdhiSasa API integration.
    Returns owner name, size, zoning, and caveats.
    """
    return {
        "parcel_number": parcel_number,
        "land_use_type": "Residential",
        "county": "Nairobi",
        "land_size": 0.125,
        "owner_name": "John Doe",
        "caveats": []
    }

def verify_parcel_ownership(parcel_number, claimed_owner_id_number):
    """
    Checks if the claimed seller matches the registered owner on ArdhiSasa.
    Mock always returns match True for testing.
    """
    return {
        "match": True,
        "verification_status": "Verified"
    }

def check_for_disputes(parcel_number):
    """
    Queries active court orders or disputes related to the land.
    Mock returns no disputes.
    """
    return []
