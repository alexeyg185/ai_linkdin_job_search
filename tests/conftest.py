import pytest
import os
import sqlite3
import tempfile
from unittest.mock import patch, MagicMock

from database.db_manager import DatabaseManager
from tests.mock_db_manager import MockDatabaseManager  # Import the mock


@pytest.fixture
def mock_db_manager():
    """
    Create a MockDatabaseManager instance for unit testing.
    This completely avoids database connections.
    """
    # Clear any existing singleton instance
    MockDatabaseManager._instance = None

    # Create new mock instance
    mock_manager = MockDatabaseManager()

    # Return the mock for use in tests
    yield mock_manager

    # No cleanup needed


@pytest.fixture
def patch_db_manager():
    """
    Patch the DatabaseManager with MockDatabaseManager.
    This is useful for testing services that create their own DatabaseManager instances.
    """
    # Create a mock instance
    mock_manager = MockDatabaseManager()

    # Patch the get_instance method to return our mock
    with patch('services.preference_service.DatabaseManager') as mock_db_class:
        mock_db_class.return_value = mock_manager

        # Also patch the DatabaseManager in case it's imported directly
        with patch('database.db_manager.DatabaseManager') as mock_direct_import:
            mock_direct_import.return_value = mock_manager

            yield mock_manager


@pytest.fixture
def in_memory_db():
    """
    Create an in-memory SQLite database for testing.
    This fixture can be used for tests that need direct database access.
    """
    # Configure the DB manager to use in-memory database
    with patch('database.db_manager.Config') as mock_config:
        mock_config.DATABASE_PATH = ':memory:'

        # Clear any existing singleton instance
        DatabaseManager._instance = None

        # Create a new instance
        db_manager = DatabaseManager()

        # Return the db_manager for use in tests
        yield db_manager

        # Clean up
        db_manager.close_all()


@pytest.fixture
def temp_db_file():
    """
    Create a temporary SQLite database file for testing.
    This fixture can be used for tests that need a persistent file-based database.
    """
    # Create a temporary file
    fd, temp_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)  # Close the file descriptor

    # Configure the DB manager to use the temporary file
    with patch('database.db_manager.Config') as mock_config:
        mock_config.DATABASE_PATH = temp_path

        # Clear any existing singleton instance
        DatabaseManager._instance = None

        # Create a new instance
        db_manager = DatabaseManager()

        # Return the db_manager and path for use in tests
        yield db_manager, temp_path

        # Clean up
        db_manager.close_all()
        if os.path.exists(temp_path):
            os.unlink(temp_path)


@pytest.fixture
def mocked_services():
    """
    Create mocks for all services.
    This fixture can be used for testing high-level components that depend on multiple services.
    """
    with patch('services.orchestrator_service.UserService') as mock_user_service, \
            patch('services.orchestrator_service.DatabaseService') as mock_db_service, \
            patch('services.orchestrator_service.PreferenceService') as mock_pref_service, \
            patch('services.orchestrator_service.ScraperService') as mock_scraper_service, \
            patch('services.orchestrator_service.AnalysisService') as mock_analysis_service, \
            patch('services.orchestrator_service.SchedulerService') as mock_scheduler_service:
        # Configure mocks
        services = {
            'user_service': mock_user_service.return_value,
            'db_service': mock_db_service.return_value,
            'pref_service': mock_pref_service.return_value,
            'scraper_service': mock_scraper_service.return_value,
            'analysis_service': mock_analysis_service.return_value,
            'scheduler_service': mock_scheduler_service.return_value
        }

        yield services


@pytest.fixture
def sample_job_data():
    """
    Create sample job data for testing.
    """
    return {
        'job_id': 'job123',
        'title': 'Senior AI Engineer',
        'company': 'Tech Corp',
        'location': 'Remote',
        'description': 'We are looking for an experienced AI Engineer...',
        'url': 'https://example.com/jobs/123',
        'source_term': 'AI Engineer',
        'scraped_at': '2023-01-01T12:00:00'
    }


@pytest.fixture
def sample_user_data():
    """
    Create sample user data for testing.
    """
    return {
        'username': 'testuser',
        'password': 'Password123!',
        'email': 'test@example.com'
    }


@pytest.fixture
def sample_analysis_data():
    """
    Create sample job analysis data for testing.
    """
    return {
        'title_analysis': {
            'title_keywords': ['AI', 'Engineer'],
            'matches_pattern': True,
            'pattern_matched': 'AI',
            'estimated_relevance': 0.9,
            'reasoning': 'Job title contains relevant pattern'
        },
        'full_analysis': {
            'required_skills_found': ['Python', 'Machine Learning'],
            'preferred_skills_found': ['TensorFlow'],
            'missing_required_skills': [],
            'job_responsibilities': ['Build AI models', 'Deploy ML systems'],
            'relevance_score': 0.85,
            'reasoning': 'Has all required skills'
        },
        'relevance_score': 0.85
    }


@pytest.fixture
def sample_preferences_data():
    """
    Create sample user preferences data for testing.
    """
    return {
        'search': {
            'job_titles': ['AI Engineer', 'Machine Learning Engineer'],
            'locations': ['Remote', 'New York, NY'],
            'experience_levels': ['Mid-Senior level'],
            'remote_preference': True
        },
        'analysis': {
            'relevant_title_patterns': ['AI', 'Machine Learning', 'ML', 'Data Scientist'],
            'required_skills': ['Python', 'Machine Learning'],
            'preferred_skills': ['TensorFlow', 'PyTorch', 'NLP'],
            'relevance_threshold': 0.7,
            'title_match_strictness': 0.8
        },
        'scheduling': {
            'schedule_type': 'daily',
            'execution_time': '08:00',
            'notifications_enabled': True
        }
    }