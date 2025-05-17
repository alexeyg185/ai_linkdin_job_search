"""
Preference service module for managing user preferences.
This module provides a service for managing user preferences across all aspects of the system.
"""

import datetime
from typing import Dict, Any

from config import Config
from database.db_manager import DatabaseManager
from database.models import UserPreferences


class PreferenceService:
    """
    Service for managing user preferences across all aspects of the system.
    """

    # Preference categories
    CATEGORY_SEARCH = "search"
    CATEGORY_ANALYSIS = "analysis"
    CATEGORY_SCHEDULING = "scheduling"
    CATEGORY_UI = "ui"
    CATEGORY_TECHNICAL = "technical"  # New category for technical settings

    # Default preferences by category
    DEFAULT_PREFERENCES = {
        CATEGORY_SEARCH: {
            "job_titles": Config.DEFAULT_SEARCH_TERMS,
            "locations": Config.DEFAULT_LOCATIONS,
            "experience_levels": ["Entry level", "Associate", "Mid-Senior level"],
            "remote_preference": True
        },
        CATEGORY_ANALYSIS: {
            "relevant_title_patterns": ["AI", "Machine Learning", "ML", "Data Scientist", "NLP", "Computer Vision"],
            "required_skills": ["Python", "Machine Learning"],
            "preferred_skills": ["TensorFlow", "PyTorch", "NLP", "Computer Vision"],
            "relevance_threshold": Config.RELEVANCE_THRESHOLD,
            "title_match_strictness": 0.8
        },
        CATEGORY_SCHEDULING: {
            "schedule_type": Config.DEFAULT_SCHEDULE_TYPE,
            "execution_time": Config.DEFAULT_EXECUTION_TIME,
            "notifications_enabled": True
        },
        CATEGORY_UI: {
            "dashboard_layout": "default",
            "default_filters": {"state": "relevant"},
            "mobile_view": "compact"
        },
        CATEGORY_TECHNICAL: {  # New default preferences for technical settings
            "chrome_executable_path": None,
            "chrome_binary_location": None
        }
    }

    def __init__(self):
        """Initialize the preference service with database connection"""
        self.db_manager = DatabaseManager()

    def setup_default_preferences(self, user_id: int) -> None:
        """
        Set up default preferences for a new user.

        Args:
            user_id: The user's ID
        """
        for category, prefs in self.DEFAULT_PREFERENCES.items():
            for name, value in prefs.items():
                self.set_preference(user_id, category, name, value)

    def get_preference(self, user_id: int, category: str, name: str, default: Any = None) -> Any:
        """
        Get a user preference.

        Args:
            user_id: The user's ID
            category: Preference category (search, analysis, scheduling, ui)
            name: Preference name
            default: Default value if preference doesn't exist

        Returns:
            value: The preference value, or default if not found
        """
        query = f"""
        SELECT value
        FROM {UserPreferences.TABLE_NAME}
        WHERE user_id = ? AND category = ? AND name = ?
        """
        result = self.db_manager.get_one(query, (user_id, category, name))

        if result:
            return UserPreferences.json_deserialize(result['value'])
        return default

    def set_preference(self, user_id: int, category: str, name: str, value: Any) -> None:
        """
        Set a user preference.

        Args:
            user_id: The user's ID
            category: Preference category (search, analysis, scheduling, ui)
            name: Preference name
            value: Preference value (will be JSON serialized)
        """
        json_value = UserPreferences.json_serialize(value)
        now = datetime.datetime.now()

        # Use INSERT OR REPLACE to handle both new and existing preferences
        query = f"""
        INSERT OR REPLACE INTO {UserPreferences.TABLE_NAME}
        (user_id, category, name, value, updated_at)
        VALUES (?, ?, ?, ?, ?)
        """
        self.db_manager.execute_write(query, (user_id, category, name, json_value, now))

    def get_preferences_by_category(self, user_id: int, category: str) -> Dict[str, Any]:
        """
        Get all preferences for a user within a category.

        Args:
            user_id: The user's ID
            category: Preference category (search, analysis, scheduling, ui)

        Returns:
            preferences: Dictionary of preference name to value
        """
        query = f"""
        SELECT name, value
        FROM {UserPreferences.TABLE_NAME}
        WHERE user_id = ? AND category = ?
        """
        results = self.db_manager.execute_query(query, (user_id, category))

        preferences = {}
        for pref in results:
            preferences[pref['name']] = UserPreferences.json_deserialize(pref['value'])

        # Fill in any missing preferences with defaults
        if category in self.DEFAULT_PREFERENCES:
            for name, default_value in self.DEFAULT_PREFERENCES[category].items():
                if name not in preferences:
                    preferences[name] = default_value

        return preferences

    def get_all_preferences(self, user_id: int) -> Dict[str, Dict[str, Any]]:
        """
        Get all preferences for a user, organized by category.

        Args:
            user_id: The user's ID

        Returns:
            preferences: Dictionary of category to preference dictionary
        """
        query = f"""
        SELECT category, name, value
        FROM {UserPreferences.TABLE_NAME}
        WHERE user_id = ?
        """
        results = self.db_manager.execute_query(query, (user_id,))

        preferences = {}
        for pref in results:
            category = pref['category']
            name = pref['name']
            value = UserPreferences.json_deserialize(pref['value'])

            if category not in preferences:
                preferences[category] = {}

            preferences[category][name] = value

        # Fill in any missing categories with defaults
        for category, default_prefs in self.DEFAULT_PREFERENCES.items():
            if category not in preferences:
                preferences[category] = {}

            # Fill in any missing preferences in this category
            for name, default_value in default_prefs.items():
                if name not in preferences[category]:
                    preferences[category][name] = default_value

        return preferences

    def update_preference_category(self, user_id: int, category: str,
                                   values: Dict[str, Any]) -> None:
        """
        Update multiple preferences within a category at once.

        Args:
            user_id: The user's ID
            category: Preference category (search, analysis, scheduling, ui)
            values: Dictionary of preference name to value
        """
        for name, value in values.items():
            self.set_preference(user_id, category, name, value)

    def delete_preference(self, user_id: int, category: str, name: str) -> bool:
        """
        Delete a user preference.

        Args:
            user_id: The user's ID
            category: Preference category
            name: Preference name

        Returns:
            success: True if preference was deleted, False if not found
        """
        query = f"""
        DELETE FROM {UserPreferences.TABLE_NAME}
        WHERE user_id = ? AND category = ? AND name = ?
        """
        result = self.db_manager.execute_write(query, (user_id, category, name))
        # SQLite returns the number of rows affected, which is > 0 if deletion occurred
        return result > 0

    def delete_category(self, user_id: int, category: str) -> bool:
        """
        Delete all preferences in a category for a user.

        Args:
            user_id: The user's ID
            category: Preference category

        Returns:
            success: True if preferences were deleted, False if none found
        """
        query = f"""
        DELETE FROM {UserPreferences.TABLE_NAME}
        WHERE user_id = ? AND category = ?
        """
        result = self.db_manager.execute_write(query, (user_id, category))
        # SQLite returns the number of rows affected, which is > 0 if deletion occurred
        return result > 0

    def reset_category_to_defaults(self, user_id: int, category: str) -> None:
        """
        Reset all preferences in a category to their default values.

        Args:
            user_id: The user's ID
            category: Preference category
        """
        # Delete existing preferences
        self.delete_category(user_id, category)

        # Set default preferences
        if category in self.DEFAULT_PREFERENCES:
            for name, value in self.DEFAULT_PREFERENCES[category].items():
                self.set_preference(user_id, category, name, value)

    def reset_all_to_defaults(self, user_id: int) -> None:
        """
        Reset all preferences for a user to their default values.

        Args:
            user_id: The user's ID
        """
        # Delete all existing preferences
        query = f"""
        DELETE FROM {UserPreferences.TABLE_NAME}
        WHERE user_id = ?
        """
        self.db_manager.execute_write(query, (user_id,))

        # Set up default preferences
        self.setup_default_preferences(user_id)