"""
Stream connector tool for AgentFleet.

This module provides tools for connecting to event stream sources,
managing connections, and buffering events.
"""

import time
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional, Callable
from queue import Queue, Empty
from dataclasses import dataclass, field
from enum import Enum
import logging

from capstone.tools.stream_simulators import (
    TwitterStreamSimulator,
    EmergencyFeedSimulator,
    SensorDataSimulator,
    StreamConfig,
)
from capstone.models import RawEvent


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StreamStatus(str, Enum):
    """Status of a stream connection."""
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    ERROR = "ERROR"
    STOPPED = "STOPPED"


@dataclass
class StreamHealth:
    """Health metrics for a stream connection."""
    status: StreamStatus
    events_received: int = 0
    last_event_time: Optional[datetime] = None
    errors: int = 0
    last_error: Optional[str] = None
    uptime_seconds: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "status": self.status.value,
            "events_received": self.events_received,
            "last_event_time": self.last_event_time.isoformat() if self.last_event_time else None,
            "errors": self.errors,
            "last_error": self.last_error,
            "uptime_seconds": self.uptime_seconds,
        }


@dataclass
class StreamConnection:
    """
    Represents a connection to an event stream source.
    
    Attributes:
        source_type: Type of stream source (twitter, emergency, sensor)
        simulator: The stream simulator instance
        health: Health metrics for the connection
        buffer: Queue for buffering events
        thread: Background thread for stream processing
        is_active: Whether the connection is active
    """
    source_type: str
    simulator: Any
    health: StreamHealth = field(default_factory=lambda: StreamHealth(status=StreamStatus.DISCONNECTED))
    buffer: Queue = field(default_factory=lambda: Queue(maxsize=1000))
    thread: Optional[threading.Thread] = None
    is_active: bool = False
    start_time: Optional[datetime] = None
    
    def start(self):
        """Start the stream connection in a background thread."""
        if self.is_active:
            logger.warning(f"Stream {self.source_type} is already active")
            return
        
        self.is_active = True
        self.start_time = datetime.utcnow()
        self.health.status = StreamStatus.CONNECTING
        
        # Start background thread
        self.thread = threading.Thread(target=self._stream_worker, daemon=True)
        self.thread.start()
        
        logger.info(f"Started stream connection for {self.source_type}")
    
    def stop(self):
        """Stop the stream connection."""
        if not self.is_active:
            return
        
        self.is_active = False
        self.simulator.stop()
        
        if self.thread:
            self.thread.join(timeout=5.0)
        
        self.health.status = StreamStatus.STOPPED
        logger.info(f"Stopped stream connection for {self.source_type}")
    
    def _stream_worker(self):
        """Background worker that processes the stream."""
        try:
            self.health.status = StreamStatus.CONNECTED
            
            for event_data in self.simulator.stream():
                if not self.is_active:
                    break
                
                try:
                    # Convert to RawEvent
                    raw_event = RawEvent(
                        source=event_data["source"],
                        timestamp=datetime.fromisoformat(event_data["timestamp"]),
                        content=event_data["content"],
                        metadata=event_data.get("metadata", {})
                    )
                    
                    # Add to buffer
                    try:
                        self.buffer.put(raw_event, timeout=1.0)
                        self.health.events_received += 1
                        self.health.last_event_time = datetime.utcnow()
                    except Exception as e:
                        logger.warning(f"Buffer full for {self.source_type}, dropping event")
                        self.health.errors += 1
                        self.health.last_error = "Buffer overflow"
                
                except Exception as e:
                    logger.error(f"Error processing event from {self.source_type}: {e}")
                    self.health.errors += 1
                    self.health.last_error = str(e)
        
        except Exception as e:
            logger.error(f"Stream worker error for {self.source_type}: {e}")
            self.health.status = StreamStatus.ERROR
            self.health.last_error = str(e)
        
        finally:
            if self.is_active:
                self.health.status = StreamStatus.DISCONNECTED
    
    def get_events(self, max_count: int = 10, timeout: float = 1.0) -> List[RawEvent]:
        """
        Get events from the buffer.
        
        Args:
            max_count: Maximum number of events to retrieve
            timeout: Timeout for waiting for events (seconds)
            
        Returns:
            List of RawEvent objects
        """
        events = []
        deadline = time.time() + timeout
        
        while len(events) < max_count and time.time() < deadline:
            try:
                remaining_time = max(0, deadline - time.time())
                event = self.buffer.get(timeout=remaining_time)
                events.append(event)
            except Empty:
                break
        
        return events
    
    def get_health(self) -> StreamHealth:
        """
        Get current health metrics for the connection.
        
        Returns:
            StreamHealth object with current metrics
        """
        if self.start_time:
            self.health.uptime_seconds = (datetime.utcnow() - self.start_time).total_seconds()
        
        return self.health


