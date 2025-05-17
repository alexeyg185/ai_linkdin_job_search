import logging
from typing import Dict, Any, Optional, Callable, List, Tuple

from services.database_service import DatabaseService
from utils.factories import JobAnalysisServiceFactory

logger = logging.getLogger(__name__)


class AnalysisService:
    """
    Compatibility wrapper for the original AnalysisService.
    Delegates to JobAnalysisService while maintaining the old interface.
    """

    def __init__(self):
        logger.info("Initializing AnalysisService")
        # Create dependencies
        self.db_service = DatabaseService()

        # Create the underlying service using factory with default configuration
        self.job_analysis_service = JobAnalysisServiceFactory.create_default_job_analysis_service()

        # Save components for direct mocking in tests
        self.client = self.job_analysis_service.title_analyzer.llm_provider.client
        self.json_parser = self.job_analysis_service.title_analyzer.json_parser
        self.max_retries = 3
        self.retry_delay = 2
        logger.info("AnalysisService initialized successfully")

    def analyze_queued_jobs(self, user_id: int, limit: int = 10,
                            callback: Optional[Callable] = None) -> Dict[str, Any]:
        logger.info(f"Entering analyze_queued_jobs(user_id={user_id}, limit={limit})")
        try:
            result = self.job_analysis_service.analyze_queued_jobs(user_id, limit, callback)
            logger.info(f"Exiting analyze_queued_jobs with result: {result}")
            return result
        except Exception as e:
            logger.exception(f"Error in analyze_queued_jobs: {e}")
            raise

    def reanalyze_job(self, job_id: str, user_id: int) -> Dict[str, Any]:
        logger.info(f"Entering reanalyze_job(job_id={job_id}, user_id={user_id})")
        try:
            result = self.job_analysis_service.reanalyze_job(job_id, user_id)
            logger.info(f"Exiting reanalyze_job with result: {result}")
            return result
        except Exception as e:
            logger.exception(f"Error in reanalyze_job: {e}")
            raise

    def _analyze_title(self, title: str, company: str,
                       analysis_prefs: Dict[str, Any],
                       job_titles: Optional[List[str]] = None) -> Tuple[float, Dict[str, Any]]:
        logger.info(f"Entering _analyze_title(title={title}, company={company})")
        try:
            score, analysis = self.job_analysis_service.title_analyzer.analyze(
                title=title,
                company=company,
                analysis_prefs=analysis_prefs,
                job_titles=job_titles
            )
            logger.info(f"Title analysis score={score}, details={analysis}")
            return score, analysis
        except Exception as e:
            logger.exception(f"Error in _analyze_title: {e}")
            raise

    def _analyze_description(self, title: str, company: str, description: str,
                             analysis_prefs: Dict[str, Any],
                             job_titles: Optional[List[str]] = None) -> Tuple[float, Dict[str, Any]]:
        logger.info(f"Entering _analyze_description(title={title}, company={company})")
        try:
            score, analysis = self.job_analysis_service.description_analyzer.analyze(
                title=title,
                company=company,
                description=description,
                analysis_prefs=analysis_prefs,
                job_titles=job_titles
            )
            logger.info(f"Description analysis score={score}, details={analysis}")
            return score, analysis
        except Exception as e:
            logger.exception(f"Error in _analyze_description: {e}")
            raise
