import os
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock
import importlib
import sys

# Configure lock path before importing to avoid side effects
tmp_dir = tempfile.gettempdir()
env_lock = os.path.join(tmp_dir, "test_monitor_chron.lock")
os.environ["MONITOR_MINUTE_LOCK"] = env_lock

# Import and reload module under test to pick up LOCKFILE_PATH
from google_alert import monitor_chron  # noqa: E402
import google_alert.sensor_db as sensor_db # noqa: E402
importlib.reload(monitor_chron)


class TestMonitorMinute(unittest.TestCase):
    def setUp(self):
        # Spy on discover_devices_cast_message to prevent real broadcasts and record calls
        self.alert_spy = MagicMock()
        self.alert_patcher = patch.object(
            monitor_chron, "discover_devices_cast_message", self.alert_spy
        )
        self.alert_patcher.start()
        self.addCleanup(self.alert_patcher.stop)

        # Create a fresh temporary DB with required tables
        self.db_fd, self.db_path = tempfile.mkstemp(suffix=".db")
        os.close(self.db_fd)
        sensor_db.init_db(self.db_path)

        # Freeze time
        self.start_time = int(time.time())
        self.time_patcher = patch("time.time", return_value=self.start_time)
        self.mock_time = self.time_patcher.start()
        self.addCleanup(self.time_patcher.stop)

    def tearDown(self):
        os.unlink(self.db_path)
        if os.path.exists(env_lock):
            os.unlink(env_lock)

    def run_main(self, **kwargs):
        # Build argument list for main
        argv = ['monitor_chron', self.db_path]
        for k, v in kwargs.items():
            argv.append(f'--{k}')
            if not isinstance(v, bool):
                argv.append(str(v))

        # Patch the real sys.argv and capture sys.exit
        with patch.object(sys, 'argv', argv), \
             patch.object(monitor_chron, 'sys') as mock_sys:

            # Now parse_args() inside main will see the right argv
            mock_sys.exit = lambda code: (_ for _ in ()).throw(SystemExit(code))
            try:
                monitor_chron.main()
            except SystemExit as e:
                return e.code
        return 0

    def test_no_readings(self):
        code = self.run_main()
        self.assertEqual(code, 0)
        self.alert_spy.assert_not_called()

    def test_temp_above_threshold(self):
        sensor_db.insert_reading(self.db_path, temperature=10.0)
        code = self.run_main()
        self.assertEqual(code, 0)
        self.alert_spy.assert_not_called()

    def test_temp_below_threshold_and_alert(self):
        # Insert a reading below threshold and run
        sensor_db.insert_reading(self.db_path, temperature=5.0)
        # Force local time to daytime hours to avoid night mode
        day_time = time.struct_time((2025, 5, 23, 12, 0, 0, 4, 143, 1))
        with patch("time.localtime", return_value=day_time):
            code = self.run_main()
        self.assertEqual(code, 0)
        # Verify alert was invoked with the default message
        self.alert_spy.assert_called_once_with("Temperature below threshold")


    def test_cooldown_behavior(self):
        # Force local time to daytime hours to avoid night mode
        day_time = time.struct_time((2025, 5, 23, 12, 0, 0, 4, 143, 1))
        with patch("time.localtime", return_value=day_time):
            # First alert
            sensor_db.insert_reading(self.db_path, temperature=5.0)
            code1 = self.run_main()
            self.assertEqual(code1, 0)
            self.alert_spy.reset_mock()

            # Advance time within cooldown and insert another low reading
            new_time = self.start_time + 10
            self.mock_time.return_value = new_time
            sensor_db.insert_reading(self.db_path, temperature=5.0)
            code2 = self.run_main()
            self.assertEqual(code2, 0)
            self.alert_spy.assert_not_called()

    def test_night_time_alert_silencing(self):
        """Test that alerts are properly silenced during night time hours"""
        # Insert a reading below threshold that would normally trigger an alert
        sensor_db.insert_reading(self.db_path, temperature=5.0)
        
        # Test different night time hours to ensure comprehensive coverage
        night_hours = [22, 23, 0, 1, 2, 3, 4, 5, 6]  # 10 PM to 6 AM
        
        for hour in night_hours:
            with self.subTest(hour=hour):
                # Reset the spy for each iteration
                self.alert_spy.reset_mock()
                
                # Force local time into night window
                night_time = time.struct_time((2025, 5, 23, hour, 0, 0, 4, 143, 1))
                with patch("time.localtime", return_value=night_time):
                    code = self.run_main()
                
                # Should exit successfully but no alert should be sent
                self.assertEqual(code, 0)
                self.alert_spy.assert_not_called()

    def test_night_mode(self):
        # Insert a reading to trigger alert
        sensor_db.insert_reading(self.db_path, temperature=5.0)
        # Force local time into night window
        night_time = time.struct_time((2025, 5, 23, 22, 0, 0, 4, 143, 1))
        with patch("time.localtime", return_value=night_time):
            code = self.run_main()
        self.assertEqual(code, 0)
        self.alert_spy.assert_not_called()


if __name__ == "__main__":
    unittest.main()
