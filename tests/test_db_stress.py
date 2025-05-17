# import unittest
# import time
# from app import app, orchestrator
# from database.models import JobStates
#
#
# class TestDatabaseStress(unittest.TestCase):
#     def setUp(self):
#         app.config['TESTING'] = True
#
#         # Create test user if needed
#         try:
#             self.user_id = orchestrator.user_service.create_user('testuser', 'Password123!', 'test@example.com')
#         except ValueError:
#             # Get existing user ID
#             user = orchestrator.user_service.get_user_by_username('testuser')
#             self.user_id = user['user_id']
#
#     def test_bulk_job_insertion(self):
#         """Test inserting and retrieving many jobs."""
#         # Create 100 test jobs
#         job_count = 100
#         for i in range(job_count):
#             job_data = {
#                 'job_id': f'stress_test_job_{i}',
#                 'title': f'Test Engineer {i}',
#                 'company': 'Test Company',
#                 'url': f'https://example.com/job/{i}'
#             }
#
#             try:
#                 orchestrator.db_service.add_job_listing(job_data)
#             except ValueError:
#                 pass  # Job already exists
#
#             # Add to user's jobs with relevant state
#             orchestrator.db_service.add_job_state(job_data['job_id'], self.user_id, JobStates.STATE_RELEVANT)
#
#         # Measure time to query jobs
#         start_time = time.time()
#         jobs = orchestrator.db_service.get_jobs_by_state(self.user_id, JobStates.STATE_RELEVANT, limit=1000)
#         query_time = time.time() - start_time
#
#         # Verify all jobs were retrieved
#         self.assertGreaterEqual(len(jobs), job_count)
#
#         # Verify query time is reasonable (threshold depends on hardware)
#         self.assertLess(query_time, 1.0, "Query should complete in under 1 second")
#
#     def test_job_state_history_performance(self):
#         """Test performance with large job state history."""
#         # Create a job with many state transitions
#         job_id = 'state_history_test_job'
#
#         job_data = {
#             'job_id': job_id,
#             'title': 'Performance Test Job',
#             'company': 'Test Company',
#             'url': 'https://example.com/job'
#         }
#
#         try:
#             orchestrator.db_service.add_job_listing(job_data)
#         except ValueError:
#             pass  # Job already exists
#
#         # Create many state entries (100 state changes)
#         states = [
#             JobStates.STATE_NEW_SCRAPED,
#             JobStates.STATE_QUEUED_FOR_ANALYSIS,
#             JobStates.STATE_ANALYZING,
#             JobStates.STATE_ANALYZED,
#             JobStates.STATE_RELEVANT,
#             JobStates.STATE_VIEWED,
#             JobStates.STATE_SAVED
#         ]
#
#         for _ in range(100):
#             for state in states:
#                 orchestrator.db_service.add_job_state(job_id, self.user_id, state)
#
#         # Measure time to get state history
#         start_time = time.time()
#         history = orchestrator.db_service.get_job_state_history(job_id, self.user_id)
#         query_time = time.time() - start_time
#
#         # Verify we got all history entries
#         self.assertGreaterEqual(len(history), 100 * len(states))
#
#         # Verify query time is reasonable
#         self.assertLess(query_time, 1.0, "State history query should complete in under 1 second")