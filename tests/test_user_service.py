import unittest
from unittest.mock import patch, MagicMock, call
import datetime
import bcrypt

from services.user_service import UserService
from tests.mock_db_manager import MockDatabaseManager


class TestUserService(unittest.TestCase):
    """Test cases for the UserService class."""

    def setUp(self):
        """Set up the test environment before each test method."""
        # Create a mock for DatabaseManager
        self.db_manager_patcher = patch('services.user_service.DatabaseManager')
        self.mock_db_manager_class = self.db_manager_patcher.start()

        # Mock instance of DatabaseManager
        self.mock_db_manager = MockDatabaseManager()
        self.mock_db_manager_class.return_value = self.mock_db_manager

        # Create a mock for PreferenceService
        self.pref_service_patcher = patch('services.user_service.PreferenceService')
        self.mock_pref_service_class = self.pref_service_patcher.start()

        # Mock instance of PreferenceService
        self.mock_pref_service = MagicMock()
        self.mock_pref_service_class.return_value = self.mock_pref_service

        # Create UserService instance with mocked dependencies
        self.user_service = UserService()

    def tearDown(self):
        """Clean up after each test method."""
        self.db_manager_patcher.stop()
        self.pref_service_patcher.stop()

    @patch('services.user_service.bcrypt')
    def test_create_user(self, mock_bcrypt):
        """Test creating a new user."""
        # Setup mocks
        self.mock_db_manager.get_one.return_value = None  # User doesn't exist
        self.mock_db_manager.execute_write.return_value = 1  # User ID

        # Mock bcrypt password hashing
        mock_bcrypt.gensalt.return_value = b'fakesalt'
        mock_bcrypt.hashpw.return_value = b'fakehashedpassword'

        # Call the method
        result = self.user_service.create_user('testuser', 'password123', 'test@example.com')

        # Assertions
        self.assertEqual(result, 1)
        mock_bcrypt.hashpw.assert_called_once_with(b'password123', b'fakesalt')
        self.mock_db_manager.execute_write.assert_called_once()
        self.mock_pref_service.setup_default_preferences.assert_called_once_with(1)

        # Test with existing username
        self.mock_db_manager.get_one.return_value = {'user_id': 1}  # User exists
        with self.assertRaises(ValueError):
            self.user_service.create_user('testuser', 'password123')

    @patch('services.user_service.bcrypt')
    def test_authenticate(self, mock_bcrypt):
        """Test user authentication."""
        # Setup mocks for successful authentication
        mock_user = {
            'user_id': 1,
            'username': 'testuser',
            'password_hash': 'fakehashedpassword',
            'email': 'test@example.com'
        }
        self.mock_db_manager.get_one.return_value = mock_user

        # Mock bcrypt password verification (successful)
        mock_bcrypt.checkpw.return_value = True

        # Call the method
        result = self.user_service.authenticate('testuser', 'password123')

        # Assertions for successful authentication
        self.assertEqual(result['user_id'], 1)
        self.assertEqual(result['username'], 'testuser')
        mock_bcrypt.checkpw.assert_called_once()

        # Verify last login was updated
        self.mock_db_manager.execute_write.assert_called_once()

        # Test failed authentication - wrong password
        mock_bcrypt.checkpw.reset_mock()
        mock_bcrypt.checkpw.return_value = False
        result = self.user_service.authenticate('testuser', 'wrongpassword')
        self.assertIsNone(result)

        # Test failed authentication - user not found
        self.mock_db_manager.get_one.return_value = None
        result = self.user_service.authenticate('nonexistent', 'password123')
        self.assertIsNone(result)

    def test_get_user_by_id(self):
        """Test getting a user by ID."""
        # Setup mock
        mock_user = {
            'user_id': 1,
            'username': 'testuser',
            'email': 'test@example.com'
        }

        def mock_get_one_side_effect(query, params):
            if "SELECT user_id, username, email" in query and params[0] == 1:
                return mock_user
            return None

        self.mock_db_manager.get_one.side_effect = mock_get_one_side_effect

        # Call the method
        result = self.user_service.get_user_by_id(1)

        # Assertions
        self.assertEqual(result['username'], 'testuser')
        self.mock_db_manager.get_one.assert_called_once()

        # Test user not found
        self.mock_db_manager.get_one.return_value = None
        result = self.user_service.get_user_by_id(999)
        self.assertIsNone(result)

    def test_get_user_by_username(self):
        """Test getting a user by username."""
        # Setup mock
        mock_user = {
            'user_id': 1,
            'username': 'testuser',
            'password_hash': 'fakehashedpassword',
            'email': 'test@example.com'
        }
        self.mock_db_manager.get_one.return_value = mock_user

        # Call the method
        result = self.user_service.get_user_by_username('testuser')

        # Assertions
        self.assertEqual(result['user_id'], 1)
        self.assertEqual(result['email'], 'test@example.com')
        self.mock_db_manager.get_one.assert_called_once()

        # Test user not found
        self.mock_db_manager.get_one.return_value = None
        result = self.user_service.get_user_by_username('nonexistent')
        self.assertIsNone(result)

    def test_update_last_login(self):
        """Test updating a user's last login time."""
        # Call the method
        self.user_service._update_last_login(1)

        # Assertions
        self.mock_db_manager.execute_write.assert_called_once()

        # Verify the query parameters
        args = self.mock_db_manager.execute_write.call_args[0]
        query, params = args
        self.assertEqual(params[1], 1)  # user_id should be second parameter

    @patch('services.user_service.bcrypt')
    def test_hash_password(self, mock_bcrypt):
        """Test password hashing."""
        # Setup mocks
        mock_bcrypt.gensalt.return_value = b'fakesalt'
        mock_bcrypt.hashpw.return_value = b'fakehashedpassword'

        # Call the method
        result = self.user_service._hash_password('password123')

        # Assertions
        self.assertEqual(result, 'fakehashedpassword')
        mock_bcrypt.gensalt.assert_called_once()
        mock_bcrypt.hashpw.assert_called_once_with(b'password123', b'fakesalt')

    @patch('services.user_service.bcrypt')
    def test_verify_password(self, mock_bcrypt):
        """Test password verification."""
        # Setup mocks
        mock_bcrypt.checkpw.return_value = True

        # Call the method
        result = self.user_service._verify_password('password123', 'fakehashedpassword')

        # Assertions
        self.assertTrue(result)
        mock_bcrypt.checkpw.assert_called_once()

        # Test failed verification
        mock_bcrypt.checkpw.reset_mock()
        mock_bcrypt.checkpw.return_value = False
        result = self.user_service._verify_password('wrongpassword', 'fakehashedpassword')
        self.assertFalse(result)

    @patch('services.user_service.bcrypt')
    def test_change_password(self, mock_bcrypt):
        """Test changing a user's password."""
        # Test successful password change
        # Reset all mocks to ensure clean state
        self.mock_db_manager.reset_all_mocks()

        # Setup specific return values for each get_one call
        def get_one_side_effect(query, params):
            if "SELECT user_id, username" in query:
                return {'user_id': 1, 'username': 'testuser'}
            elif "SELECT password_hash" in query:
                return {'password_hash': 'currenthash'}
            return None

        self.mock_db_manager.get_one.side_effect = get_one_side_effect

        # Mock password verification (success)
        mock_bcrypt.checkpw.return_value = True

        # Mock password hashing
        mock_bcrypt.gensalt.return_value = b'newsalt'
        mock_bcrypt.hashpw.return_value = b'newhashedpassword'

        # Call the method
        result = self.user_service.change_password(1, 'currentpassword', 'newpassword')

        # Assertions
        self.assertTrue(result)
        mock_bcrypt.checkpw.assert_called_once()
        mock_bcrypt.hashpw.assert_called_once()
        self.mock_db_manager.execute_write.assert_called_once()

        # Test with incorrect current password
        # Reset mocks
        self.mock_db_manager.reset_all_mocks()
        mock_bcrypt.checkpw.reset_mock()
        mock_bcrypt.hashpw.reset_mock()

        # Setup return values again
        self.mock_db_manager.get_one.side_effect = get_one_side_effect

        # Mock failed password verification
        mock_bcrypt.checkpw.return_value = False

        with self.assertRaises(ValueError):
            self.user_service.change_password(1, 'wrongpassword', 'newpassword')

        # Test with non-existent user
        # Reset mocks
        self.mock_db_manager.reset_all_mocks()
        mock_bcrypt.reset_mock()

        # For non-existent user, first get_one call should return None
        # We need a new side effect function
        def nonexistent_user_side_effect(query, params):
            # First query for user by ID returns None
            if "SELECT user_id, username" in query:
                return None
            # Should never reach other queries, but just in case
            return None

        self.mock_db_manager.get_one.side_effect = nonexistent_user_side_effect

        # Call method
        result = self.user_service.change_password(999, 'currentpassword', 'newpassword')

        # Should return False for non-existent user
        self.assertFalse(result)

        # Should return False for non-existent user
        self.assertFalse(result)

    def test_get_all_users(self):
        """Test getting all users."""
        # Setup mock
        mock_users = [
            {'user_id': 1, 'username': 'user1', 'email': 'user1@example.com'},
            {'user_id': 2, 'username': 'user2', 'email': 'user2@example.com'}
        ]
        self.mock_db_manager.execute_query.return_value = mock_users

        # Call the method
        result = self.user_service.get_all_users()

        # Assertions
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['username'], 'user1')
        self.assertEqual(result[1]['username'], 'user2')
        self.mock_db_manager.execute_query.assert_called_once()


if __name__ == '__main__':
    unittest.main()