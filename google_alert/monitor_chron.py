"""
monitor_minute.py

Run once per minute (via cron). Query average temperature from SQLite over the last minute,
alert via Chromecast if below threshold and outside cooldown,
preserve DB integrity and prevent overlapping runs.

Night mode: suppress alerts during a nightly window but continue monitoring.
"""

import time
import argparse
import sqlite3
import os
import fcntl
import logging
import logging.handlers
import sys
from functools import partial
from typing import Optional, Callable, Tuple, Any, Union

from .browser import discover_devices_cast_message

LOCKFILE_PATH = os.getenv("MONITOR_MINUTE_LOCK", "/tmp/monitor_minute.lock")


# Return an open file with an exclusive lock or exit if locked.
def acquire_lock(path: str):
    lockfile = open(path, "w")
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(0)
    return lockfile


# Parse and return command-line arguments.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check avg temp and alert if needed")
    parser.add_argument(
        "db_path", help="Path to SQLite DB containing readings and alerts tables"
    )
    parser.add_argument(
        "-s", "--threshold", type=float, default=8.0, help="Temperature threshold in °C"
    )
    parser.add_argument(
        "-c",
        "--cooldown",
        type=int,
        default=3600,
        help="Cooldown period in seconds between alerts",
    )
    parser.add_argument(
        "-w",
        "--window",
        type=int,
        default=60,
        help="Time window in seconds over which to average the temperature",
    )
    parser.add_argument(
        "-m",
        "--message",
        default="Temperature below threshold",
        help="Alert message to send when threshold is breached",
    )
    parser.add_argument(
        "--night-start", type=int, default=21, help="Hour (0-23) when night mode starts"
    )
    parser.add_argument(
        "--night-end", type=int, default=7, help="Hour (0-23) when night mode ends"
    )
    return parser.parse_args()


# Safely execute func, log on exception and exit with code.
def safe_try_with_logging_else_exit(
    func: Callable[[], Any],
    exceptions: Union[Tuple[type[BaseException], ...], type[BaseException]],
    log_level: str,
    exit_code: int,
    exit_callback: Optional[Callable[[], None]] = None,
) -> Any:
    try:
        return func()
    except exceptions as e:
        getattr(logging, log_level)(f"Error in {func.__name__}: {e}")
        if exit_callback:
            try:
                exit_callback()
            except Exception as cb_err:
                logging.error(f"Error in exit callback: {cb_err}")
        raise SystemExit(exit_code)


# Check boolean condition, log and exit if true.
def safe_check_log_and_exit(
    condition: bool,
    log_level: str,
    message: str,
    exit_code: int,
    exit_callback: Optional[Callable[[], None]] = None,
) -> None:
    if condition:
        getattr(logging, log_level)(message)
        if exit_callback:
            try:
                exit_callback()
            except Exception as cb_err:
                logging.error(f"Error in exit callback: {cb_err}")
        raise SystemExit(exit_code)


# Return average temperature over the last `window` seconds.
def get_avg_temp(db_path: str, window: int = 60) -> Optional[float]:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cutoff = int(time.time()) - window
        cur.execute(
            "SELECT AVG(temperature) FROM readings WHERE timestamp >= ?", (cutoff,)
        )
        row = cur.fetchone()
    return row[0] if row and row[0] is not None else None


# Return timestamp of last alert, or 0 if none.
def get_last_alert(db_path: str) -> int:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute("SELECT MAX(alert_time) FROM alerts")
        row = cur.fetchone()
    return row[0] or 0


# Record a new alert timestamp.
def record_alert(db_path: str, ts: Optional[int] = None) -> None:
    with sqlite3.connect(db_path) as conn:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO alerts(alert_time) VALUES (?)", (ts or int(time.time()),)
        )
        conn.commit()


# Return True if current_hour is within the night window [start,end).
def is_night_time(current_hour: int, start: int, end: int) -> bool:
    if start < end:
        return start <= current_hour < end
    return current_hour >= start or current_hour < end


def main() -> int:
    # Acquire lock and ensure it's released
    lockfile = safe_try_with_logging_else_exit(
        partial(acquire_lock, LOCKFILE_PATH), BlockingIOError, "warning", 0
    )
    try:
        args = parse_args()

        # Fetch temp
        avg_temp = safe_try_with_logging_else_exit(
            partial(get_avg_temp, args.db_path, args.window), sqlite3.Error, "error", 1
        )
        # No readings
        safe_check_log_and_exit(
            avg_temp is None, "info", "No readings in the last minute.", 0
        )
        logging.info(f"Avg temp: {avg_temp:.2f}°C")

        # Above threshold
        safe_check_log_and_exit(
            avg_temp >= args.threshold,
            "info",
            "Temperature above threshold; no alert.",
            0,
        )

        # Last alert
        last = safe_try_with_logging_else_exit(
            partial(get_last_alert, args.db_path), sqlite3.Error, "error", 1
        )
        now = int(time.time())
        elapsed = now - last

        # Clock skew
        safe_check_log_and_exit(
            elapsed < 0, "error", f"Clock skew: elapsed={elapsed}s.", 1
        )
        # Cooldown
        safe_check_log_and_exit(
            elapsed < args.cooldown, "info", f"Cooldown active ({elapsed}s).", 0
        )

        # Night mode
        safe_check_log_and_exit(
            is_night_time(time.localtime().tm_hour, args.night_start, args.night_end),
            "info",
            f"Night mode: {args.night_start}-{args.night_end}h.",
            0,
        )

        # Send alert
        logging.warning(f"Threshold crossed; alerting. Last at {last}")
        safe_try_with_logging_else_exit(
            partial(discover_devices_cast_message, args.message), Exception, "error", 1
        )

        # Record alert
        safe_try_with_logging_else_exit(
            partial(record_alert, args.db_path), sqlite3.Error, "error", 1
        )

        # Exit
        logging.info("Alert recorded")
        return 0
    finally:
        lockfile.close()


if __name__ == "__main__":
    # Configure root logger to send to syslog via /dev/log, using the LOCAL0 facility
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    syslog_handler = logging.handlers.SysLogHandler(
        address='/dev/log',
        facility=logging.handlers.SysLogHandler.LOG_LOCAL0
    )
    formatter = logging.Formatter('%(name)s[%(process)d]: %(levelname)s %(message)s')
    syslog_handler.setFormatter(formatter)
    logger.addHandler(syslog_handler)
    sys.exit(main())
