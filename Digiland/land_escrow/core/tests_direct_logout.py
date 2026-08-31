"""Unit tests for universal direct logout flow."""
from django.test import TestCase, Client
from django.urls import reverse
from core.models import User


class DirectLogoutTestCase(TestCase):
    """Test suite ensuring sign-out works reliably on GET and POST across all partitions."""

    def setUp(self):
        self.client = Client()
        self.user = User.objects.create_user(
            email='logout_test_user@example.com',
            password='TestPassword123!',
            role='Seller',
            is_email_verified=True,
            is_onboarded=True,
        )

    def test_01_get_logout_terminates_session(self):
        """GET /accounts/logout/ logs out user and redirects to login."""
        self.client.force_login(self.user)
        self.assertTrue('_auth_user_id' in self.client.session)

        response = self.client.get(reverse('account_logout'))
        self.assertEqual(response.status_code, 302)
        self.assertFalse('_auth_user_id' in self.client.session)
        self.assertTrue('/accounts/login/' in response['Location'])

    def test_02_post_logout_terminates_session(self):
        """POST /accounts/logout/ logs out user and redirects to login."""
        self.client.force_login(self.user)
        self.assertTrue('_auth_user_id' in self.client.session)

        response = self.client.post(reverse('account_logout'))
        self.assertEqual(response.status_code, 302)
        self.assertFalse('_auth_user_id' in self.client.session)
        self.assertTrue('/accounts/login/' in response['Location'])

    def test_03_staff_logout_redirects_to_staff_login(self):
        """Staff partition logout redirects to staff login portal."""
        self.client.force_login(self.user)
        response = self.client.get(reverse('frontend:logout_to_staff_login'), HTTP_HOST='staff.digiland.co.ke')
        self.assertEqual(response.status_code, 302)
        self.assertTrue('staff' in response['Location'])
