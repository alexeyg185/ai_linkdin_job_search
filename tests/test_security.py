import unittest
from unittest.mock import patch, MagicMock
import re

# Create mock for the LinkedIn scraper before importing any app modules
mock_linkedin_scraper = MagicMock()
mock_linkedin_scraper_instance = MagicMock()
mock_linkedin_scraper.return_value = mock_linkedin_scraper_instance
patch('services.scraper_service.LinkedinScraper', mock_linkedin_scraper).start()

# Now it's safe to import from app
from app import app, orchestrator


class TestSecurity(unittest.TestCase):
    def setUp(self):
        """Set up the test environment before each test method."""
        app.config['TESTING'] = True
        self.client = app.test_client()

        # Create test user if needed
        try:
            orchestrator.user_service.create_user('testuser', 'Password123!', 'test@example.com')
        except ValueError:
            pass  # User already exists

    def test_csrf_protection(self):
        """Test that CSRF protection is working."""
        # Enable CSRF for this test
        app.config['WTF_CSRF_ENABLED'] = True

        # Login first to get a session
        self.client.post('/login', data={
            'username': 'testuser',
            'password': 'Password123!'
        })

        # Try to submit a form without CSRF token
        response = self.client.post('/api/update_preferences',
                                    json={'search': {'job_titles': ['AI Engineer']}},
                                    content_type='application/json')

        # Should return 400 or redirect due to CSRF failure
        self.assertNotEqual(response.status_code, 200)

        # Reset CSRF setting
        app.config['WTF_CSRF_ENABLED'] = False

    def test_protected_routes_require_login(self):
        """Test that protected routes require login."""
        # These routes should all redirect to login
        protected_routes = [
            '/dashboard',
            '/jobs',
            '/preferences',
            '/api/update_preferences',
            '/api/update_job_state',
            '/api/run_job',
            '/api/reanalyze_job'
        ]

        for route in protected_routes:
            method = self.client.get if 'api' not in route else self.client.post
            response = method(route, follow_redirects=False)

            self.assertEqual(response.status_code, 302, f"Route {route} should redirect when not logged in")
            self.assertTrue('/login' in response.location, f"Route {route} should redirect to login")

    def test_password_policy(self):
        """Test password policy enforcement."""
        # Test with the security utility directly
        from utils.security import validate_password

        # Test weak passwords
        weak_passwords = [
            'short',  # Too short
            'lowercase',  # No uppercase, numbers, or special chars
            'UPPERCASE',  # No lowercase, numbers, or special chars
            'NoSpecial123',  # No special char
            'NoNumber!',  # No number
            'no$upper123'  # No uppercase
        ]

        for password in weak_passwords:
            valid, message = validate_password(password)
            self.assertFalse(valid, f"Should not allow weak password: {password}")
            self.assertIsNotNone(message, "Should provide an error message")

    @patch('app.flash')  # Mock flash messages since they use session
    def test_login_failure_handling(self, mock_flash):
        """Test handling of login failures."""
        # Mock the authenticate method to return None (authentication failure)
        with patch.object(orchestrator.user_service, 'authenticate', return_value=None):
            response = self.client.post('/login', data={
                'username': 'testuser',
                'password': 'wrong_password'
            }, follow_redirects=True)

            # Check for failed login message
            mock_flash.assert_called_with('Invalid username or password', 'danger')


if __name__ == '__main__':
    unittest.main()