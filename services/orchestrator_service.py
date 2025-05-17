"""
Orchestration service for coordinating workflow between components.
This module provides high-level methods for common workflows and operations.
"""

import logging
from typing import Dict, List, Any, Optional, Callable
import threading
import time

from utils.factories import AnalysisServiceFactory
from services.user_service import UserService
from services.database_service import DatabaseService
from services.preference_service import PreferenceService
from services.scraper_service import ScraperService
from services.scheduler_service import SchedulerService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OrchestratorService:
    """
    Service for coordinating workflow between different components.
    This service provides high-level methods that combine functionality
    from multiple services to implement common workflows.
    """

    def __init__(self):
        """Initialize the orchestrator with all required services."""
        self.user_service = UserService()
        self.db_service = DatabaseService()
        self.pref_service = PreferenceService()
        self.scraper_service = ScraperService()
        self.analysis_service = AnalysisServiceFactory.create_analysis_service()
        self.scheduler_service = SchedulerService()

        # Start scheduler
        self.scheduler_service.start()

    def setup_new_installation(self, admin_username: str, admin_password: str, admin_email: str) -> int:
        """
        Set up a new installation with an admin user.

        Args:
            admin_username: Username for admin account
            admin_password: Password for admin account
            admin_email: Email for admin account

        Returns:
            user_id: The ID of the created admin user
        """
        # Create admin user
        user_id = self.user_service.create_user(
            admin_username, admin_password, admin_email
        )

        # Set up default preferences
        self.pref_service.setup_default_preferences(user_id)

        # Set up default schedule
        self.scheduler_service.update_schedule(
            user_id, "daily", "08:00", True
        )

        return user_id

    def run_manual_job(self, user_id: int, callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Run a manual scraping and analysis job.

        Args:
            user_id: The user's ID
            callback: Optional callback function for status updates

        Returns:
            result: Job execution details including job_id for status tracking
        """
        job_id = self.scheduler_service.run_job_now(user_id, callback)

        return {
            "status": "started",
            "job_id": job_id,
            "user_id": user_id
        }

    def update_user_preferences(self, user_id: int, preferences: Dict[str, Dict[str, Any]]) -> None:
        """
        Update multiple preference categories for a user.

        Args:
            user_id: The user's ID
            preferences: Dictionary of category to preference dictionary
        """
        for category, prefs in preferences.items():
            self.pref_service.update_preference_category(user_id, category, prefs)

        # If scheduling preferences were updated, refresh the scheduler
        if 'scheduling' in preferences:
            schedule_prefs = preferences['scheduling']
            if 'schedule_type' in schedule_prefs and 'execution_time' in schedule_prefs:
                self.scheduler_service.update_schedule(
                    user_id,
                    schedule_prefs['schedule_type'],
                    schedule_prefs['execution_time'],
                    schedule_prefs.get('notifications_enabled', True)
                )

    def get_user_dashboard_data(self, user_id: int) -> Dict[str, Any]:
        """
        Get all data needed for the user dashboard.

        Args:
            user_id: The user's ID

        Returns:
            dashboard_data: Complete dashboard data
        """
        # Get user information
        user = self.user_service.get_user_by_id(user_id)

        # Get job statistics
        job_stats = self.db_service.get_job_statistics(user_id)

        # Get schedule information
        schedule = self.db_service.get_user_schedule(user_id)

        # Get recent jobs in different states
        recent_relevant = self.db_service.get_jobs_by_state(
            user_id, "relevant", 5
        )

        recent_saved = self.db_service.get_jobs_by_state(
            user_id, "saved", 5
        )

        recent_applied = self.db_service.get_jobs_by_state(
            user_id, "applied", 5
        )

        # Get running jobs
        running_jobs = self.scheduler_service.get_all_job_statuses(user_id)

        return {
            "user": {
                "username": user["username"],
                "email": user["email"],
                "last_login": user["last_login"]
            },
            "job_stats": job_stats,
            "schedule": schedule,
            "recent_jobs": {
                "relevant": recent_relevant,
                "saved": recent_saved,
                "applied": recent_applied
            },
            "running_jobs": running_jobs
        }

    def get_job_details(self, job_id: str, user_id: int) -> Dict[str, Any]:
        """
        Get detailed information about a job.

        Args:
            job_id: The job's LinkedIn ID
            user_id: The user's ID

        Returns:
            job_details: Complete job details
        """
        # Get job information
        job = self.db_service.get_job_by_id(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        # Get job analysis
        analysis = self.db_service.get_job_analysis(job_id, user_id)

        # Get job state history
        state_history = self.db_service.get_job_state_history(job_id, user_id)

        # Get current state
        current_state = self.db_service.get_current_job_state(job_id, user_id)

        # Mark job as viewed if not already
        if current_state and current_state["state"] in ["relevant", "saved"]:
            self.db_service.add_job_state(job_id, user_id, "viewed")

        return {
            "job": job,
            "analysis": analysis,
            "state_history": state_history,
            "current_state": current_state
        }

    def update_job_state(self, job_id: str, user_id: int, new_state: str, notes: str = None) -> Dict[str, Any]:
        """
        Update the state of a job.

        Args:
            job_id: The job's LinkedIn ID
            user_id: The user's ID
            new_state: The new state to set
            notes: Optional notes to add

        Returns:
            result: Status and updated state information
        """
        # Validate state
        if new_state not in ["saved", "applied", "rejected"]:
            raise ValueError(f"Invalid state transition: {new_state}")

        # Add new state
        self.db_service.add_job_state(job_id, user_id, new_state, notes)

        # Get updated state
        current_state = self.db_service.get_current_job_state(job_id, user_id)

        return {
            "status": "success",
            "job_id": job_id,
            "state": current_state
        }

    def search_jobs(self, user_id: int, query: str, states: List[str] = None,
                    limit: int = 20, offset: int = 0) -> Dict[str, Any]:
        """
        Search for jobs based on query and states.

        Args:
            user_id: The user's ID
            query: Search query
            states: List of states to include, or None for all
            limit: Maximum number of results
            offset: Offset for pagination

        Returns:
            search_results: Search results with pagination info
        """
        # Set up base query
        sql_query = """
        SELECT j.*, s.state, s.state_timestamp
        FROM job_listings j
        JOIN job_states s ON j.job_id = s.job_id
        WHERE s.user_id = ?
        """
        params = [user_id]

        # Add search condition if query is provided
        if query and query.strip():
            sql_query += """
            AND (
                j.title LIKE ? OR 
                j.company LIKE ? OR 
                j.description LIKE ? OR
                j.location LIKE ?
            )
            """
            search_term = f"%{query.strip()}%"
            params.extend([search_term, search_term, search_term, search_term])

        # Add state filter if provided
        if states and len(states) > 0:
            placeholders = ', '.join(['?'] * len(states))
            sql_query += f" AND s.state IN ({placeholders})"
            params.extend(states)

        # Add grouping and ordering
        sql_query += """
        GROUP BY j.job_id  -- Get only the latest state for each job
        ORDER BY s.state_timestamp DESC
        """

        # Get count query (for pagination)
        count_query = f"SELECT COUNT(*) as count FROM ({sql_query})"
        count_result = self.db_service.db_manager.get_one(count_query, tuple(params))
        total_count = count_result['count'] if count_result else 0

        # Add pagination
        sql_query += "LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        # Execute query
        results = self.db_service.db_manager.execute_query(sql_query, tuple(params))

        return {
            "results": results,
            "pagination": {
                "total": total_count,
                "limit": limit,
                "offset": offset,
                "next_offset": offset + limit if offset + limit < total_count else None,
                "prev_offset": max(0, offset - limit) if offset > 0 else None
            }
        }

    def reanalyze_job(self, job_id: str, user_id: int) -> Dict[str, Any]:
        """
        Reanalyze a job with current preferences.

        Args:
            job_id: The job's LinkedIn ID
            user_id: The user's ID

        Returns:
            result: Analysis result
        """
        return self.analysis_service.reanalyze_job(job_id, user_id)

    def stop_services(self) -> None:
        """Stop all background services when shutting down."""
        self.scheduler_service.stop()

        # Close database connections
        self.db_service.db_manager.close_all()

    def delete_job(self, job_id: str, user_id: int) -> Dict[str, Any]:
        """
        Completely delete a job from the system.

        Args:
            job_id: The job's LinkedIn ID
            user_id: The user's ID requesting the deletion

        Returns:
            result: Status of the deletion operation
        """
        try:
            # First check if job exists and user has access to it
            job_details = self.get_job_details(job_id, user_id)

            # If we get here, the job exists and user has access
            # Proceed with deletion
            success = self.db_service.delete_job(job_id, user_id)

            if success:
                logger.info(f"Job {job_id} successfully deleted by user {user_id}")
                return {
                    "status": "success",
                    "message": "Job has been permanently deleted"
                }
            else:
                logger.warning(f"Failed to delete job {job_id} for user {user_id}")
                return {
                    "status": "error",
                    "message": "Failed to delete job"
                }
        except ValueError as e:
            # Job not found or user doesn't have access
            logger.warning(
                f"User {user_id} attempted to delete job {job_id} but it doesn't exist or they don't have access")
            return {
                "status": "error",
                "message": str(e)
            }
        except Exception as e:
            logger.error(f"Error deleting job {job_id} for user {user_id}: {str(e)}")
            return {
                "status": "error",
                "message": f"Unexpected error: {str(e)}"
            }
