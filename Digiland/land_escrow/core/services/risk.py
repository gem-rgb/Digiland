# Fraud Risk Engine

def calculate_parcel_risk(land_parcel):
    """
    Calculates a fraud-risk score based on parcel info. Mock returns Low Risk (10.0).
    """
    return 10.0

def calculate_seller_risk(seller):
    """
    Calculates a fraud-risk score based on seller info. Mock returns Low Risk (5.0).
    """
    return 5.0

def calculate_document_risk(documents):
    """
    Calculates a fraud-risk score based on uploaded documents. Mock returns Low Risk (5.0).
    """
    return 5.0

def generate_transaction_risk_report(transaction):
    """
    Aggregates data to generate a final risk score.
    Returns overall score, risk factors, and recommendations.
    """
    # Assuming lower is better in this mock
    score = 20.0
    
    return {
        "overall_score": score,
        "risk_category": "Low Risk",
        "risk_factors": ["Seller account created recently"],
        "recommendation": "Proceed to Escrow"
    }
