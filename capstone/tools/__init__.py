"""
AgentFleet Tools Module

Contains custom tools for agents:
- Stream connectors
- Verification tools
- Memory Bank tools
- Job queue tools
"""

from capstone.tools.stream_simulators import (
    TwitterStreamSimulator,
    EmergencyFeedSimulator,
    SensorDataSimulator,
    StreamConfig,
)

from capstone.tools.stream_connector import (
    StreamConnector,
    StreamConnection,
    StreamStatus,
    StreamHealth,
    get_stream_connector,
    stream_connector_tool,
)

from capstone.tools.memory_tools import (
    query_memory_bank,
    store_incident_memory,
    get_memory_bank_stats,
    retrieve_incident_by_id,
    MEMORY_TOOLS,
)

__all__ = [
    # Simulators
    "TwitterStreamSimulator",
    "EmergencyFeedSimulator",
    "SensorDataSimulator",
    "StreamConfig",
    # Connector
    "StreamConnector",
    "StreamConnection",
    "StreamStatus",
    "StreamHealth",
    "get_stream_connector",
    "stream_connector_tool",
    # Memory Tools
    "query_memory_bank",
    "store_incident_memory",
    "get_memory_bank_stats",
    "retrieve_incident_by_id",
    "MEMORY_TOOLS",
]
