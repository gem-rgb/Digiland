"""Test Script for 4-Partition Isolation & Subdomain Access Control.
"""
import os
import sys
import django

# Setup Django Environment
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "land_escrow.settings")
django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from core.partition_middleware import PartitionIsolationMiddleware, resolve_request_partition

User = get_user_model()

def test_partition_isolation():
    print("==================================================")
    print("RUNNING 4-PARTITION SECURITY ISOLATION VERIFICATION")
    print("==================================================")

    factory = RequestFactory()
    middleware = PartitionIsolationMiddleware(get_response=lambda req: None)

    # Create dummy users for each role
    buyer, _ = User.objects.get_or_create(email="buyer_test@digiland.co.ke", defaults={"role": "Buyer"})
    agent, _ = User.objects.get_or_create(email="agent_test@digiland.co.ke", defaults={"role": "Agent"})
    lawyer, _ = User.objects.get_or_create(email="lawyer_test@digiland.co.ke", defaults={"role": "Lawyer"})
    admin, _ = User.objects.get_or_create(email="admin_test@digiland.co.ke", defaults={"role": "Admin", "is_staff": True})

    # Test 1: Buyer accessing App portal -> Allowed
    req_app_buyer = factory.get("/api/v1/parcels/", HTTP_HOST="app.digiland.co.ke")
    req_app_buyer.user = buyer
    resp1 = middleware(req_app_buyer)
    assert resp1 is None, "Buyer should be allowed on app partition"
    print(" [PASS] Buyer allowed on app.digiland.co.ke")

    # Test 2: Agent accessing App portal -> BLOCKED (403)
    req_app_agent = factory.get("/api/v1/parcels/", HTTP_HOST="app.digiland.co.ke")
    req_app_agent.user = agent
    resp2 = middleware(req_app_agent)
    assert resp2.status_code == 403, f"Agent should be blocked on app partition, got {resp2.status_code}"
    print(" [PASS] Agent blocked on app.digiland.co.ke with 403 Forbidden")

    # Test 3: Agent accessing Staff portal -> Allowed
    req_staff_agent = factory.get("/api/v1/parcels/", HTTP_HOST="staff.digiland.co.ke")
    req_staff_agent.user = agent
    resp3 = middleware(req_staff_agent)
    assert resp3 is None, "Agent should be allowed on staff partition"
    print(" [PASS] Agent allowed on staff.digiland.co.ke")

    # Test 4: Buyer accessing Staff portal -> BLOCKED (403)
    req_staff_buyer = factory.get("/api/v1/parcels/", HTTP_HOST="staff.digiland.co.ke")
    req_staff_buyer.user = buyer
    resp4 = middleware(req_staff_buyer)
    assert resp4.status_code == 403, "Buyer should be blocked on staff partition"
    print(" [PASS] Buyer blocked on staff.digiland.co.ke with 403 Forbidden")

    # Test 5: Admin accessing Admin portal -> Allowed
    req_admin = factory.get("/api/v1/admin/dashboard/", HTTP_HOST="admin.digiland.co.ke")
    req_admin.user = admin
    resp5 = middleware(req_admin)
    assert resp5 is None, "Admin should be allowed on admin partition"
    print(" [PASS] Admin allowed on admin.digiland.co.ke")

    # Test 6: Buyer accessing Admin portal -> BLOCKED (403)
    req_admin_buyer = factory.get("/api/v1/admin/dashboard/", HTTP_HOST="admin.digiland.co.ke")
    req_admin_buyer.user = buyer
    resp6 = middleware(req_admin_buyer)
    assert resp6.status_code == 403, "Buyer should be blocked on admin partition"
    print(" [PASS] Buyer blocked on admin.digiland.co.ke with 403 Forbidden")

    print("\n==================================================")
    print("ALL 4-PARTITION SECURITY ISOLATION TESTS PASSED 100%")
    print("==================================================")

if __name__ == "__main__":
    test_partition_isolation()
