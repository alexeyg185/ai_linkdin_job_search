"""
LinkedIn job scraper service.
This module handles the scraping of LinkedIn job listings based on user preferences.
"""

import logging
import os
import random
import re
import time
import hashlib
import asyncio
import threading
from typing import Dict, Any, Optional, Callable, Set, Tuple, List

from linkedin_jobs_scraper import LinkedinScraper
from linkedin_jobs_scraper.events import Events, EventData
from linkedin_jobs_scraper.filters import RelevanceFilters, TimeFilters, TypeFilters, ExperienceLevelFilters
from linkedin_jobs_scraper.query import Query, QueryOptions, QueryFilters

from config import Config
from constants.scraping import ScrapingConstants
from database.models import JobStates
from services.database_service import DatabaseService
from services.preference_service import PreferenceService
from utils.security import validate_url

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ScraperService:
    """
    Service for scraping LinkedIn job listings based on user preferences.
    """

    def __init__(self):
        """Initialize the scraper service."""
        self.db_service = DatabaseService()
        self.scraper = None

        # Initialize instance variables before using them
        self.current_jobs: Set[str] = set()
        self.current_user_id: Optional[int] = None
        self.callback: Optional[Callable[[str, Dict[str, Any]], None]] = None
        self.allowed_job_ids: Optional[List[str]] = None

        # Add a lock for thread safety
        self.scraper_lock = threading.Lock()

        # Pending URL jobs for single URL scraping
        self.pending_url_jobs = {}

        # Now initialize the scraper
        self.initialize_scraper()

    def _get_chrome_paths(self, user_id: int) -> Tuple[Optional[str], Optional[str]]:
        """
        Get chrome paths from user preferences.

        Args:
            user_id: The user's ID

        Returns:
            chrome_executable_path, chrome_binary_location
        """
        pref_service = PreferenceService()
        tech_prefs = pref_service.get_preferences_by_category(
            user_id, PreferenceService.CATEGORY_TECHNICAL
        )

        chrome_executable_path = tech_prefs.get('chrome_executable_path')
        chrome_binary_location = tech_prefs.get('chrome_binary_location')

        # Log the paths retrieved from preferences
        logger.debug(f"Retrieved chrome_executable_path from preferences: {chrome_executable_path}")
        logger.debug(f"Retrieved chrome_binary_location from preferences: {chrome_binary_location}")

        return chrome_executable_path, chrome_binary_location

    def _validate_file_path(self, path: Optional[str]) -> Optional[str]:
        """
        Validate if a file path exists.

        Args:
            path: File path to validate

        Returns:
            path: Valid file path or None if invalid
        """
        if not path:
            return None

        # Check if the file exists
        if os.path.isfile(path):
            return path

        # If the path doesn't exist, log a warning and return None
        logger.warning(f"Invalid file path: {path}")
        return None

    def _ensure_scraper_initialized(self) -> bool:
        """
        Ensure the scraper is initialized properly.

        Returns:
            is_initialized: True if initialized successfully, False otherwise
        """
        try:
            if self.scraper is None:
                self.initialize_scraper()

            return self.scraper is not None
        except Exception as e:
            logger.error(f"Failed to initialize scraper: {str(e)}")
            return False

    def initialize_scraper(self) -> None:
        """Initialize the LinkedIn scraper with credentials from config."""
        # Initialize the scraper if not already done
        if self.scraper is None:
            try:
                # Get paths from user preferences if a user is set
                chrome_executable_path = None
                chrome_binary_location = None

                if self.current_user_id:
                    chrome_executable_path, chrome_binary_location = self._get_chrome_paths(self.current_user_id)

                # Validate paths
                chrome_executable_path = self._validate_file_path(chrome_executable_path)
                chrome_binary_location = self._validate_file_path(chrome_binary_location)

                # Log the paths being used
                logger.info(f"Initializing scraper with chrome_executable_path: {chrome_executable_path}")
                logger.info(f"Initializing scraper with chrome_binary_location: {chrome_binary_location}")

                self.scraper = LinkedinScraper(
                    chrome_executable_path=chrome_executable_path,  # Use provided path or None to auto-detect
                    chrome_binary_location=chrome_binary_location,  # Use provided path or None to auto-detect
                    chrome_options=None,
                    headless=True,  # Run in headless mode
                    max_workers=1,  # Number of workers
                    slow_mo=0.5,  # Slow down to avoid detection
                    page_load_timeout=30  # Timeout in seconds
                )

                # Set up event listeners with lambda wrappers to convert bound methods to functions
                self.scraper.on(Events.DATA, lambda data: self._handle_data(data))
                self.scraper.on(Events.ERROR, lambda error: self._handle_error(error))
                self.scraper.on(Events.END, lambda: self._handle_end())

            except Exception as e:
                logger.error(f"Error initializing scraper: {str(e)}")
                # Fallback to None, will be attempted again later
                self.scraper = None
                raise

    def _handle_data(self, data: EventData) -> None:
        """
        Handle job data received from the scraper.

        Args:
            data: Job data from the scraper
        """
        if not self.current_user_id:
            logger.warning("No current_user_id set for scraping session")
            return

        # Check if we have a list of allowed job IDs, and if so, check if this job is in the list
        if self.allowed_job_ids and data.job_id not in self.allowed_job_ids:
            logger.debug(f"Skipping job not in allowed IDs list: {data.job_id}")
            return

        # Check if we already found this job in this run
        if data.job_id in self.current_jobs:
            logger.debug(f"Duplicate job in current run: {data.job_id}")
            return

        # Add to current jobs set
        self.current_jobs.add(data.job_id)

        # Process job data
        try:
            # Prepare job data for database
            job_data = {
                'job_id': data.job_id,
                'title': data.title,
                'company': data.company,
                'location': data.location,
                'description': data.description,
                'url': data.link,
                'source_term': data.query
            }

            # Check if this is from a single URL job
            single_url_job = False
            if hasattr(data, 'custom_data') and data.custom_data:
                if 'single_url_job' in data.custom_data:
                    single_url_job = True
                    job_request_id = data.custom_data.get('job_request_id')
                    self.pending_url_jobs[job_request_id] = job_data

            # Check if job already exists
            existing_job = self.db_service.get_job_by_id(data.job_id)

            if not existing_job:
                # Add new job listing
                self.db_service.add_job_listing(job_data)

                # Add initial state
                self.db_service.add_job_state(
                    data.job_id,
                    self.current_user_id,
                    JobStates.STATE_NEW_SCRAPED
                )

                # Add to queue for analysis
                self.db_service.add_job_state(
                    data.job_id,
                    self.current_user_id,
                    JobStates.STATE_QUEUED_FOR_ANALYSIS
                )

                logger.info(f"Added new job: {data.title} at {data.company}")
            else:
                # Check if this user already has a state for this job
                current_state = self.db_service.get_current_job_state(
                    data.job_id, self.current_user_id
                )

                if not current_state:
                    # First time this user has seen this job
                    self.db_service.add_job_state(
                        data.job_id,
                        self.current_user_id,
                        JobStates.STATE_NEW_SCRAPED
                    )

                    # Add to queue for analysis
                    self.db_service.add_job_state(
                        data.job_id,
                        self.current_user_id,
                        JobStates.STATE_QUEUED_FOR_ANALYSIS
                    )

                    logger.info(f"Added existing job to user: {data.title}")
                elif current_state['state'] not in [
                    JobStates.STATE_ANALYZED,
                    JobStates.STATE_RELEVANT,
                    JobStates.STATE_IRRELEVANT,
                    JobStates.STATE_VIEWED,
                    JobStates.STATE_SAVED,
                    JobStates.STATE_APPLIED,
                    JobStates.STATE_REJECTED
                ]:
                    # Job exists for this user but hasn't been analyzed yet
                    # Only queue it if it's not already in a post-analysis state
                    self.db_service.add_job_state(
                        data.job_id,
                        self.current_user_id,
                        JobStates.STATE_QUEUED_FOR_ANALYSIS
                    )
                    logger.info(f"Requeing job for analysis: {data.title}")
                else:
                    logger.debug(f"Job already processed by user: {data.job_id}")

            # Call callback if provided
            if self.callback:
                try:
                    self.callback("job_found", job_data)
                except Exception as e:
                    logger.error(f"Error in callback: {str(e)}")

            # Check if we've found all the job IDs we're looking for
            if self.allowed_job_ids and set(self.allowed_job_ids).issubset(self.current_jobs):
                logger.info(f"Found all requested job IDs ({len(self.allowed_job_ids)}). Stopping scraper.")
                # Call the end callback before stopping
                if self.callback:
                    try:
                        self.callback("end", {"jobs_found": len(self.current_jobs), "early_termination": True})
                    except Exception as e:
                        logger.error(f"Error in callback: {str(e)}")

                # Stop the scraper
                if self.scraper:
                    try:
                        self.scraper.stop()
                        logger.info("Scraper stopped successfully")
                    except Exception as e:
                        logger.error(f"Error stopping scraper: {str(e)}")

        except Exception as e:
            logger.error(f"Error handling job data: {str(e)}")
    def _handle_error(self, error) -> None:
        """
        Handle errors from the scraper.

        Args:
            error: Error object
        """
        logger.error(f"Scraper error: {error}")

        # Call callback if provided
        if self.callback:
            try:
                self.callback("error", {"error": str(error)})
            except Exception as e:
                logger.error(f"Error in callback: {str(e)}")

    def _handle_end(self) -> None:
        """Handle end of scraping session."""
        logger.info(f"Scraping session ended. Found {len(self.current_jobs)} jobs.")

        # Call callback if provided
        if self.callback:
            try:
                self.callback("end", {"jobs_found": len(self.current_jobs)})
            except Exception as e:
                logger.error(f"Error in callback: {str(e)}")

        # Clear current jobs and allowed job IDs
        self.current_jobs = set()
        self.allowed_job_ids = None

    def _map_experience_level(self, level: str) -> ExperienceLevelFilters:
        """
        Map experience level string to LinkedIn filter.

        Args:
            level: Experience level string

        Returns:
            filter: LinkedIn experience level filter
        """
        level_map = {
            "Internship": ExperienceLevelFilters.INTERNSHIP,
            "Entry level": ExperienceLevelFilters.ENTRY_LEVEL,
            "Associate": ExperienceLevelFilters.ASSOCIATE,
            "Mid-Senior level": ExperienceLevelFilters.MID_SENIOR,
            "Director": ExperienceLevelFilters.DIRECTOR,
            "Executive": ExperienceLevelFilters.EXECUTIVE
        }

        return level_map.get(level, ExperienceLevelFilters.MID_SENIOR)


    def scrape_jobs(self, user_id: int, callback: Optional[Callable] = None, job_limit: int = None) -> Dict[str, Any]:
        """
        Scrape jobs based on user preferences.

        Args:
            user_id: The user's ID
            callback: Optional callback function for progress updates
            job_limit: Optional limit on number of jobs to scrape

        Returns:
            result: Dictionary with scraping statistics
        """
        # Set current user and callback
        self.current_user_id = user_id
        self.callback = callback
        self.current_jobs = set()

        # Check if we need to update the scraper with user's Chrome paths
        chrome_executable_path, chrome_binary_location = self._get_chrome_paths(user_id)
        if (chrome_executable_path or chrome_binary_location) and self.scraper:
            # We need to reinitialize the scraper with the new paths
            self.scraper = None

        # Ensure scraper is initialized
        if not self._ensure_scraper_initialized():
            if self.callback:
                self.callback("error",
                              {"error": "Failed to initialize LinkedIn scraper. Please check the ChromeDriver path."})
            return {
                "status": "error",
                "error": "Failed to initialize LinkedIn scraper. Please check the ChromeDriver path.",
                "jobs_found": 0
            }

        # Get user preferences
        pref_service = PreferenceService()
        search_prefs = pref_service.get_preferences_by_category(user_id, PreferenceService.CATEGORY_SEARCH)

        # Extract search parameters
        job_titles = search_prefs.get('job_titles', Config.DEFAULT_SEARCH_TERMS)
        locations = search_prefs.get('locations', Config.DEFAULT_LOCATIONS)
        experience_levels = search_prefs.get('experience_levels', ["Entry level", "Associate", "Mid-Senior level"])
        remote_preference = search_prefs.get('remote_preference', True)

        # Map experience levels to LinkedIn filters
        experience_filters = [self._map_experience_level(level) for level in experience_levels]

        try:
            # Define queries based on preferences
            queries = []
            for title in job_titles:
                for location in locations:
                    # Create the QueryFilters object without the 'remote' parameter
                    filters = QueryFilters(
                        relevance=RelevanceFilters.RELEVANT,
                        time=TimeFilters.MONTH,
                        type=[TypeFilters.FULL_TIME],
                        experience=experience_filters
                    )
                    # Check if the library has a specific method to set remote preference
                    if hasattr(filters, 'set_remote') and remote_preference:
                        filters.set_remote(remote_preference)
                    elif hasattr(QueryFilters, 'REMOTE') and remote_preference:
                        # Some libraries define constants instead
                        filters.type.append(QueryFilters.REMOTE)

                    # Set limit to job_limit if provided, otherwise use a higher default value
                    limit = min(job_limit if job_limit is not None else ScrapingConstants.DEFAULT_JOB_LIMIT, ScrapingConstants.MAX_JOB_LIMIT)

                    queries.append(
                        Query(
                            query=title,
                            options=QueryOptions(
                                locations=[location],
                                apply_link=False,
                                limit=limit,
                                filters=filters
                            ),
                        )
                    )

            # Start scraping
            if self.callback:
                self.callback("start", {"queries": len(queries)})

            # Run all queries without limiting by default
            for query in queries:
                self.scraper.run(query)

                time.sleep(random.uniform(ScrapingConstants.QUERY_DELAY_MIN, ScrapingConstants.QUERY_DELAY_MAX))

            return {
                "status": "success",
                "jobs_found": len(self.current_jobs),
                "queries_executed": len(queries)
            }

        except Exception as e:
            logger.error(f"Error in scrape_jobs: {str(e)}")
            if self.callback:
                self.callback("error", {"error": str(e)})

            return {
                "status": "error",
                "error": str(e),
                "jobs_found": len(self.current_jobs)
            }

        finally:
            # Update schedule last run time
            self.db_service.update_last_run(user_id)

    def scrape_company_jobs(self, company_jobs_url: str, user_id: int, job_ids: List[str] = None,
                           callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Scrape jobs from a company jobs URL with specific job IDs.

        Args:
            company_jobs_url: URL of the company jobs page
            user_id: The user's ID
            job_ids: List of job IDs to filter by (required)
            callback: Optional callback function

        Returns:
            result: Dictionary with scraping statistics
        """
        # Set current user and callback
        self.current_user_id = user_id
        self.callback = callback
        self.current_jobs = set()

        # Set allowed job IDs for filtering
        if job_ids:
            # Convert job IDs to strings if they aren't already
            self.allowed_job_ids = [str(job_id) for job_id in job_ids]
            logger.info(f"Will filter for {len(self.allowed_job_ids)} job IDs")
        else:
            logger.warning("No job IDs provided for filtering")
            return {
                "status": "error",
                "error": "Job IDs are required to filter jobs",
                "jobs_found": 0
            }

        # Check if we need to update the scraper with user's Chrome paths
        chrome_executable_path, chrome_binary_location = self._get_chrome_paths(user_id)
        if (chrome_executable_path or chrome_binary_location) and self.scraper:
            # We need to reinitialize the scraper with the new paths
            self.scraper = None

        # Ensure scraper is initialized
        if not self._ensure_scraper_initialized():
            if self.callback:
                self.callback("error",
                              {"error": "Failed to initialize LinkedIn scraper. Please check the ChromeDriver path."})
            return {
                "status": "error",
                "error": "Failed to initialize LinkedIn scraper. Please check the ChromeDriver path.",
                "jobs_found": 0
            }

        try:
            # Get user preferences for location
            pref_service = PreferenceService()
            search_prefs = pref_service.get_preferences_by_category(user_id, PreferenceService.CATEGORY_SEARCH)

            # Extract locations from preferences (use the first one as default)
            preferred_locations = search_prefs.get('locations', Config.DEFAULT_LOCATIONS)
            default_location = preferred_locations[0] if preferred_locations else 'Remote'

            # Create the QueryFilters with company_jobs_url
            filters = QueryFilters(
                company_jobs_url=company_jobs_url  # Use company_jobs_url as requested
            )

            # Create the query - use empty string for title since we're filtering by job IDs
            # But DO include location to prevent "worldwide" default
            query = Query(
                query="",  # Empty string for title since we're filtering by job IDs
                options=QueryOptions(
                    locations=[default_location],  # Add location to prevent "worldwide" default
                    apply_link=False,
                    limit=50,  # Higher limit to ensure we catch all the specified job IDs
                    filters=filters
                )
            )

            # Start scraping
            if self.callback:
                self.callback("start", {"company_url": company_jobs_url, "job_ids": job_ids})

            # Log the job IDs we're filtering for
            logger.info(f"Filtering for job IDs: {job_ids}")

            # Run the query
            self.scraper.run([query])

            return {
                "status": "success",
                "jobs_found": len(self.current_jobs),
                "job_ids_matched": list(self.current_jobs)
            }

        except Exception as e:
            logger.error(f"Error in scrape_company_jobs: {str(e)}")
            if self.callback:
                self.callback("error", {"error": str(e)})

            return {
                "status": "error",
                "error": str(e),
                "jobs_found": len(self.current_jobs)
            }