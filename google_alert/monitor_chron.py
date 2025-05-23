import time
import argparse
import sqlite3
import sys
import logging
import os
import fcntl
from typing import Optional, Callable, Tuple, Any, Union, Sequence

from .browser import discover_devices_cast_message

"""
monitor_minute.py

Run once per minute (via cron). Query average temperature from SQLite over the last minute,
alert via Chromecast if below threshold and outside cooldown,
prevent overlapping runs via file locking.
"""

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)

LOCKFILE_PATH = os.getenv("MONITOR_MINUTE_LOCK", "/tmp/monitor_minute.lock")


def acquire_lock(path: str):
    """Return an open file with an exclusive lock or raise SystemExit if locked."""
    lockfile = open(path, "w")
    try:
        fcntl.flock(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise SystemExit(0)
    return lockfile


def parse_args() -> argparse.Namespace:
    """Parse and return command-line arguments."""
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
        "-m",
        "--message",
        default="Temperature below threshold",
        help="Alert message to send when threshold is breached",
    )
    return parser.parse_args()


def safe_try_with_logging_else_exit(
    func: Callable[[], Any],
    exceptions: Union[Tuple[type[Exception], ...], type[Exception]],
    log_level: str,
    exit_code: int,
    exit_callback: Optional[Callable[[], None]] = None,
) -> Any:
    """
    Safely execute `func`, catch specified exceptions, log at `log_level`,
    call exit_callback if provided, and exit with `exit_code`.
    Returns the result of func on success.
    """
    try:
        return func()
    except exceptions as e:
        log_msg = f"Error in {func.__name__}: {e}"
        getattr(logging, log_level)(log_msg)
        if exit_callback:
            try:
                exit_callback()
            except Exception as cb_err:
                logging.error(f"Error in exit callback: {cb_err}")
        raise SystemExit(exit_code)


def safe_check_log_and_exit(
    condition: Callable[[], bool],
    log_level: str,
    message: str,
    exit_code: int,
    exit_callback: Optional[Callable[[], None]] = None,
) -> None:
    """
    If `condition()` is True, log `message` at `log_level`, call exit_callback,
    and exit with `exit_code`. Otherwise, continue.
    """
    if condition():
        getattr(logging, log_level)(message)
        if exit_callback:
            try:
                exit_callback()
            except Exception as cb_err:
                logging.error(f"Error in exit callback: {cb_err}")
        raise SystemExit(exit_code)


def get_avg_temp(db_path: str, window: int = 60) -> Optional[float]:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cutoff = int(time.time()) - window
        cur.execute(
            "SELECT AVG(temperature) FROM readings WHERE timestamp >= ?", (cutoff,)
        )
        row = cur.fetchone()
    finally:
        conn.close()
    return row[0] if row and row[0] is not None else None


def get_last_alert(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("SELECT MAX(alert_time) FROM alerts")
        row = cur.fetchone()
    finally:
        conn.close()
    return row[0] or 0


def record_alert(db_path: str, ts: Optional[int] = None) -> None:
    conn = sqlite3.connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO alerts(alert_time) VALUES (?)", (ts or int(time.time()),)
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    # Prevent overlap
    lockfile = safe_try_with_logging_else_exit(
        lambda: acquire_lock(LOCKFILE_PATH), BlockingIOError, "warning", 0
    )

    args = parse_args()

    # Fetch average temperature
    avg_temp = safe_try_with_logging_else_exit(
        lambda: get_avg_temp(args.db_path), sqlite3.Error, "error", 1, lockfile.close
    )
    # Check for missing readings
    safe_check_log_and_exit(
        lambda: avg_temp is None,
        "info",
        "No readings in the last minute.",
        0,
        lockfile.close,
    )
    logging.info(f"Avg temp: {avg_temp:.2f}°C")

    # Check above threshold
    safe_check_log_and_exit(
        lambda: avg_temp >= args.threshold,
        "info",
        "Temperature above threshold; no alert.",
        0,
        lockfile.close,
    )

    # Below threshold: check cooldown
    last = safe_try_with_logging_else_exit(
        lambda: get_last_alert(args.db_path), sqlite3.Error, "error", 1, lockfile.close
    )

    # 
    now = int(time.time())
    elapsed = now - last

    # Check for clock skew
    safe_check_log_and_exit(
        lambda: elapsed < 0,
        "error",
        f"Clock skew detected: last alert in the future (elapsed={elapsed}s).",
        1,
        lockfile.close,
    )
    # Check cooldown
    safe_check_log_and_exit(
        lambda: elapsed < args.cooldown,
        "info",
        f"Cooldown active ({elapsed}s); no alert.",
        0,
        lockfile.close,
    )

    # Send alert
    logging.warning(f"Threshold crossed; alerting. Last at {last}")
    safe_try_with_logging_else_exit(
        lambda: discover_devices_cast_message(args.message),
        Exception,
        "error",
        1,
        lockfile.close,
    )

    # Record alert
    safe_try_with_logging_else_exit(
        lambda: record_alert(args.db_path), sqlite3.Error, "error", 1, lockfile.close
    )

    logging.info("Alert executed and recorded.")
    lockfile.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
