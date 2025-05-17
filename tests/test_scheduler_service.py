import unittest
from unittest.mock import patch, MagicMock, call
import threading
import datetime

from services.scheduler_service import SchedulerService
from database.models import ScheduleSettings


class TestSchedulerService(unittest.TestCase):
    """Test cases for the SchedulerService class."""

    def setUp(self):
        """Set up the test environment before each test method."""
        # Create mocks for dependencies
        self.db_service_patcher = patch('services.scheduler_service.DatabaseService')
        self.mock_db_service_class = self.db_service_patcher.start()
        self.mock_db_service = MagicMock()
        self.mock_db_service_class.return_value = self.mock_db_service

        self.scraper_service_patcher = patch('services.scheduler_service.ScraperService')
        self.mock_scraper_service_class = self.scraper_service_patcher.start()
        self.mock_scraper_service = MagicMock()
        self.mock_scraper_service_class.return_value = self.mock_scraper_service

        self.analysis_service_patcher = patch('services.scheduler_service.AnalysisService')
        self.mock_analysis_service_class = self.analysis_service_patcher.start()
        self.mock_analysis_service = MagicMock()
        self.mock_analysis_service_class.return_value = self.mock_analysis_service

        # Mock schedule library
        self.schedule_patcher = patch('services.scheduler_service.schedule')
        self.mock_schedule = self.schedule_patcher.start()

        # Mock threading
        self.threading_patcher = patch('services.scheduler_service.threading')
        self.mock_threading = self.threading_patcher.start()

        # Mock time to avoid sleep delays
        self.time_patcher = patch('services.scheduler_service.time')
        self.mock_time = self.time_patcher.start()

        # Mock datetime
        self.datetime_patcher = patch('services.scheduler_service.datetime')
        self.mock_datetime = self.datetime_patcher.start()
        self.mock_datetime.datetime.now.return_value = datetime.datetime(2023, 1, 1, 12, 0, 0)
        self.mock_datetime.datetime.isoformat = datetime.datetime.isoformat

        # Mock logging
        self.logging_patcher = patch('services.scheduler_service.logger')
        self.mock_logger = self.logging_patcher.start()

        # Mock traceback
        self.traceback_patcher = patch('services.scheduler_service.traceback')
        self.mock_traceback = self.traceback_patcher.start()

        # Create service instance
        self.scheduler_service = SchedulerService()

        # Reset running_jobs for test isolation
        self.scheduler_service.running_jobs = {}
        self.scheduler_service.callbacks = {}

    def tearDown(self):
        """Clean up after each test method."""
        self.db_service_patcher.stop()
        self.scraper_service_patcher.stop()
        self.analysis_service_patcher.stop()
        self.schedule_patcher.stop()
        self.threading_patcher.stop()
        self.time_patcher.stop()
        self.datetime_patcher.stop()
        self.logging_patcher.stop()
        self.traceback_patcher.stop()

        # Stop any threads that might have been started
        if hasattr(self.scheduler_service, 'stop_event'):
            self.scheduler_service.stop_event.set()

    def test_init(self):
        """Test initialization of SchedulerService."""
        # Verify services were initialized
        self.assertIsNotNone(self.scheduler_service.db_service)
        self.assertIsNotNone(self.scheduler_service.scraper_service)
        self.assertIsNotNone(self.scheduler_service.analysis_service)

        # Verify status tracking was initialized
        self.assertEqual(self.scheduler_service.running_jobs, {})
        self.assertIsInstance(self.scheduler_service.status_lock, MagicMock)
        self.assertEqual(self.scheduler_service.callbacks, {})

        # Verify threading was set up
        self.assertIsNone(self.scheduler_service.scheduler_thread)
        self.assertIsInstance(self.scheduler_service.stop_event, MagicMock)

    def test_start(self):
        """Test starting the scheduler thread."""
        # First call should start thread
        self.scheduler_service.start()

        # Verify thread was created and started
        self.mock_threading.Thread.assert_called_once_with(
            target=self.scheduler_service._scheduler_loop,
            daemon=True
        )
        self.mock_threading.Thread.return_value.start.assert_called_once()

        # Second call should do nothing if thread is running
        self.mock_threading.Thread.reset_mock()
        self.mock_threading.Thread.return_value.is_alive.return_value = True
        self.scheduler_service.start()
        self.mock_threading.Thread.assert_not_called()

    def test_stop(self):
        """Test stopping the scheduler thread."""
        # Set up a mock thread
        mock_thread = MagicMock()
        self.scheduler_service.scheduler_thread = mock_thread

        # Thread is alive
        mock_thread.is_alive.return_value = True

        # Call stop
        self.scheduler_service.stop()

        # Verify thread was stopped
        self.scheduler_service.stop_event.set.assert_called_once()
        mock_thread.join.assert_called_once()
        self.assertIsNone(self.scheduler_service.scheduler_thread)

        # Test with no thread
        self.scheduler_service.stop_event.reset_mock()
        self.scheduler_service.scheduler_thread = None
        self.scheduler_service.stop()
        self.scheduler_service.stop_event.set.assert_not_called()

    def test_restart(self):
        """Test restarting the scheduler."""
        # Mock stop and start methods
        with patch.object(self.scheduler_service, 'stop') as mock_stop:
            with patch.object(self.scheduler_service, 'start') as mock_start:
                # Call restart
                self.scheduler_service.restart()

                # Verify stop and start were called
                mock_stop.assert_called_once()
                mock_start.assert_called_once()

    def test_scheduler_loop(self):
        """Test the main scheduler loop."""
        # Mock _load_schedules method
        with patch.object(self.scheduler_service, '_load_schedules') as mock_load:
            # Set up the loop to run once then exit
            self.scheduler_service.stop_event.is_set.side_effect = [False, True]

            # Call the method
            self.scheduler_service._scheduler_loop()

            # Verify schedules were loaded
            mock_load.assert_called_once()

            # Verify schedule.run_pending was called
            self.mock_schedule.run_pending.assert_called_once()

            # Verify sleep was called
            self.mock_time.sleep.assert_called_once_with(1)

    def test_load_schedules(self):
        """Test loading schedules from the database."""
        # Mock active schedules
        mock_schedules = [
            {
                'user_id': 1,
                'schedule_type': ScheduleSettings.TYPE_DAILY,
                'execution_time': '08:00'
            },
            {
                'user_id': 2,
                'schedule_type': ScheduleSettings.TYPE_WEEKLY,
                'execution_time': 'monday 10:00'
            },
            {
                'user_id': 3,
                'schedule_type': ScheduleSettings.TYPE_CUSTOM,
                'execution_time': 'interval:6'
            }
        ]
        self.mock_db_service.get_active_schedules.return_value = mock_schedules

        # Mock schedule job objects
        mock_daily_job = MagicMock()
        mock_weekly_job = MagicMock()
        mock_custom_job = MagicMock()

        # Set up schedule.every() chain
        self.mock_schedule.every.return_value.day.at.return_value = mock_daily_job
        self.mock_schedule.every.return_value.monday.at.return_value = mock_weekly_job
        self.mock_schedule.every.return_value.hours = mock_custom_job

        # Call the method
        self.scheduler_service._load_schedules()

        # Verify schedule was cleared first
        self.mock_schedule.clear.assert_called_once()

        # Verify active schedules were loaded
        self.mock_db_service.get_active_schedules.assert_called_once()

        # Verify jobs were created
        mock_daily_job.do.assert_called_once()
        mock_weekly_job.do.assert_called_once()
        mock_custom_job.do.assert_called_once()

        # Test error handling for invalid weekly format
        self.mock_schedule.clear.reset_mock()
        self.mock_db_service.get_active_schedules.return_value = [
            {
                'user_id': 2,
                'schedule_type': ScheduleSettings.TYPE_WEEKLY,
                'execution_time': 'invalid format'  # Invalid format
            }
        ]

        # Call method again
        self.scheduler_service._load_schedules()

        # Verify error was logged
        self.mock_logger.error.assert_called_once()

    def test_run_scheduled_job(self):
        """Test running a scheduled job."""
        # Mock scraper and analyzer results
        self.mock_scraper_service.scrape_jobs.return_value = {'status': 'success', 'jobs_found': 5}
        self.mock_analysis_service.analyze_queued_jobs.return_value = {'analyzed': 5, 'relevant': 3}

        # Mock _set_job_status and _update_job_status
        with patch.object(self.scheduler_service, '_set_job_status') as mock_set:
            with patch.object(self.scheduler_service, '_update_job_status') as mock_update:
                # Call the method
                self.scheduler_service._run_scheduled_job(1)

                # Verify status was set at start
                mock_set.assert_any_call(
                    'scheduled_1_' + str(int(self.mock_time.time.return_value)),
                    {
                        'status': 'running',
                        'user_id': 1,
                        'type': 'scheduled',
                        'start_time': '2023-01-01T12:00:00',
                        'steps': []
                    }
                )

                # Verify scraper was called
                self.mock_scraper_service.scrape_jobs.assert_called_once()

                # Verify analyzer was called
                self.mock_analysis_service.analyze_queued_jobs.assert_called_once()

                # Verify status updates were made
                self.assertTrue(mock_update.call_count >= 2)

                # Verify status was set as completed at end
                mock_set.assert_any_call(
                    'scheduled_1_' + str(int(self.mock_time.time.return_value)),
                    {
                        'status': 'completed',
                        'user_id': 1,
                        'type': 'scheduled',
                        'start_time': '2023-01-01T12:00:00',
                        'end_time': '2023-01-01T12:00:00',
                        'steps': mock_update.return_value,
                        'result': {
                            'scraping': {'status': 'success', 'jobs_found': 5},
                            'analyzing': {'analyzed': 5, 'relevant': 3}
                        }
                    }
                )

                # Verify last_run was updated
                self.mock_db_service.update_last_run.assert_called_once_with(1)

        # Test error handling
        self.mock_scraper_service.scrape_jobs.side_effect = Exception("Test error")

        with patch.object(self.scheduler_service, '_set_job_status') as mock_set:
            # Call the method
            self.scheduler_service._run_scheduled_job(1)

            # Verify error was logged
            self.mock_logger.error.assert_called()

            # Verify status was set as failed
            mock_set.assert_any_call(
                'scheduled_1_' + str(int(self.mock_time.time.return_value)),
                {
                    'status': 'failed',
                    'user_id': 1,
                    'type': 'scheduled',
                    'start_time': '2023-01-01T12:00:00',
                    'end_time': '2023-01-01T12:00:00',
                    'steps': [],
                    'error': 'Test error'
                }
            )

    def test_run_job_now(self):
        """Test running a job immediately."""
        # Mock is_testing to be False to ensure Thread is created
        with patch('sys.modules', {'pytest': None, 'unittest': None}):
            # Call the method
            job_id = self.scheduler_service.run_job_now(1)

            # Verify a thread was started
            self.mock_threading.Thread.assert_called_once()
            self.mock_threading.Thread.return_value.start.assert_called_once()

            # Verify job_id format
            self.assertTrue(job_id.startswith('manual_1_'))

            # Test with callback
            mock_callback = MagicMock()
            self.mock_threading.Thread.reset_mock()

            job_id = self.scheduler_service.run_job_now(1, mock_callback)

            # Verify callback was registered
            self.assertEqual(self.scheduler_service.callbacks[job_id], mock_callback)

            # Verify thread was started
            self.mock_threading.Thread.assert_called_once()
            self.mock_threading.Thread.return_value.start.assert_called_once()

    def test_run_manual_job(self):
        """Test running a manual job in a thread."""
        # Set up job ID
        job_id = 'manual_1_123456789'

        # Mock scraper and analyzer results
        self.mock_scraper_service.scrape_jobs.return_value = {'status': 'success', 'jobs_found': 5}
        self.mock_analysis_service.analyze_queued_jobs.return_value = {'analyzed': 5, 'relevant': 3}

        # Mock _set_job_status and _update_job_status
        with patch.object(self.scheduler_service, '_set_job_status') as mock_set:
            with patch.object(self.scheduler_service, '_update_job_status') as mock_update:
                # Call the method
                self.scheduler_service._run_manual_job(job_id, 1)

                # Verify status was set at start
                mock_set.assert_any_call(
                    job_id,
                    {
                        'status': 'running',
                        'user_id': 1,
                        'type': 'manual',
                        'start_time': '2023-01-01T12:00:00',
                        'steps': []
                    }
                )

                # Verify scraper was called
                self.mock_scraper_service.scrape_jobs.assert_called_once()

                # Verify analyzer was called
                self.mock_analysis_service.analyze_queued_jobs.assert_called_once()

                # Verify status updates were made
                self.assertTrue(mock_update.call_count >= 2)

                # Verify status was set as completed at end
                mock_set.assert_any_call(
                    job_id,
                    {
                        'status': 'completed',
                        'user_id': 1,
                        'type': 'manual',
                        'start_time': '2023-01-01T12:00:00',
                        'end_time': '2023-01-01T12:00:00',
                        'steps': mock_update.return_value,
                        'result': {
                            'scraping': {'status': 'success', 'jobs_found': 5},
                            'analyzing': {'analyzed': 5, 'relevant': 3}
                        }
                    }
                )

                # Verify last_run was updated
                self.mock_db_service.update_last_run.assert_called_once_with(1)

        # Test error handling
        self.mock_scraper_service.scrape_jobs.side_effect = Exception("Test error")

        with patch.object(self.scheduler_service, '_set_job_status') as mock_set:
            # Call the method
            self.scheduler_service._run_manual_job(job_id, 1)

            # Verify error was logged
            self.mock_logger.error.assert_called()
            self.mock_traceback.print_exc.assert_called_once()

            # Verify status was set as failed
            mock_set.assert_any_call(
                job_id,
                {
                    'status': 'failed',
                    'user_id': 1,
                    'type': 'manual',
                    'start_time': '2023-01-01T12:00:00',
                    'end_time': '2023-01-01T12:00:00',
                    'steps': [],
                    'error': 'Test error'
                }
            )

    def test_set_job_status(self):
        """Test setting a job's status."""
        # Set up test data
        job_id = 'test_job_1'
        status = {'status': 'running', 'step': 'scraping'}

        # Call the method
        self.scheduler_service._set_job_status(job_id, status)

        # Verify status was set
        self.assertEqual(self.scheduler_service.running_jobs[job_id], status)

        # Test with registered callback
        mock_callback = MagicMock()
        self.scheduler_service.callbacks[job_id] = mock_callback

        # Call the method again
        self.scheduler_service._set_job_status(job_id, status)

        # Verify callback was called
        mock_callback.assert_called_once_with(status)

        # Test callback cleanup on completed status
        mock_callback.reset_mock()
        completed_status = {'status': 'completed', 'result': 'success'}

        self.scheduler_service._set_job_status(job_id, completed_status)

        # Verify callback was called
        mock_callback.assert_called_once_with(completed_status)

        # Verify callback was removed
        self.assertNotIn(job_id, self.scheduler_service.callbacks)

        # Test callback error handling
        job_id = 'test_job_2'
        self.scheduler_service.callbacks[job_id] = MagicMock(side_effect=Exception("Callback error"))

        # Call the method - should not raise exception
        self.scheduler_service._set_job_status(job_id, status)

        # Verify error was logged
        self.mock_logger.error.assert_called()

    def test_update_job_status(self):
        """Test updating a job's status."""
        # Set up test data
        job_id = 'test_job_1'
        self.scheduler_service.running_jobs[job_id] = {
            'status': 'running',
            'steps': [],
            'current_step': None,
            'last_update': None
        }

        # Call the method for new step
        self.scheduler_service._update_job_status(job_id, 'scraping', 'start', {'total': 5})

        # Verify step was added
        job_status = self.scheduler_service.running_jobs[job_id]
        self.assertEqual(len(job_status['steps']), 1)
        self.assertEqual(job_status['steps'][0]['name'], 'scraping')
        self.assertEqual(job_status['steps'][0]['events'][0]['event'], 'start')
        self.assertEqual(job_status['current_step'], 'scraping')

        # Call the method again for same step
        self.scheduler_service._update_job_status(job_id, 'scraping', 'progress', {'completed': 2})

        # Verify event was added to existing step
        job_status = self.scheduler_service.running_jobs[job_id]
        self.assertEqual(len(job_status['steps']), 1)
        self.assertEqual(len(job_status['steps'][0]['events']), 2)
        self.assertEqual(job_status['steps'][0]['events'][1]['event'], 'progress')

        # Test with registered callback
        mock_callback = MagicMock()
        self.scheduler_service.callbacks[job_id] = mock_callback

        # Call the method again
        self.scheduler_service._update_job_status(job_id, 'scraping', 'complete', {'jobs_found': 5})

        # Verify callback was called
        mock_callback.assert_called_once()
        args = mock_callback.call_args[0][0]
        self.assertEqual(args['job_id'], job_id)
        self.assertEqual(args['step'], 'scraping')
        self.assertEqual(args['event'], 'complete')

        # Test callback error handling
        mock_callback.reset_mock()
        mock_callback.side_effect = Exception("Callback error")

        # Call the method - should not raise exception
        self.scheduler_service._update_job_status(job_id, 'analyzing', 'start', {'total': 5})

        # Verify error was logged
        self.mock_logger.error.assert_called()

        # Test job not found
        self.scheduler_service._update_job_status('nonexistent', 'scraping', 'start', {'total': 5})
        # Should not raise exception

    def test_get_job_status(self):
        """Test getting a job's status."""
        # Set up test data
        job_id = 'test_job_1'
        status = {'status': 'running', 'step': 'scraping'}
        self.scheduler_service.running_jobs[job_id] = status

        # Call the method
        result = self.scheduler_service.get_job_status(job_id)

        # Verify result
        self.assertEqual(result, status)

        # Test job not found
        result = self.scheduler_service.get_job_status('nonexistent')
        self.assertIsNone(result)

    def test_get_all_job_statuses(self):
        """Test getting all job statuses."""
        # Set up test data
        self.scheduler_service.running_jobs = {
            'job1': {'status': 'running', 'user_id': 1},
            'job2': {'status': 'completed', 'user_id': 1},
            'job3': {'status': 'running', 'user_id': 2}
        }

        # Call the method without filtering
        result = self.scheduler_service.get_all_job_statuses()

        # Verify result
        self.assertEqual(len(result), 3)
        self.assertIn('job1', result)
        self.assertIn('job2', result)
        self.assertIn('job3', result)

        # Test with user filtering
        result = self.scheduler_service.get_all_job_statuses(1)

        # Verify result
        self.assertEqual(len(result), 2)
        self.assertIn('job1', result)
        self.assertIn('job2', result)
        self.assertNotIn('job3', result)

    def test_update_schedule(self):
        """Test updating a user's schedule."""
        # Mock _load_schedules
        with patch.object(self.scheduler_service, '_load_schedules') as mock_load:
            # Call the method
            self.scheduler_service.update_schedule(1, 'daily', '08:00', True)

            # Verify database was updated
            self.mock_db_service.update_user_schedule.assert_called_once_with(
                1, 'daily', '08:00', True
            )

            # Verify schedules were reloaded
            mock_load.assert_called_once()

    def test_cancel_job(self):
        """Test canceling a running job."""
        # Set up test data
        job_id = 'test_job_1'
        self.scheduler_service.running_jobs[job_id] = {
            'status': 'running',
            'step': 'scraping'
        }

        # Call the method
        result = self.scheduler_service.cancel_job(job_id)

        # Verify result
        self.assertTrue(result)

        # Verify job status was updated
        self.assertEqual(self.scheduler_service.running_jobs[job_id]['status'], 'canceled')
        self.assertIn('end_time', self.scheduler_service.running_jobs[job_id])

        # Test with registered callback
        job_id = 'test_job_2'
        mock_callback = MagicMock()
        self.scheduler_service.callbacks[job_id] = mock_callback
        self.scheduler_service.running_jobs[job_id] = {
            'status': 'running',
            'step': 'scraping'
        }

        # Call the method
        result = self.scheduler_service.cancel_job(job_id)

        # Verify callback was called
        mock_callback.assert_called_once()

        # Verify callback was removed
        self.assertNotIn(job_id, self.scheduler_service.callbacks)

        # Test job not found
        result = self.scheduler_service.cancel_job('nonexistent')
        self.assertFalse(result)

    def test_run_manual_job_no_limit(self):
        """Test running a manual job without job limit."""
        # Set up job ID
        job_id = 'manual_1_123456789'

        # Mock scraper and analyzer results
        self.mock_scraper_service.scrape_jobs.return_value = {'status': 'success', 'jobs_found': 5}
        self.mock_analysis_service.analyze_queued_jobs.return_value = {'analyzed': 5, 'relevant': 3}

        # Mock _set_job_status and _update_job_status
        with patch.object(self.scheduler_service, '_set_job_status') as mock_set:
            with patch.object(self.scheduler_service, '_update_job_status') as mock_update:
                # Call the method
                self.scheduler_service._run_manual_job(job_id, 1)

                # Verify scraper was called without job limit
                self.mock_scraper_service.scrape_jobs.assert_called_once_with(
                    1,
                    self.mock_scraper_service.scrape_jobs.call_args[0][1]  # Same callback
                )

                # Verify no job_limit parameter was passed
                self.assertEqual(len(self.mock_scraper_service.scrape_jobs.call_args[0]),
                                 2)  # Only user_id and callback


if __name__ == '__main__':
    unittest.main()