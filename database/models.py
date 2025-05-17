import sqlite3
import json
import datetime
from typing import Dict, Any, List, Optional


class Users:
    """Users table for authentication and user management"""
    TABLE_NAME = "users"

    CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        email TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        last_login TIMESTAMP
    );
    """


class UserPreferences:
    """User preferences table for storing all user-specific settings"""
    TABLE_NAME = "user_preferences"

    CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS user_preferences (
        pref_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        category TEXT NOT NULL,
        name TEXT NOT NULL,
        value TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        UNIQUE (user_id, category, name)
    );
    """

    @staticmethod
    def json_serialize(value: Any) -> str:
        """Convert a value to JSON string for storage"""
        return json.dumps(value)

    @staticmethod
    def json_deserialize(value: str) -> Any:
        """Convert a JSON string from storage to Python object"""
        return json.loads(value)


class JobListings:
    """Job listings table for storing scraped jobs"""
    TABLE_NAME = "job_listings"

    CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS job_listings (
        internal_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT UNIQUE NOT NULL,
        title TEXT NOT NULL,
        company TEXT NOT NULL,
        location TEXT,
        description TEXT,
        url TEXT NOT NULL,
        scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        source_term TEXT
    );
    """


class JobAnalysis:
    """Job analysis table for storing LLM analysis results"""
    TABLE_NAME = "job_analysis"

    CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS job_analysis (
        analysis_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        relevance_score REAL NOT NULL,
        analysis_details TEXT NOT NULL,
        analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (job_id) REFERENCES job_listings(job_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id),
        UNIQUE (job_id, user_id)
    );
    """

    @staticmethod
    def json_serialize(value: Dict[str, Any]) -> str:
        """Convert analysis details dictionary to JSON string for storage"""
        return json.dumps(value)

    @staticmethod
    def json_deserialize(value: str) -> Dict[str, Any]:
        """Convert a JSON string from storage to Python dictionary"""
        return json.loads(value)


class JobStates:
    """Job states table for tracking the status of each job for each user"""
    TABLE_NAME = "job_states"

    # Job state constants
    STATE_NEW_SCRAPED = "new_scraped"
    STATE_QUEUED_FOR_ANALYSIS = "queued_for_analysis"
    STATE_ANALYZING = "analyzing"
    STATE_ANALYZED = "analyzed"
    STATE_RELEVANT = "relevant"
    STATE_IRRELEVANT = "irrelevant"
    STATE_VIEWED = "viewed"
    STATE_SAVED = "saved"
    STATE_APPLIED = "applied"
    STATE_REJECTED = "rejected"

    # All valid states
    VALID_STATES = [
        STATE_NEW_SCRAPED,
        STATE_QUEUED_FOR_ANALYSIS,
        STATE_ANALYZING,
        STATE_ANALYZED,
        STATE_RELEVANT,
        STATE_IRRELEVANT,
        STATE_VIEWED,
        STATE_SAVED,
        STATE_APPLIED,
        STATE_REJECTED
    ]

    CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS job_states (
        state_id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT NOT NULL,
        user_id INTEGER NOT NULL,
        state TEXT NOT NULL CHECK (state IN (
            'new_scraped', 'queued_for_analysis', 'analyzing', 'analyzed',
            'relevant', 'irrelevant', 'viewed', 'saved', 'applied', 'rejected'
        )),
        state_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        notes TEXT,
        FOREIGN KEY (job_id) REFERENCES job_listings(job_id),
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """


class ScheduleSettings:
    """Schedule settings table for storing scheduler configuration"""
    TABLE_NAME = "schedule_settings"

    # Schedule type constants
    TYPE_DAILY = "daily"
    TYPE_WEEKLY = "weekly"
    TYPE_CUSTOM = "custom"

    # All valid types
    VALID_TYPES = [TYPE_DAILY, TYPE_WEEKLY, TYPE_CUSTOM]

    CREATE_TABLE = """
    CREATE TABLE IF NOT EXISTS schedule_settings (
        setting_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        schedule_type TEXT NOT NULL CHECK (schedule_type IN ('daily', 'weekly', 'custom')),
        execution_time TEXT NOT NULL,
        last_run TIMESTAMP,
        enabled BOOLEAN NOT NULL DEFAULT 1,
        FOREIGN KEY (user_id) REFERENCES users(user_id)
    );
    """


def create_all_tables(conn: sqlite3.Connection) -> None:
    """Create all tables in the database if they don't exist"""
    cursor = conn.cursor()

    # Create tables
    cursor.execute(Users.CREATE_TABLE)
    cursor.execute(UserPreferences.CREATE_TABLE)
    cursor.execute(JobListings.CREATE_TABLE)
    cursor.execute(JobAnalysis.CREATE_TABLE)
    cursor.execute(JobStates.CREATE_TABLE)
    cursor.execute(ScheduleSettings.CREATE_TABLE)

    # Create indexes for performance
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_job_listings_job_id ON {JobListings.TABLE_NAME}(job_id);")
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_job_states_job_id_user_id ON {JobStates.TABLE_NAME}(job_id, user_id);")
    cursor.execute(f"CREATE INDEX IF NOT EXISTS idx_job_states_state ON {JobStates.TABLE_NAME}(state);")
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_job_analysis_job_id_user_id ON {JobAnalysis.TABLE_NAME}(job_id, user_id);")
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id_category ON {UserPreferences.TABLE_NAME}(user_id, category);")

    conn.commit()