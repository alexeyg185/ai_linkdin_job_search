"""
Database package initialization.
This module ensures the database components are correctly initialized.
"""

from database.db_manager import DatabaseManager

# Initialize database at package import time, creating tables if needed
db_manager = DatabaseManager()