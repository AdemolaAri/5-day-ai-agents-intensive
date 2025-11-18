"""
Ingest Agent A2A Server.

This module exposes the Ingest Agent as an A2A-compatible HTTP service
using FastAPI and uvicorn.
"""

import os
import logging
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

from capstone.agents.ingest_agent import create_ingest_agent
from capstone.mcp_envelope import MCPEnvelope, parse_envelope


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# FastAPI app
app = FastAPI(
    title="Ingest Agent",
    description="AgentFleet Ingest Agent - Event stream ingestion and normalization",
    version="1.0.0"
)


# Global agent instance
agent = None


class TaskRequest(BaseModel):
    """Request model for A2A task endpoint."""
    message: Optional[str] = None
    envelope: Optional[Dict[str, Any]] = None
    source_type: Optional[str] = "all"
    max_events: Optional[int] = 10


class TaskResponse(BaseModel):
    """Response model for A2A task endpoint."""
    success: bool
    response: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None


@app.on_event("startup")
async def startup_event():
    """Initialize the agent on startup."""
    global agent
    
    try:
        logger.info("Starting Ingest Agent server...")
        agent = create_ingest_agent()
        logger.info("Ingest Agent initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize agent: {e}")
        raise


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("Shutting down Ingest Agent server...")
    
    # Disconnect from all streams
    try:
        from capstone.tools.stream_connector import get_stream_connector
        connector = get_stream_connector()
        connector.disconnect_all()
        logger.info("Disconnected from all event streams")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "agent": "Ingest Agent",
        "status": "running",
        "version": "1.0.0",
        "description": "Event stream ingestion and normalization agent"
    }


@app.get("/.well-known/agent-card.json")
async def agent_card():
    """
    Agent card endpoint for A2A protocol.
    
    Returns agent capabilities and metadata.
    """
    return {
        "name": "Ingest Agent",
        "description": "Ingests events from multiple stream sources, normalizes data, and forwards to Verifier Agent",
        "version": "1.0.0",
        "capabilities": [
            "event_ingestion",
            "event_normalization",
            "entity_extraction",
            "stream_management"
        ],
        "endpoints": {
            "tasks": "/tasks",
            "health": "/health",
            "metrics": "/metrics"
        },
        "tools": [
            {
                "name": "stream_connector",
                "description": "Connect to and manage event stream sources"
            },
            {
                "name": "normalize_event",
                "description": "Normalize raw events with entity extraction"
            },
            {
                "name": "forward_to_verifier",
                "description": "Forward events to Verifier Agent via A2A"
            }
        ],
        "input_schema": {
            "type": "object",
            "properties": {
                "message": {"type": "string"},
                "envelope": {"type": "object"},
                "source_type": {"type": "string", "enum": ["twitter", "emergency", "sensor", "all"]},
                "max_events": {"type": "integer"}
            }
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "success": {"type": "boolean"},
                "response": {"type": "string"},
                "data": {"type": "object"},
                "error": {"type": "string"}
            }
        },
        "next_agents": [
            {
                "name": "Verifier Agent",
                "url": "http://localhost:8002",
                "description": "Fact-checking and source reliability scoring"
            }
        ]
    }


@app.post("/tasks")
async def process_task(request: TaskRequest) -> TaskResponse:
    """
    A2A task endpoint.
    
    Processes incoming tasks from other agents or external sources.
    """
    try:
        logger.info(f"Received task request: {request.dict()}")
        
        # If envelope is provided, parse it
        if request.envelope:
            envelope, error = parse_envelope(request.envelope)
            if error:
                logger.error(f"Invalid envelope: {error}")
                return TaskResponse(
                    success=False,
                    error=f"Invalid envelope: {error}"
                )
            
            # Process envelope
            message = f"Process the event from envelope with session_id {envelope.session_id}"
            response = agent.process_message(message)
            
            return TaskResponse(
                success=True,
                response=response,
                data={"session_id": envelope.session_id}
            )
        
        # If message is provided, process it
        elif request.message:
            response = agent.process_message(request.message)
            return TaskResponse(
                success=True,
                response=response
            )
        
        # Default: process event batch
        else:
            result = agent.process_event_batch(
                source_type=request.source_type,
                max_events=request.max_events
            )
            
            return TaskResponse(
                success=result["success"],
                response=result.get("response"),
                data=result
            )
    
    except Exception as e:
        logger.error(f"Error processing task: {e}", exc_info=True)
        return TaskResponse(
            success=False,
            error=str(e)
        )


@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns the health status of the agent and connected streams.
    """
    try:
        from capstone.tools.stream_connector import get_stream_connector
        
        connector = get_stream_connector()
        stream_health = connector.get_health_status()
        
        return {
            "status": "healthy",
            "agent": "ingest_agent",
            "timestamp": datetime.utcnow().isoformat(),
            "streams": stream_health,
            "agent_ready": agent is not None
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={
                "status": "unhealthy",
                "agent": "ingest_agent",
                "error": str(e)
            }
        )


@app.get("/metrics")
async def metrics():
    """
    Metrics endpoint for Prometheus-compatible scraping.
    
    Returns agent performance metrics.
    """
    try:
        from capstone.tools.stream_connector import get_stream_connector
        
        connector = get_stream_connector()
        stream_health = connector.get_health_status()
        
        # Calculate total events
        total_events = sum(
            health.get("events_received", 0)
            for health in stream_health.values()
        )
        
        # Calculate total errors
        total_errors = sum(
            health.get("errors", 0)
            for health in stream_health.values()
        )
        
        # Prometheus-style metrics
        metrics_text = f"""# HELP ingest_agent_events_total Total number of events ingested
# TYPE ingest_agent_events_total counter
ingest_agent_events_total {total_events}

# HELP ingest_agent_errors_total Total number of errors
# TYPE ingest_agent_errors_total counter
ingest_agent_errors_total {total_errors}

# HELP ingest_agent_streams_connected Number of connected streams
# TYPE ingest_agent_streams_connected gauge
ingest_agent_streams_connected {len([h for h in stream_health.values() if h.get("status") == "CONNECTED"])}

# HELP ingest_agent_up Agent is up and running
# TYPE ingest_agent_up gauge
ingest_agent_up 1
"""
        
        return JSONResponse(
            content={"metrics": metrics_text, "raw_data": stream_health},
            media_type="text/plain"
        )
    
    except Exception as e:
        logger.error(f"Metrics collection failed: {e}")
        return JSONResponse(
            status_code=500,
            content={"error": str(e)}
        )


def start_server(host: str = "0.0.0.0", port: int = 8001):
    """
    Start the Ingest Agent A2A server.
    
    Args:
        host: Host to bind to
        port: Port to bind to
    """
    logger.info(f"Starting Ingest Agent server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    # Load environment variables
    from dotenv import load_dotenv
    load_dotenv()
    
    # Start server
    start_server()
