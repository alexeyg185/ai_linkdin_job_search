import unittest
from unittest.mock import patch, MagicMock
from flask import session

# Mock the LinkedIn scraper before importing app
with patch('services.scraper_service.LinkedinScraper') as mock_scraper_class:
    # Create a mock instance that will be returned by the LinkedinScraper constructor
    mock_scraper = MagicMock()
    mock_scraper_class.return_value = mock_scraper
    mock_scraper.on = MagicMock()

    # Now import the app after the patch is in place
    with patch('services.analysis_service.OpenAI') as mock_openai_class:  # Updated to match the new import
        mock_openai_instance = MagicMock()
        mock_openai_class.return_value = mock_openai_instance

        from app import app, orchestrator


class TestRoutes(unittest.TestCase):
    """Test cases for the Flask routes."""

    def setUp(self):
        """Set up test environment."""
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False  # Disable CSRF for testing
        self.client = app.test_client()
        self.app_context = app.app_context()
        self.app_context.push()

        # Create test user if needed
        with patch('services.user_service.bcrypt') as mock_bcrypt:
            mock_bcrypt.gensalt.return_value = b'fakesalt'
            mock_bcrypt.hashpw.return_value = b'fakehashedpassword'
            mock_bcrypt.checkpw.return_value = True

            try:
                orchestrator.user_service.create_user('testuser', 'Password123!', 'test@example.com')
            except ValueError:
                pass  # User already exists

    def tearDown(self):
        """Clean up after tests."""
        self.app_context.pop()

    def login(self, username='testuser', password='Password123!'):
        """Helper method to login a user."""
        return self.client.post('/login', data={
            'username': username,
            'password': password
        }, follow_redirects=True)

    def logout(self):
        """Helper method to logout a user."""
        return self.client.get('/logout', follow_redirects=True)

    @patch('app.render_template')
    def test_index_redirects_to_login(self, mock_render):
        """Test index route behavior."""
        mock_render.return_value = "Mocked template"

        # When not logged in, index should render template
        with patch('flask_login.utils._get_user') as mock_get_user:
            mock_user = MagicMock()
            mock_user.is_authenticated = False
            mock_get_user.return_value = mock_user

            response = self.client.get('/')
            self.assertEqual(response.status_code, 200)
            mock_render.assert_called_once_with('index.html')

    @patch('app.render_template')
    def test_login_page_loads(self, mock_render):
        """Test login page loads correctly."""
        mock_render.return_value = "Mocked login template"
        response = self.client.get('/login')
        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once_with('auth/login.html')

    @patch('services.user_service.UserService.authenticate')
    @patch('app.render_template')
    def test_login_with_valid_credentials(self, mock_render, mock_authenticate):
        """Test login with valid credentials."""
        mock_render.return_value = "Mocked dashboard template"

        # Mock successful authentication
        mock_authenticate.return_value = {
            'user_id': 1,
            'username': 'testuser',
            'email': 'test@example.com'
        }

        response = self.login()
        self.assertEqual(response.status_code, 200)  # follow_redirects=True in login() method

    @patch('services.user_service.UserService.authenticate')
    @patch('app.render_template')
    def test_login_with_invalid_credentials(self, mock_render, mock_authenticate):
        """Test login with invalid credentials."""
        mock_render.return_value = "Mocked login template"

        # Mock failed authentication
        mock_authenticate.return_value = None

        response = self.login(username='testuser', password='wrongpassword')
        self.assertEqual(response.status_code, 200)

    def test_dashboard_requires_login(self):
        """Test dashboard page requires login."""
        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/login' in response.location)

    @patch('flask_login.utils._get_user')
    @patch('services.orchestrator_service.OrchestratorService.get_user_dashboard_data')
    @patch('app.render_template')
    def test_dashboard_loads_after_login(self, mock_render, mock_get_data, mock_get_user):
        """Test dashboard page loads correctly after login."""
        mock_render.return_value = "Mocked dashboard template"

        # Mock the current_user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_authenticated = True
        mock_get_user.return_value = mock_user

        # Mock dashboard data with all required keys
        mock_get_data.return_value = {
            'user': {'username': 'testuser', 'email': 'test@example.com'},
            'job_stats': {
                'total_jobs': 0,
                'states': {},
                'by_company': {},
                'by_location': {},  # Add this missing key
                'recent_activity': []
            },
            'schedule': None,
            'recent_jobs': {'relevant': [], 'saved': [], 'applied': []},
            'running_jobs': {}
        }

        response = self.client.get('/dashboard')
        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once_with('dashboard/index.html', data=mock_get_data.return_value)

    @patch('flask_login.utils._get_user')
    @patch('services.orchestrator_service.OrchestratorService.search_jobs')
    @patch('app.render_template')
    def test_jobs_page_loads(self, mock_render, mock_search_jobs, mock_get_user):
        """Test jobs listing page loads correctly."""
        mock_render.return_value = "Mocked jobs template"

        # Mock the current_user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_authenticated = True
        mock_get_user.return_value = mock_user

        # Mock search results
        mock_search_jobs.return_value = {
            'results': [],
            'pagination': {'total': 0, 'limit': 20, 'offset': 0, 'next_offset': None, 'prev_offset': None}
        }

        response = self.client.get('/jobs')
        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once_with('jobs/list.html', results=mock_search_jobs.return_value,
                                            query='', states=['relevant', 'saved'])

    @patch('flask_login.utils._get_user')
    @patch('services.orchestrator_service.OrchestratorService.search_jobs')
    @patch('app.render_template')
    def test_jobs_filter_by_state(self, mock_render, mock_search_jobs, mock_get_user):
        """Test jobs listing with state filtering."""
        mock_render.return_value = "Mocked jobs template"

        # Mock the current_user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_authenticated = True
        mock_get_user.return_value = mock_user

        # Mock search results
        mock_search_jobs.return_value = {
            'results': [],
            'pagination': {'total': 0, 'limit': 20, 'offset': 0, 'next_offset': None, 'prev_offset': None}
        }

        response = self.client.get('/jobs?state=relevant&state=saved')
        self.assertEqual(response.status_code, 200)  # Fixed typo: changed a200 to 200

        # Check that the correct states were passed to the search function
        mock_search_jobs.assert_called_with(1, '', ['relevant', 'saved'], 20, 0)

    @patch('flask_login.utils._get_user')
    @patch('services.orchestrator_service.OrchestratorService.get_job_details')
    @patch('app.render_template')
    def test_job_detail_page_loads(self, mock_render, mock_get_details, mock_get_user):
        """Test job detail page loads correctly."""
        mock_render.return_value = "Mocked job detail template"

        # Mock the current_user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_authenticated = True
        mock_get_user.return_value = mock_user

        # Mock job details
        job_id = "test_job_1"
        mock_get_details.return_value = {
            'job': {'job_id': job_id, 'title': 'Test Job', 'company': 'Test Company',
                    'description': 'Test Description'},
            'analysis': None,
            'state_history': [],
            'current_state': {'state': 'relevant'}
        }

        response = self.client.get(f'/jobs/{job_id}')
        self.assertEqual(response.status_code, 200)
        mock_render.assert_called_once_with('jobs/detail.html', job=mock_get_details.return_value)

        # Check that job details were requested with correct parameters
        mock_get_details.assert_called_once_with(job_id, 1)

    @patch('flask_login.utils._get_user')
    @patch('services.preference_service.PreferenceService.get_all_preferences')
    @patch('services.database_service.DatabaseService.get_user_schedule')
    @patch('app.render_template')
    def test_preferences_page_loads(self, mock_render, mock_get_schedule, mock_get_preferences, mock_get_user):
        """Test preferences page loads correctly."""
        mock_render.return_value = "Mocked preferences template"

        # Mock the current_user
        mock_user = MagicMock()
        mock_user.id = 1
        mock_user.is_authenticated = True
        mock_get_user.return_value = mock_user

        # Mock preferences and schedule
        mock_get_preferences.return_value = {
            'search': {'job_titles': ['Data Scientist']},
            'analysis': {'required_skills': ['Python']},
            'technical': {'chrome_executable_path': None, 'chrome_binary_location': None}
        }
        mock_get_schedule.return_value = {
            'schedule_type': 'daily',
            'execution_time': '08:00'
        }

        response = self.client.get('/preferences')
        self.assertEqual(response.status_code, 200)  # Fixed typo: changed a200 to 200
        mock_render.assert_called_once_with('preferences/settings.html',
                                            preferences=mock_get_preferences.return_value,
                                            schedule=mock_get_schedule.return_value)

    @patch('services.user_service.UserService.get_all_users')
    def test_setup_page_redirects_if_users_exist(self, mock_get_all_users):
        """Test setup page redirects if users already exist."""
        # Mock users exist
        mock_get_all_users.return_value = [{'user_id': 1, 'username': 'testuser'}]

        response = self.client.get('/setup')
        self.assertEqual(response.status_code, 302)
        self.assertTrue('/login' in response.location)


if __name__ == '__main__':
    unittest.main()