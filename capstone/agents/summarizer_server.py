"""
Summarizer Agent Server for AgentFleet.

This module exposes the Summarizer Agent as an A2A-compatible HTTP service
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

from capstone.agents.summarizer_agent import create_summarizer_agent
from capstone.mcp_envelope import parse_envelope


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Create FastAPI app
app = FastAPI(
    title="Summarizer Agent",
    description="AgentFleet Summarizer Agent - Generates concise incident briefs with memory integration",
    version="1.0.0"
)


# Initialize agent
summarizer_agent = None


def get_agent():
    """Get or create the Summarizer Agent instance."""
    global summarizer_agent
    if summarizer_agent is None:
        triage_url = os.getenv("TRIAGE_AGENT_URL", "http://localhost:8004")
        summarizer_agent = create_summarizer_agent(
            model_name="gemini-2.0-flash-lite",
            triage_url=triage_url
        )
    return summarizer_agent


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
        "name": "summarizer_agent",
        "description": "Summarizer Agent that generates concise incident briefs with memory integration",
        "version": "1.0.0",
        "capabilities": [
            "incident_summarization",
            "key_fact_extraction",
            "memory_bank_query",
            "pattern_recognition",
            "session_management"
        ],
        "endpoints": {
            "tasks": "/tasks",
            "health": "/health"
        },
        "input_schema": {
            "type": "object",
            "properties": {
                "schema": {"type": "string", "enum": ["verified_event_v1"]},
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
                "schema": {"type": "string", "enum": ["incident_brief_v1"]},
                "session_id": {"type": "string"},
                "timestamp": {"type": "string"},
                "source_agent": {"type": "string", "const": "summarizer_agent"},
                "payload": {
                    "type": "object",
                    "properties": {
                        "type": {"type": "string", "const": "incident"},
                        "data": {
                            "type": "object",
                            "properties": {
                                "incident_id": {"type": "string"},
                                "summary": {"type": "string"},
                                "key_facts": {"type": "array"},
                                "location": {"type": "string"},
                                "affected_entities": {"type": "array"},
                                "similar_incidents": {"type": "array"}
                            }
                        }
                    }
                }
            }
        },
        "metadata": {
            "max_summary_words": 200,
            "memory_bank_enabled": True,
            "session_management": True,
            "timeout_ms": 30000
        }
    }
    
    return JSONResponse(content=card)


@app.post("/tasks")
async def process_task(request: Request):
    """
    Process an A2A task request.
    
    This endpoint receives MCP envelopes containing verified events,
    processes them to generate incident briefs, and returns the results.
    
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
        
        # Process the event envelope
        result = agent.process_event_envelope(envelope_data)
        
        if result.get("success"):
            logger.info(f"Successfully processed event for session {result.get('session_id')}")
            
            return JSONResponse(
                status_code=200,
                content={
                    "status": "success",
                    "result": result,
                    "session_id": result.get("session_id"),
                    "agent": "summarizer_agent"
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
        
        return JSONResponse(
            status_code=200,
            content={
                "status": "healthy",
                "agent": "summarizer_agent",
                "model": agent.model_name,
                "active_sessions": len(agent.active_sessions),
                "triage_url": agent.triage_url
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
        "agent": "summarizer_agent",
        "description": "AgentFleet Summarizer Agent - Generates concise incident briefs",
        "version": "1.0.0",
        "endpoints": {
            "agent_card": "/.well-known/agent-card.json",
            "tasks": "/tasks",
            "health": "/health"
        }
    }


def start_server(host: str = "0.0.0.0", port: int = 8003):
    """
    Start the Summarizer Agent server.
    
    Args:
        host: Host address to bind to
        port: Port number to listen on
    """
    logger.info(f"Starting Summarizer Agent server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    # Get configuration from environment
    host = os.getenv("SUMMARIZER_HOST", "0.0.0.0")
    port = int(os.getenv("SUMMARIZER_PORT", "8003"))
    
    start_server(host=host, port=port)
