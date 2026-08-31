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

    def test_06_staff_login_on_admin_host_redirects_to_staff_host(self):
        """Accessing /staff/login/ on admin.digiland.co.ke must cleanly redirect to https://staff.digiland.co.ke/staff/login/."""
        response = self.client.get(
            "/staff/login/",
            HTTP_HOST="admin.digiland.co.ke",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://staff.digiland.co.ke/staff/login/")

    def test_07_admin_login_on_staff_host_redirects_to_admin_host(self):
        """Accessing /admin/login/ on staff.digiland.co.ke must cleanly redirect to https://admin.digiland.co.ke/admin/login/."""
        response = self.client.get(
            "/admin/login/",
            HTTP_HOST="staff.digiland.co.ke",
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response["Location"], "https://admin.digiland.co.ke/admin/login/")

    def test_08_authenticated_admin_visiting_staff_login_does_not_loop(self):
        """An authenticated Admin user visiting https://staff.digiland.co.ke/staff/login/ must get 200 OK (no redirect loop)."""
        from core.models import User
        admin_user, _ = User.objects.get_or_create(
            email="admin_test_loop@digiland.co.ke",
            defaults={"role": "Admin", "is_staff": True, "is_superuser": True, "is_active": True}
        )
        self.client.force_login(admin_user)
        response = self.client.get(
            "/staff/login/",
            HTTP_HOST="staff.digiland.co.ke",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Staff Workspace", response.content.decode("utf-8"))

    def test_09_authenticated_agent_visiting_admin_login_does_not_loop(self):
        """An authenticated Agent user visiting https://admin.digiland.co.ke/admin/login/ must get 200 OK (no redirect loop)."""
        from core.models import User
        agent_user, _ = User.objects.get_or_create(
            email="agent_test_loop@digiland.co.ke",
            defaults={"role": "Agent", "is_active": True, "is_identity_verified": True}
        )
        self.client.force_login(agent_user)
        response = self.client.get(
            "/admin/login/",
            HTTP_HOST="admin.digiland.co.ke",
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Admin Command Terminal", response.content.decode("utf-8"))

    def test_10_staff_login_post_authenticates_agent(self):
        """Posting valid Agent credentials to /staff/login/ logs the user in."""
        from core.models import User
        from core.auth_backends import EmailOrUsernameModelBackend
        agent_email = "agent_auth_test@digiland.co.ke"
        agent_pwd = "AgentPassword123!"
        EmailOrUsernameModelBackend.reset_lockout(agent_email, "127.0.0.1")
        agent_user, _ = User.objects.get_or_create(
            email=agent_email,
            defaults={"role": "Agent", "is_active": True, "is_identity_verified": True}
        )
        agent_user.set_password(agent_pwd)
        agent_user.save()

        response = self.client.post(
            "/staff/login/",
            {"email": agent_email, "password": agent_pwd},
            HTTP_HOST="staff.digiland.co.ke",
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn("_auth_user_id", self.client.session)
        self.assertEqual(str(self.client.session["_auth_user_id"]), str(agent_user.id))

