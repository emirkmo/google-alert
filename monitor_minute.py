"""
monitor_minute.py

Run once per minute (via cron). Query average temperature from SQLite over the last minute,
and invoke the Chromecast alert script if the average falls below the threshold,
but only if no alert was triggered in the past hour.
"""
import time
import subprocess
import argparse
import sqlite3
import sys

def get_avg_temp(db_path, window=60):
    """Return the average temperature over the last `window` seconds."""
    now = int(time.time())
    cutoff = now - window
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS readings (
            timestamp INTEGER NOT NULL,
            temperature REAL NOT NULL
        )""")
    cur.execute("""
        SELECT AVG(temperature) FROM readings
        WHERE timestamp >= ?
    """, (cutoff,))
    row = cur.fetchone()
    conn.close()
    return row[0] if row and row[0] is not None else None

def get_last_alert(db_path):
    """Return the timestamp of the last alert, or 0 if none."""
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            alert_time INTEGER NOT NULL
        )""")
    cur.execute("SELECT MAX(alert_time) FROM alerts")
    row = cur.fetchone()
    conn.close()
    return row[0] if row and row[0] else 0

def record_alert(db_path, ts=None):
    """Record a new alert at time `ts` (now if None)."""
    if ts is None:
        ts = int(time.time())
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("INSERT INTO alerts(alert_time) VALUES (?)", (ts,))
    conn.commit()
    conn.close()

def main(args):
    # get average temp
    avg_temp = get_avg_temp(args.db_path, window=60)
    if avg_temp is None:
        print("No readings in the last minute.")
        return 0
    print(f"Avg temp (last minute): {avg_temp:.2f}°C")

    if avg_temp < args.threshold:
        last_alert = get_last_alert(args.db_path)
        now = int(time.time())
        if now - last_alert >= args.cooldown:
            print(f"Threshold crossed. Triggering alert (last at {last_alert}).")
            cmd = [args.alert_script, '--play', '--message', args.message]
            if args.devices:
                cmd.extend(['--devices'] + args.devices)
            try:
                subprocess.run(cmd, check=True)
                record_alert(args.db_path, now)
                print("Alert executed and recorded.")
            except subprocess.CalledProcessError as e:
                print(f"Alert script failed: {e}", file=sys.stderr)
                return 1
        else:
            print(f"Alert suppressed (cooldown). {now - last_alert}s since last alert.")
    else:
        print("Temperature above threshold; no alert.")
    return 0

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Check avg temp over the last minute and alert if needed.")
    parser.add_argument('db_path', help="Path to SQLite DB containing readings and alerts tables")
    parser.add_argument('--threshold', '-s', type=float, default=8.0,
                        help="Temperature threshold in °C")
    parser.add_argument('--cooldown', '-c', type=int, default=3600,
                        help="Cooldown in seconds between alerts")
    parser.add_argument('--alert-script', '-a', default='chromecast_alert.py',
                        help="Path to the alert script")
    parser.add_argument('--devices', '-d', nargs='+',
                        help="Chromecast friendly names for the alert script")
    parser.add_argument('--message', '-m', default='Temperature below threshold',
                        help="Message for the alert script")
    args = parser.parse_args()
    sys.exit(main(args))

