import bcrypt
import datetime
from typing import Dict, Any, Optional, Tuple

from database.db_manager import DatabaseManager
from database.models import Users
from services.preference_service import PreferenceService


class UserService:
    """
    Service for user management, authentication, and registration.
    """

    def __init__(self):
        """Initialize the user service with database connection"""
        self.db_manager = DatabaseManager()
        self.preference_service = PreferenceService()

    def create_user(self, username: str, password: str, email: str = None) -> int:
        """
        Create a new user with the given credentials.

        Args:
            username: Unique username for the user
            password: Plain text password (will be hashed)
            email: Optional email address

        Returns:
            user_id: The ID of the created user

        Raises:
            ValueError: If username already exists
        """
        # Check if username already exists
        existing_user = self.get_user_by_username(username)
        if existing_user:
            raise ValueError(f"Username '{username}' already exists")

        # Hash the password
        password_hash = self._hash_password(password)

        # Insert the user into the database
        query = f"""
        INSERT INTO {Users.TABLE_NAME} (username, password_hash, email, created_at)
        VALUES (?, ?, ?, ?)
        """
        now = datetime.datetime.now()
        user_id = self.db_manager.execute_write(
            query,
            (username, password_hash, email, now)
        )

        # Set up default preferences for the new user
        self.preference_service.setup_default_preferences(user_id)

        return user_id

    def authenticate(self, username: str, password: str) -> Optional[Dict[str, Any]]:
        """
        Authenticate a user with the given credentials.

        Args:
            username: User's username
            password: Plain text password to verify

        Returns:
            user: User record if authentication succeeds, None otherwise
        """
        # Get the user by username
        user = self.get_user_by_username(username)
        if not user:
            return None

        # Verify the password
        if not self._verify_password(password, user['password_hash']):
            return None

        # Update last login time
        self._update_last_login(user['user_id'])

        return user

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a user by their ID.

        Args:
            user_id: The user's ID

        Returns:
            user: User record if found, None otherwise
        """
        query = f"""
        SELECT user_id, username, email, created_at, last_login
        FROM {Users.TABLE_NAME}
        WHERE user_id = ?
        """
        return self.db_manager.get_one(query, (user_id,))

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get a user by their username.

        Args:
            username: The user's username

        Returns:
            user: User record if found, None otherwise
        """
        query = f"""
        SELECT user_id, username, password_hash, email, created_at, last_login
        FROM {Users.TABLE_NAME}
        WHERE username = ?
        """
        return self.db_manager.get_one(query, (username,))

    def _update_last_login(self, user_id: int) -> None:
        """
        Update a user's last login time.

        Args:
            user_id: The user's ID
        """
        query = f"""
        UPDATE {Users.TABLE_NAME}
        SET last_login = ?
        WHERE user_id = ?
        """
        now = datetime.datetime.now()
        self.db_manager.execute_write(query, (now, user_id))

    def _hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            password_hash: Hashed password
        """
        password_bytes = password.encode('utf-8')
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password_bytes, salt)
        return hashed.decode('utf-8')

    def _verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against a hash.

        Args:
            password: Plain text password
            password_hash: Hashed password

        Returns:
            is_valid: True if the password matches the hash, False otherwise
        """
        password_bytes = password.encode('utf-8')
        hash_bytes = password_hash.encode('utf-8')
        return bcrypt.checkpw(password_bytes, hash_bytes)

    def change_password(self, user_id: int, current_password: str, new_password: str) -> bool:
        """
        Change a user's password.

        Args:
            user_id: The user's ID
            current_password: Current plain text password
            new_password: New plain text password

        Returns:
            success: True if password was changed, False otherwise

        Raises:
            ValueError: If current password is incorrect
        """
        # Get the user
        user = self.get_user_by_id(user_id)
        if not user:
            return False

        # Get current password hash
        password_query = f"SELECT password_hash FROM {Users.TABLE_NAME} WHERE user_id = ?"
        password_result = self.db_manager.get_one(password_query, (user_id,))

        # This check is needed to handle potential database inconsistencies
        if not password_result:
            return False

        current_hash = password_result['password_hash']

        # Verify current password
        if not self._verify_password(current_password, current_hash):
            raise ValueError("Current password is incorrect")

        # Hash the new password
        new_hash = self._hash_password(new_password)

        # Update the password
        query = f"""
        UPDATE {Users.TABLE_NAME}
        SET password_hash = ?
        WHERE user_id = ?
        """
        self.db_manager.execute_write(query, (new_hash, user_id))

        return True

    def get_all_users(self) -> list:
        """
        Get all users in the system.

        Returns:
            users: List of user records
        """
        query = f"""
        SELECT user_id, username, email, created_at, last_login
        FROM {Users.TABLE_NAME}
        ORDER BY username
        """
        return self.db_manager.execute_query(query)