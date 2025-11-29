#!/usr/bin/env python3
"""
AgentFleet Agent Management Utilities

This module provides utility functions for agent management tasks including
health checks, status monitoring, and A2A communication helpers.
"""

import os
import time
import logging
import requests
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class A2ARequest:
    """A2A request configuration."""
    agent_url: str
    envelope: Dict[str, Any]
    timeout: int = 30
    max_retries: int = 3
    retry_delay: float = 1.0


@dataclass
class A2AResponse:
    """A2A response result."""
    success: bool
    status_code: int
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    response_time: float = 0.0


class A2ACommunicator:
    """
    Handles A2A (Agent-to-Agent) communication with retry logic and error handling.
    
    Features:
    - Automatic retry with exponential backoff
    - Timeout handling
    - Error logging and recovery
    - Health check integration
    """
    
    def __init__(self, registry=None):
        """
        Initialize A2A communicator.
        
        Args:
            registry: Optional agent registry for health checking
        """
        self.registry = registry
        self.default_timeout = 30
        self.max_retries = 3
        self.retry_delay = 1.0
        self.session = requests.Session()
        
        # Configure session
        self.session.headers.update({
            'Content-Type': 'application/json',
            'User-Agent': 'AgentFleet-A2A-Client/1.0'
        })
    
    def send_a2a_request(self, request: A2ARequest) -> A2AResponse:
        """
        Send an A2A request with retry logic.
        
        Args:
            request: A2A request configuration
            
        Returns:
            A2A response result
        """
        start_time = time.time()
        
        for attempt in range(request.max_retries + 1):
            try:
                # Check if agent is healthy (if registry is available)
                if self.registry:
                    agent_id = self._extract_agent_id_from_url(request.agent_url)
                    if agent_id:
                        agent_info = self.registry.get_agent(agent_id)
                        if agent_info and agent_info.status != "healthy":
                            logger.warning(f"Agent {agent_id} is not healthy: {agent_info.status}")
                
                # Send the request
                response = self.session.post(
                    f"{request.agent_url}/tasks",
                    json=request.envelope,
                    timeout=request.timeout
                )
                
                response_time = time.time() - start_time
                
                if response.status_code == 200:
                    logger.debug(f"A2A request successful ({response_time:.2f}s)")
                    return A2AResponse(
                        success=True,
                        status_code=response.status_code,
                        data=response.json(),
                        response_time=response_time
                    )
                else:
                    error_msg = f"HTTP {response.status_code}: {response.text}"
                    logger.warning(f"A2A request failed: {error_msg}")
                    
                    if attempt < request.max_retries:
                        delay = request.retry_delay * (2 ** attempt)
                        logger.info(f"Retrying in {delay:.1f} seconds...")
                        time.sleep(delay)
                        continue
                    else:
                        return A2AResponse(
                            success=False,
                            status_code=response.status_code,
                            error=error_msg,
                            response_time=response_time
                        )
            
            except requests.exceptions.Timeout:
                error_msg = f"Request timed out after {request.timeout}s"
                logger.warning(f"A2A request timeout: {error_msg}")
                
                if attempt < request.max_retries:
                    delay = request.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    return A2AResponse(
                        success=False,
                        status_code=0,
                        error=error_msg,
                        response_time=time.time() - start_time
                    )
            
            except requests.exceptions.ConnectionError as e:
                error_msg = f"Connection error: {e}"
                logger.error(f"A2A connection error: {error_msg}")
                
                if attempt < request.max_retries:
                    delay = request.retry_delay * (2 ** attempt)
                    logger.info(f"Retrying in {delay:.1f} seconds...")
                    time.sleep(delay)
                    continue
                else:
                    return A2AResponse(
                        success=False,
                        status_code=0,
                        error=error_msg,
                        response_time=time.time() - start_time
                    )
            
            except Exception as e:
                error_msg = f"Unexpected error: {e}"
                logger.error(f"A2A unexpected error: {error_msg}")
                return A2AResponse(
                    success=False,
                    status_code=0,
                    error=error_msg,
                    response_time=time.time() - start_time
                )
    
    def _extract_agent_id_from_url(self, url: str) -> Optional[str]:
        """
        Extract agent ID from URL.
        
        Args:
            url: Agent URL (e.g., "http://localhost:8001")
            
        Returns:
            Agent ID or None if not recognized
        """
        port_mapping = {
            "8001": "ingest",
            "8002": "verifier", 
            "8003": "summarizer",
            "8004": "triage",
            "8005": "dispatcher"
        }
        
        for port, agent_id in port_mapping.items():
            if f":{port}" in url:
                return agent_id
        
        return None
    
    def health_check_agent(self, agent_url: str, timeout: int = 5) -> Tuple[bool, str]:
        """
        Perform health check on an agent.
        
        Args:
            agent_url: URL of the agent
            timeout: Timeout for health check
            
        Returns:
            Tuple of (is_healthy, status_message)
        """
        try:
            response = self.session.get(f"{agent_url}/health", timeout=timeout)
            
            if response.status_code == 200:
                health_data = response.json()
                status = health_data.get("status", "unknown")
                
                if status == "healthy":
                    return True, f"Healthy ({response.elapsed.total_seconds():.2f}s)"
                else:
                    return False, f"Unhealthy status: {status}"
            else:
                return False, f"HTTP {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Connection failed: {e}"
    
    def discover_agent_capabilities(self, agent_url: str, timeout: int = 10) -> Dict[str, Any]:
        """
        Discover agent capabilities from agent card.
        
        Args:
            agent_url: URL of the agent
            timeout: Timeout for discovery
            
        Returns:
            Agent capabilities and metadata
        """
        try:
            response = self.session.get(
                f"{agent_url}/.well-known/agent-card.json",
                timeout=timeout
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.warning(f"Failed to get agent card: HTTP {response.status_code}")
                return {}
                
        except requests.exceptions.RequestException as e:
            logger.warning(f"Failed to discover agent capabilities: {e}")
            return {}


def check_all_agent_health(agent_urls: List[str]) -> Dict[str, Tuple[bool, str]]:
    """
    Check health of multiple agents.
    
    Args:
        agent_urls: List of agent URLs
        
    Returns:
        Dictionary mapping URLs to health status
    """
    communicator = A2ACommunicator()
    results = {}
    
    for url in agent_urls:
        healthy, message = communicator.health_check_agent(url)
        results[url] = (healthy, message)
    
    return results


def send_envelope_to_agent(
    agent_url: str,
    envelope: Dict[str, Any],
    timeout: int = 30,
    max_retries: int = 3
) -> A2AResponse:
    """
    Send MCP envelope to agent.
    
    Args:
        agent_url: Target agent URL
        envelope: MCP envelope to send
        timeout: Request timeout
        max_retries: Maximum retry attempts
        
    Returns:
        A2A response result
    """
    request = A2ARequest(
        agent_url=agent_url,
        envelope=envelope,
        timeout=timeout,
        max_retries=max_retries
    )
    
    communicator = A2ACommunicator()
    return communicator.send_a2a_request(request)


def format_agent_status_table(agent_status: Dict[str, Tuple[bool, str]]) -> str:
    """
    Format agent status as a table for display.
    
    Args:
        agent_status: Dictionary of agent URL to status
    
    Returns:
        Formatted table string
    """
    table_lines = ["Agent Health Status", "=" * 50]
    
    for url, (healthy, message) in agent_status.items():
        status_symbol = "✓" if healthy else "✗"
        status_color = "\033[92m" if healthy else "\033[91m"
        
        # Extract agent name from URL
        agent_name = url.replace("http://localhost:", "").replace("0.0.0.0:", "")
        if ":" in agent_name:
            port = agent_name.split(":")[-1]
            agent_name = {
                "8001": "Ingest Agent",
                "8002": "Verifier Agent", 
                "8003": "Summarizer Agent",
                "8004": "Triage Agent",
                "8005": "Dispatcher Agent"
            }.get(port, f"Agent on port {port}")
        
        table_lines.append(f"{status_color}{status_symbol} {agent_name:20}\033[0m {message}")
    
    table_lines.append("=" * 50)
    return "\n".join(table_lines)


# Utility functions for common agent management tasks
def wait_for_agent_health(agent_url: str, timeout: int = 60, check_interval: int = 5) -> bool:
    """
    Wait for an agent to become healthy.
    
    Args:
        agent_url: Agent URL to monitor
        timeout: Maximum time to wait
        check_interval: Interval between health checks
        
    Returns:
        True if agent becomes healthy, False if timeout
    """
    communicator = A2ACommunicator()
    start_time = time.time()
    
    while time.time() - start_time < timeout:
        healthy, message = communicator.health_check_agent(agent_url)
        
        if healthy:
            logger.info(f"Agent {agent_url} is healthy: {message}")
            return True
        
        logger.info(f"Agent {agent_url} not ready: {message}")
        time.sleep(check_interval)
    
    logger.error(f"Timeout waiting for agent {agent_url} to become healthy")
    return False


def wait_for_all_agents_health(agent_urls: List[str], timeout: int = 120) -> bool:
    """
    Wait for all agents to become healthy.
    
    Args:
        agent_urls: List of agent URLs
        timeout: Maximum time to wait
        
    Returns:
        True if all agents become healthy, False if timeout
    """
    logger.info(f"Waiting for {len(agent_urls)} agents to become healthy...")
    
    for url in agent_urls:
        if not wait_for_agent_health(url, timeout):
            return False
    
    logger.info("All agents are healthy")
    return True


def create_mcp_envelope(
    schema: str,
    source_agent: str,
    payload: Dict[str, Any],
    session_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a properly formatted MCP envelope.
    
    Args:
        schema: Envelope schema type
        source_agent: Source agent name
        payload: Payload data
        session_id: Optional session ID
        
    Returns:
        MCP envelope dictionary
    """
    import uuid
    
    return {
        "schema": schema,
        "session_id": session_id or str(uuid.uuid4()),
        "timestamp": datetime.utcnow().isoformat(),
        "source_agent": source_agent,
        "payload": payload
    }