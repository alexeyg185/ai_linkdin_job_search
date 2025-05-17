import os
from pathlib import Path
import secrets
from dotenv import load_dotenv

# This project requires Python 3.11+

# Load environment variables from .env file if it exists
load_dotenv()

# Base directory of the application
BASE_DIR = Path(__file__).resolve().parent


# Application settings
class Config:
    # Flask settings
    SECRET_KEY = os.getenv('SECRET_KEY', secrets.token_hex(32))
    DEBUG = os.getenv('DEBUG', 'False') == 'True'

    # Database settings
    DATABASE_PATH = os.getenv('DATABASE_PATH', os.path.join(BASE_DIR, 'database', 'jobsearch.db'))

    # OpenAI API settings
    OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
    OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4.1-nano')

    # LinkedIn scraper settings
    LINKEDIN_EMAIL = os.getenv('LINKEDIN_EMAIL', '')
    LINKEDIN_PASSWORD = os.getenv('LINKEDIN_PASSWORD', '')

    # Job search settings
    DEFAULT_SEARCH_TERMS = ['AI Engineer', 'Machine Learning Engineer', 'Data Scientist']
    DEFAULT_LOCATIONS = ['New York, NY', 'San Francisco, CA']

    # Scheduling settings
    DEFAULT_SCHEDULE_TYPE = 'daily'
    DEFAULT_EXECUTION_TIME = '08:00'

    # Security settings
    SESSION_TIMEOUT = int(os.getenv('SESSION_TIMEOUT', 3600))  # 1 hour in seconds

    # Network settings
    HOST = os.getenv('HOST', '0.0.0.0')
    PORT = int(os.getenv('PORT', 5000))

    # Application settings
    JOBS_PER_PAGE = int(os.getenv('JOBS_PER_PAGE', 20))

    # Analysis settings
    RELEVANCE_THRESHOLD = float(os.getenv('RELEVANCE_THRESHOLD', 0.7))

    # Feature flags
    ENABLE_REGISTRATION = os.getenv('ENABLE_REGISTRATION', 'False') == 'True'

    # Set secure cookie options
    SESSION_COOKIE_SECURE = True  # Only send cookies over HTTPS
    SESSION_COOKIE_HTTPONLY = True  # Prevent JavaScript from accessing cookies
    SESSION_COOKIE_SAMESITE = 'Lax'  # Controls how cookies are sent with cross-site requests
    PERMANENT_SESSION_LIFETIME = 3600  # Session timeout in seconds (1 hour)
    WTF_CSRF_ENABLED = True  # Ensure CSRF protection is enabled