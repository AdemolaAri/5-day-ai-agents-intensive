"""
MCP (Model Context Protocol) Envelope utilities for AgentFleet.

This module provides utilities for creating, parsing, and validating
MCP-inspired message envelopes used for agent-to-agent communication.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Dict, Any, Optional, Literal
from enum import Enum
import json
import uuid


class EnvelopeSchema(str, Enum):
    """Supported MCP envelope schema versions."""
    MCP_ENVELOPE_V1 = "mcp_envelope_v1"
    EVENT_V1 = "event_v1"
    VERIFIED_EVENT_V1 = "verified_event_v1"
    INCIDENT_BRIEF_V1 = "incident_brief_v1"
    TRIAGED_INCIDENT_V1 = "triaged_incident_v1"
    DISPATCH_V1 = "dispatch_v1"


class PayloadType(str, Enum):
    """Types of payloads that can be sent in envelopes."""
    EVENT = "event"
    INCIDENT = "incident"
    TRIAGE = "triage"
    DISPATCH = "dispatch"
    ERROR = "error"
    ACK = "acknowledgment"


@dataclass
class MCPEnvelope:
    """
    MCP-inspired message envelope for agent-to-agent communication.
    
    Attributes:
        schema: Schema version identifier
        session_id: Unique session identifier for incident lifecycle
        timestamp: Envelope creation timestamp
        source_agent: Name of the agent that created the envelope
        payload: The actual message payload
        metadata: Additional metadata (optional)
    """
    schema: str
    session_id: str
    timestamp: datetime
    source_agent: str
    payload: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Serialize envelope to dictionary.
        
        Returns:
            Dictionary representation of the envelope
        """
        return {
            "schema": self.schema,
            "session_id": self.session_id,
            "timestamp": self.timestamp.isoformat(),
            "source_agent": self.source_agent,
            "payload": self.payload,
            "metadata": self.metadata
        }
    
    def to_json(self) -> str:
        """
        Serialize envelope to JSON string.
        
        Returns:
            JSON string representation of the envelope
        """
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MCPEnvelope":
        """
        Deserialize envelope from dictionary.
        
        Args:
            data: Dictionary containing envelope data
            
        Returns:
            MCPEnvelope instance
            
        Raises:
            ValueError: If required fields are missing
        """
        required_fields = ["schema", "session_id", "timestamp", "source_agent", "payload"]
        missing_fields = [field for field in required_fields if field not in data]
        
        if missing_fields:
            raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")
        
        return cls(
            schema=data["schema"],
            session_id=data["session_id"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            source_agent=data["source_agent"],
            payload=data["payload"],
            metadata=data.get("metadata", {})
        )
    
    @classmethod
    def from_json(cls, json_str: str) -> "MCPEnvelope":
        """
        Deserialize envelope from JSON string.
        
        Args:
            json_str: JSON string containing envelope data
            
        Returns:
            MCPEnvelope instance
            
        Raises:
            ValueError: If JSON is invalid or required fields are missing
        """
        try:
            data = json.loads(json_str)
            return cls.from_dict(data)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {e}")
    
    def validate_schema(self) -> bool:
        """
        Validate that the envelope has a recognized schema.
        
        Returns:
            True if schema is valid, False otherwise
        """
        try:
            EnvelopeSchema(self.schema)
            return True
        except ValueError:
            return False
    
    def validate_payload_type(self) -> bool:
        """
        Validate that the payload has a recognized type field.
        
        Returns:
            True if payload type is valid, False otherwise
        """
        if "type" not in self.payload:
            return False
        
        try:
            PayloadType(self.payload["type"])
            return True
        except ValueError:
            return False
    
    def validate(self) -> tuple[bool, Optional[str]]:
        """
        Validate the entire envelope structure.
        
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Check schema
        if not self.validate_schema():
            return False, f"Invalid schema: {self.schema}"
        
        # Check required fields
        if not self.session_id:
            return False, "Missing session_id"
        
        if not self.source_agent:
            return False, "Missing source_agent"
        
        if not self.payload:
            return False, "Missing payload"
        
        # Check payload structure
        if not isinstance(self.payload, dict):
            return False, "Payload must be a dictionary"
        
        if "type" not in self.payload:
            return False, "Payload missing 'type' field"
        
        if "data" not in self.payload:
            return False, "Payload missing 'data' field"
        
        return True, None


def create_envelope(
    schema: str,
    source_agent: str,
    payload: Dict[str, Any],
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> MCPEnvelope:
    """
    Create a new MCP envelope with automatic session_id and timestamp.
    
    Args:
        schema: Schema version identifier
        source_agent: Name of the agent creating the envelope
        payload: The message payload
        session_id: Optional session identifier (generated if not provided)
        metadata: Optional additional metadata
        
    Returns:
        New MCPEnvelope instance
    """
    if session_id is None:
        session_id = str(uuid.uuid4())
    
    if metadata is None:
        metadata = {}
    
    return MCPEnvelope(
        schema=schema,
        session_id=session_id,
        timestamp=datetime.utcnow(),
        source_agent=source_agent,
        payload=payload,
        metadata=metadata
    )


def create_event_envelope(
    source_agent: str,
    event_data: Dict[str, Any],
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> MCPEnvelope:
    """
    Create an envelope for event data.
    
    Args:
        source_agent: Name of the agent creating the envelope
        event_data: Event data dictionary
        session_id: Optional session identifier
        metadata: Optional additional metadata
        
    Returns:
        MCPEnvelope with event payload
    """
    payload = {
        "type": PayloadType.EVENT.value,
        "data": event_data,
        "metadata": metadata or {}
    }
    
    return create_envelope(
        schema=EnvelopeSchema.EVENT_V1.value,
        source_agent=source_agent,
        payload=payload,
        session_id=session_id,
        metadata=metadata
    )


def create_incident_envelope(
    source_agent: str,
    incident_data: Dict[str, Any],
    session_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> MCPEnvelope:
    """
    Create an envelope for incident data.
    
    Args:
        source_agent: Name of the agent creating the envelope
        incident_data: Incident data dictionary
        session_id: Session identifier (required for incidents)
        metadata: Optional additional metadata
        
    Returns:
        MCPEnvelope with incident payload
    """
    payload = {
        "type": PayloadType.INCIDENT.value,
        "data": incident_data,
        "metadata": metadata or {}
    }
    
    return create_envelope(
        schema=EnvelopeSchema.INCIDENT_BRIEF_V1.value,
        source_agent=source_agent,
        payload=payload,
        session_id=session_id,
        metadata=metadata
    )


def create_triage_envelope(
    source_agent: str,
    triage_data: Dict[str, Any],
    session_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> MCPEnvelope:
    """
    Create an envelope for triage data.
    
    Args:
        source_agent: Name of the agent creating the envelope
        triage_data: Triage data dictionary
        session_id: Session identifier (required for triage)
        metadata: Optional additional metadata
        
    Returns:
        MCPEnvelope with triage payload
    """
    payload = {
        "type": PayloadType.TRIAGE.value,
        "data": triage_data,
        "metadata": metadata or {}
    }
    
    return create_envelope(
        schema=EnvelopeSchema.TRIAGED_INCIDENT_V1.value,
        source_agent=source_agent,
        payload=payload,
        session_id=session_id,
        metadata=metadata
    )


def create_dispatch_envelope(
    source_agent: str,
    dispatch_data: Dict[str, Any],
    session_id: str,
    metadata: Optional[Dict[str, Any]] = None
) -> MCPEnvelope:
    """
    Create an envelope for dispatch data.
    
    Args:
        source_agent: Name of the agent creating the envelope
        dispatch_data: Dispatch data dictionary
        session_id: Session identifier (required for dispatch)
        metadata: Optional additional metadata
        
    Returns:
        MCPEnvelope with dispatch payload
    """
    payload = {
        "type": PayloadType.DISPATCH.value,
        "data": dispatch_data,
        "metadata": metadata or {}
    }
    
    return create_envelope(
        schema=EnvelopeSchema.DISPATCH_V1.value,
        source_agent=source_agent,
        payload=payload,
        session_id=session_id,
        metadata=metadata
    )


def create_error_envelope(
    source_agent: str,
    error_message: str,
    error_details: Optional[Dict[str, Any]] = None,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> MCPEnvelope:
    """
    Create an envelope for error reporting.
    
    Args:
        source_agent: Name of the agent reporting the error
        error_message: Error message
        error_details: Optional error details
        session_id: Optional session identifier
        metadata: Optional additional metadata
        
    Returns:
        MCPEnvelope with error payload
    """
    payload = {
        "type": PayloadType.ERROR.value,
        "data": {
            "error_message": error_message,
            "error_details": error_details or {}
        },
        "metadata": metadata or {}
    }
    
    return create_envelope(
        schema=EnvelopeSchema.MCP_ENVELOPE_V1.value,
        source_agent=source_agent,
        payload=payload,
        session_id=session_id,
        metadata=metadata
    )


def parse_envelope(data: Dict[str, Any]) -> tuple[MCPEnvelope, Optional[str]]:
    """
    Parse and validate an envelope from dictionary data.
    
    Args:
        data: Dictionary containing envelope data
        
    Returns:
        Tuple of (envelope, error_message)
        If parsing succeeds, error_message is None
        If parsing fails, envelope is None and error_message contains the error
    """
    try:
        envelope = MCPEnvelope.from_dict(data)
        is_valid, error_msg = envelope.validate()
        
        if not is_valid:
            return None, error_msg
        
        return envelope, None
    except Exception as e:
        return None, str(e)


def validate_envelope_data(data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
    """
    Validate envelope data without creating an envelope instance.
    
    Args:
        data: Dictionary containing envelope data
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    envelope, error_msg = parse_envelope(data)
    
    if envelope is None:
        return False, error_msg
    
    return True, None