class StreamConnector:
    """
    Manages connections to multiple event stream sources.
    
    Provides a unified interface for connecting to different stream types,
    monitoring health, and retrieving events.
    """
    
    def __init__(self):
        """Initialize the stream connector."""
        self.connections: Dict[str, StreamConnection] = {}
        self.logger = logging.getLogger(__name__)
    
    def connect(
        self,
        source_type: str,
        config: Optional[StreamConfig] = None
    ) -> StreamConnection:
        """
        Connect to an event stream source.
        
        Args:
            source_type: Type of stream ("twitter", "emergency", "sensor")
            config: Optional stream configuration
            
        Returns:
            StreamConnection object
            
        Raises:
            ValueError: If source_type is not supported
        """
        # Check if already connected
        if source_type in self.connections:
            connection = self.connections[source_type]
            if connection.is_active:
                self.logger.info(f"Already connected to {source_type}")
                return connection
            else:
                # Reconnect
                connection.start()
                return connection
        
        # Create simulator based on source type
        if source_type == "twitter":
            simulator = TwitterStreamSimulator(config)
        elif source_type == "emergency":
            simulator = EmergencyFeedSimulator(config)
        elif source_type == "sensor":
            simulator = SensorDataSimulator(config)
        else:
            raise ValueError(f"Unsupported source type: {source_type}")
        
        # Create connection
        connection = StreamConnection(
            source_type=source_type,
            simulator=simulator
        )
        
        # Start the connection
        connection.start()
        
        # Store connection
        self.connections[source_type] = connection
        
        self.logger.info(f"Connected to {source_type} stream")
        return connection
    
    def disconnect(self, source_type: str):
        """
        Disconnect from an event stream source.
        
        Args:
            source_type: Type of stream to disconnect
        """
        if source_type in self.connections:
            connection = self.connections[source_type]
            connection.stop()
            self.logger.info(f"Disconnected from {source_type} stream")
    
    def disconnect_all(self):
        """Disconnect from all event stream sources."""
        for source_type in list(self.connections.keys()):
            self.disconnect(source_type)
    
    def get_connection(self, source_type: str) -> Optional[StreamConnection]:
        """
        Get a stream connection by source type.
        
        Args:
            source_type: Type of stream
            
        Returns:
            StreamConnection object or None if not connected
        """
        return self.connections.get(source_type)
    
    def get_all_connections(self) -> Dict[str, StreamConnection]:
        """
        Get all active stream connections.
        
        Returns:
            Dictionary of source_type -> StreamConnection
        """
        return self.connections.copy()
    
    def get_health_status(self) -> Dict[str, Dict[str, Any]]:
        """
        Get health status for all connections.
        
        Returns:
            Dictionary of source_type -> health metrics
        """
        health_status = {}
        
        for source_type, connection in self.connections.items():
            health = connection.get_health()
            health_status[source_type] = health.to_dict()
        
        return health_status
    
    def get_events_batch(
        self,
        source_types: Optional[List[str]] = None,
        max_per_source: int = 10,
        timeout: float = 1.0
    ) -> Dict[str, List[RawEvent]]:
        """
        Get a batch of events from multiple sources.
        
        Args:
            source_types: List of source types to get events from (all if None)
            max_per_source: Maximum events per source
            timeout: Timeout for waiting for events
            
        Returns:
            Dictionary of source_type -> list of RawEvent objects
        """
        if source_types is None:
            source_types = list(self.connections.keys())
        
        events_batch = {}
        
        for source_type in source_types:
            connection = self.connections.get(source_type)
            if connection and connection.is_active:
                events = connection.get_events(max_count=max_per_source, timeout=timeout)
                if events:
                    events_batch[source_type] = events
        
        return events_batch
    
    def is_healthy(self, source_type: str) -> bool:
        """
        Check if a stream connection is healthy.
        
        Args:
            source_type: Type of stream to check
            
        Returns:
            True if connection is healthy, False otherwise
        """
        connection = self.connections.get(source_type)
        if not connection:
            return False
        
        health = connection.get_health()
        
        # Check if connected
        if health.status != StreamStatus.CONNECTED:
            return False
        
        # Check if receiving events (should have received event in last 30 seconds)
        if health.last_event_time:
            time_since_last_event = (datetime.utcnow() - health.last_event_time).total_seconds()
            if time_since_last_event > 30:
                return False
        
        # Check error rate (less than 10% errors)
        if health.events_received > 0:
            error_rate = health.errors / health.events_received
            if error_rate > 0.1:
                return False
        
        return True


