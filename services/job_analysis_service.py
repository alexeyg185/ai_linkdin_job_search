import logging
from typing import Dict, Any, Optional, Callable, List, Tuple

from constants.analysis import AnalysisConstants
from database.models import JobStates
from services.analysis_strategy import AnalysisStrategy
from services.preference_service import PreferenceService

logger = logging.getLogger(__name__)


class JobAnalysisService:
    """Service for analyzing job listings using LLM with strategy pattern."""

    def __init__(self,
                 title_analyzer: AnalysisStrategy,
                 description_analyzer: AnalysisStrategy,
                 db_service=None):
        logger.info("Initializing JobAnalysisService")
        self.title_analyzer = title_analyzer
        self.description_analyzer = description_analyzer
        self.db_service = db_service
        logger.info("JobAnalysisService initialized successfully")

    def analyze_job(self, job: Dict[str, Any], user_id: Optional[int] = None,
                    analysis_prefs: Optional[Dict[str, Any]] = None,
                    job_titles: Optional[List[str]] = None,
                    store_results: bool = True) -> Dict[str, Any]:
        logger.info(f"Entering analyze_job(job_id={job.get('job_id')}, user_id={user_id})")
        try:
            if analysis_prefs is None:
                analysis_prefs = {}
                logger.debug("No analysis_prefs provided, using empty dict")

            # Get title relevance and analysis
            title_relevance, title_analysis = self._analyze_job_title(job, analysis_prefs, job_titles)
            title_match_strictness = analysis_prefs.get('title_match_strictness',
                                                        AnalysisConstants.DEFAULT_TITLE_MATCH_STRICTNESS)
            threshold = title_match_strictness

            # Handle based on title relevance
            if title_relevance >= threshold:
                return self._handle_full_analysis(job, user_id, title_relevance, title_analysis,
                                                  analysis_prefs, job_titles, store_results)
            else:
                return self._handle_skipped_analysis(job, user_id, title_relevance, title_analysis,
                                                     analysis_prefs, store_results)
        except Exception as e:
            logger.exception(f"Error analyzing job {job.get('job_id', 'unknown')}")
            return {
                "job_id": job.get('job_id', 'unknown'),
                "title": job.get('title', 'unknown'),
                "company": job.get('company', 'unknown'),
                "status": "error",
                "error": str(e)
            }

    def _analyze_job_title(self, job: Dict[str, Any], analysis_prefs: Dict[str, Any],
                           job_titles: Optional[List[str]]) -> Tuple[float, Dict[str, Any]]:
        """Analyze job title and return relevance score and analysis details"""
        title_relevance, title_analysis = self.title_analyzer.analyze(
            title=job['title'],
            company=job['company'],
            analysis_prefs=analysis_prefs,
            job_titles=job_titles
        )
        logger.info(f"Title relevance={title_relevance}, analysis={title_analysis}")
        return title_relevance, title_analysis

    def _handle_full_analysis(self, job: Dict[str, Any], user_id: Optional[int],
                              title_relevance: float, title_analysis: Dict[str, Any],
                              analysis_prefs: Dict[str, Any], job_titles: Optional[List[str]],
                              store_results: bool) -> Dict[str, Any]:
        """Handle case where title is relevant enough for full analysis"""
        logger.info(f"Proceeding with description analysis for job {job['job_id']}")

        # Analyze description
        relevance_score, full_analysis = self.description_analyzer.analyze(
            title=job['title'],
            company=job['company'],
            description=job['description'],
            analysis_prefs=analysis_prefs,
            job_titles=job_titles
        )
        logger.info(f"Description relevance={relevance_score}, analysis={full_analysis}")

        # Create analysis details
        details = {
            "title_analysis": title_analysis,
            "title_relevance": title_relevance,
            "full_analysis": full_analysis,
            "relevance_score": relevance_score
        }

        # Store results if needed
        if store_results and self.db_service and user_id:
            self._store_analysis_and_update_state(job['job_id'], user_id, relevance_score, details, analysis_prefs)

        # Determine if job is relevant based on threshold
        threshold = analysis_prefs.get('relevance_threshold', AnalysisConstants.DEFAULT_RELEVANCE_THRESHOLD)
        is_relevant = relevance_score >= threshold

        # Create result
        result = self._create_analysis_result(job, relevance_score, is_relevant, details)
        logger.info(f"Exiting analyze_job with result: {result}")
        return result

    def _handle_skipped_analysis(self, job: Dict[str, Any], user_id: Optional[int],
                                 title_relevance: float, title_analysis: Dict[str, Any],
                                 analysis_prefs: Dict[str, Any], store_results: bool) -> Dict[str, Any]:
        """Handle case where title relevance is too low to proceed with full analysis"""
        logger.info(f"Skipping full analysis for job {job['job_id']} due to low title relevance")

        # Create analysis details
        details = {
            "title_analysis": title_analysis,
            "title_relevance": title_relevance,
            "full_analysis": None,
            "relevance_score": title_relevance,
            "skip_reason": "Title not relevant"
        }

        # Store results if needed
        if store_results and self.db_service and user_id:
            self._store_analysis_and_update_state(job['job_id'], user_id, title_relevance, details, analysis_prefs)

        # Create result
        result = self._create_analysis_result(job, title_relevance, False, details)
        logger.info(f"Exiting analyze_job with skip result: {result}")
        return result

    def _create_analysis_result(self, job: Dict[str, Any], relevance_score: float,
                                is_relevant: bool, details: Dict[str, Any]) -> Dict[str, Any]:
        """Create a standardized analysis result dictionary"""
        result = {
            "job_id": job['job_id'],
            "title": job['title'],
            "company": job['company'],
            "relevance_score": relevance_score,
            "is_relevant": is_relevant,
            "analysis_details": details
        }
        return result

    def _store_analysis_and_update_state(self, job_id: str, user_id: int,
                                         relevance_score: float, details: Dict[str, Any],
                                         analysis_prefs: Dict[str, Any]) -> None:
        """Store analysis results and update job states in the database"""
        if not self.db_service or not user_id:
            return

        # Store analysis
        logger.debug(f"Storing analysis result to DB for job {job_id}")
        self.db_service.add_job_analysis(job_id, user_id, relevance_score, details)

        # Update job states
        self._update_job_states(job_id, user_id, relevance_score, analysis_prefs)

    def _update_job_states(self, job_id: str, user_id: int,
                           relevance_score: float, analysis_prefs: Dict[str, Any]) -> None:
        logger.info(f"Updating job states for job {job_id}, user {user_id}")
        if not self.db_service:
            logger.debug("No db_service provided, skipping state update")
            return
        self.db_service.add_job_state(job_id, user_id, JobStates.STATE_ANALYZED)
        threshold = analysis_prefs.get('relevance_threshold', AnalysisConstants.DEFAULT_RELEVANCE_THRESHOLD)
        state = JobStates.STATE_RELEVANT if relevance_score >= threshold else JobStates.STATE_IRRELEVANT
        self.db_service.add_job_state(job_id, user_id, state)
        logger.info(f"Job {job_id} state updated to {state}")

    def analyze_queued_jobs(self, user_id: int, limit: int = 10,
                            callback: Optional[Callable] = None) -> Dict[str, Any]:
        logger.info(f"Entering analyze_queued_jobs(user_id={user_id}, limit={limit})")
        if not self.db_service:
            logger.error("Database service is required for analyze_queued_jobs")
            raise ValueError("Database service is required for analyze_queued_jobs")

        # Get queued jobs
        queued = self.db_service.get_jobs_by_state(user_id, JobStates.STATE_QUEUED_FOR_ANALYSIS, limit)
        logger.info(f"Found {len(queued)} queued jobs")

        results = {"total": len(queued), "analyzed": 0, "relevant": 0, "not_relevant": 0, "errors": 0, "skipped": 0}

        if callback:
            callback("start", {"total_jobs": len(queued)})

        # Get preferences and job titles
        analysis_prefs, job_titles = self._get_user_preferences(user_id)

        # Process each job
        for job in queued:
            self._process_queued_job(job, user_id, analysis_prefs, job_titles, results, callback)

        if callback:
            callback("complete", results)
        logger.info(f"Exiting analyze_queued_jobs with results: {results}")
        return results

    def _get_user_preferences(self, user_id: int) -> Tuple[Dict[str, Any], List[str]]:
        """Get user preferences and job titles for analysis"""
        pref_service = PreferenceService()
        analysis_prefs = pref_service.get_preferences_by_category(user_id, PreferenceService.CATEGORY_ANALYSIS)
        search_prefs = pref_service.get_preferences_by_category(user_id, PreferenceService.CATEGORY_SEARCH)
        job_titles = search_prefs.get('job_titles', [])
        return analysis_prefs, job_titles

    def _process_queued_job(self, job: Dict[str, Any], user_id: int,
                            analysis_prefs: Dict[str, Any], job_titles: List[str],
                            results: Dict[str, Any], callback: Optional[Callable]) -> None:
        """Process a single queued job for analysis"""
        try:
            # Check for existing analysis
            existing = self.db_service.get_job_analysis(job['job_id'], user_id)
            if existing:
                logger.info(f"Job {job['job_id']} already analyzed, skipping")
                self._handle_already_analyzed_job(job, user_id, existing, analysis_prefs, results)
                return

            # Update job state and notify
            self.db_service.add_job_state(job['job_id'], user_id, JobStates.STATE_ANALYZING)
            if callback:
                callback("analyzing", job)

            # Analyze the job
            analysis = self.analyze_job(job=job, user_id=user_id, analysis_prefs=analysis_prefs,
                                        job_titles=job_titles, store_results=True)

            # Update results
            self._update_analysis_results(analysis, results)

            if callback:
                callback("analyzed", analysis)
        except Exception as e:
            logger.exception(f"Error in analyze_queued_jobs for job {job['job_id']}")
            results['errors'] += 1
            if callback:
                callback("error", {"job_id": job['job_id'], "error": str(e)})

    def _update_analysis_results(self, analysis: Dict[str, Any], results: Dict[str, Any]) -> None:
        """Update the results dictionary based on analysis outcome"""
        results['analyzed'] += 1
        if analysis.get('is_relevant'):
            results['relevant'] += 1
        else:
            results['not_relevant'] += 1

    def _handle_already_analyzed_job(self, job: Dict[str, Any], user_id: int,
                                     existing_analysis: Dict[str, Any],
                                     analysis_prefs: Dict[str, Any],
                                     results: Dict[str, Any]) -> None:
        logger.info(f"Handling already analyzed job {job['job_id']} for user {user_id}")
        self.db_service.add_job_state(job['job_id'], user_id, JobStates.STATE_ANALYZED)
        threshold = analysis_prefs.get('relevance_threshold', AnalysisConstants.DEFAULT_RELEVANCE_THRESHOLD)
        state = JobStates.STATE_RELEVANT if existing_analysis[
                                                'relevance_score'] >= threshold else JobStates.STATE_IRRELEVANT
        self.db_service.add_job_state(job['job_id'], user_id, state)
        results['analyzed'] += 1
        results['skipped'] += 1
        if state == JobStates.STATE_RELEVANT:
            results['relevant'] += 1
        else:
            results['not_relevant'] += 1

    def reanalyze_job(self, job_id: str, user_id: int) -> Dict[str, Any]:
        logger.info(f"Entering reanalyze_job(job_id={job_id}, user_id={user_id})")
        if not self.db_service:
            logger.error("Database service is required for reanalyze_job")
            raise ValueError("Database service is required for reanalyze_job")

        # Get job by ID
        job = self._get_job_by_id_or_raise(job_id)

        # Get preferences and job titles
        analysis_prefs, job_titles = self._get_user_preferences(user_id)

        # Update job state and perform analysis
        self.db_service.add_job_state(job_id, user_id, JobStates.STATE_ANALYZING)

        try:
            result = self.analyze_job(job=job, user_id=user_id, analysis_prefs=analysis_prefs,
                                      job_titles=job_titles, store_results=True)
            # Add status field for UI compatibility
            result["status"] = "success"
            logger.info(f"Exiting reanalyze_job with result: {result}")
            return result
        except Exception as e:
            logger.exception(f"Error in reanalyze_job for job {job_id}")
            # Return error with status for UI compatibility
            return {
                "status": "error",
                "job_id": job_id,
                "error": str(e)
            }

    def _get_job_by_id_or_raise(self, job_id: str) -> Dict[str, Any]:
        """Get job by ID or raise exception if not found"""
        job = self.db_service.get_job_by_id(job_id)
        if not job:
            logger.error(f"Job not found: {job_id}")
            raise ValueError(f"Job not found: {job_id}")
        return job