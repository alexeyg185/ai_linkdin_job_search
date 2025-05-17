"""
Database service module for handling database operations.
This service provides higher-level methods for database operations related to specific
entity types in the application.
"""

import datetime
import logging
from typing import Dict, List, Any, Optional, Set, Tuple
import json

from database.db_manager import DatabaseManager
from database.models import (
    Users, UserPreferences, JobListings, JobAnalysis,
    JobStates, ScheduleSettings
)


class DatabaseService:
    """
    Service for database operations that provides entity-specific methods
    to simplify data access and manipulation.
    """

    def __init__(self):
        """Initialize the database service."""
        self.db_manager = DatabaseManager()

    # Job Listings Methods

    def add_job_listing(self, job_data: Dict[str, Any]) -> int:
        """
        Add a new job listing to the database.

        Args:
            job_data: Dictionary containing job listing data
                Required keys: job_id, title, company, url
                Optional keys: location, description, source_term

        Returns:
            internal_id: The internal ID of the new job listing

        Raises:
            ValueError: If required fields are missing or if job_id already exists
        """
        # Validate required fields
        required_fields = {'job_id', 'title', 'company', 'url'}
        missing_fields = required_fields - set(job_data.keys())
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

        # Check if job already exists
        existing_job = self.get_job_by_id(job_data['job_id'])
        if existing_job:
            raise ValueError(f"Job with ID {job_data['job_id']} already exists")

        # Prepare job data
        job_fields = {
            'job_id': job_data['job_id'],
            'title': job_data['title'],
            'company': job_data['company'],
            'location': job_data.get('location', ''),
            'description': job_data.get('description', ''),
            'url': job_data['url'],
            'source_term': job_data.get('source_term', ''),
            'scraped_at': datetime.datetime.now()
        }

        # Insert job listing
        placeholders = ', '.join(['?'] * len(job_fields))
        columns = ', '.join(job_fields.keys())
        values = tuple(job_fields.values())

        query = f"""
        INSERT INTO {JobListings.TABLE_NAME} ({columns})
        VALUES ({placeholders})
        """

        return self.db_manager.execute_write(query, values)

    def get_job_by_id(self, job_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a job listing by its job_id.

        Args:
            job_id: The job's LinkedIn ID

        Returns:
            job: Job record if found, None otherwise
        """
        query = f"""
        SELECT *
        FROM {JobListings.TABLE_NAME}
        WHERE job_id = ?
        """
        return self.db_manager.get_one(query, (job_id,))

    def get_jobs_by_state(self, user_id: int, state: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        Get job listings by their current state for a specific user.
        Only returns jobs where the requested state is the most recent state.

        Args:
            user_id: The user's ID
            state: Job state to filter by
            limit: Maximum number of jobs to return
            offset: Offset for pagination

        Returns:
            jobs: List of job records
        """
        query = f"""
        SELECT j.*, s.state, s.state_timestamp, s.notes
        FROM {JobListings.TABLE_NAME} j
        JOIN {JobStates.TABLE_NAME} s ON j.job_id = s.job_id
        WHERE s.user_id = ? 
        AND s.state = ?
        AND s.state_timestamp = (
            SELECT MAX(state_timestamp)
            FROM {JobStates.TABLE_NAME}
            WHERE job_id = s.job_id AND user_id = s.user_id
        )
        ORDER BY s.state_timestamp DESC
        LIMIT ? OFFSET ?
        """
        return self.db_manager.execute_query(query, (user_id, state, limit, offset))
    def get_job_states_by_user(self, user_id: int) -> Dict[str, int]:
        """
        Get count of jobs in each state for a user.

        Args:
            user_id: The user's ID

        Returns:
            state_counts: Dictionary of state to count
        """
        query = f"""
        SELECT state, COUNT(*) as count
        FROM {JobStates.TABLE_NAME}
        WHERE user_id = ?
        GROUP BY state
        """
        results = self.db_manager.execute_query(query, (user_id,))

        # Convert to dictionary
        state_counts = {state: 0 for state in JobStates.VALID_STATES}
        for row in results:
            state_counts[row['state']] = row['count']

        return state_counts

    # Job States Methods

    def add_job_state(self, job_id: str, user_id: int, state: str, notes: str = None) -> int:
        """
        Add a new job state record.

        Args:
            job_id: The job's LinkedIn ID
            user_id: The user's ID
            state: The job state
            notes: Optional notes

        Returns:
            state_id: The ID of the new state record

        Raises:
            ValueError: If state is not valid
        """
        # Validate state
        if state not in JobStates.VALID_STATES:
            raise ValueError(f"Invalid state: {state}")

        # Insert state
        query = f"""
        INSERT INTO {JobStates.TABLE_NAME} (job_id, user_id, state, notes, state_timestamp)
        VALUES (?, ?, ?, ?, ?)
        """
        now = datetime.datetime.now()

        return self.db_manager.execute_write(query, (job_id, user_id, state, notes, now))

    def get_job_state_history(self, job_id: str, user_id: int) -> List[Dict[str, Any]]:
        """
        Get the state history for a job.

        Args:
            job_id: The job's LinkedIn ID
            user_id: The user's ID

        Returns:
            history: List of state records in chronological order
        """
        query = f"""
        SELECT *
        FROM {JobStates.TABLE_NAME}
        WHERE job_id = ? AND user_id = ?
        ORDER BY state_timestamp ASC
        """
        return self.db_manager.execute_query(query, (job_id, user_id))

    def get_current_job_state(self, job_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the current state for a job.

        Args:
            job_id: The job's LinkedIn ID
            user_id: The user's ID

        Returns:
            state: State record if found, None otherwise
        """
        query = f"""
        SELECT *
        FROM {JobStates.TABLE_NAME}
        WHERE job_id = ? AND user_id = ?
        ORDER BY state_timestamp DESC
        LIMIT 1
        """
        return self.db_manager.get_one(query, (job_id, user_id))

    # Job Analysis Methods

    def add_job_analysis(self, job_id: str, user_id: int,
                         relevance_score: float, analysis_details: Dict[str, Any]) -> int:
        """
        Add a new job analysis record.

        Args:
            job_id: The job's LinkedIn ID
            user_id: The user's ID
            relevance_score: Score indicating job relevance (0-1)
            analysis_details: Dictionary with analysis results

        Returns:
            analysis_id: The ID of the new analysis record
        """
        # Serialize analysis details
        analysis_json = JobAnalysis.json_serialize(analysis_details)

        # Insert analysis
        query = f"""
        INSERT OR REPLACE INTO {JobAnalysis.TABLE_NAME} 
        (job_id, user_id, relevance_score, analysis_details, analyzed_at)
        VALUES (?, ?, ?, ?, ?)
        """
        now = datetime.datetime.now()

        return self.db_manager.execute_write(
            query,
            (job_id, user_id, relevance_score, analysis_json, now)
        )

    def get_job_analysis(self, job_id: str, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get the analysis for a job.

        Args:
            job_id: The job's LinkedIn ID
            user_id: The user's ID

        Returns:
            analysis: Analysis record if found, None otherwise
        """
        query = f"""
        SELECT *
        FROM {JobAnalysis.TABLE_NAME}
        WHERE job_id = ? AND user_id = ?
        """
        result = self.db_manager.get_one(query, (job_id, user_id))

        if result:
            # Deserialize analysis details
            result['analysis_details'] = JobAnalysis.json_deserialize(result['analysis_details'])

        return result

    # Scheduling Methods

    def get_user_schedule(self, user_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a user's schedule settings.

        Args:
            user_id: The user's ID

        Returns:
            schedule: Schedule settings if found, None otherwise
        """
        query = f"""
        SELECT *
        FROM {ScheduleSettings.TABLE_NAME}
        WHERE user_id = ?
        """
        return self.db_manager.get_one(query, (user_id,))

    def update_user_schedule(self, user_id: int, schedule_type: str,
                             execution_time: str, enabled: bool = True) -> int:
        """
        Update a user's schedule settings.

        Args:
            user_id: The user's ID
            schedule_type: daily, weekly, or custom
            execution_time: Time or cron expression
            enabled: Whether the schedule is enabled

        Returns:
            setting_id: The ID of the updated schedule settings

        Raises:
            ValueError: If schedule_type is not valid
        """
        # Validate schedule type
        if schedule_type not in ScheduleSettings.VALID_TYPES:
            raise ValueError(f"Invalid schedule type: {schedule_type}")

        # Check if schedule exists
        existing = self.get_user_schedule(user_id)

        if existing:
            # Update existing schedule
            query = f"""
            UPDATE {ScheduleSettings.TABLE_NAME}
            SET schedule_type = ?, execution_time = ?, enabled = ?
            WHERE user_id = ?
            """
            self.db_manager.execute_write(
                query,
                (schedule_type, execution_time, enabled, user_id)
            )
            return existing['setting_id']
        else:
            # Insert new schedule
            query = f"""
            INSERT INTO {ScheduleSettings.TABLE_NAME}
            (user_id, schedule_type, execution_time, enabled)
            VALUES (?, ?, ?, ?)
            """
            return self.db_manager.execute_write(
                query,
                (user_id, schedule_type, execution_time, enabled)
            )

    def update_last_run(self, user_id: int) -> None:
        """
        Update the last_run timestamp for a user's schedule.

        Args:
            user_id: The user's ID
        """
        query = f"""
        UPDATE {ScheduleSettings.TABLE_NAME}
        SET last_run = ?
        WHERE user_id = ?
        """
        now = datetime.datetime.now()
        self.db_manager.execute_write(query, (now, user_id))

    def get_active_schedules(self) -> List[Dict[str, Any]]:
        """
        Get all active user schedules.

        Returns:
            schedules: List of active schedule settings
        """
        query = f"""
        SELECT s.*, u.username
        FROM {ScheduleSettings.TABLE_NAME} s
        JOIN {Users.TABLE_NAME} u ON s.user_id = u.user_id
        WHERE s.enabled = 1
        """
        return self.db_manager.execute_query(query)

    # Statistics Methods

    def get_job_statistics(self, user_id: int) -> Dict[str, Any]:
        """
        Get comprehensive job statistics for a user.

        Args:
            user_id: The user's ID

        Returns:
            stats: Dictionary with various statistics
        """
        stats = {
            'total_jobs': 0,
            'states': self.get_job_states_by_user(user_id),
            'by_company': {},
            'by_location': {},
            'recent_activity': []
        }

        # Get total jobs
        query = f"""
        SELECT COUNT(DISTINCT job_id) as count
        FROM {JobStates.TABLE_NAME}
        WHERE user_id = ?
        """
        result = self.db_manager.get_one(query, (user_id,))
        if result:
            stats['total_jobs'] = result['count']

        # Get jobs by company
        query = f"""
        SELECT j.company, COUNT(*) as count
        FROM {JobListings.TABLE_NAME} j
        JOIN {JobStates.TABLE_NAME} s ON j.job_id = s.job_id
        WHERE s.user_id = ?
        GROUP BY j.company
        ORDER BY count DESC
        LIMIT 10
        """
        results = self.db_manager.execute_query(query, (user_id,))
        for row in results:
            stats['by_company'][row['company']] = row['count']

        # Get jobs by location
        query = f"""
        SELECT j.location, COUNT(*) as count
        FROM {JobListings.TABLE_NAME} j
        JOIN {JobStates.TABLE_NAME} s ON j.job_id = s.job_id
        WHERE s.user_id = ? AND j.location != ''
        GROUP BY j.location
        ORDER BY count DESC
        LIMIT 10
        """
        results = self.db_manager.execute_query(query, (user_id,))
        for row in results:
            stats['by_location'][row['location']] = row['count']

        # Get recent activity
        query = f"""
        SELECT j.title, j.company, s.state, s.state_timestamp
        FROM {JobStates.TABLE_NAME} s
        JOIN {JobListings.TABLE_NAME} j ON s.job_id = j.job_id
        WHERE s.user_id = ?
        ORDER BY s.state_timestamp DESC
        LIMIT 10
        """
        stats['recent_activity'] = self.db_manager.execute_query(query, (user_id,))

        return stats

    def get_job_by_url(self, url: str) -> Optional[Dict[str, Any]]:
        """
        Get a job listing by its URL.

        Args:
            url: The job's URL

        Returns:
            job: Job record if found, None otherwise
        """
        query = f"""
        SELECT *
        FROM {JobListings.TABLE_NAME}
        WHERE url = ?
        """
        return self.db_manager.get_one(query, (url,))

    def delete_job(self, job_id: str, user_id: int = None) -> bool:
        """
        Delete a job and its related data from the database.

        Args:
            job_id: The job's LinkedIn ID
            user_id: Optional user ID to restrict deletion to user-specific data

        Returns:
            success: True if the operation was successful, False otherwise
        """
        # Use a transaction to ensure all related data is deleted atomically
        with self.db_manager.transaction() as conn:
            try:
                if user_id is not None:
                    # Delete only user-specific data

                    # Delete job states for this user
                    states_query = f"""
                    DELETE FROM {JobStates.TABLE_NAME}
                    WHERE job_id = ? AND user_id = ?
                    """
                    conn.execute(states_query, (job_id, user_id))

                    # Delete job analysis for this user
                    analysis_query = f"""
                    DELETE FROM {JobAnalysis.TABLE_NAME}
                    WHERE job_id = ? AND user_id = ?
                    """
                    conn.execute(analysis_query, (job_id, user_id))

                    # Check if any other users still have references to this job
                    ref_check_query = f"""
                    SELECT COUNT(*) as ref_count 
                    FROM (
                        SELECT user_id FROM {JobStates.TABLE_NAME} WHERE job_id = ?
                        UNION
                        SELECT user_id FROM {JobAnalysis.TABLE_NAME} WHERE job_id = ?
                    )
                    """
                    cursor = conn.execute(ref_check_query, (job_id, job_id))
                    ref_count = cursor.fetchone()[0]

                    # Only delete the job listing if no other users reference it
                    if ref_count == 0:
                        job_query = f"""
                        DELETE FROM {JobListings.TABLE_NAME}
                        WHERE job_id = ?
                        """
                        conn.execute(job_query, (job_id,))

                    # Operation is considered successful if we get here
                    return True
                else:
                    # Delete all data for this job regardless of user

                    # Delete job states first (due to foreign key constraints)
                    states_query = f"""
                    DELETE FROM {JobStates.TABLE_NAME}
                    WHERE job_id = ?
                    """
                    conn.execute(states_query, (job_id,))

                    # Delete job analysis
                    analysis_query = f"""
                    DELETE FROM {JobAnalysis.TABLE_NAME}
                    WHERE job_id = ?
                    """
                    conn.execute(analysis_query, (job_id,))

                    # Finally delete the job listing itself
                    job_query = f"""
                    DELETE FROM {JobListings.TABLE_NAME}
                    WHERE job_id = ?
                    """
                    result = conn.execute(job_query, (job_id,))

                    # Check if any rows were affected
                    return result.rowcount > 0

            except Exception as e:
                # Log the error and re-raise to trigger rollback
                logging.error(f"Error deleting job {job_id}: {str(e)}")
                raise