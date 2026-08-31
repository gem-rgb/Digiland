"""Tests for Host Security, Subdomain Isolation, and Malformed Hostname Rejection."""
from django.test import TestCase, Client, override_settings


class HostSecurityPartitionTestCase(TestCase):
    """Test suite ensuring strict canonical hostname enforcement and partition security."""

    def setUp(self):
        self.client = Client()

    def test_01_malformed_spoofed_host_is_strictly_rejected(self):
        """Requests using spoofed, intermediary, or malformed hostnames (e.g. app.digiland.staff.co.ke) must be rejected with 400 Bad Request."""
        malformed_hosts = [
            "app.digiland.staff.co.ke",
            "staff.app.digiland.co.ke",
            "fake-digiland.co.ke",
            "staff.attacker.com",
            "app.digiland.co.ke.evil.com",
        ]
        for bad_host in malformed_hosts:
            with self.subTest(host=bad_host):
                response = self.client.get("/parcels/", HTTP_HOST=bad_host)
                # Django's DisallowedHost / PartitionIsolationMiddleware must reject with 400
                self.assertEqual(
                    response.status_code, 400,
                    f"Expected HTTP 400 Bad Request for malformed host '{bad_host}', got {response.status_code}"
                )

    def test_02_staff_url_on_app_portal_redirects_to_canonical_staff_domain(self):
        """Accessing staff endpoints on app.digiland.co.ke must redirect to https://staff.digiland.co.ke."""
        response = self.client.get(
            "/staff/dashboard/",
            HTTP_HOST="app.digiland.co.ke",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://staff.digiland.co.ke/staff/login/"))

    def test_03_admin_url_on_non_admin_portal_is_forbidden(self):
        """Accessing admin endpoints on app.digiland.co.ke or staff.digiland.co.ke must return 403 Forbidden."""
        for portal_host in ["app.digiland.co.ke", "staff.digiland.co.ke", "digiland.co.ke"]:
            with self.subTest(host=portal_host):
                response = self.client.get(
                    "/admin/dashboard/",
                    HTTP_HOST=portal_host,
                )
                self.assertEqual(response.status_code, 403)

    def test_04_exact_canonical_host_resolves_cleanly(self):
        """Exact canonical hostnames (staff.digiland.co.ke, app.digiland.co.ke) resolve without rejection."""
        # Staff login page on canonical staff host
        response = self.client.get(
            "/staff/login/",
            HTTP_HOST="staff.digiland.co.ke",
        )
        self.assertEqual(response.status_code, 200)

        # Login page on canonical app host
        response = self.client.get(
            "/accounts/login/",
            HTTP_HOST="app.digiland.co.ke",
        )
        self.assertEqual(response.status_code, 200)

    def test_05_portal_spoofing_headers_and_params_ignored(self):
        """HTTP_X_DIGILAND_PORTAL and ?portal= query parameters must NOT override host-based security."""
        # Trying to access admin with spoofed header on app host
        response = self.client.get(
            "/admin/dashboard/",
            HTTP_HOST="app.digiland.co.ke",
            HTTP_X_DIGILAND_PORTAL="admin",
        )
        self.assertEqual(response.status_code, 403)

        # Trying to access staff with ?portal=staff query on app host
        response = self.client.get(
            "/staff/dashboard/?portal=staff",
            HTTP_HOST="app.digiland.co.ke",
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(response["Location"].startswith("https://staff.digiland.co.ke"))
