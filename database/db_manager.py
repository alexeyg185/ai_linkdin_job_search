import sqlite3
import os
import threading
from typing import Any, Dict, List, Optional, Tuple, Union, Self
from contextlib import contextmanager

from config import Config
from database.models import create_all_tables


class DatabaseManager:
    """
    Database manager for SQLite with connection pooling and transaction management.
    This class implements the singleton pattern to ensure only one database manager exists.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls) -> Self:
        """Create singleton instance"""
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(DatabaseManager, cls).__new__(cls)
                cls._instance._initialize()
            return cls._instance

    def _initialize(self) -> None:
        """Initialize database and connection pool"""
        self.db_path = Config.DATABASE_PATH
        self.connection_pool = {}
        self.pool_lock = threading.Lock()

        # For in-memory databases, use a shared connection string
        if self.db_path == ':memory:':
            self.connection_string = 'file::memory:?cache=shared'
            self.use_uri = True
        else:
            # Regular file-based database
            self.connection_string = self.db_path
            self.use_uri = False
            # Ensure database directory exists
            if os.path.dirname(self.db_path):
                os.makedirs(os.path.dirname(self.db_path), exist_ok=True)

        # Initialize database with tables
        with self.get_connection() as conn:
            create_all_tables(conn)

    def get_connection(self) -> sqlite3.Connection:
        """
        Get a database connection for the current thread.
        Creates a new connection if none exists for this thread.
        """
        thread_id = threading.get_ident()

        with self.pool_lock:
            if thread_id not in self.connection_pool:
                # Create new connection with row factory for dictionary results
                conn = sqlite3.connect(self.connection_string,
                                      uri=self.use_uri,
                                      check_same_thread=False)
                conn.row_factory = sqlite3.Row

                # Enable foreign keys
                conn.execute("PRAGMA foreign_keys = ON")

                self.connection_pool[thread_id] = conn

            return self.connection_pool[thread_id]

    @contextmanager
    def transaction(self) -> sqlite3.Connection:
        """
        Context manager for database transactions.
        Handles commit and rollback automatically.
        """
        conn = self.get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def close_all(self) -> None:
        """Close all database connections"""
        with self.pool_lock:
            for conn in self.connection_pool.values():
                conn.close()
            self.connection_pool.clear()

    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """
        Execute a SELECT query and return the results as a list of dictionaries.
        """
        with self.transaction() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    def execute_write(self, query: str, params: tuple = ()) -> int:
        """
        Execute an INSERT, UPDATE, or DELETE query and return the last row ID.
        """
        with self.transaction() as conn:
            cursor = conn.execute(query, params)
            return cursor.lastrowid

    def execute_many(self, query: str, params_list: List[tuple]) -> None:
        """
        Execute multiple INSERT, UPDATE, or DELETE queries with different parameters.
        """
        with self.transaction() as conn:
            conn.executemany(query, params_list)

    def get_one(self, query: str, params: tuple = ()) -> Optional[Dict[str, Any]]:
        """
        Execute a SELECT query and return the first result as a dictionary.
        Returns None if no result is found.
        """
        with self.transaction() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return dict(row) if row else None

    def table_exists(self, table_name: str) -> bool:
        """Check if a table exists in the database"""
        query = """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
        """
        result = self.get_one(query, (table_name,))
        return result is not None