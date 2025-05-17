import unittest
from flask import session
from app import app, orchestrator


class TestMobileResponsiveness(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
        self.client = app.test_client()

        # Create test user if needed
        try:
            orchestrator.user_service.create_user('testuser', 'Password123!', 'test@example.com')
        except ValueError:
            pass  # User already exists

        # Login
        self.client.post('/login', data={
            'username': 'testuser',
            'password': 'Password123!'
        })

    def test_mobile_api_responses(self):
        """Test API endpoints return compact data suitable for mobile."""
        # Set mobile user agent
        mobile_headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'
        }

        # Test dashboard data - should be compact for mobile
        response = self.client.get('/dashboard', headers=mobile_headers)
        self.assertEqual(response.status_code, 200)

        # Check if mobile view is activated (implementation specific)
        self.assertIn(b'mobile-view', response.data)

        # Test job listing - should have pagination optimized for mobile
        response = self.client.get('/jobs', headers=mobile_headers)
        self.assertEqual(response.status_code, 200)

        # Mobile should show fewer jobs per page
        self.assertIn(b'limit=10', response.data)  # Assuming mobile shows 10 jobs per page

    def test_mobile_preference_setting(self):
        """Test setting mobile view preference."""
        # Set mobile UI preference
        data = {
            'mobile_view': 'compact'
        }

        response = self.client.post('/api/update_preferences',
                                    json={'ui': data},
                                    content_type='application/json')

        self.assertEqual(response.status_code, 200)

        # Verify preference was saved
        user = orchestrator.user_service.get_user_by_username('testuser')
        prefs = orchestrator.pref_service.get_preferences_by_category(user['user_id'], 'ui')
        self.assertEqual(prefs['mobile_view'], 'compact')