# Global stream connector instance
_global_connector: Optional[StreamConnector] = None


def get_stream_connector() -> StreamConnector:
    """
    Get the global stream connector instance.
    
    Returns:
        StreamConnector instance
    """
    global _global_connector
    
    if _global_connector is None:
        _global_connector = StreamConnector()
    
    return _global_connector


def stream_connector_tool(
    source_type: str,
    action: str = "connect",
    max_events: int = 10
) -> Dict[str, Any]:
    """
    Tool function for connecting to and managing event streams.
    
    This function can be registered as an ADK tool for agents to use.
    
    Args:
        source_type: Type of stream ("twitter", "emergency", "sensor", "all")
        action: Action to perform ("connect", "disconnect", "get_events", "health")
        max_events: Maximum number of events to retrieve (for get_events action)
        
    Returns:
        Dictionary with action result
    """
    connector = get_stream_connector()
    
    try:
        if action == "connect":
            if source_type == "all":
                # Connect to all sources
                results = {}
                for src in ["twitter", "emergency", "sensor"]:
                    connection = connector.connect(src)
                    results[src] = {
                        "status": "connected",
                        "health": connection.get_health().to_dict()
                    }
                return {"success": True, "connections": results}
            else:
                connection = connector.connect(source_type)
                return {
                    "success": True,
                    "source_type": source_type,
                    "status": "connected",
                    "health": connection.get_health().to_dict()
                }
        
        elif action == "disconnect":
            if source_type == "all":
                connector.disconnect_all()
                return {"success": True, "message": "Disconnected from all sources"}
            else:
                connector.disconnect(source_type)
                return {"success": True, "source_type": source_type, "status": "disconnected"}
        
        elif action == "get_events":
            if source_type == "all":
                events_batch = connector.get_events_batch(max_per_source=max_events)
                # Convert events to dictionaries
                result = {}
                for src, events in events_batch.items():
                    result[src] = [event.to_dict() for event in events]
                return {"success": True, "events": result, "total_count": sum(len(e) for e in result.values())}
            else:
                connection = connector.get_connection(source_type)
                if not connection:
                    return {"success": False, "error": f"Not connected to {source_type}"}
                
                events = connection.get_events(max_count=max_events)
                return {
                    "success": True,
                    "source_type": source_type,
                    "events": [event.to_dict() for event in events],
                    "count": len(events)
                }
        
        elif action == "health":
            if source_type == "all":
                health_status = connector.get_health_status()
                return {"success": True, "health": health_status}
            else:
                connection = connector.get_connection(source_type)
                if not connection:
                    return {"success": False, "error": f"Not connected to {source_type}"}
                
                health = connection.get_health()
                return {
                    "success": True,
                    "source_type": source_type,
                    "health": health.to_dict(),
                    "is_healthy": connector.is_healthy(source_type)
                }
        
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    except Exception as e:
        logger.error(f"Error in stream_connector_tool: {e}")
        return {"success": False, "error": str(e)}
