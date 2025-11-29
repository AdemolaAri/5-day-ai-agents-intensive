"""
Data models for AgentFleet incident response system.

This module defines all data structures used throughout the agent pipeline,
including events, incidents, jobs, and their serialization methods.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, Any, List, Optional
from enum import Enum


class SeverityLevel(str, Enum):
    """Incident severity classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class JobStatus(str, Enum):
    """Job processing status."""
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class IncidentStatus(str, Enum):
    """Incident lifecycle status."""
    DISPATCHED = "DISPATCHED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"


@dataclass
class RawEvent:
    """
    Raw event data from external sources before normalization.
    
    Attributes:
        source: Event source identifier (e.g., "twitter", "emergency", "sensor")
        timestamp: Event occurrence time
        content: Raw event content/text
        metadata: Additional source-specific metadata
    """
    source: str
    timestamp: datetime
    content: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "content": self.content,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RawEvent":
        """Deserialize from dictionary."""
        return cls(
            source=data["source"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            content=data["content"],
            metadata=data.get("metadata", {})
        )


@dataclass
class NormalizedEvent:
    """
    Normalized event with extracted entities and standardized format.
    
    Attributes:
        event_id: Unique event identifier
        source: Event source identifier
        timestamp: Event occurrence time
        content: Normalized event content
        entities: Extracted entities (locations, times, types)
        location: Extracted location information
        event_type: Classified event type
    """
    event_id: str
    source: str
    timestamp: datetime
    content: str
    entities: List[str] = field(default_factory=list)
    location: Optional[str] = None
    event_type: str = "unknown"
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "content": self.content,
            "entities": self.entities,
            "location": self.location,
            "event_type": self.event_type
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "NormalizedEvent":
        """Deserialize from dictionary."""
        return cls(
            event_id=data["event_id"],
            source=data["source"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            content=data["content"],
            entities=data.get("entities", []),
            location=data.get("location"),
            event_type=data.get("event_type", "unknown")
        )


@dataclass
class Claim:
    """
    A verifiable claim extracted from an event.
    
    Attributes:
        text: The claim text
        source: Source of the claim
    """
    text: str
    source: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "text": self.text,
            "source": self.source
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Claim":
        """Deserialize from dictionary."""
        return cls(
            text=data["text"],
            source=data["source"]
        )


@dataclass
class VerificationResult:
    """
    Result of claim verification process.
    
    Attributes:
        claim: The verified claim
        verified: Whether the claim was verified
        confidence: Confidence score (0.0 to 1.0)
        sources: List of verification sources
    """
    claim: Claim
    verified: bool
    confidence: float
    sources: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "claim": self.claim.to_dict(),
            "verified": self.verified,
            "confidence": self.confidence,
            "sources": self.sources
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerificationResult":
        """Deserialize from dictionary."""
        return cls(
            claim=Claim.from_dict(data["claim"]),
            verified=data["verified"],
            confidence=data["confidence"],
            sources=data.get("sources", [])
        )


@dataclass
class VerifiedEvent:
    """
    Event with verification results and reliability scoring.
    
    Attributes:
        event_id: Unique event identifier
        original_event: The normalized event that was verified
        reliability_score: Overall reliability score (0.0 to 1.0)
        verified_claims: List of verification results
        verification_timestamp: When verification was completed
    """
    event_id: str
    original_event: NormalizedEvent
    reliability_score: float
    verified_claims: List[VerificationResult] = field(default_factory=list)
    verification_timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "original_event": self.original_event.to_dict(),
            "reliability_score": self.reliability_score,
            "verified_claims": [vc.to_dict() for vc in self.verified_claims],
            "verification_timestamp": self.verification_timestamp.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "VerifiedEvent":
        """Deserialize from dictionary."""
        return cls(
            event_id=data["event_id"],
            original_event=NormalizedEvent.from_dict(data["original_event"]),
            reliability_score=data["reliability_score"],
            verified_claims=[
                VerificationResult.from_dict(vc) for vc in data.get("verified_claims", [])
            ],
            verification_timestamp=datetime.fromisoformat(data["verification_timestamp"])
        )


@dataclass
class IncidentBrief:
    """
    Concise incident summary with key facts.
    
    Attributes:
        incident_id: Unique incident identifier
        summary: Brief summary (max 200 words)
        key_facts: List of key facts
        location: Incident location
        affected_entities: List of affected entities
        similar_incidents: List of similar historical incident IDs
        created_at: Creation timestamp
    """
    incident_id: str
    summary: str
    key_facts: List[str] = field(default_factory=list)
    location: str = ""
    affected_entities: List[str] = field(default_factory=list)
    similar_incidents: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "incident_id": self.incident_id,
            "summary": self.summary,
            "key_facts": self.key_facts,
            "location": self.location,
            "affected_entities": self.affected_entities,
            "similar_incidents": self.similar_incidents,
            "created_at": self.created_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentBrief":
        """Deserialize from dictionary."""
        return cls(
            incident_id=data["incident_id"],
            summary=data["summary"],
            key_facts=data.get("key_facts", []),
            location=data.get("location", ""),
            affected_entities=data.get("affected_entities", []),
            similar_incidents=data.get("similar_incidents", []),
            created_at=datetime.fromisoformat(data["created_at"])
        )


@dataclass
class TriagedIncident:
    """
    Incident with severity classification and priority assignment.
    
    Attributes:
        incident_id: Unique incident identifier
        brief: The incident brief
        severity: Severity level classification
        priority_score: Priority score (0.0 to 1.0)
        job_id: Associated job identifier
        reasoning: Explanation for severity assignment
        triaged_at: Triage completion timestamp
    """
    incident_id: str
    brief: IncidentBrief
    severity: SeverityLevel
    priority_score: float
    job_id: str
    reasoning: str = ""
    triaged_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "incident_id": self.incident_id,
            "brief": self.brief.to_dict(),
            "severity": self.severity.value,
            "priority_score": self.priority_score,
            "job_id": self.job_id,
            "reasoning": self.reasoning,
            "triaged_at": self.triaged_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TriagedIncident":
        """Deserialize from dictionary."""
        return cls(
            incident_id=data["incident_id"],
            brief=IncidentBrief.from_dict(data["brief"]),
            severity=SeverityLevel(data["severity"]),
            priority_score=data["priority_score"],
            job_id=data["job_id"],
            reasoning=data.get("reasoning", ""),
            triaged_at=datetime.fromisoformat(data["triaged_at"])
        )


@dataclass
class Action:
    """
    Recommended action for incident response.
    
    Attributes:
        action: Action description
        responsible: Responsible party
        timeline: Expected timeline
    """
    action: str
    responsible: str
    timeline: str
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "action": self.action,
            "responsible": self.responsible,
            "timeline": self.timeline
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Action":
        """Deserialize from dictionary."""
        return cls(
            action=data["action"],
            responsible=data["responsible"],
            timeline=data["timeline"]
        )


@dataclass
class DispatchedIncident:
    """
    Fully processed incident with recommended actions.
    
    Attributes:
        incident_id: Unique incident identifier
        triaged_incident: The triaged incident
        recommended_actions: List of recommended actions
        communication_template: Communication template for stakeholders
        status: Current incident status
        dispatched_at: Dispatch completion timestamp
    """
    incident_id: str
    triaged_incident: TriagedIncident
    recommended_actions: List[Action] = field(default_factory=list)
    communication_template: str = ""
    status: IncidentStatus = IncidentStatus.DISPATCHED
    dispatched_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "incident_id": self.incident_id,
            "triaged_incident": self.triaged_incident.to_dict(),
            "recommended_actions": [action.to_dict() for action in self.recommended_actions],
            "communication_template": self.communication_template,
            "status": self.status.value,
            "dispatched_at": self.dispatched_at.isoformat()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DispatchedIncident":
        """Deserialize from dictionary."""
        return cls(
            incident_id=data["incident_id"],
            triaged_incident=TriagedIncident.from_dict(data["triaged_incident"]),
            recommended_actions=[
                Action.from_dict(action) for action in data.get("recommended_actions", [])
            ],
            communication_template=data.get("communication_template", ""),
            status=IncidentStatus(data.get("status", "DISPATCHED")),
            dispatched_at=datetime.fromisoformat(data["dispatched_at"])
        )


@dataclass
class Job:
    """
    Job queue entry for long-running operations.
    
    Attributes:
        job_id: Unique job identifier
        incident_id: Associated incident identifier
        status: Current job status
        created_at: Job creation timestamp
        updated_at: Last update timestamp
        result: Job result data (optional)
    """
    job_id: str
    incident_id: str
    status: JobStatus
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    result: Optional[Dict[str, Any]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "job_id": self.job_id,
            "incident_id": self.incident_id,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "result": self.result
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Deserialize from dictionary."""
        return cls(
            job_id=data["job_id"],
            incident_id=data["incident_id"],
            status=JobStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
            result=data.get("result")
        )
