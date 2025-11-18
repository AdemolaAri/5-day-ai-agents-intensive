"""
Verifier Agent Server - A2A Protocol Endpoint

This module exposes the Verifier Agent as an HTTP service using the
Agent-to-Agent (A2A) protocol. The server:
- Listens on port 8002
- Exposes agent card at /.well-known/agent-card.json
- Accepts A2A requests at /tasks endpoint
- Validates MCP envelopes before processing
- Returns A2A response envelopes

Requirements Satisfied:
- 6.1: Expose agent via A2A protocol on HTTP endpoint
- 6.2: Generate agent card at /.well-known/agent-card.json
- 6.3: Validate envelope schema before processing
- 6.4: Return A2A response envelope with status and result
"""

import os
import sys
import logging
import json
from datetime import datetime
from typing import Dict, Any
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from capstone.agents.verifier_agent import create_verifier_agent
from capstone.mcp_envelope import parse_envelope, create_envelope, EnvelopeSchema


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Create FastAPI app
app = FastAPI(
    title="Verifier Agent",
    description="AgentFleet Verifier Agent - Claim verification and source reliability scoring",
    version="1.0.0"
)


# Initialize agent
verifier_agent = None
SUMMARIZER_URL = os.getenv("SUMMARIZER_URL", "http://localhost:8003")


@app.on_event("startup")
async def startup_event():
    """Initialize the Verifier Agent on startup."""
    global verifier_agent
    try:
        logger.info("Initializing Verifier Agent...")
        verifier_agent = create_verifier_agent(
            model_name="gemini-2.0-flash-lite",
            summarizer_url=SUMMARIZER_URL
        )
        logger.info("Verifier Agent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize Verifier Agent: {e}")
        raise


@app.get("/.well-known/agent-card.json")
async def get_agent_card():
    """
    Return the agent card describing this agent's capabilities.
    
    The agent card follows the A2A protocol specification and includes:
    - Agent name and description
    - Supported capabilities
    - Input/output schemas
    - Endpoint information
    
    Returns:
        Agent card JSON
    """
    agent_card = {
        "name": "verifier_agent",
        "description": "Verifier Agent for claim verification and source reliability scoring",
        "version": "1.0.0",
        "capabilities": [
            "claim_extraction",
            "fact_checking",
            "reliability_scoring",
            "event_verification"
        ],
        "input_schema": {
            "type": "mcp_envelope",
            "schema": "event_v1",
            "required_fields": ["session_id", "source_agent", "payload"]
        },
        "output_schema": {
            "type": "mcp_envelope",
            "schema": "verified_event_v1",
            "fields": ["event_id", "reliability_score", "verified_claims"]
        },
        "endpoints": {
            "tasks": "/tasks",
            "health": "/health",
            "metrics": "/metrics"
        },
        "tools": [
            {
                "name": "extract_claims",
                "description": "Extract verifiable claims from event content"
            },
            {
                "name": "verify_claim",
                "description": "Verify a claim using search results"
            },
            {
                "name": "score_reliability",
                "description": "Calculate overall reliability score"
            },
            {
                "name": "forward_to_summarizer",
                "description": "Forward verified event to Summarizer Agent"
            }
        ],
        "metadata": {
            "agent_type": "specialist",
            "pipeline_position": 2,
            "upstream_agents": ["ingest_agent"],
            "downstream_agents": ["summarizer_agent"]
        }
    }
    
    return JSONResponse(content=agent_card)


@app.post("/tasks")
async def process_task(request: Request):
    """
    Process an A2A task request.
    
    This endpoint:
    1. Receives MCP envelope from upstream agent (Ingest Agent)
    2. Validates envelope schema
    3. Processes event through Verifier Agent
    4. Returns A2A response envelope
    
    Args:
        request: FastAPI request containing MCP envelope
        
    Returns:
        A2A response envelope with verification results
    """
    try:
        # Parse request body
        envelope_data = await request.json()
        
        logger.info(f"Received A2A request from {envelope_data.get('source_agent', 'unknown')}")
        
        # Validate envelope
        envelope, error_msg = parse_envelope(envelope_data)
        if not envelope:
            logger.error(f"Invalid envelope: {error_msg}")
            raise HTTPException(status_code=400, detail=f"Invalid envelope: {error_msg}")
        
        # Validate schema
        if not envelope.validate_schema():
            logger.error(f"Invalid schema: {envelope.schema}")
            raise HTTPException(status_code=400, detail=f"Invalid schema: {envelope.schema}")
        
        # Process event
        result = verifier_agent.process_event_envelope(envelope_data)
        
        # Create response envelope
        response_envelope = create_envelope(
            schema=EnvelopeSchema.MCP_ENVELOPE_V1.value,
            source_agent="verifier_agent",
            payload={
                "type": "response",
                "data": result,
                "metadata": {
                    "processing_timestamp": datetime.utcnow().isoformat(),
                    "original_session_id": envelope.session_id
                }
            },
            session_id=envelope.session_id
        )
        
        logger.info(f"Successfully processed event {envelope.payload.get('data', {}).get('event_id', 'unknown')}")
        
        return JSONResponse(content=response_envelope.to_dict())
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing task: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        Health status of the agent
    """
    return {
        "status": "healthy",
        "agent": "verifier_agent",
        "timestamp": datetime.utcnow().isoformat(),
        "ready": verifier_agent is not None
    }


@app.get("/metrics")
async def get_metrics():
    """
    Metrics endpoint for monitoring.
    
    Returns:
        Agent metrics in Prometheus-compatible format
    """
    # In production, this would return actual metrics
    # For now, return placeholder metrics
    return {
        "agent_requests_total": 0,
        "agent_request_duration_seconds": 0.0,
        "agent_errors_total": 0,
        "tool_invocations_total": 0,
        "timestamp": datetime.utcnow().isoformat()
    }


def main():
    """Run the Verifier Agent server."""
    port = int(os.getenv("VERIFIER_PORT", "8002"))
    host = os.getenv("VERIFIER_HOST", "0.0.0.0")
    
    logger.info(f"Starting Verifier Agent server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
