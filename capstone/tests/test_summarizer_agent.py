"""
Tests for Summarizer Agent.

This module tests the core functionality of the Summarizer Agent including:
- Summary generation with word limit
- Key fact extraction
- Memory Bank integration
- Session management
- A2A forwarding
"""

import pytest
import json
from datetime import datetime
from capstone.agents.summarizer_agent import (
    SummarizerAgent,
    generate_summary_tool,
    extract_key_facts_tool
)
from capstone.mcp_envelope import create_envelope, EnvelopeSchema, PayloadType
from capstone.models import NormalizedEvent, VerifiedEvent, Claim, VerificationResult


def test_generate_summary_tool():
    """Test summary generation with word limit."""
    result = generate_summary_tool(
        event_content="Major flooding reported in downtown area. Multiple streets are underwater. Emergency services are responding.",
        event_location="Downtown District",
        event_type="flooding",
        reliability_score=0.85,
        max_words=200
    )
    
    assert result["success"] is True
    assert "summary" in result
    assert result["word_count"] <= 200
    assert result["within_limit"] is True
    assert "flooding" in result["summary"].lower()
    assert "downtown" in result["summary"].lower()


def test_generate_summary_tool_truncation():
    """Test that long content is truncated to word limit."""
    long_content = " ".join(["word"] * 300)  # 300 words
    
    result = generate_summary_tool(
        event_content=long_content,
        event_location="Test Location",
        event_type="test",
        reliability_score=0.5,
        max_words=50
    )
    
    assert result["success"] is True
    assert result["word_count"] <= 50
    assert result["within_limit"] is True


def test_extract_key_facts_tool():
    """Test key fact extraction from event data."""
    event_data = {
        "event_id": "evt_123",
        "location": "Downtown District",
        "event_type": "flooding",
        "reliability_score": 0.85,
        "entities": ["Main Street", "City Hall", "Central Park"],
        "verified_claims": [
            {"verified": True, "confidence": 0.9},
            {"verified": True, "confidence": 0.8},
            {"verified": False, "confidence": 0.3}
        ]
    }
    
    result = extract_key_facts_tool(
        event_content="Flooding reported with 50 people evacuated and 10 buildings damaged",
        event_data=json.dumps(event_data)
    )
    
    assert result["success"] is True
    assert "key_facts" in result
    assert len(result["key_facts"]) > 0
    
    # Check that key information is extracted
    facts_str = " ".join(result["key_facts"])
    assert "Downtown District" in facts_str or "Location" in facts_str


def test_summarizer_agent_initialization():
    """Test Summarizer Agent initialization."""
    agent = SummarizerAgent(
        model_name="gemini-2.0-flash-lite",
        triage_url="http://localhost:8004"
    )
    
    assert agent.agent_name == "summarizer_agent"
    assert agent.model_name == "gemini-2.0-flash-lite"
    assert agent.triage_url == "http://localhost:8004"
    assert len(agent.active_sessions) == 0


def test_session_management():
    """Test session creation and management."""
    agent = SummarizerAgent()
    
    # Create new session
    session_id = agent._get_or_create_session()
    assert session_id is not None
    assert session_id in agent.active_sessions
    
    # Get existing session
    same_session_id = agent._get_or_create_session(session_id)
    assert same_session_id == session_id
    
    # Update session context
    event_data = {"event_id": "evt_123", "content": "test"}
    agent._update_session_context(session_id, event_data)
    
    assert len(agent.active_sessions[session_id]["events"]) == 1
    assert agent.active_sessions[session_id]["events"][0] == event_data


def test_process_event_envelope():
    """Test processing of verified event envelope."""
    agent = SummarizerAgent()
    
    # Create a verified event envelope
    normalized_event = NormalizedEvent(
        event_id="evt_123",
        source="twitter",
        timestamp=datetime.utcnow(),
        content="Major flooding in downtown area",
        entities=["downtown"],
        location="Downtown District",
        event_type="flooding"
    )
    
    verified_event_data = {
        "event_id": "evt_123",
        "original_event": normalized_event.to_dict(),
        "reliability_score": 0.85,
        "verified_claims": [],
        "verification_timestamp": datetime.utcnow().isoformat()
    }
    
    envelope = create_envelope(
        schema=EnvelopeSchema.VERIFIED_EVENT_V1.value,
        source_agent="verifier_agent",
        payload={
            "type": PayloadType.EVENT.value,
            "data": verified_event_data
        }
    )
    
    # Process the envelope
    result = agent.process_event_envelope(envelope.to_dict())
    
    assert result["success"] is True
    assert "session_id" in result
    assert result["session_id"] in agent.active_sessions


def test_invalid_envelope_handling():
    """Test handling of invalid envelopes."""
    agent = SummarizerAgent()
    
    # Invalid envelope (missing required fields)
    invalid_envelope = {
        "schema": "invalid_schema",
        "payload": {}
    }
    
    result = agent.process_event_envelope(invalid_envelope)
    
    assert result["success"] is False
    assert "error" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
