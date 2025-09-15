# Google Alert

A temperature monitoring system that sends alerts via Chromecast when temperatures fall below a configured threshold. Perfect for monitoring server rooms, greenhouses, or any environment where temperature monitoring is critical.

## Features

- 🌡️ **Temperature Monitoring**: Continuous monitoring with configurable thresholds
- 📺 **Chromecast Alerts**: Instant notifications via Chromecast devices
- 🌙 **Night Mode**: Suppress alerts during specified hours (e.g., 9 PM - 7 AM)
- ⏰ **Cooldown Period**: Prevent alert spam with configurable cooldown periods
- 🔒 **Process Safety**: File locking prevents overlapping monitoring processes
- 📊 **SQLite Storage**: Persistent storage of temperature readings and alert history
- 🧪 **Comprehensive Testing**: Full test suite with 100% test coverage

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/emirkmo/google-alert.git
cd google-alert

# Install with uv (recommended)
uv sync

# Or install with pip
pip install -e .
```

### Basic Usage

1. **Start temperature monitoring**:
   ```bash
   python temp_sensor.py /path/to/database.db
   ```

2. **Set up monitoring alerts** (run via cron every minute):
   ```bash
   python -m google_alert.monitor_chron /path/to/database.db
   ```

## Configuration

### Monitor Settings

The monitor supports several command-line options:

```bash
python -m google_alert.monitor_chron database.db [options]

Options:
  -s, --threshold FLOAT    Temperature threshold in °C (default: 8.0)
  -c, --cooldown INT       Cooldown period in seconds (default: 3600)
  -w, --window INT         Time window in seconds for averaging (default: 60)
  -m, --message TEXT       Alert message (default: "Temperature below threshold")
  --night-start INT        Hour when night mode starts (0-23, default: 21)
  --night-end INT          Hour when night mode ends (0-23, default: 7)
```

### Example Cron Setup

Add to your crontab (`crontab -e`) to run monitoring every minute:

```bash
* * * * * /path/to/venv/bin/python -m google_alert.monitor_chron /path/to/database.db
```

## Architecture

### Components

- **`temp_sensor.py`**: Main temperature sensor script that reads from DHT22/AM2302 sensors
- **`monitor_chron.py`**: Cron job script that checks temperature averages and sends alerts
- **`sensor_db.py`**: Database operations for storing readings and alert history
- **`browser.py`**: Chromecast device discovery and message broadcasting

### Database Schema

The system uses SQLite with two main tables:

- **`readings`**: Stores temperature and humidity readings with timestamps
- **`alerts`**: Tracks alert history for cooldown management

## Development

### Running Tests

```bash
# Install development dependencies
uv sync --extra dev

# Run all tests
uv run pytest tests/ -v

# Run specific test
uv run pytest tests/test_monitor.py::TestMonitorMinute::test_night_time_alert_silencing -v
```

### Building the Package

```bash
# Build distribution packages
uv build

# The built packages will be in the dist/ directory
```

## Requirements

- Python 3.11+
- DHT22/AM2302 temperature sensor (for temp_sensor.py)
- Chromecast devices on the same network
- SQLite database

### Dependencies

- `orjson`: Fast JSON serialization
- `pychromecast`: Chromecast device communication
- `Adafruit_DHT`: DHT sensor library (for temp_sensor.py)

## Alert Logic

The system follows this decision tree for sending alerts:

1. ✅ **Temperature Check**: Is average temperature below threshold?
2. ✅ **Cooldown Check**: Has enough time passed since last alert?
3. ✅ **Night Mode Check**: Is current time outside night mode hours?
4. ✅ **Send Alert**: If all conditions are met, broadcast to Chromecast devices

## Night Mode

Night mode suppresses alerts during specified hours to avoid disturbing sleep. The default night window is 9 PM to 7 AM, but this can be customized via command-line options.

## Troubleshooting

### Common Issues

1. **No Chromecast devices found**: Ensure devices are on the same network and not in guest mode
2. **Database locked**: Check for multiple instances running simultaneously
3. **Sensor read errors**: Verify DHT sensor connections and permissions

### Logging

The system logs to syslog (LOCAL0 facility) by default. Check your system logs:

```bash
# On systemd systems
journalctl -f -u your-service

# On traditional systems
tail -f /var/log/syslog | grep monitor_chron
```

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is open source. Please check the repository for license details.

## Support

For issues and questions:
- Open an issue on GitHub
- Check the troubleshooting section above
- Review the test cases for usage examples
