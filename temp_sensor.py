import Adafruit_DHT # type: ignore
from time import sleep
from typing import Any, TypedDict, Iterable
import json
import logging
import logging.handlers
import sqlite3
from pathlib import Path
from google_alert import sensor_db
import time


sensor = Adafruit_DHT.DHT22
# DHT22 sensor conntected to GPIO12 as per instructions
pin = 12
DEFAULT_DB = Path("/var/lib/temp_sensor/data.db")

Reading = tuple[int, float, float | None]

def format_vals(humidity: Any, temperature: Any) -> tuple[float, float | None] | None:
    if temperature is None:
        return None
    try:
        temp_c = float(f"{temperature:0.1f}")
    except (ValueError, TypeError) as err:
        logging.error(err)
        return None

    try:
        humidity_percent = float(f"{humidity:0.1f}")
    except (ValueError, TypeError) as err:
        logging.error(err)
        humidity_percent = None
    return temp_c, humidity_percent

def print_json():
    """Continually print json"""
    while True:
        humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
        ts = int(time.time())
        reading = format_vals(humidity, temperature)
        if not reading:
            continue
        temp_c, humidity_percent = reading
        as_float_dict = {"timestamp": ts, "temperature": temp_c, "humidity": humidity_percent}
        print(json.dumps(as_float_dict))

class JSONTemps(TypedDict):
    timestamp: int
    temperature: float
    humidity: float | None

def get_last_x(db_path: Path, limit: int = 24) -> Iterable[JSONTemps]:
    """
    Fetch the `limit` most recent readings and print them as JSON:
      [{"timestamp":…, "temperature":…, "humidity":…}, …]
    """
    with sqlite3.connect(str(db_path)) as conn:
        cur = conn.cursor()
        cur.execute(
            "SELECT timestamp, temperature, humidity "
            "FROM readings "
            "ORDER BY timestamp DESC "
            f"LIMIT {limit}"
        )
        rows = cur.fetchall()
    for ts, temp, hum in reversed(rows):
        yield {"timestamp": ts, "temperature": temp, "humidity": hum}

def main():
    """Write data to sqlite"""
    DEFAULT_DB.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_DB.touch(exist_ok=True)
    sensor_db.init_db(DEFAULT_DB)
    readings: list[Reading] = []
    while True:
        humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)
        ts = int(time.time())
        reading = format_vals(humidity=humidity, temperature=temperature)
        if reading:
            readings.append((ts, *reading))


        if len(readings) >= 24:
            try:
                sensor_db.insert_readings(DEFAULT_DB,readings)
            except Exception as e:
                logging.error(f"DB error inserting batch: {e}")
        readings.clear()        
        sleep(2.5)

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

    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        print("Shutting down sensor due to system exit | keyboard interrupt")