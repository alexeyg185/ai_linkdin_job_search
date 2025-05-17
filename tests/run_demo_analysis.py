#!/usr/bin/env python3
"""
A test script to analyze a specific job in the database.
This script directly uses the AnalysisService to analyze a job.
"""

import sys
import os
import logging
from typing import Dict, Any

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Add project root to path if needed
# sys.path.append('/path/to/your/project/root')

from services.analysis_service import AnalysisService
from services.database_service import DatabaseService
from services.preference_service import PreferenceService

def analyze_specific_job(job_id: str, user_id: int) -> Dict[str, Any]:
    """
    Analyze a specific job for a user.
    
    Args:
        job_id: The job's LinkedIn ID
        user_id: The user's ID
        
    Returns:
        result: Analysis result
    """
    analysis_service = AnalysisService()
    db_service = DatabaseService()
    
    # Get the job
    job = db_service.get_job_by_id(job_id)
    if not job:
        logger.error(f"Job not found: {job_id}")
        return {"error": "Job not found"}
    
    logger.info(f"Found job: {job['title']} at {job['company']}")
    
    # Create a callback function to log progress
    def progress_callback(event: str, data: Dict[str, Any]) -> None:
        logger.info(f"Event: {event}, Data: {data}")
    
    # Reanalyze the job
    result = analysis_service.reanalyze_job(job_id, user_id)
    logger.info(f"Analysis result: {result}")
    return result

def analyze_random_job(user_id: int) -> Dict[str, Any]:
    """
    Analyze a random job for a user.
    
    Args:
        user_id: The user's ID
        
    Returns:
        result: Analysis result
    """
    db_service = DatabaseService()
    
    # Get a job that has a state for this user
    query = """
    SELECT DISTINCT j.job_id, j.title, j.company
    FROM job_listings j
    JOIN job_states s ON j.job_id = s.job_id
    WHERE s.user_id = ?
    LIMIT 1
    """
    job = db_service.db_manager.get_one(query, (user_id,))
    
    if not job:
        logger.error(f"No jobs found for user {user_id}")
        return {"error": "No jobs found"}
    
    logger.info(f"Selected job: {job['title']} at {job['company']}")
    
    # Analyze this job
    return analyze_specific_job(job['job_id'], user_id)

if __name__ == "__main__":
    # You can modify these values as needed
    USER_ID = 1  # Default to first user
    
    # Check if job_id is provided as command line argument
    if len(sys.argv) > 1:
        JOB_ID = sys.argv[1]
        logger.info(f"Analyzing specific job: {JOB_ID}")
        result = analyze_specific_job(JOB_ID, USER_ID)
    else:
        logger.info(f"Analyzing random job for user {USER_ID}")
        result = analyze_random_job(USER_ID)
    
    # Print final result
    print("\nFinal Analysis Result:")
    print("======================")
    if result.get("status") == "success":
        print(f"Job: {result.get('job_id')}")
        print(f"Relevance Score: {result.get('relevance_score', 0) * 100:.2f}%")
        print(f"Is Relevant: {result.get('is_relevant', False)}")
        
        # Print analysis details if available
        analysis = result.get("analysis", {})
        if analysis.get("full_analysis"):
            full_analysis = analysis["full_analysis"]
            print("\nFull Analysis:")
            print(f"Required Skills Found: {', '.join(full_analysis.get('required_skills_found', []))}")
            print(f"Preferred Skills Found: {', '.join(full_analysis.get('preferred_skills_found', []))}")
            print(f"Missing Required Skills: {', '.join(full_analysis.get('missing_required_skills', []))}")
            print(f"\nReasoning: {full_analysis.get('reasoning', 'Not provided')}")
    else:
        print(f"Error: {result.get('error', 'Unknown error')}")
