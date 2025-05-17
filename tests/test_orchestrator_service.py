import unittest
from unittest.mock import patch, MagicMock, call

from services.orchestrator_service import OrchestratorService


class TestOrchestratorService(unittest.TestCase):
    """Test cases for the OrchestratorService class."""

    def setUp(self):
        """Set up the test environment before each test method."""
        # Create mocks for all services
        self.user_service_patcher = patch('services.orchestrator_service.UserService')
        self.mock_user_service_class = self.user_service_patcher.start()
        self.mock_user_service = MagicMock()
        self.mock_user_service_class.return_value = self.mock_user_service

        self.db_service_patcher = patch('services.orchestrator_service.DatabaseService')
        self.mock_db_service_class = self.db_service_patcher.start()
        self.mock_db_service = MagicMock()
        self.mock_db_service_class.return_value = self.mock_db_service

        self.pref_service_patcher = patch('services.orchestrator_service.PreferenceService')
        self.mock_pref_service_class = self.pref_service_patcher.start()
        self.mock_pref_service = MagicMock()
        self.mock_pref_service_class.return_value = self.mock_pref_service

        self.scraper_service_patcher = patch('services.orchestrator_service.ScraperService')
        self.mock_scraper_service_class = self.scraper_service_patcher.start()
        self.mock_scraper_service = MagicMock()
        self.mock_scraper_service_class.return_value = self.mock_scraper_service

        self.analysis_service_patcher = patch('services.orchestrator_service.AnalysisService')
        self.mock_analysis_service_class = self.analysis_service_patcher.start()
        self.mock_analysis_service = MagicMock()
        self.mock_analysis_service_class.return_value = self.mock_analysis_service

        self.scheduler_service_patcher = patch('services.orchestrator_service.SchedulerService')
        self.mock_scheduler_service_class = self.scheduler_service_patcher.start()
        self.mock_scheduler_service = MagicMock()
        self.mock_scheduler_service_class.return_value = self.mock_scheduler_service

        # Mock logging
        self.logging_patcher = patch('services.orchestrator_service.logger')
        self.mock_logger = self.logging_patcher.start()

        # Create service instance
        self.orchestrator_service = OrchestratorService()

    def tearDown(self):
        """Clean up after each test method."""
        self.user_service_patcher.stop()
        self.db_service_patcher.stop()
        self.pref_service_patcher.stop()
        self.scraper_service_patcher.stop()
        self.analysis_service_patcher.stop()
        self.scheduler_service_patcher.stop()
        self.logging_patcher.stop()

    def test_init(self):
        """Test initialization of OrchestratorService."""
        # Verify services were initialized
        self.assertIsNotNone(self.orchestrator_service.user_service)
        self.assertIsNotNone(self.orchestrator_service.db_service)
        self.assertIsNotNone(self.orchestrator_service.pref_service)
        self.assertIsNotNone(self.orchestrator_service.scraper_service)
        self.assertIsNotNone(self.orchestrator_service.analysis_service)
        self.assertIsNotNone(self.orchestrator_service.scheduler_service)

        # Verify scheduler was started
        self.mock_scheduler_service.start.assert_called_once()

    def test_setup_new_installation(self):
        """Test setting up a new installation with admin user."""
        # Mock user creation
        self.mock_user_service.create_user.return_value = 1

        # Call the method
        result = self.orchestrator_service.setup_new_installation(
            'admin', 'password123', 'admin@example.com'
        )

        # Verify user was created
        self.mock_user_service.create_user.assert_called_once_with(
            'admin', 'password123', 'admin@example.com'
        )

        # Verify preferences were set up
        self.mock_pref_service.setup_default_preferences.assert_called_once_with(1)

        # Verify schedule was set up
        self.mock_scheduler_service.update_schedule.assert_called_once_with(
            1, "daily", "08:00", True
        )

        # Verify result
        self.assertEqual(result, 1)

    def test_run_manual_job(self):
        """Test running a manual job."""
        # Mock scheduler
        self.mock_scheduler_service.run_job_now.return_value = 'job123'

        # Call the method
        mock_callback = MagicMock()
        result = self.orchestrator_service.run_manual_job(1, mock_callback)

        # Verify scheduler was called
        self.mock_scheduler_service.run_job_now.assert_called_once_with(1, mock_callback)

        # Verify result
        self.assertEqual(result['status'], 'started')
        self.assertEqual(result['job_id'], 'job123')
        self.assertEqual(result['user_id'], 1)

    def test_update_user_preferences(self):
        """Test updating user preferences."""
        # Prepare test data
        preferences = {
            'search': {
                'job_titles': ['AI Engineer', 'Machine Learning Engineer'],
                'locations': ['Remote', 'New York']
            },
            'analysis': {
                'required_skills': ['Python', 'TensorFlow'],
                'relevance_threshold': 0.8
            },
            'scheduling': {
                'schedule_type': 'weekly',
                'execution_time': 'Monday 09:00',
                'notifications_enabled': True
            }
        }

        # Call the method
        self.orchestrator_service.update_user_preferences(1, preferences)

        # Verify preference service was called for each category
        self.mock_pref_service.update_preference_category.assert_any_call(
            1, 'search', preferences['search']
        )
        self.mock_pref_service.update_preference_category.assert_any_call(
            1, 'analysis', preferences['analysis']
        )
        self.mock_pref_service.update_preference_category.assert_any_call(
            1, 'scheduling', preferences['scheduling']
        )

        # Verify scheduler was updated for scheduling preferences
        self.mock_scheduler_service.update_schedule.assert_called_once_with(
            1, 'weekly', 'Monday 09:00', True
        )

        # Test without scheduling preferences
        self.mock_pref_service.update_preference_category.reset_mock()
        self.mock_scheduler_service.update_schedule.reset_mock()

        preferences_without_scheduling = {
            'search': {
                'job_titles': ['Data Scientist']
            }
        }

        # Call the method
        self.orchestrator_service.update_user_preferences(1, preferences_without_scheduling)

        # Verify preference service was called
        self.mock_pref_service.update_preference_category.assert_called_once()

        # Verify scheduler was not updated
        self.mock_scheduler_service.update_schedule.assert_not_called()

    def test_get_user_dashboard_data(self):
        """Test getting user dashboard data."""
        # Mock service responses
        self.mock_user_service.get_user_by_id.return_value = {
            'username': 'testuser',
            'email': 'test@example.com',
            'last_login': '2023-01-01 12:00:00'
        }

        self.mock_db_service.get_job_statistics.return_value = {
            'total_jobs': 50,
            'states': {'relevant': 10, 'applied': 5},
            'by_company': {'Company A': 3},
            'recent_activity': []
        }

        self.mock_db_service.get_user_schedule.return_value = {
            'schedule_type': 'daily',
            'execution_time': '08:00',
            'enabled': True
        }

        self.mock_db_service.get_jobs_by_state.return_value = []

        self.mock_scheduler_service.get_all_job_statuses.return_value = {}

        # Call the method
        result = self.orchestrator_service.get_user_dashboard_data(1)

        # Verify services were called
        self.mock_user_service.get_user_by_id.assert_called_once_with(1)
        self.mock_db_service.get_job_statistics.assert_called_once_with(1)
        self.mock_db_service.get_user_schedule.assert_called_once_with(1)

        # Verify DB service was called for each job state
        self.mock_db_service.get_jobs_by_state.assert_any_call(1, "relevant", 5)
        self.mock_db_service.get_jobs_by_state.assert_any_call(1, "saved", 5)
        self.mock_db_service.get_jobs_by_state.assert_any_call(1, "applied", 5)

        # Verify scheduler was queried for jobs
        self.mock_scheduler_service.get_all_job_statuses.assert_called_once_with(1)

        # Verify result structure
        self.assertIn('user', result)
        self.assertIn('job_stats', result)
        self.assertIn('schedule', result)
        self.assertIn('recent_jobs', result)
        self.assertIn('running_jobs', result)

        # Verify user data
        self.assertEqual(result['user']['username'], 'testuser')
        self.assertEqual(result['user']['email'], 'test@example.com')

    def test_get_job_details(self):
        """Test getting detailed job information."""
        # Mock service responses
        self.mock_db_service.get_job_by_id.return_value = {
            'job_id': 'job123',
            'title': 'Data Scientist',
            'company': 'Company A',
            'description': 'Job description'
        }

        self.mock_db_service.get_job_analysis.return_value = {
            'relevance_score': 0.85,
            'analysis_details': {'required_skills_found': ['Python']}
        }

        self.mock_db_service.get_job_state_history.return_value = [
            {'state': 'new_scraped', 'state_timestamp': '2023-01-01 12:00:00'},
            {'state': 'analyzed', 'state_timestamp': '2023-01-01 12:05:00'}
        ]

        self.mock_db_service.get_current_job_state.return_value = {
            'state': 'analyzed',
            'state_timestamp': '2023-01-01 12:05:00'
        }

        # Call the method
        result = self.orchestrator_service.get_job_details('job123', 1)

        # Verify services were called
        self.mock_db_service.get_job_by_id.assert_called_once_with('job123')
        self.mock_db_service.get_job_analysis.assert_called_once_with('job123', 1)
        self.mock_db_service.get_job_state_history.assert_called_once_with('job123', 1)
        self.mock_db_service.get_current_job_state.assert_called_once_with('job123', 1)

        # Verify job was not marked as viewed (already in analyzed state)
        self.mock_db_service.add_job_state.assert_not_called()

        # Verify result structure
        self.assertIn('job', result)
        self.assertIn('analysis', result)
        self.assertIn('state_history', result)
        self.assertIn('current_state', result)

        # Verify job data
        self.assertEqual(result['job']['title'], 'Data Scientist')
        self.assertEqual(result['analysis']['relevance_score'], 0.85)
        self.assertEqual(len(result['state_history']), 2)
        self.assertEqual(result['current_state']['state'], 'analyzed')

        # Test marking as viewed
        self.mock_db_service.get_current_job_state.return_value = {
            'state': 'relevant',
            'state_timestamp': '2023-01-01 12:05:00'
        }

        # Reset mocks
        self.mock_db_service.add_job_state.reset_mock()

        # Call the method again
        result = self.orchestrator_service.get_job_details('job123', 1)

        # Verify job was marked as viewed (state was 'relevant')
        self.mock_db_service.add_job_state.assert_called_once_with('job123', 1, 'viewed')

        # Test job not found
        self.mock_db_service.get_job_by_id.return_value = None

        # Verify exception is raised
        with self.assertRaises(ValueError):
            self.orchestrator_service.get_job_details('nonexistent', 1)

    def test_update_job_state(self):
        """Test updating a job's state."""
        # Mock service responses
        self.mock_db_service.add_job_state.return_value = 1
        self.mock_db_service.get_current_job_state.return_value = {
            'state': 'saved',
            'state_timestamp': '2023-01-01 12:00:00'
        }

        # Call the method
        result = self.orchestrator_service.update_job_state('job123', 1, 'saved', 'Good fit')

        # Verify service was called
        self.mock_db_service.add_job_state.assert_called_once_with('job123', 1, 'saved', 'Good fit')
        self.mock_db_service.get_current_job_state.assert_called_once_with('job123', 1)

        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['job_id'], 'job123')
        self.assertEqual(result['state']['state'], 'saved')

        # Test invalid state
        with self.assertRaises(ValueError):
            self.orchestrator_service.update_job_state('job123', 1, 'invalid_state')

    def test_search_jobs(self):
        """Test searching for jobs."""
        # Mock service response
        self.mock_db_service.db_manager.get_one.return_value = {'count': 50}
        self.mock_db_service.db_manager.execute_query.return_value = [
            {'job_id': 'job1', 'title': 'Data Scientist', 'company': 'Company A'},
            {'job_id': 'job2', 'title': 'ML Engineer', 'company': 'Company B'}
        ]

        # Call the method
        result = self.orchestrator_service.search_jobs(
            1, 'python', ['relevant', 'saved'], 20, 0
        )

        # Verify db manager was called for count and results
        self.mock_db_service.db_manager.get_one.assert_called_once()
        self.mock_db_service.db_manager.execute_query.assert_called_once()

        # Verify result structure
        self.assertIn('results', result)
        self.assertIn('pagination', result)
        self.assertEqual(len(result['results']), 2)
        self.assertEqual(result['pagination']['total'], 50)
        self.assertEqual(result['pagination']['limit'], 20)
        self.assertEqual(result['pagination']['offset'], 0)
        self.assertEqual(result['pagination']['next_offset'], 20)
        self.assertIsNone(result['pagination']['prev_offset'])

        # Test pagination - second page
        self.mock_db_service.db_manager.reset_mock()
        self.orchestrator_service.search_jobs(1, 'python', ['relevant'], 20, 20)

        # Verify pagination parameters
        args = self.mock_db_service.db_manager.execute_query.call_args[0][1]
        self.assertEqual(args[-2], 20)  # limit
        self.assertEqual(args[-1], 20)  # offset

    def test_reanalyze_job(self):
        """Test reanalyzing a job."""
        # Mock service response
        self.mock_analysis_service.reanalyze_job.return_value = {
            'status': 'success',
            'relevance_score': 0.85,
            'is_relevant': True
        }

        # Call the method
        result = self.orchestrator_service.reanalyze_job('job123', 1)

        # Verify service was called
        self.mock_analysis_service.reanalyze_job.assert_called_once_with('job123', 1)

        # Verify result
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['relevance_score'], 0.85)
        self.assertEqual(result['is_relevant'], True)

    def test_stop_services(self):
        """Test stopping all services."""
        # Call the method
        self.orchestrator_service.stop_services()

        # Verify scheduler was stopped
        self.mock_scheduler_service.stop.assert_called_once()

        # Verify database connections were closed
        self.mock_db_service.db_manager.close_all.assert_called_once()

    def test_delete_job(self):
        """Test deleting a job through the orchestrator."""
        # Mock job details
        mock_job = {
            'job': {'job_id': 'test_job_1', 'title': 'Test Job'},
            'analysis': {'relevance_score': 0.8},
            'state_history': [{'state': 'relevant'}],
            'current_state': {'state': 'relevant'}
        }

        # Mock get_job_details to return our test job
        with patch.object(self.orchestrator_service, 'get_job_details') as mock_get_details:
            mock_get_details.return_value = mock_job

            # Mock database service delete_job to return success
            self.mock_db_service.delete_job.return_value = True

            # Call the method
            result = self.orchestrator_service.delete_job('test_job_1', 1)

            # Assertions
            self.assertEqual(result['status'], 'success')
            self.assertIn('message', result)

            # Verify get_job_details was called to check access
            mock_get_details.assert_called_once_with('test_job_1', 1)

            # Verify delete_job was called with both job_id and user_id
            self.mock_db_service.delete_job.assert_called_once_with('test_job_1', 1)

            # Test failed deletion
            self.mock_db_service.delete_job.reset_mock()
            self.mock_db_service.delete_job.return_value = False
            result = self.orchestrator_service.delete_job('test_job_1', 1)
            self.assertEqual(result['status'], 'error')

            # Test job not found / no access
            mock_get_details.side_effect = ValueError("Job not found")
            result = self.orchestrator_service.delete_job('nonexistent', 1)
            self.assertEqual(result['status'], 'error')
            self.assertIn('message', result)

            # Test unexpected error
            mock_get_details.side_effect = Exception("Unexpected error")
            result = self.orchestrator_service.delete_job('test_job_1', 1)
            self.assertEqual(result['status'], 'error')
            self.assertIn('Unexpected error', result['message'])


if __name__ == '__main__':
    unittest.main()