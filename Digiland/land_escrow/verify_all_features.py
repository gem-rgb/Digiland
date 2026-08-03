import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'land_escrow.settings')
django.setup()

from django.test import Client
from django.contrib.auth import get_user_model
from core.models import Transaction, LandParcel, PopupAdCampaign, Document, LawyerPostTransactionTask
from django.conf import settings

User = get_user_model()

print("=" * 60)
print("FULL PLATFORM VERIFICATION REPORT")
print("=" * 60)

# --- AI FEATURE FLAGS ---
print("\n--- AI Feature Flags ---")
print(f"  ENABLE_AI_AD_CAMPAIGNS:       {getattr(settings, 'ENABLE_AI_AD_CAMPAIGNS', 'NOT SET')}")
print(f"  ENABLE_AI_DOC_VERIFICATION:   {getattr(settings, 'ENABLE_AI_DOC_VERIFICATION', 'NOT SET')}")
print(f"  ENABLE_AI_PRICE_PREDICTION:   {getattr(settings, 'ENABLE_AI_PRICE_PREDICTION', 'NOT SET')}")

# --- SELLER TESTS ---
seller = User.objects.get(email='legalhusla@gmail.com')
c = Client()
c.force_login(seller)
print("\n--- Seller (legalhusla@gmail.com) ---")
for path, name in [
    ('/seller/dashboard/', 'Seller Dashboard'),
    ('/seller/promotions/', 'Promotions (AI Ad Campaigns)'),
    ('/parcels/LR-PROMO-PARKLANDS-2026/', 'Promoted Parcel Detail'),
    ('/parcels/LR-VERIFIED-KAREN-2026/', 'Verified Parcel Detail'),
    ('/price-prediction/', 'Price Prediction (Should be disabled)'),
]:
    r = c.get(path)
    status = 'OK' if r.status_code == 200 else f'FAIL ({r.status_code})'
    extra = ''
    if 'price-prediction' in path and r.status_code == 200:
        content = r.content.decode()
        extra = ' [Disabled notice: ' + ('YES' if 'disabled' in content.lower() else 'NO') + ']'
    if 'promotions' in path and r.status_code == 200:
        content = r.content.decode()
        extra = ' [Parklands campaign: ' + ('FOUND' if 'Parklands' in content else 'NOT FOUND') + ']'
    print(f"  {name}: {status}{extra}")

# --- BUYER TESTS ---
buyer = User.objects.get(email='buyer_demo@example.com')
c2 = Client()
c2.force_login(buyer)
print("\n--- Buyer (buyer_demo@example.com) ---")
for path, name in [
    ('/parcels/', 'Marketplace Listings'),
    ('/parcels/LR-VERIFIED-KAREN-2026/', 'Verified Parcel Detail'),
    ('/transactions/', 'Buyer Transactions'),
]:
    r = c2.get(path)
    status = 'OK' if r.status_code == 200 else f'REDIRECT -> {r.url}' if r.status_code == 302 else f'FAIL ({r.status_code})'
    print(f"  {name}: {status}")

# --- AGENT TESTS ---
agent = User.objects.get(email='agent_demo@example.com')
c3 = Client()
c3.force_login(agent)
print("\n--- Agent (agent_demo@example.com) ---")
for path, name in [
    ('/agent/dashboard/', 'Agent Dashboard'),
    ('/agent/job-board/', 'Agent Job Board'),
]:
    r = c3.get(path)
    status = 'OK' if r.status_code == 200 else f'REDIRECT -> {r.url}' if r.status_code == 302 else f'FAIL ({r.status_code})'
    print(f"  {name}: {status}")

# --- LAWYER TESTS ---
lawyer = User.objects.get(email='lawyer_demo@example.com')
c4 = Client()
c4.force_login(lawyer)
tx = Transaction.objects.first()
print("\n--- Lawyer (lawyer_demo@example.com) ---")
if tx:
    try:
        r = c4.get(f'/transactions/{tx.id}/lawyer-tasks/')
        status = 'OK' if r.status_code == 200 else f'FAIL ({r.status_code})'
        print(f"  Lawyer Post-Transaction Tasks: {status}")
    except Exception as e:
        print(f"  Lawyer Post-Transaction Tasks: ERROR ({e})")
else:
    print("  No transaction to test")

# --- DATABASE SUMMARY ---
print("\n--- Database Summary ---")
print(f"  Land Parcels: {LandParcel.objects.count()}")
print(f"  AGENT_APPROVED parcels: {LandParcel.objects.filter(verification_status='AGENT_APPROVED').count()}")
print(f"  Active Ad Campaigns: {PopupAdCampaign.objects.filter(status='Active').count()}")
print(f"  Verified Documents: {Document.objects.filter(verification_status='Match').count()}")
print(f"  Lawyer Tasks: {LawyerPostTransactionTask.objects.count()}")
print(f"  Transactions: {Transaction.objects.count()}")

print("\n" + "=" * 60)
print("VERIFICATION COMPLETE")
print("=" * 60)
