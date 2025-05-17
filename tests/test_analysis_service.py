from unittest.mock import MagicMock, patch

import services.analysis_service as asvc_mod
from utils.factories import JobAnalysisServiceFactory


class FakeJAS:
    def __init__(self, title_analyzer, description_analyzer, db_service):
        self.title_analyzer = title_analyzer
        self.description_analyzer = description_analyzer
        self.db_service = db_service
        self.analyze_queued_jobs = MagicMock(return_value={
            'total': 2,
            'analyzed': 2,
            'relevant': 1,
            'not_relevant': 1,
            'errors': 0,
            'skipped': 0
        })
        self.reanalyze_job = MagicMock(return_value={
            'status': 'success',
            'job_id': 'j1',
            'relevance_score': 0.4,
            'is_relevant': False
        })


class TestAnalysisService:
    """Unit tests for the AnalysisService compatibility wrapper."""

    def setup_method(self):
        # Create mocks
        self.mock_db_service = MagicMock()

        # Create mock for the LLM provider and client
        self.mock_client = MagicMock()
        self.mock_llm_provider = MagicMock()
        self.mock_llm_provider.client = self.mock_client

        # Create a mock for the JSON parser
        self.mock_json_parser = MagicMock()

        # Patch DatabaseService in the analysis_service module
        self.db_service_patcher = patch('services.analysis_service.DatabaseService',
                                        return_value=self.mock_db_service)
        self.db_service_patcher.start()

        # Patch JobAnalysisServiceFactory to return our fake class
        self.create_default_patcher = patch(
            'services.analysis_service.JobAnalysisServiceFactory.create_default_job_analysis_service')
        self.mock_create_default = self.create_default_patcher.start()

        # Create a FakeJAS with mocked title_analyzer and description_analyzer
        self.mock_title_analyzer = MagicMock()
        self.mock_title_analyzer.llm_provider = self.mock_llm_provider  # Set the llm_provider with our mock
        self.mock_title_analyzer.json_parser = self.mock_json_parser

        self.mock_description_analyzer = MagicMock()

        fake_jas = FakeJAS(self.mock_title_analyzer, self.mock_description_analyzer, self.mock_db_service)
        self.mock_create_default.return_value = fake_jas

        # Instantiate the service
        self.service = asvc_mod.AnalysisService()
        # Keep reference to the fake job analysis service
        self.mock_jas = self.service.job_analysis_service

    def teardown_method(self):
        # Restore originals and stop patchers
        self.db_service_patcher.stop()
        self.create_default_patcher.stop()

    def test_init(self):
        # Service should use our mocked DB and client
        assert self.service.db_service is self.mock_db_service
        # Fix: The service.client is now the mock_client, not the mock_llm_provider
        assert self.service.client is self.mock_client
        # Retry settings from compatibility wrapper
        assert self.service.max_retries == 3
        assert self.service.retry_delay == 2

    def test_analyze_queued_jobs_delegates(self):
        # Delegates to job_analysis_service.analyze_queued_jobs
        result = self.service.analyze_queued_jobs(10, limit=5, callback='cb')
        self.mock_jas.analyze_queued_jobs.assert_called_once_with(10, 5, 'cb')
        assert result == {
            'total': 2,
            'analyzed': 2,
            'relevant': 1,
            'not_relevant': 1,
            'errors': 0,
            'skipped': 0
        }

    def test_reanalyze_job_delegates(self):
        # Delegates to job_analysis_service.reanalyze_job
        result = self.service.reanalyze_job('jid', user_id=20)
        self.mock_jas.reanalyze_job.assert_called_once_with('jid', 20)
        assert result['status'] == 'success'
        assert result['job_id'] == 'j1'

    def test_analyze_title_delegates(self):
        # Mock the title analyzer strategy
        fake_ta = MagicMock()
        fake_ta.analyze.return_value = (0.9, {'a': 1})
        self.mock_jas.title_analyzer = fake_ta

        relevance, analysis = self.service._analyze_title(
            't', 'c', {'pref': 1}, ['T']
        )
        fake_ta.analyze.assert_called_once_with(
            title='t', company='c', analysis_prefs={'pref': 1}, job_titles=['T']
        )
        assert relevance == 0.9
        assert analysis == {'a': 1}

    def test_analyze_description_delegates(self):
        # Mock the description analyzer strategy
        fake_da = MagicMock()
        fake_da.analyze.return_value = (0.8, {'b': 2})
        self.mock_jas.description_analyzer = fake_da

        relevance, analysis = self.service._analyze_description(
            't', 'c', 'desc', {'pref': 1}, ['T']
        )
        fake_da.analyze.assert_called_once_with(
            title='t', company='c', description='desc', analysis_prefs={'pref': 1}, job_titles=['T']
        )
        assert relevance == 0.8
        assert analysis == {'b': 2}