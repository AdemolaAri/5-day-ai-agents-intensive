# AgentFleet Tools

This directory contains custom tools for the AgentFleet incident response system.

## Stream Simulators

Three event stream simulators are provided for testing and demonstration:

### TwitterStreamSimulator
- Generates realistic social media posts about incidents
- Incident types: flooding, fire, power outage, traffic, weather
- Configurable event rate and burst probability
- Includes metadata: tweet_id, user, retweets, likes, verified status

### EmergencyFeedSimulator
- Generates official emergency alerts
- Alert types: weather, evacuation, hazmat, infrastructure, public safety
- Severity levels: CRITICAL, HIGH, MODERATE, LOW
- Includes metadata: alert_id, agency, priority, expiration time

### SensorDataSimulator
- Generates IoT sensor readings
- Sensor types: water_level, temperature, air_quality, seismic, pressure, radiation
- Simulates normal readings with occasional anomalies
- Includes metadata: sensor_id, value, unit, status, calibration date

## Stream Connector

The `StreamConnector` class provides a unified interface for managing event streams:

### Features
- Connect to multiple stream sources simultaneously
- Background thread processing with event buffering
- Health monitoring with metrics (events received, errors, uptime)
- Batch event retrieval from multiple sources
- Automatic reconnection handling

### Usage

```python
from capstone.tools import get_stream_connector, stream_connector_tool

# Get the global connector instance
connector = get_stream_connector()

# Connect to a stream
result = stream_connector_tool("twitter", "connect")

# Get events
result = stream_connector_tool("twitter", "get_events", max_events=10)

# Check health
result = stream_connector_tool("twitter", "health")

# Connect to all streams
result = stream_connector_tool("all", "connect")

# Disconnect
result = stream_connector_tool("twitter", "disconnect")
```

### Tool Function

The `stream_connector_tool` function can be registered as an ADK tool for agents:

**Parameters:**
- `source_type`: "twitter", "emergency", "sensor", or "all"
- `action`: "connect", "disconnect", "get_events", or "health"
- `max_events`: Maximum number of events to retrieve (default: 10)

**Returns:**
- Dictionary with action result, including success status and relevant data

## Requirements Satisfied

This implementation satisfies the following requirements:

- **Requirement 1.1**: Establishes connections to all configured event stream sources
- **Requirement 1.5**: Maintains connection health metrics for each event stream source

The stream connector provides:
- ✓ Multiple simultaneous stream connections
- ✓ Event buffering (up to 1000 events per stream)
- ✓ Health monitoring (status, events received, errors, uptime)
- ✓ Batch event retrieval
- ✓ Automatic background processing
- ✓ Graceful connection management

## Testing

Run the test suite to verify functionality:

```bash
python test_stream_tools.py
```

The test suite verifies:
- Individual simulator functionality
- Stream connection establishment
- Event retrieval
- Health monitoring
- Multi-stream management
- Graceful disconnection
