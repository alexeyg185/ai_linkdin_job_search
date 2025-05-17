import unittest
import pytest
from unittest.mock import patch, MagicMock, call
import json
import datetime

from services.preference_service import PreferenceService
from database.models import UserPreferences
from tests.mock_db_manager import MockDatabaseManager


class TestPreferenceService(unittest.TestCase):
    """Test cases for the PreferenceService class."""

    def setUp(self):
        """Set up the test environment before each test method."""
        # Create the mock database manager
        self.mock_db_manager = MockDatabaseManager()

        # Patch the DatabaseManager to return our mock
        self.db_manager_patcher = patch('services.preference_service.DatabaseManager')
        self.mock_db_manager_class = self.db_manager_patcher.start()
        self.mock_db_manager_class.return_value = self.mock_db_manager

        # Create PreferenceService instance with mocked dependencies
        self.pref_service = PreferenceService()

        # Patch Config to use test values
        self.config_patcher = patch('services.preference_service.Config')
        self.mock_config = self.config_patcher.start()
        self.mock_config.DEFAULT_SEARCH_TERMS = ['AI Engineer', 'Machine Learning Engineer', 'Data Scientist']
        self.mock_config.DEFAULT_LOCATIONS = ['Remote', 'New York, NY']
        self.mock_config.RELEVANCE_THRESHOLD = 0.7
        self.mock_config.DEFAULT_SCHEDULE_TYPE = 'daily'
        self.mock_config.DEFAULT_EXECUTION_TIME = '08:00'

    def tearDown(self):
        """Clean up after each test method."""
        self.db_manager_patcher.stop()
        self.config_patcher.stop()

    def test_setup_default_preferences(self):
        """Test setting up default preferences for a new user."""
        # Mock execute_write
        self.mock_db_manager.execute_write.return_value = 1

        # Call the method
        self.pref_service.setup_default_preferences(1)

        # Verify execute_write was called multiple times (once for each default preference)
        self.assertTrue(self.mock_db_manager.execute_write.call_count > 0)

        # Verify some specific preferences were set
        calls = self.mock_db_manager.execute_write.call_args_list

        # Helper to check if a specific preference was set
        def has_preference_call(category, name):
            for call_obj in calls:
                args, _ = call_obj
                query, params = args
                if category in str(params) and name in str(params):
                    return True
            return False

        # Check some specific preferences
        self.assertTrue(has_preference_call('search', 'job_titles'))
        self.assertTrue(has_preference_call('analysis', 'relevance_threshold'))
        self.assertTrue(has_preference_call('scheduling', 'schedule_type'))

    def test_get_preference(self):
        """Test getting a specific preference."""
        # Setup mock for existing preference
        # Use UserPreferences.json_serialize instead of json.dumps directly
        serialized_value = UserPreferences.json_serialize(['Python', 'SQL'])
        mock_result = {'value': serialized_value}
        self.mock_db_manager.get_one.return_value = mock_result

        # Call the method
        result = self.pref_service.get_preference(1, 'analysis', 'required_skills')

        # Assertions
        self.assertEqual(result, ['Python', 'SQL'])
        self.mock_db_manager.get_one.assert_called_once()

        # Test with non-existent preference
        self.mock_db_manager.get_one.reset_mock()
        self.mock_db_manager.get_one.return_value = None
        default_value = ['JavaScript']
        result = self.pref_service.get_preference(1, 'analysis', 'missing_skill', default_value)
        self.assertEqual(result, default_value)

    def test_set_preference(self):
        """Test setting a preference."""
        self.mock_db_manager.reset_all_mocks()
        # Mock execute_write
        self.mock_db_manager.execute_write.return_value = 1

        # Call the method
        skills = ['Python', 'TensorFlow', 'Data Science']
        self.pref_service.set_preference(1, 'analysis', 'required_skills', skills)

        # Verify execute_write was called with correct parameters
        self.mock_db_manager.execute_write.assert_called_once()

        # Check that the value was JSON serialized properly
        args = self.mock_db_manager.execute_write.call_args[0]
        query, params = args

        # params should be (user_id, category, name, json_value, timestamp)
        self.assertEqual(params[0], 1)
        self.assertEqual(params[1], 'analysis')
        self.assertEqual(params[2], 'required_skills')

        # Check the serialized JSON value - use UserPreferences.json_deserialize
        json_value = params[3]
        deserialized_value = UserPreferences.json_deserialize(json_value)
        self.assertEqual(deserialized_value, skills)

    def test_get_preferences_by_category(self):
        """Test getting all preferences in a category."""
        # We need to patch the DEFAULT_PREFERENCES to match our test data
        original_defaults = self.pref_service.DEFAULT_PREFERENCES['analysis'].copy()
        self.pref_service.DEFAULT_PREFERENCES['analysis']['required_skills'] = ['Python', 'SQL']
        self.pref_service.DEFAULT_PREFERENCES['analysis']['preferred_skills'] = ['TensorFlow', 'PyTorch']

        # Setup mock for query results
        mock_results = [
            {'name': 'required_skills', 'value': UserPreferences.json_serialize(['Python', 'SQL'])},
            {'name': 'preferred_skills', 'value': UserPreferences.json_serialize(['TensorFlow', 'PyTorch'])}
        ]
        self.mock_db_manager.execute_query.return_value = mock_results

        # Call the method
        result = self.pref_service.get_preferences_by_category(1, 'analysis')

        # Assertions
        self.assertEqual(result['required_skills'], ['Python', 'SQL'])
        self.assertEqual(result['preferred_skills'], ['TensorFlow', 'PyTorch'])

        # Restore original defaults
        self.pref_service.DEFAULT_PREFERENCES['analysis'] = original_defaults

    def test_get_all_preferences(self):
        """Test getting all preferences for a user."""
        # Override default preferences for the test
        original_search_defaults = self.pref_service.DEFAULT_PREFERENCES['search'].copy()
        original_analysis_defaults = self.pref_service.DEFAULT_PREFERENCES['analysis'].copy()

        # Set the specific defaults we want to test with
        self.pref_service.DEFAULT_PREFERENCES['search']['job_titles'] = ['Data Scientist']
        self.pref_service.DEFAULT_PREFERENCES['analysis']['required_skills'] = ['Python']

        # Setup mock for query results
        mock_results = [
            {'category': 'search', 'name': 'job_titles', 'value': UserPreferences.json_serialize(['Data Scientist'])},
            {'category': 'analysis', 'name': 'required_skills', 'value': UserPreferences.json_serialize(['Python'])}
        ]
        self.mock_db_manager.execute_query.return_value = mock_results

        # Call the method
        result = self.pref_service.get_all_preferences(1)

        # Assertions
        self.assertEqual(result['search']['job_titles'], ['Data Scientist'])
        self.assertEqual(result['analysis']['required_skills'], ['Python'])

        # Restore original defaults
        self.pref_service.DEFAULT_PREFERENCES['search'] = original_search_defaults
        self.pref_service.DEFAULT_PREFERENCES['analysis'] = original_analysis_defaults

    def test_update_preference_category(self):
        """Test updating multiple preferences in a category."""
        # Mock set_preference
        with patch.object(self.pref_service, 'set_preference') as mock_set:
            # Call the method
            values = {
                'required_skills': ['Python', 'SQL'],
                'preferred_skills': ['TensorFlow', 'PyTorch'],
                'relevance_threshold': 0.8
            }
            self.pref_service.update_preference_category(1, 'analysis', values)

            # Verify set_preference was called for each value
            self.assertEqual(mock_set.call_count, 3)

            # Verify specific calls
            expected_calls = [
                call(1, 'analysis', 'required_skills', ['Python', 'SQL']),
                call(1, 'analysis', 'preferred_skills', ['TensorFlow', 'PyTorch']),
                call(1, 'analysis', 'relevance_threshold', 0.8)
            ]
            mock_set.assert_has_calls(expected_calls, any_order=True)

    def test_delete_preference(self):
        """Test deleting a preference."""
        # Setup mock
        self.mock_db_manager.execute_write.return_value = 1

        # Call the method
        result = self.pref_service.delete_preference(1, 'analysis', 'required_skills')

        # Assertions
        self.assertTrue(result)  # Use assertTrue for simpler assertion
        self.mock_db_manager.execute_write.assert_called_once()

        # Test deleting non-existent preference
        self.mock_db_manager.execute_write.reset_mock()
        self.mock_db_manager.execute_write.return_value = 0  # SQLite returns 0 for no affected rows
        result = self.pref_service.delete_preference(1, 'analysis', 'non_existent')
        self.assertFalse(result)  # Use assertFalse for simpler assertion

    def test_delete_category(self):
        """Test deleting all preferences in a category."""
        # Setup mock
        self.mock_db_manager.execute_write.return_value = 1

        # Call the method
        result = self.pref_service.delete_category(1, 'analysis')

        # Assertions
        self.assertTrue(result)  # Use assertTrue for simpler assertion
        self.mock_db_manager.execute_write.assert_called_once()

        # Test deleting non-existent category
        self.mock_db_manager.execute_write.reset_mock()
        self.mock_db_manager.execute_write.return_value = 0  # SQLite returns 0 for no affected rows
        result = self.pref_service.delete_category(1, 'non_existent')
        self.assertFalse(result)  # Use assertFalse for simpler assertion

    def test_reset_category_to_defaults(self):
        """Test resetting a category to default values."""
        # Setup mocks
        self.mock_db_manager.execute_write.return_value = 1

        # Mock delete_category and set_preference
        with patch.object(self.pref_service, 'delete_category') as mock_delete:
            with patch.object(self.pref_service, 'set_preference') as mock_set:
                # Call the method
                self.pref_service.reset_category_to_defaults(1, 'analysis')

                # Verify delete_category was called
                mock_delete.assert_called_once_with(1, 'analysis')

                # Verify set_preference was called for each default preference
                default_count = len(self.pref_service.DEFAULT_PREFERENCES['analysis'])
                self.assertEqual(mock_set.call_count, default_count)

    def test_reset_all_to_defaults(self):
        """Test resetting all preferences to default values."""
        # Set up mocks
        self.mock_db_manager.execute_write.return_value = 1

        # Mock setup_default_preferences to avoid calling the actual method
        with patch.object(self.pref_service, 'setup_default_preferences') as mock_setup:
            # Call the method
            self.pref_service.reset_all_to_defaults(1)

            # Verify delete query was executed
            self.mock_db_manager.execute_write.assert_called_once()

            # Verify setup_default_preferences was called
            mock_setup.assert_called_once_with(1)