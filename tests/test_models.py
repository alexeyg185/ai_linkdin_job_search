import unittest
import sqlite3
import json
from unittest.mock import patch, MagicMock

from database.models import (
    Users, UserPreferences, JobListings, JobAnalysis,
    JobStates, ScheduleSettings, create_all_tables
)


class TestModels(unittest.TestCase):
    """Test cases for database models."""

    def setUp(self):
        """Set up the test environment before each test method."""
        # Create an in-memory SQLite database for testing
        self.conn = sqlite3.connect(':memory:')
        self.conn.row_factory = sqlite3.Row

    def tearDown(self):
        """Clean up after each test method."""
        self.conn.close()

    def test_create_all_tables(self):
        """Test that all tables are created correctly."""
        # Create all tables
        create_all_tables(self.conn)

        # Get list of tables
        cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]

        # Check all expected tables exist
        expected_tables = [
            Users.TABLE_NAME,
            UserPreferences.TABLE_NAME,
            JobListings.TABLE_NAME,
            JobAnalysis.TABLE_NAME,
            JobStates.TABLE_NAME,
            ScheduleSettings.TABLE_NAME
        ]

        for table in expected_tables:
            self.assertIn(table, tables)

        # Check that indexes were created
        cursor = self.conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
        indexes = [row[0] for row in cursor.fetchall()]

        expected_indexes = [
            f"idx_job_listings_job_id",
            f"idx_job_states_job_id_user_id",
            f"idx_job_states_state",
            f"idx_job_analysis_job_id_user_id",
            f"idx_user_preferences_user_id_category"
        ]

        for idx in expected_indexes:
            self.assertIn(idx, indexes)

    def test_users_model(self):
        """Test the Users model."""
        # Create users table
        self.conn.execute(Users.CREATE_TABLE)

        # Insert a user
        self.conn.execute(
            f"INSERT INTO {Users.TABLE_NAME} (username, password_hash) VALUES (?, ?)",
            ("testuser", "hashvalue")
        )

        # Verify user was inserted
        cursor = self.conn.execute(f"SELECT * FROM {Users.TABLE_NAME}")
        user = cursor.fetchone()
        self.assertEqual(user['username'], "testuser")
        self.assertEqual(user['password_hash'], "hashvalue")

    def test_user_preferences_model(self):
        """Test the UserPreferences model."""
        # Create users and preferences tables
        self.conn.execute(Users.CREATE_TABLE)
        self.conn.execute(UserPreferences.CREATE_TABLE)

        # Insert a user
        self.conn.execute(
            f"INSERT INTO {Users.TABLE_NAME} (user_id, username, password_hash) VALUES (?, ?, ?)",
            (1, "testuser", "hashvalue")
        )

        # Insert a preference
        test_value = {"key": "value", "nested": {"innerkey": "innervalue"}}
        json_value = UserPreferences.json_serialize(test_value)

        self.conn.execute(
            f"INSERT INTO {UserPreferences.TABLE_NAME} (user_id, category, name, value) VALUES (?, ?, ?, ?)",
            (1, "test_category", "test_name", json_value)
        )

        # Verify preference was inserted
        cursor = self.conn.execute(f"SELECT * FROM {UserPreferences.TABLE_NAME}")
        pref = cursor.fetchone()
        self.assertEqual(pref['user_id'], 1)
        self.assertEqual(pref['category'], "test_category")
        self.assertEqual(pref['name'], "test_name")

        # Test JSON serialization/deserialization
        deserialized = UserPreferences.json_deserialize(pref['value'])
        self.assertEqual(deserialized, test_value)
        self.assertEqual(deserialized['nested']['innerkey'], "innervalue")

    def test_job_listings_model(self):
        """Test the JobListings model."""
        # Create job listings table
        self.conn.execute(JobListings.CREATE_TABLE)

        # Insert a job listing
        self.conn.execute(
            f"""
            INSERT INTO {JobListings.TABLE_NAME} 
            (job_id, title, company, location, description, url, source_term) 
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("job123", "Test Job", "Test Company", "Remote", "Job description", "http://example.com", "python")
        )

        # Verify job was inserted
        cursor = self.conn.execute(f"SELECT * FROM {JobListings.TABLE_NAME}")
        job = cursor.fetchone()
        self.assertEqual(job['job_id'], "job123")
        self.assertEqual(job['title'], "Test Job")
        self.assertEqual(job['company'], "Test Company")

    def test_job_analysis_model(self):
        """Test the JobAnalysis model."""
        # Create required tables
        self.conn.execute(Users.CREATE_TABLE)
        self.conn.execute(JobListings.CREATE_TABLE)
        self.conn.execute(JobAnalysis.CREATE_TABLE)

        # Insert a user and job
        self.conn.execute(
            f"INSERT INTO {Users.TABLE_NAME} (user_id, username, password_hash) VALUES (?, ?, ?)",
            (1, "testuser", "hashvalue")
        )
        self.conn.execute(
            f"INSERT INTO {JobListings.TABLE_NAME} (job_id, title, company, url) VALUES (?, ?, ?, ?)",
            ("job123", "Test Job", "Test Company", "http://example.com")
        )

        # Insert job analysis
        analysis_details = {
            "title_analysis": {"relevance": 0.8},
            "skills_found": ["Python", "SQL"],
            "overall_score": 0.75
        }
        json_value = JobAnalysis.json_serialize(analysis_details)

        self.conn.execute(
            f"""
            INSERT INTO {JobAnalysis.TABLE_NAME} 
            (job_id, user_id, relevance_score, analysis_details) 
            VALUES (?, ?, ?, ?)
            """,
            ("job123", 1, 0.75, json_value)
        )

        # Verify analysis was inserted
        cursor = self.conn.execute(f"SELECT * FROM {JobAnalysis.TABLE_NAME}")
        analysis = cursor.fetchone()
        self.assertEqual(analysis['job_id'], "job123")
        self.assertEqual(analysis['user_id'], 1)
        self.assertEqual(analysis['relevance_score'], 0.75)

        # Test JSON serialization/deserialization
        deserialized = JobAnalysis.json_deserialize(analysis['analysis_details'])
        self.assertEqual(deserialized, analysis_details)
        self.assertEqual(deserialized['skills_found'], ["Python", "SQL"])

    def test_job_states_model(self):
        """Test the JobStates model."""
        # Create required tables
        self.conn.execute(Users.CREATE_TABLE)
        self.conn.execute(JobListings.CREATE_TABLE)
        self.conn.execute(JobStates.CREATE_TABLE)

        # Insert a user and job
        self.conn.execute(
            f"INSERT INTO {Users.TABLE_NAME} (user_id, username, password_hash) VALUES (?, ?, ?)",
            (1, "testuser", "hashvalue")
        )
        self.conn.execute(
            f"INSERT INTO {JobListings.TABLE_NAME} (job_id, title, company, url) VALUES (?, ?, ?, ?)",
            ("job123", "Test Job", "Test Company", "http://example.com")
        )

        # Insert job state
        self.conn.execute(
            f"""
            INSERT INTO {JobStates.TABLE_NAME} 
            (job_id, user_id, state, notes) 
            VALUES (?, ?, ?, ?)
            """,
            ("job123", 1, JobStates.STATE_NEW_SCRAPED, "Test note")
        )

        # Verify state was inserted
        cursor = self.conn.execute(f"SELECT * FROM {JobStates.TABLE_NAME}")
        state = cursor.fetchone()
        self.assertEqual(state['job_id'], "job123")
        self.assertEqual(state['user_id'], 1)
        self.assertEqual(state['state'], JobStates.STATE_NEW_SCRAPED)
        self.assertEqual(state['notes'], "Test note")

        # Test state validation
        with self.assertRaises(sqlite3.IntegrityError):
            # Try to insert invalid state
            self.conn.execute(
                f"""
                INSERT INTO {JobStates.TABLE_NAME} 
                (job_id, user_id, state) 
                VALUES (?, ?, ?)
                """,
                ("job123", 1, "invalid_state")
            )

    def test_schedule_settings_model(self):
        """Test the ScheduleSettings model."""
        # Create required tables
        self.conn.execute(Users.CREATE_TABLE)
        self.conn.execute(ScheduleSettings.CREATE_TABLE)

        # Insert a user
        self.conn.execute(
            f"INSERT INTO {Users.TABLE_NAME} (user_id, username, password_hash) VALUES (?, ?, ?)",
            (1, "testuser", "hashvalue")
        )

        # Insert schedule settings
        self.conn.execute(
            f"""
            INSERT INTO {ScheduleSettings.TABLE_NAME} 
            (user_id, schedule_type, execution_time, enabled) 
            VALUES (?, ?, ?, ?)
            """,
            (1, ScheduleSettings.TYPE_DAILY, "08:00", 1)
        )

        # Verify settings were inserted
        cursor = self.conn.execute(f"SELECT * FROM {ScheduleSettings.TABLE_NAME}")
        settings = cursor.fetchone()
        self.assertEqual(settings['user_id'], 1)
        self.assertEqual(settings['schedule_type'], ScheduleSettings.TYPE_DAILY)
        self.assertEqual(settings['execution_time'], "08:00")
        self.assertEqual(settings['enabled'], 1)

        # Test schedule type validation
        with self.assertRaises(sqlite3.IntegrityError):
            # Try to insert invalid schedule type
            self.conn.execute(
                f"""
                INSERT INTO {ScheduleSettings.TABLE_NAME} 
                (user_id, schedule_type, execution_time) 
                VALUES (?, ?, ?)
                """,
                (1, "invalid_type", "08:00")
            )


if __name__ == '__main__':
    unittest.main()