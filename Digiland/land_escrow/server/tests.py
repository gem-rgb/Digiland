from django.test import TestCase


class PublicMarketingPageTests(TestCase):
    def test_public_marketing_pages_render_through_react_shell(self):
        for path, content_key in [
            ('/about/', 'about'),
            ('/architecture/', 'architecture'),
            ('/investors/', 'investors'),
            ('/terms/', 'terms'),
            ('/privacy/', 'privacy'),
        ]:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, f'"content_key": "{content_key}"')

    def test_public_marketing_pages_redirect_without_trailing_slash(self):
        for path in ['/about', '/architecture', '/investors', '/terms', '/privacy']:
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 301)
