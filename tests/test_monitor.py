import os
import sqlite3
import tempfile
import time
import unittest
from unittest.mock import patch, MagicMock
import importlib

# Configure lock path before importing to avoid side effects
tmp_dir = tempfile.gettempdir()
env_lock = os.path.join(tmp_dir, 'test_monitor_minute.lock')
os.environ['MONITOR_MINUTE_LOCK'] = env_lock

# Import and reload module under test to pick up LOCKFILE_PATH
from google_alert import monitor_chron as monitor_minute # noqa: E402
importlib.reload(monitor_minute)

class TestMonitorMinute(unittest.TestCase):
    def setUp(self):
        # Spy on discover_devices_cast_message to prevent real broadcasts and record calls
        self.alert_spy = MagicMock()
        self.alert_patcher = patch(
            'monitor_minute.discover_devices_cast_message',
            self.alert_spy
        )
        self.alert_patcher.start()
        self.addCleanup(self.alert_patcher.stop)

        # Create a fresh temporary DB with required tables
        self.db_fd, self.db_path = tempfile.mkstemp(suffix='.db')
        os.close(self.db_fd)
        with sqlite3.connect(self.db_path) as conn:
            cur = conn.cursor()
            cur.execute('CREATE TABLE readings(timestamp INTEGER, temperature REAL)')
            cur.execute('CREATE TABLE alerts(alert_time INTEGER)')
            conn.commit()

        # Freeze time
        self.start_time = int(time.time())
        self.time_patcher = patch('time.time', return_value=self.start_time)
        self.mock_time = self.time_patcher.start()
        self.addCleanup(self.time_patcher.stop)

    def tearDown(self):
        os.unlink(self.db_path)
        if os.path.exists(env_lock):
            os.unlink(env_lock)

    def run_main(self, **kwargs):
        # Build argument list for main
        args = [self.db_path]
        for k, v in kwargs.items():
            args.append(f'--{k}')
            if not isinstance(v, bool):
                args.append(str(v))

        # Patch sys.exit to capture exit code
        with patch.object(monitor_minute, 'sys') as mock_sys:
            mock_sys.exit = lambda code: (_ for _ in ()).throw(SystemExit(code))
            try:
                monitor_minute.main()
            except SystemExit as e:
                return e.code
        return 0

    def test_no_readings(self):
        code = self.run_main()
        self.assertEqual(code, 0)
        self.alert_spy.assert_not_called()

    def test_temp_above_threshold(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('INSERT INTO readings VALUES(?, ?)', (self.start_time, 10.0))
            conn.commit()
        code = self.run_main()
        self.assertEqual(code, 0)
        self.alert_spy.assert_not_called()

    def test_temp_below_threshold_and_alert(self):
        # Insert a reading below threshold and run
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('INSERT INTO readings VALUES(?, ?)', (self.start_time, 5.0))
            conn.commit()
        code = self.run_main()
        self.assertEqual(code, 0)
        # Verify alert was invoked exactly once with correct message
        args = monitor_minute.parse_args()
        self.alert_spy.assert_called_once_with(args.message)

    def test_cooldown_behavior(self):
        # First alert
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('INSERT INTO readings VALUES(?, ?)', (self.start_time, 5.0))
            conn.commit()
        code1 = self.run_main()
        self.assertEqual(code1, 0)
        self.alert_spy.reset_mock()

        # Advance time within cooldown and insert another low reading
        new_time = self.start_time + 10
        self.mock_time.return_value = new_time
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('INSERT INTO readings VALUES(?, ?)', (new_time, 5.0))
            conn.commit()
        code2 = self.run_main()
        self.assertEqual(code2, 0)
        self.alert_spy.assert_not_called()

    def test_night_mode(self):
        # Insert a reading to trigger alert
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('INSERT INTO readings VALUES(?, ?)', (self.start_time, 5.0))
            conn.commit()
        # Force local time into night window
        night_time = time.struct_time((2025, 5, 23, 22, 0, 0, 4, 143, 1))
        with patch('time.localtime', return_value=night_time):
            code = self.run_main()
        self.assertEqual(code, 0)
        self.alert_spy.assert_not_called()

if __name__ == '__main__':
    unittest.main()
