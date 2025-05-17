import unittest
from unittest.mock import patch, MagicMock
import time

from app import app, orchestrator
from database.models import JobStates


class TestIntegration(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

        # Ensure a test user exists
        try:
            self.user_id = orchestrator.user_service.create_user(
                'testuser', 'Password123!', 'test@example.com'
            )
        except ValueError:
            user = orchestrator.user_service.get_user_by_username('testuser')
            self.user_id = user['user_id']

        # Set up test preferences
        test_prefs = {
            'search': {
                'job_titles': ['Test Engineer'],
                'locations': ['Remote'],
                'experience_levels': ['Entry level'],
                'remote_preference': True
            },
            'analysis': {
                'relevant_title_patterns': ['Test', 'QA'],
                'required_skills': ['Python', 'Testing'],
                'preferred_skills': ['Automation'],
                'relevance_threshold': 0.7,
                'title_match_strictness': 0.8
            }
        }
        orchestrator.update_user_preferences(self.user_id, test_prefs)

    def test_scrape_analyze_workflow(self):
        """Test the complete workflow of scraping and analyzing jobs."""
        # Mock the LinkedIn scraper to return test data
        with patch('services.scraper_service.LinkedinScraper') as mock_scraper_class:
            mock_scraper = MagicMock()
            mock_scraper_class.return_value = mock_scraper

            # When .run() is called, emit two fake jobs
            def run_and_emit(query):
                from linkedin_jobs_scraper.events import EventData
                test_jobs = [
                    {
                        'job_id': 'test_job_1',
                        'title': 'Test Engineer',
                        'company': 'Test Company',
                        'location': 'Remote',
                        'description': 'We need a Python test engineer with automation skills.',
                        'link': 'https://example.com/job1',
                        'query_keyword': 'Test Engineer'
                    },
                    {
                        'job_id': 'test_job_2',
                        'title': 'Senior Developer',
                        'company': 'Dev Corp',
                        'location': 'New York',
                        'description': 'Senior developer position.',
                        'link': 'https://example.com/job2',
                        'query_keyword': 'Test Engineer'
                    }
                ]
                for job in test_jobs:
                    ev = MagicMock(spec=EventData)
                    for k, v in job.items():
                        setattr(ev, k, v)
                    orchestrator.scraper_service._handle_data(ev)
                orchestrator.scraper_service._handle_end()

            mock_scraper.run.side_effect = run_and_emit

            # Mock LLM calls by patching OpenAIProvider
            from services.llm_provider import OpenAIProvider
            with patch('services.analysis_service.OpenAIProvider') as mock_provider_cls:
                # Prepare fake provider instance
                fake_provider = MagicMock()
                fake_provider.client = MagicMock()
                fake_provider.client.chat = MagicMock()
                fake_provider.client.chat.completions = MagicMock()

                # Title and description responses
                title_resp = MagicMock()
                title_resp.choices = [MagicMock(message=MagicMock(content=
                    '{"title_keywords":["Test"],"matches_pattern":true,"pattern_matched":"Test","estimated_relevance":0.9,"reasoning":"ok"}'
                ))]
                desc_resp = MagicMock()
                desc_resp.choices = [MagicMock(message=MagicMock(content=
                    '{"required_skills_found":["Python"],"preferred_skills_found":["Automation"],"missing_required_skills":["Testing"],"job_responsibilities":["Test automation"],"relevance_score":0.75,"reasoning":"ok"}'
                ))]

                # Return title, desc, title, desc...
                fake_provider.client.chat.completions.create.side_effect = [
                    title_resp, desc_resp, title_resp, desc_resp
                ]
                mock_provider_cls.return_value = fake_provider

                # Kick off the manual run
                result = orchestrator.run_manual_job(self.user_id)
                job_id = result['job_id']

                # Wait for background job to complete
                for _ in range(10):
                    status = orchestrator.scheduler_service.get_job_status(job_id)
                    if status and status['status'] in ('completed', 'failed'):
                        break
                    time.sleep(0.5)

                self.assertIsNotNone(status)
                self.assertEqual(status['status'], 'completed')

                # Verify scraping saved at least one NEW_SCRAPED job
                new_jobs = orchestrator.db_service.get_jobs_by_state(
                    self.user_id, JobStates.STATE_NEW_SCRAPED
                )
                self.assertGreaterEqual(len(new_jobs), 1)

                # Verify analysis occurred
                analyzed = orchestrator.db_service.get_jobs_by_state(
                    self.user_id, JobStates.STATE_ANALYZED
                )
                self.assertGreaterEqual(len(analyzed), 1)

                # Verify at least one relevant
                relevant = orchestrator.db_service.get_jobs_by_state(
                    self.user_id, JobStates.STATE_RELEVANT
                )
                self.assertGreaterEqual(len(relevant), 1)

    def test_job_state_transitions(self):
        """Test that job states transition correctly."""
        # Create a test job
        job_data = {
            'job_id': 'state_test_job',
            'title': 'Test Engineer',
            'company': 'Test Company',
            'url': 'https://example.com/job'
        }

        # Add job to database
        try:
            orchestrator.db_service.add_job_listing(job_data)
        except ValueError:
            pass  # Job already exists

        # Clean up: Delete any existing states for this test job
        # This ensures we start with a clean slate
        orchestrator.db_service.db_manager.execute_write(
            "DELETE FROM job_states WHERE job_id = ?",
            ('state_test_job',)
        )

        # Test state transitions
        states_to_test = [
            JobStates.STATE_NEW_SCRAPED,
            JobStates.STATE_QUEUED_FOR_ANALYSIS,
            JobStates.STATE_ANALYZING,
            JobStates.STATE_ANALYZED,
            JobStates.STATE_RELEVANT,
            JobStates.STATE_VIEWED,
            JobStates.STATE_SAVED,
            JobStates.STATE_APPLIED
        ]

        for state in states_to_test:
            orchestrator.db_service.add_job_state('state_test_job', self.user_id, state)
            current_state = orchestrator.db_service.get_current_job_state('state_test_job', self.user_id)
            self.assertEqual(current_state['state'], state)

        # Verify state history is recorded
        history = orchestrator.db_service.get_job_state_history('state_test_job', self.user_id)
        self.assertEqual(len(history), len(states_to_test))

    def test_job_deletion_integration(self):
        """Test the complete workflow of deleting a job from the system."""
        # Create a test job
        job_data = {
            'job_id': 'delete_integration_test_job',
            'title': 'Test Engineer',
            'company': 'Test Company',
            'url': 'https://example.com/job'
        }

        # Add job to database
        try:
            orchestrator.db_service.add_job_listing(job_data)
        except ValueError:
            pass  # Job already exists

        # Add job states
        orchestrator.db_service.add_job_state('delete_integration_test_job', self.user_id, JobStates.STATE_NEW_SCRAPED)
        orchestrator.db_service.add_job_state('delete_integration_test_job', self.user_id, JobStates.STATE_RELEVANT)

        # Add job analysis
        analysis_details = {
            'title_analysis': {'relevance': 0.8},
            'full_analysis': {'required_skills_found': ['Python']}
        }
        orchestrator.db_service.add_job_analysis(
            'delete_integration_test_job', self.user_id, 0.8, analysis_details
        )

        # Verify job exists before deletion
        job = orchestrator.db_service.get_job_by_id('delete_integration_test_job')
        self.assertIsNotNone(job)

        # Verify states exist
        states = orchestrator.db_service.get_job_state_history('delete_integration_test_job', self.user_id)
        self.assertGreaterEqual(len(states), 2)

        # Verify analysis exists
        analysis = orchestrator.db_service.get_job_analysis('delete_integration_test_job', self.user_id)
        self.assertIsNotNone(analysis)

        # Now delete the job
        result = orchestrator.delete_job('delete_integration_test_job', self.user_id)

        # Verify deletion was successful
        self.assertEqual(result['status'], 'success')

        # Verify states no longer exist
        states = orchestrator.db_service.get_job_state_history('delete_integration_test_job', self.user_id)
        self.assertEqual(len(states), 0)

        # Verify analysis no longer exists
        analysis = orchestrator.db_service.get_job_analysis('delete_integration_test_job', self.user_id)
        self.assertIsNone(analysis)

        # If this is the only user with references to this job, it should be gone
        job = orchestrator.db_service.get_job_by_id('delete_integration_test_job')
        self.assertIsNone(job)

    def test_job_deletion_multi_user(self):
        """Test that deleting a job preserves data for other users."""
        # Create two test users if they don't exist
        try:
            user1_id = orchestrator.user_service.create_user('testuser1', 'Password123!', 'test1@example.com')
        except ValueError:
            user = orchestrator.user_service.get_user_by_username('testuser1')
            user1_id = user['user_id']

        try:
            user2_id = orchestrator.user_service.create_user('testuser2', 'Password123!', 'test2@example.com')
        except ValueError:
            user = orchestrator.user_service.get_user_by_username('testuser2')
            user2_id = user['user_id']

        # Create a test job
        job_data = {
            'job_id': 'multi_user_test_job',
            'title': 'Shared Job',
            'company': 'Test Company',
            'url': 'https://example.com/job'
        }

        # Add job to database
        try:
            orchestrator.db_service.add_job_listing(job_data)
        except ValueError:
            pass  # Job already exists

        # Add job states and analysis for both users
        for user_id in [user1_id, user2_id]:
            # Add states
            orchestrator.db_service.add_job_state('multi_user_test_job', user_id, JobStates.STATE_NEW_SCRAPED)
            orchestrator.db_service.add_job_state('multi_user_test_job', user_id, JobStates.STATE_RELEVANT)

            # Add analysis
            analysis_details = {
                'title_analysis': {'relevance': 0.8},
                'full_analysis': {'required_skills_found': ['Python']}
            }
            orchestrator.db_service.add_job_analysis(
                'multi_user_test_job', user_id, 0.8, analysis_details
            )

        # Verify both users have data
        for user_id in [user1_id, user2_id]:
            states = orchestrator.db_service.get_job_state_history('multi_user_test_job', user_id)
            self.assertGreaterEqual(len(states), 2)

            analysis = orchestrator.db_service.get_job_analysis('multi_user_test_job', user_id)
            self.assertIsNotNone(analysis)

        # Delete the job for user1
        result = orchestrator.delete_job('multi_user_test_job', user1_id)

        # Verify deletion was successful
        self.assertEqual(result['status'], 'success')

        # Verify job still exists in the main table (shared resource)
        job = orchestrator.db_service.get_job_by_id('multi_user_test_job')
        self.assertIsNotNone(job)

        # Verify user1's data is gone
        states1 = orchestrator.db_service.get_job_state_history('multi_user_test_job', user1_id)
        self.assertEqual(len(states1), 0)

        analysis1 = orchestrator.db_service.get_job_analysis('multi_user_test_job', user1_id)
        self.assertIsNone(analysis1)

        # Verify user2's data still exists
        states2 = orchestrator.db_service.get_job_state_history('multi_user_test_job', user2_id)
        self.assertGreaterEqual(len(states2), 2)

        analysis2 = orchestrator.db_service.get_job_analysis('multi_user_test_job', user2_id)
        self.assertIsNotNone(analysis2)

        # Clean up - delete for user2 as well
        orchestrator.delete_job('multi_user_test_job', user2_id)

        # Now the job itself should be gone since all user references are removed
        job = orchestrator.db_service.get_job_by_id('multi_user_test_job')
        self.assertIsNone(job)

    def test_integration_job_state_progression(self):
        """Test that as jobs progress through states, old states are not returned in queries."""
        # Create a test job and add to database
        job_data = {
            'job_id': f'test_integration_{int(time.time())}',  # Use timestamp for uniqueness
            'title': 'Integration Test Job',
            'company': 'Test Company',
            'url': 'https://example.com/test'
        }

        try:
            orchestrator.db_service.add_job_listing(job_data)
        except ValueError:
            pass  # Job already exists

        job_id = job_data['job_id']

        # Clean up any existing queued jobs for this user before test
        orchestrator.db_service.db_manager.execute_write(
            f"DELETE FROM job_states WHERE user_id = ? AND state = ?",
            (self.user_id, JobStates.STATE_QUEUED_FOR_ANALYSIS)
        )

        orchestrator.db_service.db_manager.execute_write(
            f"DELETE FROM job_states WHERE user_id = ? AND state = ?",
            (self.user_id, JobStates.STATE_ANALYZED)
        )

        # Add job to queue
        orchestrator.db_service.add_job_state(job_id, self.user_id, JobStates.STATE_QUEUED_FOR_ANALYSIS)

        # Verify job is in queue
        queued = orchestrator.db_service.get_jobs_by_state(self.user_id, JobStates.STATE_QUEUED_FOR_ANALYSIS)
        self.assertEqual(len(queued), 1, "Job should be in queue")

        # Progress job to analyzed state
        orchestrator.db_service.add_job_state(job_id, self.user_id, JobStates.STATE_ANALYZED)

        # Now job should not appear in queue
        queued = orchestrator.db_service.get_jobs_by_state(self.user_id, JobStates.STATE_QUEUED_FOR_ANALYSIS)
        self.assertEqual(len(queued), 0, "Job should not be in queue after being analyzed")

        # But should appear in analyzed state
        analyzed = orchestrator.db_service.get_jobs_by_state(self.user_id, JobStates.STATE_ANALYZED)
        self.assertEqual(len(analyzed), 1, "Job should be in analyzed state")