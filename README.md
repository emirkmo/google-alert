# Google Alert

A Python library for sending temperature alerts via Chromecast devices. This library provides the core functionality for monitoring temperature data stored in SQLite and broadcasting alerts when thresholds are exceeded.

## Features

- 📺 **Chromecast Alerts**: Instant notifications via Chromecast devices
- 🌙 **Night Mode**: Suppress alerts during specified hours (e.g., 9 PM - 7 AM)
- ⏰ **Cooldown Period**: Prevent alert spam with configurable cooldown periods
- 🔒 **Process Safety**: File locking prevents overlapping monitoring processes
- 📊 **SQLite Integration**: Works with temperature data stored in SQLite databases
- 🧪 **Comprehensive Testing**: Full test suite covering all core functionality

## Quick Start

### Installation

**From PyPI (recommended):**
```bash
pip install google-alert
```

**From source:**
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

**Set up monitoring alerts** (run via cron every minute):
```bash
python -m google_alert.monitor_chron /path/to/database.db
```

**Note**: This library focuses on the alerting functionality. For a complete temperature monitoring system including DHT sensor reading, see the [DHT22 Temperature Monitor](https://github.com/emirkmo/dht22_temp_monitor_google_alert/) repository, which includes the `temp_sensor.py` implementation and embedded Adafruit_DHT library.

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

### Core Modules

- **`monitor_chron.py`**: Main monitoring script that checks temperature averages and sends alerts
- **`sensor_db.py`**: Database operations for reading temperature data and managing alert history
- **`browser.py`**: Chromecast device discovery and message broadcasting

### Module Descriptions

#### `monitor_chron.py`
The core monitoring module that runs as a cron job. It:
- Queries average temperature from SQLite over a configurable time window
- Checks if temperature is below threshold
- Enforces cooldown periods to prevent alert spam
- Implements night mode to suppress alerts during specified hours
- Uses file locking to prevent overlapping runs
- Sends alerts via Chromecast when conditions are met

#### `sensor_db.py`
Database interface module that provides:
- SQLite database initialization with proper schema
- Temperature reading insertion and retrieval
- Alert history tracking for cooldown management
- Average temperature calculation over time windows

#### `browser.py`
Chromecast communication module that handles:
- Automatic discovery of Chromecast devices on the network
- Message broadcasting to all available devices
- Error handling for network and device communication issues

### Example Usage

This library is designed to work with any temperature data source. See the `examples/` directory for usage examples:

- **`examples/temp_sensor.py`**: Simple example showing how to use the library with DHT sensors
- **[DHT22 Temperature Monitor](https://github.com/emirkmo/dht22_temp_monitor_google_alert/)**: Complete production implementation with modular sensor handling

## Library Design Philosophy

### Separation of Concerns

This library follows a clean separation of concerns:

- **`google_alert`**: Pure alerting library focused on Chromecast notifications
- **Sensor implementations**: Separate repositories handle hardware-specific data collection
- **Database schema**: Controlled by the alerting library for consistency

### Why Separate Repositories?

1. **Library Reusability**: The `google_alert` package can be used with any temperature data source (DHT22, DS18B20, BME280, etc.)
2. **Independent Evolution**: Alerting logic and sensor hardware can evolve independently
3. **Clear Dependencies**: Sensor implementations depend on the alerting library, not vice versa
4. **Focused Scope**: Each repository has a single, well-defined responsibility

### Publishing to PyPI

This library uses **trusted publishing** for secure, automated PyPI releases via GitHub Actions. No API tokens are required!

#### Automated Publishing

Releases are automatically published to PyPI when GitHub releases are created:

1. **Update version** in `pyproject.toml`
2. **Create GitHub release** with a tag
3. **GitHub Actions** automatically builds and publishes to PyPI via the `pypi` environment

**Note**: The `pypi` environment has protection rules requiring approval before publishing.

#### Manual Publishing

For manual publishing (requires PyPI API token):

```bash
# Build the package
uv build

# Publish to PyPI
uv publish
```

#### Trusted Publishing Setup

The repository is configured for PyPI trusted publishing with these settings:
- **PyPI Project**: `google-alert`
- **GitHub Owner**: `emirkmo`
- **GitHub Repository**: `google-alert`
- **Workflow**: `.github/workflows/ci-cd.yml`
- **Environment**: `pypi` (with protection rules)

#### Verifying Setup

Check the environment and publishing configuration:

```bash
# Verify GitHub environment exists
gh api repos/emirkmo/google-alert/environments

# Check workflow configuration
gh workflow view ci-cd.yml
```

The minimal dependencies (`orjson`, `pychromecast`) make it lightweight and suitable for distribution.

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

### Examples

Check the `examples/` directory for usage examples:
- `examples/temp_sensor.py`: Simple DHT sensor integration example

### Building the Package

```bash
# Build distribution packages
uv build

# The built packages will be in the dist/ directory
```

## Requirements

- Python 3.11+
- Chromecast devices on the same network
- SQLite database with temperature readings

### Dependencies

- `orjson`: Fast JSON serialization
- `pychromecast`: Chromecast device communication

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
3. **No temperature data**: Ensure your temperature sensor system is writing data to the SQLite database

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
