"""Unit tests for OAuth Sign-In Confirmation Gate."""
from django.test import TestCase, Client
from django.urls import reverse
from core.models import User


class OAuthConfirmationGateTestCase(TestCase):
    """Test suite ensuring returning social login users encounter the confirmation gate."""

    def setUp(self):
        self.client = Client()
        self.seller_user = User.objects.create_user(
            email='seller_oauth_test@example.com',
            password='TestPassword123!',
            first_name='Tricky',
            last_name='Taitumu',
            role='Seller',
            is_email_verified=True,
            is_onboarded=True,
        )
        self.buyer_user = User.objects.create_user(
            email='buyer_oauth_test@example.com',
            password='TestPassword123!',
            first_name='Faith',
            last_name='Wanjiku',
            role='Buyer',
            is_email_verified=True,
            is_onboarded=True,
        )

    def test_01_social_confirm_view_renders_for_authenticated_user(self):
        """Authenticated users visiting /auth/social/confirm/ see their identity and target workspace."""
        self.client.force_login(self.seller_user)
        response = self.client.get(reverse('frontend:social_auth_confirm'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Make sure that you want to sign in to Digiland')
        self.assertContains(response, 'seller_oauth_test@example.com')
        self.assertContains(response, 'Seller Dashboard')

    def test_02_social_confirm_submission_redirects_to_target_workspace(self):
        """Submitting confirmation directs the seller to seller dashboard."""
        self.client.force_login(self.seller_user)
        response = self.client.post(reverse('frontend:social_auth_confirm'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue('seller' in response['Location'])

    def test_03_unauthenticated_user_redirected_to_login(self):
        """Unauthenticated access to /auth/social/confirm/ redirects to login."""
        response = self.client.get(reverse('frontend:social_auth_confirm'))
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/accounts/login/' in response['Location'])
