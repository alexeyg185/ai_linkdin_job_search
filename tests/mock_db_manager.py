"""
Mock database manager for testing.
This module provides a mock implementation of the DatabaseManager for unit tests.
"""

from unittest.mock import MagicMock
from typing import Any, Dict, List, Optional, Tuple, Union, Self
from contextlib import contextmanager


class MockDatabaseManager:
    """
    Mock implementation of DatabaseManager for testing.
    This class mocks all methods of DatabaseManager to avoid actual database operations.
    """
    _instance = None

    def __new__(cls) -> Self:
        """Create singleton instance"""
        if cls._instance is None:
            cls._instance = super(MockDatabaseManager, cls).__new__(cls)
            cls._instance._initialize()
        return cls._instance

    def _initialize(self) -> None:
        """Initialize mock database manager"""
        self.get_connection = MagicMock()
        self.execute_query = MagicMock()
        self.execute_write = MagicMock()
        self.execute_many = MagicMock()
        self.get_one = MagicMock()
        self.table_exists = MagicMock()
        self.close_all = MagicMock()

        # Default return values
        self.get_one.return_value = None
        self.execute_query.return_value = []
        self.execute_write.return_value = 1
        self.table_exists.return_value = True

        # Add connection context manager
        self.transaction = MagicMock()

    @contextmanager
    def get_connection_context(self):
        """Context manager for mock connection"""
        yield MagicMock()

    def reset_all_mocks(self) -> None:
        """Reset all mocks to their initial state"""
        self.get_connection.reset_mock()
        self.execute_query.reset_mock()
        self.execute_write.reset_mock()
        self.execute_many.reset_mock()
        self.get_one.reset_mock()
        self.table_exists.reset_mock()
        self.close_all.reset_mock()
        self.transaction.reset_mock()

        # Reset default return values
        self.get_one.return_value = None
        self.execute_query.return_value = []
        self.execute_write.return_value = 1
        self.table_exists.return_value = True