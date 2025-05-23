"""
sensor_db.py

A simple, Pythonic, type-annotated library for persisting temperature
(and humidity) readings into a SQLite database.
Use this module to initialize the schema and insert new readings.
"""
import sqlite3
import time
from pathlib import Path
from typing import Optional, Union, Iterable, Tuple


def init_db(db_path: Union[str, Path]) -> None:
    """
    Initialize the SQLite database with the required tables.

    Tables created:
      - readings(timestamp INTEGER PRIMARY KEY, temperature REAL NOT NULL, humidity REAL)
      - alerts(alert_time INTEGER PRIMARY KEY)
    """
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS readings (
                timestamp INTEGER PRIMARY KEY,
                temperature REAL NOT NULL,
                humidity REAL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS alerts (
                alert_time INTEGER PRIMARY KEY
            )
            """
        )
        conn.commit()


def insert_reading(
    db_path: Union[str, Path],
    temperature: float,
    humidity: Optional[float] = None
) -> None:
    """
    Insert a single sensor reading.
    The timestamp is automatically set to the current time.

    Args:
        db_path: Path to SQLite database.
        temperature: Temperature value.
        humidity: Humidity value (optional).
    """
    ts: int = int(time.time())
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO readings(timestamp, temperature, humidity) VALUES (?, ?, ?)",
            (ts, temperature, humidity)
        )
        conn.commit()


def insert_readings(
    db_path: Union[str, Path],
    readings: Iterable[Tuple[int, float, Optional[float]]]
) -> None:
    """
    Batch insert multiple sensor readings efficiently.

    Each reading must be a tuple:
      (timestamp, temperature, humidity)

    Args:
        db_path: Path to SQLite database.
        readings: Iterable of (timestamp, temperature, humidity).
    """
    with sqlite3.connect(str(db_path)) as conn:
        conn.executemany(
            "INSERT OR REPLACE INTO readings(timestamp, temperature, humidity) VALUES (?, ?, ?)",
            readings
        )
        conn.commit()

# Example usage:
#
# from sensor_db import init_db, insert_reading, insert_readings
# init_db('data.db')
# insert_reading('data.db', temperature=22.5, humidity=45.0)
# batch = [
#     (1620000000, 21.0, 40.0),
#     (1620000060, 22.3, 42.1),
#     (1620000120, 23.5, 43.2)
# ]
# insert_readings('data.db', batch)

