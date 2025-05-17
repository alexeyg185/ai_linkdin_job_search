import unittest
import os
import sqlite3
from unittest.mock import patch, MagicMock
import threading

from database.db_manager import DatabaseManager


class TestDatabaseManager(unittest.TestCase):
    """Test cases for the DatabaseManager class."""

    def setUp(self):
        """Set up the test environment before each test method."""
        # Create a mock configuration with in-memory database
        self.patcher = patch('database.db_manager.Config')
        self.mock_config = self.patcher.start()
        self.mock_config.DATABASE_PATH = ':memory:'

        # Clear the singleton instance before each test
        DatabaseManager._instance = None

    def tearDown(self):
        """Clean up after each test method."""
        self.patcher.stop()

        # Close any open connections
        if hasattr(self, 'db_manager') and self.db_manager:
            self.db_manager.close_all()

    def test_singleton_pattern(self):
        """Test that DatabaseManager implements the singleton pattern correctly."""
        db1 = DatabaseManager()
        db2 = DatabaseManager()
        self.assertIs(db1, db2, "DatabaseManager should return the same instance")

    def test_initialize(self):
        """Test that the database is initialized correctly."""
        # Mock the create_all_tables function
        with patch('database.db_manager.create_all_tables') as mock_create:
            db_manager = DatabaseManager()

            # Verify create_all_tables was called
            mock_create.assert_called_once()

            # Verify connection was created
            self.assertIsNotNone(db_manager.get_connection())

    def test_get_connection(self):
        """Test getting a connection from the pool."""
        db_manager = DatabaseManager()
        conn1 = db_manager.get_connection()

        # Test connection is a SQLite connection
        self.assertIsInstance(conn1, sqlite3.Connection)

        # Same thread should get same connection
        conn2 = db_manager.get_connection()
        self.assertIs(conn1, conn2)

    def test_transaction_commit(self):
        """Test transaction with successful commit."""
        db_manager = DatabaseManager()

        # Create a test table
        with db_manager.transaction() as conn:
            conn.execute("CREATE TABLE test (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test (value) VALUES (?)", ("test_value",))

        # Verify data was committed
        result = db_manager.get_one("SELECT value FROM test WHERE id = 1")
        self.assertEqual(result['value'], "test_value")

    def test_transaction_rollback(self):
        """Test transaction with rollback on exception."""
        db_manager = DatabaseManager()

        # Create a test table
        with db_manager.transaction() as conn:
            conn.execute("CREATE TABLE test_rollback (id INTEGER PRIMARY KEY, value TEXT)")

        # Try a transaction that will raise an exception
        try:
            with db_manager.transaction() as conn:
                conn.execute("INSERT INTO test_rollback (value) VALUES (?)", ("test_value",))
                # Raise an exception to trigger rollback
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Verify data was not committed
        result = db_manager.execute_query("SELECT COUNT(*) as count FROM test_rollback")
        self.assertEqual(result[0]['count'], 0)

    def test_execute_query(self):
        """Test executing a SELECT query."""
        db_manager = DatabaseManager()

        # Create a test table and insert data
        with db_manager.transaction() as conn:
            conn.execute("CREATE TABLE test_query (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test_query (value) VALUES (?)", ("value1",))
            conn.execute("INSERT INTO test_query (value) VALUES (?)", ("value2",))

        # Execute query
        results = db_manager.execute_query("SELECT * FROM test_query ORDER BY id")

        # Verify results
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0]['value'], "value1")
        self.assertEqual(results[1]['value'], "value2")

    def test_execute_write(self):
        """Test executing a write query."""
        db_manager = DatabaseManager()

        # Create a test table
        with db_manager.transaction() as conn:
            conn.execute("CREATE TABLE test_write (id INTEGER PRIMARY KEY, value TEXT)")

        # Execute write
        row_id = db_manager.execute_write(
            "INSERT INTO test_write (value) VALUES (?)",
            ("test_value",)
        )

        # Verify row was inserted
        self.assertEqual(row_id, 1)

        # Verify data
        result = db_manager.get_one("SELECT value FROM test_write WHERE id = ?", (row_id,))
        self.assertEqual(result['value'], "test_value")

    def test_execute_many(self):
        """Test executing multiple write queries."""
        db_manager = DatabaseManager()

        # Create a test table
        with db_manager.transaction() as conn:
            conn.execute("CREATE TABLE test_many (id INTEGER PRIMARY KEY, value TEXT)")

        # Execute multiple inserts
        values = [("value1",), ("value2",), ("value3",)]
        db_manager.execute_many(
            "INSERT INTO test_many (value) VALUES (?)",
            values
        )

        # Verify rows were inserted
        results = db_manager.execute_query("SELECT value FROM test_many ORDER BY id")
        self.assertEqual(len(results), 3)
        self.assertEqual(results[0]['value'], "value1")
        self.assertEqual(results[1]['value'], "value2")
        self.assertEqual(results[2]['value'], "value3")

    def test_get_one(self):
        """Test getting a single result."""
        db_manager = DatabaseManager()

        # Create a test table and insert data
        with db_manager.transaction() as conn:
            conn.execute("CREATE TABLE test_get_one (id INTEGER PRIMARY KEY, value TEXT)")
            conn.execute("INSERT INTO test_get_one (value) VALUES (?)", ("value1",))

        # Get one result
        result = db_manager.get_one("SELECT * FROM test_get_one WHERE id = ?", (1,))

        # Verify result
        self.assertEqual(result['id'], 1)
        self.assertEqual(result['value'], "value1")

        # Test getting non-existent row
        result = db_manager.get_one("SELECT * FROM test_get_one WHERE id = ?", (999,))
        self.assertIsNone(result)

    def test_table_exists(self):
        """Test checking if a table exists."""
        db_manager = DatabaseManager()

        # Create a test table
        with db_manager.transaction() as conn:
            conn.execute("CREATE TABLE test_exists (id INTEGER PRIMARY KEY)")

        # Check table exists
        self.assertTrue(db_manager.table_exists("test_exists"))
        self.assertFalse(db_manager.table_exists("nonexistent_table"))

    def test_multiple_threads(self):
        """Test DatabaseManager with multiple threads."""
        db_manager = DatabaseManager()

        # Create a test table
        with db_manager.transaction() as conn:
            conn.execute("CREATE TABLE test_threads (id INTEGER PRIMARY KEY, thread_id INTEGER)")

        # Function to run in thread
        def thread_func(thread_id):
            # Don't get a connection here, let transaction() handle it
            with db_manager.transaction() as conn:
                conn.execute("INSERT INTO test_threads (thread_id) VALUES (?)", (thread_id,))

        # Start multiple threads
        threads = []
        for i in range(5):
            thread = threading.Thread(target=thread_func, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Check that all threads inserted data
        results = db_manager.execute_query("SELECT thread_id FROM test_threads ORDER BY thread_id")
        self.assertEqual(len(results), 5)
        # Validate each thread's data was inserted
        for i in range(5):
            self.assertEqual(results[i]['thread_id'], i)

    def test_close_all(self):
        """Test closing all connections."""
        db_manager = DatabaseManager()

        # Get a connection
        conn = db_manager.get_connection()

        # Close all connections
        db_manager.close_all()

        # Connection pool should be empty
        self.assertEqual(len(db_manager.connection_pool), 0)


if __name__ == '__main__':
    unittest.main()