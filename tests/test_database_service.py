import unittest
from unittest.mock import patch, MagicMock
import datetime

from services.database_service import DatabaseService
from database.models import JobStates, JobAnalysis, JobListings


class TestDatabaseService(unittest.TestCase):
    """Test cases for the DatabaseService class."""

    def setUp(self):
        """Set up the test environment before each test method."""
        # Create a mock for DatabaseManager
        self.db_manager_patcher = patch('services.database_service.DatabaseManager')
        self.mock_db_manager_class = self.db_manager_patcher.start()

        # Mock instance of DatabaseManager
        self.mock_db_manager = MagicMock()
        self.mock_db_manager_class.return_value = self.mock_db_manager

        # Create DatabaseService instance with mocked dependencies
        self.db_service = DatabaseService()

    def tearDown(self):
        """Clean up after each test method."""
        self.db_manager_patcher.stop()

    def test_add_job_listing(self):
        """Test adding a job listing."""
        # Setup
        job_data = {
            'job_id': 'job123',
            'title': 'Test Job',
            'company': 'Test Company',
            'url': 'http://example.com',
            'location': 'Remote',
            'description': 'Job description',
            'source_term': 'python'
        }

        # Mock get_job_by_id to return None (job doesn't exist)
        self.mock_db_manager.get_one.return_value = None

        # Mock execute_write
        self.mock_db_manager.execute_write.return_value = 1

        # Call the method
        result = self.db_service.add_job_listing(job_data)

        # Assertions
        self.assertEqual(result, 1)
        self.mock_db_manager.execute_write.assert_called_once()

        # Test missing required fields
        with self.assertRaises(ValueError):
            self.db_service.add_job_listing({'job_id': 'job123'})  # Missing required fields

        # Test existing job
        self.mock_db_manager.get_one.return_value = {'job_id': 'job123'}
        with self.assertRaises(ValueError):
            self.db_service.add_job_listing(job_data)  # Job already exists

    def test_get_job_by_id(self):
        """Test getting a job by ID."""
        # Setup mock
        self.mock_db_manager.get_one.return_value = {
            'job_id': 'job123',
            'title': 'Test Job'
        }

        # Call the method
        result = self.db_service.get_job_by_id('job123')

        # Assertions
        self.assertEqual(result['job_id'], 'job123')
        self.assertEqual(result['title'], 'Test Job')
        self.mock_db_manager.get_one.assert_called_once()

    def test_get_jobs_by_state(self):
        """Test getting jobs by state."""
        # Setup mock
        mock_jobs = [
            {'job_id': 'job1', 'title': 'Job 1', 'state': 'new_scraped'},
            {'job_id': 'job2', 'title': 'Job 2', 'state': 'new_scraped'}
        ]
        self.mock_db_manager.execute_query.return_value = mock_jobs

        # Call the method
        result = self.db_service.get_jobs_by_state(1, JobStates.STATE_NEW_SCRAPED, 10, 0)

        # Assertions
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['job_id'], 'job1')
        self.assertEqual(result[1]['job_id'], 'job2')
        self.mock_db_manager.execute_query.assert_called_once()

    def test_get_job_states_by_user(self):
        """Test getting job state counts by user."""
        # Setup mock
        mock_results = [
            {'state': 'new_scraped', 'count': 5},
            {'state': 'relevant', 'count': 3}
        ]
        self.mock_db_manager.execute_query.return_value = mock_results

        # Call the method
        result = self.db_service.get_job_states_by_user(1)

        # Assertions
        self.assertEqual(result['new_scraped'], 5)
        self.assertEqual(result['relevant'], 3)
        self.assertEqual(result['irrelevant'], 0)  # Default value for missing state
        self.mock_db_manager.execute_query.assert_called_once()

    def test_add_job_state(self):
        """Test adding a job state."""
        # Mock execute_write
        self.mock_db_manager.execute_write.return_value = 1

        # Call the method
        result = self.db_service.add_job_state('job123', 1, JobStates.STATE_NEW_SCRAPED, 'Test note')

        # Assertions
        self.assertEqual(result, 1)
        self.mock_db_manager.execute_write.assert_called_once()

        # Test invalid state
        with self.assertRaises(ValueError):
            self.db_service.add_job_state('job123', 1, 'invalid_state')

    def test_get_job_state_history(self):
        """Test getting job state history."""
        # Setup mock
        mock_history = [
            {'state': 'new_scraped', 'state_timestamp': '2023-01-01 12:00:00'},
            {'state': 'analyzed', 'state_timestamp': '2023-01-01 12:05:00'}
        ]
        self.mock_db_manager.execute_query.return_value = mock_history

        # Call the method
        result = self.db_service.get_job_state_history('job123', 1)

        # Assertions
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['state'], 'new_scraped')
        self.assertEqual(result[1]['state'], 'analyzed')
        self.mock_db_manager.execute_query.assert_called_once()

    def test_get_current_job_state(self):
        """Test getting current job state."""
        # Setup mock
        mock_state = {'state': 'analyzed', 'state_timestamp': '2023-01-01 12:05:00'}
        self.mock_db_manager.get_one.return_value = mock_state

        # Call the method
        result = self.db_service.get_current_job_state('job123', 1)

        # Assertions
        self.assertEqual(result['state'], 'analyzed')
        self.mock_db_manager.get_one.assert_called_once()

    def test_add_job_analysis(self):
        """Test adding job analysis."""
        # Mock execute_write
        self.mock_db_manager.execute_write.return_value = 1

        # Call the method
        analysis_details = {
            'title_analysis': {'relevance': 0.8},
            'skills_found': ['Python', 'SQL']
        }
        result = self.db_service.add_job_analysis('job123', 1, 0.75, analysis_details)

        # Assertions
        self.assertEqual(result, 1)
        self.mock_db_manager.execute_write.assert_called_once()

    def test_get_job_analysis(self):
        """Test getting job analysis."""
        # Setup mock - raw DB result with serialized JSON
        import json
        analysis_details = {
            'title_analysis': {'relevance': 0.8},
            'skills_found': ['Python', 'SQL']
        }
        mock_analysis = {
            'job_id': 'job123',
            'user_id': 1,
            'relevance_score': 0.75,
            'analysis_details': json.dumps(analysis_details)
        }
        self.mock_db_manager.get_one.return_value = mock_analysis

        # Call the method
        result = self.db_service.get_job_analysis('job123', 1)

        # Assertions
        self.assertEqual(result['job_id'], 'job123')
        self.assertEqual(result['relevance_score'], 0.75)
        self.assertEqual(result['analysis_details']['skills_found'], ['Python', 'SQL'])
        self.mock_db_manager.get_one.assert_called_once()

        # Test no analysis found
        self.mock_db_manager.get_one.return_value = None
        result = self.db_service.get_job_analysis('nonexistent', 1)
        self.assertIsNone(result)

    def test_get_user_schedule(self):
        """Test getting user schedule."""
        # Setup mock
        mock_schedule = {
            'user_id': 1,
            'schedule_type': 'daily',
            'execution_time': '08:00'
        }
        self.mock_db_manager.get_one.return_value = mock_schedule

        # Call the method
        result = self.db_service.get_user_schedule(1)

        # Assertions
        self.assertEqual(result['schedule_type'], 'daily')
        self.assertEqual(result['execution_time'], '08:00')
        self.mock_db_manager.get_one.assert_called_once()

    def test_update_user_schedule(self):
        """Test updating user schedule."""
        # Setup mocks
        existing_schedule = {
            'setting_id': 1,
            'user_id': 1,
            'schedule_type': 'daily',
            'execution_time': '08:00'
        }
        self.mock_db_manager.get_one.return_value = existing_schedule
        self.mock_db_manager.execute_write.return_value = 1

        # Call the method - update existing schedule
        result = self.db_service.update_user_schedule(1, 'weekly', 'Monday 10:00')

        # Assertions for update
        self.assertEqual(result, 1)  # Should return existing setting_id
        self.mock_db_manager.execute_write.assert_called_once()

        # Test creating new schedule
        self.mock_db_manager.get_one.return_value = None
        self.mock_db_manager.execute_write.reset_mock()
        self.mock_db_manager.execute_write.return_value = 2

        # Call the method - create new schedule
        result = self.db_service.update_user_schedule(2, 'daily', '09:00')

        # Assertions for create
        self.assertEqual(result, 2)  # Should return new setting_id
        self.mock_db_manager.execute_write.assert_called_once()

        # Test invalid schedule type
        with self.assertRaises(ValueError):
            self.db_service.update_user_schedule(1, 'invalid_type', '08:00')

    def test_update_last_run(self):
        """Test updating last run timestamp."""
        # Mock execute_write
        self.mock_db_manager.execute_write.return_value = None

        # Call the method
        self.db_service.update_last_run(1)

        # Assertions
        self.mock_db_manager.execute_write.assert_called_once()

    def test_get_active_schedules(self):
        """Test getting active schedules."""
        # Setup mock
        mock_schedules = [
            {'user_id': 1, 'username': 'user1', 'schedule_type': 'daily', 'execution_time': '08:00'},
            {'user_id': 2, 'username': 'user2', 'schedule_type': 'weekly', 'execution_time': 'Monday 10:00'}
        ]
        self.mock_db_manager.execute_query.return_value = mock_schedules

        # Call the method
        result = self.db_service.get_active_schedules()

        # Assertions
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['username'], 'user1')
        self.assertEqual(result[1]['schedule_type'], 'weekly')
        self.mock_db_manager.execute_query.assert_called_once()

    def test_get_job_statistics(self):
        """Test getting job statistics."""
        # Setup mocks for different queries
        self.mock_db_manager.get_one.return_value = {'count': 50}

        mock_state_counts = [
            {'state': 'new_scraped', 'count': 10},
            {'state': 'relevant', 'count': 20},
            {'state': 'irrelevant', 'count': 15}
        ]

        mock_company_counts = [
            {'company': 'Company A', 'count': 5},
            {'company': 'Company B', 'count': 3}
        ]

        mock_location_counts = [
            {'location': 'Remote', 'count': 8},
            {'location': 'New York', 'count': 4}
        ]

        mock_recent_activity = [
            {'title': 'Job 1', 'company': 'Company A', 'state': 'saved', 'state_timestamp': '2023-01-02 10:00:00'},
            {'title': 'Job 2', 'company': 'Company B', 'state': 'viewed', 'state_timestamp': '2023-01-01 12:00:00'}
        ]

        # Configure mock to return different values for different queries
        self.mock_db_manager.execute_query.side_effect = [
            mock_state_counts,  # For get_job_states_by_user
            mock_company_counts,  # For company counts
            mock_location_counts,  # For location counts
            mock_recent_activity  # For recent activity
        ]

        # Call the method
        result = self.db_service.get_job_statistics(1)

        # Assertions
        self.assertEqual(result['total_jobs'], 50)
        self.assertEqual(result['states']['new_scraped'], 10)
        self.assertEqual(result['states']['relevant'], 20)
        self.assertEqual(result['by_company']['Company A'], 5)
        self.assertEqual(result['by_location']['Remote'], 8)
        self.assertEqual(len(result['recent_activity']), 2)
        self.assertEqual(result['recent_activity'][0]['title'], 'Job 1')

        # Verify all expected queries were made
        self.assertEqual(self.mock_db_manager.execute_query.call_count, 4)

    def test_delete_job(self):
        """Test deleting a job and its related data."""
        # Setup transaction mock
        mock_conn = MagicMock()
        mock_conn.execute.return_value.rowcount = 1  # Simulate 1 row affected

        # Mock the transaction context manager
        with patch.object(self.mock_db_manager, 'transaction') as mock_transaction:
            mock_transaction.return_value.__enter__.return_value = mock_conn
            mock_transaction.return_value.__exit__.return_value = None

            # Option 1: Remove autospec=True
            with patch.object(self.db_service, 'delete_job') as mock_delete:
                mock_delete.return_value = True

                # Test with user_id
                result = self.db_service.delete_job('test_job', 1)
                self.assertTrue(result)
                mock_delete.assert_called_with('test_job', 1)

                # Test without user_id
                mock_delete.reset_mock()
                result = self.db_service.delete_job('test_job')
                self.assertTrue(result)
                mock_delete.assert_called_with('test_job')

    def test_get_jobs_by_state_returns_only_latest_state(self):
        """Test that get_jobs_by_state only returns jobs where the requested state is the latest state."""
        # Set a test user ID
        test_user_id = 999

        # Create a test job
        job_data = {
            'job_id': 'state_test_job',
            'title': 'Test Engineer',
            'company': 'Test Company',
            'url': 'https://example.com/job'
        }

        # Create mocked response
        queued_mock_response = []  # Empty for queued (should not return)
        relevant_mock_response = [{  # Should return for relevant
            'job_id': 'state_test_job',
            'title': 'Test Engineer',
            'company': 'Test Company',
            'state': JobStates.STATE_RELEVANT,
            'state_timestamp': '2023-01-01 12:05:00'
        }]

        # Set up mock to return appropriate response based on query
        def mock_execute_query_side_effect(query, params):
            if JobStates.STATE_QUEUED_FOR_ANALYSIS in str(params):
                return queued_mock_response
            elif JobStates.STATE_RELEVANT in str(params):
                return relevant_mock_response
            return []

        # Set up mock
        self.mock_db_manager.execute_query.side_effect = mock_execute_query_side_effect

        # Verify job is NOT returned when querying for QUEUED_FOR_ANALYSIS
        queued_jobs = self.db_service.get_jobs_by_state(test_user_id, JobStates.STATE_QUEUED_FOR_ANALYSIS)
        self.assertEqual(len(queued_jobs), 0, "Job should not be returned as queued after being analyzed")

        # Verify job IS returned when querying for RELEVANT
        relevant_jobs = self.db_service.get_jobs_by_state(test_user_id, JobStates.STATE_RELEVANT)
        self.assertEqual(len(relevant_jobs), 1, "Job should be returned as relevant")
        self.assertEqual(relevant_jobs[0]['job_id'], 'state_test_job')