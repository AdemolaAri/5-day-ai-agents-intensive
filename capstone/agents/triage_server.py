"""
Triage Agent Server for AgentFleet.

This module exposes the Triage Agent as an A2A-compatible HTTP service
using FastAPI and uvicorn. The agent is accessible via:
- Agent card: /.well-known/agent-card.json
- Task endpoint: /tasks
- Health endpoint: /health

Requirements Satisfied:
- 6.1: Expose agent via A2A protocol
- 6.2: Generate agent card at /.well-known/agent-card.json
- 6.3: Validate envelope schema before processing
- 6.4: Return A2A response envelope with status and result
"""

import os
import logging
import json
from typing import Dict, Any
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
import uvicorn

from capstone.agents.triage_agent import create_triage_agent
from capstone.mcp_envelope import parse_envelope


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Create FastAPI app
app = FastAPI(
    title="Triage Agent",
    description="AgentFleet Triage Agent - Classifies incident severity and manages job queue",
    version="1.0.0"
)


# Initialize agent
triage_agent = None


def get_agent():
    """Get or create the Triage Agent instance."""
    global triage_agent
    if triage_agent is None:
        dispatcher_url = os.getenv("DISPATCHER_AGENT_URL", "http://localhost:8005")
        db_path = os.getenv("DATABASE_PATH", "./capstone/data/agentfleet.db")
        triage_agent = create_triage_agent(
            model_name="gemini-2.0-flash-lite",
            dispatcher_url=dispatcher_url,
            db_path=db_path
        )
    return triage_agent


@app.get("/.well-known/agent-card.json")
async def agent_card():
    """
    Return the agent card describing this agent's capabilities.
    
    The agent card follows the A2A protocol specification and includes:
    - Agent name and description
    - Supported capabilities
    - API endpoints
    - Input/output schemas
    """
    card = {
        "name": "triage_agent",
        "description": "Triage Agent that classifies incident severity and manages job queue",
        "version": "1.0.0",
        "capabilities": [
            "severity_classification",
            "priority_scoring",
            "job_queue_management",
            "incident_triage"
        ],
        "endpoints": {
            "tasks": "/tasks",
            "health": "/health"
        },
        "input_schema": {
            "type": "object",
            "properties": {
                "schema": {"type": "string", "enum": ["incident_brief_v1"]},
                "session_id": {"type": "string"},
                "timestamp": {"type": "string"},
                "source_agent": {"type": "string"},
                "payload": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string"},
                        "data": {"type": "object"}
                    }
                }
            },
            "required": ["schema", "session_id", "payload"]
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "schema": {"type": "string", "enum": ["triaged_incident_v1"]},
                "session_id": {"type": "string"},
                "timestamp": {"type": "string"},
                "source_agent": {"type": "string", "const": "triage_agent"},
                "payload": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "const": "triage"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "incident_id": {"type": "string"},
                                "severity": {"type": "string", "enum": ["LOW", "MEDIUM", "HIGH", "CRITICAL"]},
                                "priority_score": {"type": "number"},
                                "job_id": {"type": "string"},
                                "reasoning": {"type": "string"},
                                "triaged_at": {"type": "string"}
                            }
                        }
                    }
                }
            }
        },
        "metadata": {
            "severity_levels": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            "priority_score_range": [0.0, 1.0],
            "job_queue_enabled": True,
            "timeout_ms": 30000
        }
    }
    
    return JSONResponse(content=card)


@app.post("/tasks")
async def process_task(request: Request):
    """
    Process an A2A task request.
    
    This endpoint receives MCP envelopes containing incident briefs,
    processes them to classify severity and create job entries,
    and returns the results.
    
    Args:
        request: FastAPI request containing MCP envelope
        
    Returns:
        A2A response envelope with processing results
    """
    try:
        # Parse request body
        envelope_data = await request.json()
        
        logger.info(f"Received task request from {envelope_data.get('source_agent', 'unknown')}")
        
        # Validate envelope
        envelope, error_msg = parse_envelope(envelope_data)
        if not envelope:
            logger.error(f"Invalid envelope: {error_msg}")
            raise HTTPException(status_code=400, detail=f"Invalid envelope: {error_msg}")
        
        # Get agent instance
        agent = get_agent()
        
        # Process the incident envelope
        result = agent.process_incident_envelope(envelope_data)
        
        if result.get("success"):
            logger.info(f"Successfully processed incident {result.get('incident_id')} for session {result.get('session_id')}")
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "result": result,
                    "session_id": result.get("session_id"),
                    "incident_id": result.get("incident_id"),
                    "agent": "triage_agent"
                }
            )
        else:
            logger.error(f"Processing failed: {result.get('error')}")
            raise HTTPException(
                status_code=500,
                detail=f"Processing failed: {result.get('error')}"
            )
    
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
    try:
        agent = get_agent()
        
        # Query job queue stats
        from capstone.agents.triage_agent import query_jobs_tool
        pending_jobs = query_jobs_tool(status="PENDING", db_path=agent.db_path)
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "agent": "triage_agent",
                "model": agent.model_name,
                "dispatcher_url": agent.dispatcher_url,
                "db_path": agent.db_path,
                "pending_jobs": pending_jobs.get("count", 0) if pending_jobs.get("success") else 0
            }
        )
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "error": str(e)
            }
        )


@app.get("/")
async def root():
    """Root endpoint with agent information."""
    return {
        "agent": "triage_agent",
        "description": "AgentFleet Triage Agent - Classifies incident severity and manages job queue",
        "version": "1.0.0",
        "endpoints": {
            "agent_card": "/.well-known/agent-card.json",
            "tasks": "/tasks",
            "health": "/health"
        }
    }


def start_server(host: str = "0.0.0.0", port: int = 8004):
    """
    Start the Triage Agent server.
    
    Args:
        host: Host address to bind to
        port: Port number to listen on
    """
    logger.info(f"Starting Triage Agent server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("TRIAGE_HOST", "0.0.0.0")
    port = int(os.getenv("TRIAGE_PORT", "8004"))
    
    start_server(host=host, port=port)
