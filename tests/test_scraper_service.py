import unittest
from unittest.mock import patch, MagicMock, call, ANY
import random

from services.scraper_service import ScraperService
from database.models import JobStates
from linkedin_jobs_scraper.events import Events, EventData
from linkedin_jobs_scraper.filters import ExperienceLevelFilters


class TestScraperService(unittest.TestCase):
    """Test cases for the ScraperService class."""

    def setUp(self):
        """Set up the test environment before each test method."""
        # Create mocks for dependencies
        self.db_service_patcher = patch('services.scraper_service.DatabaseService')
        self.mock_db_service_class = self.db_service_patcher.start()
        self.mock_db_service = MagicMock()
        self.mock_db_service_class.return_value = self.mock_db_service

        # Mock LinkedinScraper
        self.linkedin_scraper_patcher = patch('services.scraper_service.LinkedinScraper')
        self.mock_scraper_class = self.linkedin_scraper_patcher.start()
        self.mock_scraper = MagicMock()
        self.mock_scraper_class.return_value = self.mock_scraper

        # Mock Config
        self.config_patcher = patch('services.scraper_service.Config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.DEFAULT_SEARCH_TERMS = ['Python Developer', 'Data Scientist']
        self.mock_config.DEFAULT_LOCATIONS = ['Remote', 'New York']

        # Mock time and random to avoid real delays
        self.time_patcher = patch('services.scraper_service.time')
        self.mock_time = self.time_patcher.start()

        self.random_patcher = patch('services.scraper_service.random')
        self.mock_random = self.random_patcher.start()
        self.mock_random.uniform.return_value = 0.1  # Fast delay for testing

        # Mock logging
        self.logging_patcher = patch('services.scraper_service.logger')
        self.mock_logger = self.logging_patcher.start()

        # Create service instance
        self.scraper_service = ScraperService()

        # Reset the current_jobs set
        self.scraper_service.current_jobs = set()
        self.scraper_service.current_user_id = None
        self.scraper_service.callback = None

    def tearDown(self):
        """Clean up after each test method."""
        self.db_service_patcher.stop()
        self.linkedin_scraper_patcher.stop()
        self.config_patcher.stop()
        self.time_patcher.stop()
        self.random_patcher.stop()
        self.logging_patcher.stop()

    def test_initialize_scraper(self):
        """Test initialization of LinkedIn scraper."""
        # Verify scraper was initialized with correct parameters
        self.mock_scraper_class.assert_called_once()

        # Verify event handlers were set up - use ANY for the handler functions
        self.mock_scraper.on.assert_any_call(Events.DATA, ANY)
        self.mock_scraper.on.assert_any_call(Events.ERROR, ANY)
        self.mock_scraper.on.assert_any_call(Events.END, ANY)

    def test_handle_data_new_job(self):
        """Test handling data for a new job."""
        # Setup mocks
        self.scraper_service.current_user_id = 1
        self.mock_db_service.get_job_by_id.return_value = None  # Job doesn't exist

        # Create mock event data
        event_data = MagicMock(spec=EventData)
        event_data.job_id = 'job1'
        event_data.title = 'Data Scientist'
        event_data.company = 'Company A'
        event_data.location = 'Remote'
        event_data.description = 'Job description'
        event_data.link = 'http://example.com/job1'
        event_data.query_keyword = 'data scientist'

        # Setup callback
        mock_callback = MagicMock()
        self.scraper_service.callback = mock_callback

        # Call the method
        self.scraper_service._handle_data(event_data)

        # Assertions
        self.assertIn('job1', self.scraper_service.current_jobs)

        # Verify job was added to database
        self.mock_db_service.add_job_listing.assert_called_once()
        args = self.mock_db_service.add_job_listing.call_args[0][0]
        self.assertEqual(args['job_id'], 'job1')
        self.assertEqual(args['title'], 'Data Scientist')

        # Verify job states were added
        self.mock_db_service.add_job_state.assert_any_call('job1', 1, JobStates.STATE_NEW_SCRAPED)
        self.mock_db_service.add_job_state.assert_any_call('job1', 1, JobStates.STATE_QUEUED_FOR_ANALYSIS)

        # Verify callback was called
        mock_callback.assert_called_once_with('job_found', args)

    def test_handle_data_existing_job_new_user(self):
        """Test handling data for an existing job but new to the user."""
        # Setup mocks
        self.scraper_service.current_user_id = 1

        # Job exists but user hasn't seen it
        self.mock_db_service.get_job_by_id.return_value = {'job_id': 'job1'}
        self.mock_db_service.get_current_job_state.return_value = None

        # Create mock event data
        event_data = MagicMock(spec=EventData)
        event_data.job_id = 'job1'
        event_data.title = 'Data Scientist'
        event_data.company = 'Company A'
        event_data.location = 'Remote'
        event_data.description = 'Job description'
        event_data.link = 'http://example.com/job1'
        event_data.query_keyword = 'data scientist'

        # Call the method
        self.scraper_service._handle_data(event_data)

        # Assertions
        self.assertIn('job1', self.scraper_service.current_jobs)

        # Verify job was not added again
        self.mock_db_service.add_job_listing.assert_not_called()

        # Verify job states were added for the user
        self.mock_db_service.add_job_state.assert_any_call('job1', 1, JobStates.STATE_NEW_SCRAPED)
        self.mock_db_service.add_job_state.assert_any_call('job1', 1, JobStates.STATE_QUEUED_FOR_ANALYSIS)

    def test_handle_data_existing_job_existing_user(self):
        """Test handling data for a job the user has already processed."""
        # Setup mocks
        self.scraper_service.current_user_id = 1

        # Job exists and user has already seen it
        self.mock_db_service.get_job_by_id.return_value = {'job_id': 'job1'}
        self.mock_db_service.get_current_job_state.return_value = {'state': 'viewed'}

        # Create mock event data
        event_data = MagicMock(spec=EventData)
        event_data.job_id = 'job1'
        event_data.title = 'Data Scientist'

        # Call the method
        self.scraper_service._handle_data(event_data)

        # Assertions
        self.assertIn('job1', self.scraper_service.current_jobs)

        # Verify no state changes
        self.mock_db_service.add_job_state.assert_not_called()

    def test_handle_data_duplicate_in_run(self):
        """Test handling a job that was already found in the current run."""
        # Setup mocks
        self.scraper_service.current_user_id = 1

        # Add job to current_jobs to simulate it was already processed
        self.scraper_service.current_jobs.add('job1')

        # Create mock event data
        event_data = MagicMock(spec=EventData)
        event_data.job_id = 'job1'

        # Call the method
        self.scraper_service._handle_data(event_data)

        # Verify no database calls were made
        self.mock_db_service.get_job_by_id.assert_not_called()
        self.mock_db_service.add_job_listing.assert_not_called()
        self.mock_db_service.add_job_state.assert_not_called()

    def test_handle_data_no_user_id(self):
        """Test handling data when no user ID is set."""
        # Don't set current_user_id
        self.scraper_service.current_user_id = None

        # Create mock event data
        event_data = MagicMock(spec=EventData)
        event_data.job_id = 'job1'

        # Call the method
        self.scraper_service._handle_data(event_data)

        # Verify warning was logged
        self.mock_logger.warning.assert_called_once()

        # Verify no database calls were made
        self.mock_db_service.get_job_by_id.assert_not_called()
        self.mock_db_service.add_job_listing.assert_not_called()

    def test_handle_error(self):
        """Test handling scraper errors."""
        # Setup callback
        mock_callback = MagicMock()
        self.scraper_service.callback = mock_callback

        # Call the method
        error = Exception("Scraper error")
        self.scraper_service._handle_error(error)

        # Verify error was logged
        self.mock_logger.error.assert_called_once()

        # Verify callback was called
        mock_callback.assert_called_once_with('error', {'error': 'Scraper error'})

    def test_handle_end(self):
        """Test handling end of scraping session."""
        # Setup data
        self.scraper_service.current_jobs.add('job1')
        self.scraper_service.current_jobs.add('job2')

        # Setup callback
        mock_callback = MagicMock()
        self.scraper_service.callback = mock_callback

        # Call the method
        self.scraper_service._handle_end()

        # Verify info was logged
        self.mock_logger.info.assert_called_once()

        # Verify callback was called
        mock_callback.assert_called_once_with('end', {'jobs_found': 2})

        # Verify current_jobs was cleared
        self.assertEqual(len(self.scraper_service.current_jobs), 0)

    def test_map_experience_level(self):
        """Test mapping experience level strings to LinkedIn filters."""
        # Call the method with different levels
        entry = self.scraper_service._map_experience_level('Entry level')
        associate = self.scraper_service._map_experience_level('Associate')
        mid_senior = self.scraper_service._map_experience_level('Mid-Senior level')
        director = self.scraper_service._map_experience_level('Director')
        executive = self.scraper_service._map_experience_level('Executive')
        internship = self.scraper_service._map_experience_level('Internship')
        unknown = self.scraper_service._map_experience_level('Unknown level')

        # Assertions
        self.assertEqual(entry, ExperienceLevelFilters.ENTRY_LEVEL)
        self.assertEqual(associate, ExperienceLevelFilters.ASSOCIATE)
        self.assertEqual(mid_senior, ExperienceLevelFilters.MID_SENIOR)
        self.assertEqual(director, ExperienceLevelFilters.DIRECTOR)
        self.assertEqual(executive, ExperienceLevelFilters.EXECUTIVE)
        self.assertEqual(internship, ExperienceLevelFilters.INTERNSHIP)
        self.assertEqual(unknown, ExperienceLevelFilters.MID_SENIOR)  # Default

    @patch('services.scraper_service.PreferenceService')
    @patch('services.scraper_service.Query')
    def test_scrape_jobs(self, mock_query_class, mock_pref_service_class):
        """Test scraping jobs based on user preferences."""
        # Setup mocks
        mock_pref_service = MagicMock()
        mock_pref_service_class.return_value = mock_pref_service

        # Setup preferences
        mock_prefs = {
            'job_titles': ['Data Scientist', 'Machine Learning Engineer'],
            'locations': ['Remote', 'New York'],
            'experience_levels': ['Entry level', 'Mid-Senior level'],
            'remote_preference': True
        }
        mock_pref_service.get_preferences_by_category.return_value = mock_prefs

        # Setup Query mocks - we'll need 4 of them (2 titles * 2 locations)
        mock_query_instances = [MagicMock() for _ in range(4)]
        mock_query_class.side_effect = mock_query_instances

        # Mock callback
        mock_callback = MagicMock()

        # Call the method
        result = self.scraper_service.scrape_jobs(1, mock_callback)

        # Assertions
        self.assertEqual(result['status'], 'success')
        self.assertEqual(result['queries_executed'], 4)

        # Verify queries were created and run
        self.assertEqual(mock_query_class.call_count, 4)
        self.assertEqual(self.mock_scraper.run.call_count, 4)

        # Verify callback was called
        mock_callback.assert_any_call('start', {'queries': 4})

        # Verify user_id and callback were set
        self.assertEqual(self.scraper_service.current_user_id, 1)
        self.assertEqual(self.scraper_service.callback, mock_callback)

        # Verify last_run was updated
        self.mock_db_service.update_last_run.assert_called_once_with(1)

        # Verify time.sleep was called between queries
        self.assertEqual(self.mock_time.sleep.call_count, 4)

    @patch('services.scraper_service.PreferenceService')
    def test_scrape_jobs_error(self, mock_pref_service_class):
        """Test handling errors during job scraping."""
        # Setup mocks
        mock_pref_service = MagicMock()
        mock_pref_service_class.return_value = mock_pref_service

        # Setup preferences
        mock_prefs = {
            'job_titles': ['Data Scientist'],
            'locations': ['Remote'],
            'experience_levels': ['Entry level'],
            'remote_preference': True
        }
        mock_pref_service.get_preferences_by_category.return_value = mock_prefs

        # Make scraper.run raise an exception
        self.mock_scraper.run.side_effect = Exception("Scraper error")

        # Mock callback
        mock_callback = MagicMock()

        # Call the method
        result = self.scraper_service.scrape_jobs(1, mock_callback)

        # Assertions
        self.assertEqual(result['status'], 'error')
        self.assertIn('error', result)

        # Verify callback was called with error
        mock_callback.assert_any_call('error', {'error': 'Scraper error'})

        # Verify last_run was still updated despite error
        self.mock_db_service.update_last_run.assert_called_once_with(1)

    @patch('services.scraper_service.PreferenceService')
    def test_scrape_jobs_no_limit(self, mock_pref_service_class):
        """Test scraping jobs without limit."""
        # Setup mocks
        mock_pref_service = MagicMock()
        mock_pref_service_class.return_value = mock_pref_service

        # Setup preferences
        mock_prefs = {
            'job_titles': ['Data Scientist'],
            'locations': ['Remote'],
            'experience_levels': ['Entry level'],
            'remote_preference': True
        }
        mock_tech_prefs = {
            'chrome_executable_path': None,
            'chrome_binary_location': None
        }

        # Side effect to return different preferences based on category
        def get_preferences_side_effect(user_id, category):
            if category == 'search':
                return mock_prefs
            elif category == 'technical':
                return mock_tech_prefs
            return {}

        mock_pref_service.get_preferences_by_category.side_effect = get_preferences_side_effect

        # Call the method without job limit
        result = self.scraper_service.scrape_jobs(1)

        # Assertions
        self.assertEqual(result['status'], 'success')

        # Verify scraper was run
        self.mock_scraper.run.assert_called_once()

        # Verify the query had a higher default limit
        query = self.mock_scraper.run.call_args[0][0]
        self.assertEqual(query.options.limit, 25)  # Default limit should be 25 now



if __name__ == '__main__':
    unittest.main()