"""
Dispatcher Agent Server for AgentFleet.

This module exposes the Dispatcher Agent as an A2A-compatible HTTP service
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

from capstone.agents.dispatcher_agent import create_dispatcher_agent, get_incident_cache
from capstone.mcp_envelope import parse_envelope


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Create FastAPI app
app = FastAPI(
    title="Dispatcher Agent",
    description="AgentFleet Dispatcher Agent - Generates actions and finalizes incidents",
    version="1.0.0"
)


# Initialize agent
dispatcher_agent = None


def get_agent():
    """Get or create the Dispatcher Agent instance."""
    global dispatcher_agent
    if dispatcher_agent is None:
        db_path = os.getenv("DATABASE_PATH", "./capstone/data/agentfleet.db")
        dispatcher_agent = create_dispatcher_agent(
            model_name="gemini-2.0-flash-lite",
            db_path=db_path
        )
    return dispatcher_agent


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
        "name": "dispatcher_agent",
        "description": "Dispatcher Agent that generates actions and finalizes incidents",
        "version": "1.0.0",
        "capabilities": [
            "action_generation",
            "communication_templates",
            "incident_persistence",
            "dashboard_notification"
        ],
        "endpoints": {
            "tasks": "/tasks",
            "health": "/health",
            "incidents": "/incidents"
        },
        "input_schema": {
            "type": "object",
            "properties": {
                "schema": {"type": "string", "enum": ["triaged_incident_v1"]},
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
                "schema": {"type": "string", "enum": ["dispatch_v1"]},
                "session_id": {"type": "string"},
                "timestamp": {"type": "string"},
                "source_agent": {"type": "string", "const": "dispatcher_agent"},
                "payload": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "const": "dispatch"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "incident_id": {"type": "string"},
                                "recommended_actions": {"type": "array"},
                                "communication_template": {"type": "string"},
                                "status": {"type": "string", "enum": ["DISPATCHED", "ACKNOWLEDGED", "RESOLVED"]},
                                "dispatched_at": {"type": "string"}
                            }
                        }
                    }
                }
            }
        },
        "metadata": {
            "action_generation": True,
            "communication_templates": True,
            "severity_levels_supported": ["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            "timeout_ms": 30000
        }
    }
    
    return JSONResponse(content=card)


@app.post("/tasks")
async def process_task(request: Request):
    """
    Process an A2A task request.
    
    This endpoint receives MCP envelopes containing triaged incidents,
    processes them to generate actions and persist data,
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
        
        # Process the triage envelope
        result = agent.process_triage_envelope(envelope_data)
        
        if result.get("success"):
            logger.info(f"Successfully processed incident {result.get('incident_id')} for session {result.get('session_id')}")
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "result": result,
                    "session_id": result.get("session_id"),
                    "incident_id": result.get("incident_id"),
                    "agent": "dispatcher_agent"
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
        
        # Get incident cache stats
        cache = get_incident_cache()
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "agent": "dispatcher_agent",
                "model": agent.model_name,
                "db_path": agent.db_path,
                "cached_incidents": len(cache)
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


@app.get("/incidents")
async def get_incidents():
    """
    Get all incidents from cache.
    
    Returns:
        List of incidents in cache
    """
    try:
        cache = get_incident_cache()
        
        # Convert to list and sort by priority
        incidents = list(cache.values())
        incidents.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
        
        return JSONResponse(
            status_code=200,
            content={
                "incidents": incidents,
                "count": len(incidents)
            }
        )
    except Exception as e:
        logger.error(f"Error getting incidents: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/incidents/{incident_id}")
async def get_incident(incident_id: str):
    """
    Get a specific incident from cache.
    
    Args:
        incident_id: Incident identifier
        
    Returns:
        Incident data
    """
    try:
        cache = get_incident_cache()
        
        if incident_id not in cache:
            raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
        
        return JSONResponse(
            status_code=200,
            content=cache[incident_id]
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting incident: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
async def root():
    """Root endpoint with agent information."""
    return {
        "agent": "dispatcher_agent",
        "description": "AgentFleet Dispatcher Agent - Generates actions and finalizes incidents",
        "version": "1.0.0",
        "endpoints": {
            "agent_card": "/.well-known/agent-card.json",
            "tasks": "/tasks",
            "health": "/health",
            "incidents": "/incidents"
        }
    }


def start_server(host: str = "0.0.0.0", port: int = 8005):
    """
    Start the Dispatcher Agent server.
    
    Args:
        host: Host address to bind to
        port: Port number to listen on
    """
    logger.info(f"Starting Dispatcher Agent server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("DISPATCHER_HOST", "0.0.0.0")
    port = int(os.getenv("DISPATCHER_PORT", "8005"))
    
    start_server(host=host, port=port)
