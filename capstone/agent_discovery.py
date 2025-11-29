#!/usr/bin/env python3
"""
AgentFleet Agent Discovery and Registration System

This module provides agent discovery, registry management, and health monitoring
capabilities for the AgentFleet system. It maintains a registry of all agents
with their status, capabilities, and connection information.

Usage:
    # As a module
    from capstone.agent_discovery import AgentRegistry
    
    # As a standalone service
    python agent_discovery.py --serve
"""

import os
import json
import time
import logging
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from pathlib import Path
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class AgentInfo:
    """Information about a registered agent."""
    name: str
    url: str
    status: str = "unknown"  # unknown, healthy, unhealthy, offline
    last_check: Optional[datetime] = None
    capabilities: List[str] = field(default_factory=list)
    endpoints: Dict[str, str] = field(default_factory=dict)
    version: str = "1.0.0"
    error_count: int = 0
    consecutive_failures: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        if self.last_check:
            data['last_check'] = self.last_check.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentInfo':
        """Create from dictionary with JSON deserialization."""
        if 'last_check' in data and data['last_check']:
            data['last_check'] = datetime.fromisoformat(data['last_check'])
        return cls(**data)


class AgentRegistry:
    """
    Registry for managing AgentFleet agents.
    
    Features:
    - Agent registration and discovery
    - Health monitoring and status tracking
    - Automatic retry for failed connections
    - Capability-based agent lookup
    - Persistent storage of agent information
    """
    
    def __init__(self, registry_file: Optional[str] = None):
        """
        Initialize the agent registry.
        
        Args:
            registry_file: Path to persistent registry file
        """
        self.registry_file = registry_file or "agent_registry.json"
        self.agents: Dict[str, AgentInfo] = {}
        self.health_check_interval = 30  # seconds
        self.max_consecutive_failures = 3
        self.retry_delay = 5  # seconds
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread = None
        
        # Load existing registry
        self._load_registry()
        
        # Default agent configurations
        self._setup_default_agents()
    
    def _setup_default_agents(self):
        """Set up default agent configurations."""
        default_agents = {
            "ingest": AgentInfo(
                name="Ingest Agent",
                url="http://localhost:8001",
                capabilities=["event_ingestion", "event_normalization", "entity_extraction"],
                endpoints={
                    "tasks": "/tasks",
                    "health": "/health",
                    "agent_card": "/.well-known/agent-card.json"
                }
            ),
            "verifier": AgentInfo(
                name="Verifier Agent",
                url="http://localhost:8002",
                capabilities=["claim_extraction", "fact_checking", "reliability_scoring"],
                endpoints={
                    "tasks": "/tasks",
                    "health": "/health",
                    "agent_card": "/.well-known/agent-card.json"
                }
            ),
            "summarizer": AgentInfo(
                name="Summarizer Agent",
                url="http://localhost:8003",
                capabilities=["incident_summarization", "key_fact_extraction", "memory_bank_query"],
                endpoints={
                    "tasks": "/tasks",
                    "health": "/health",
                    "agent_card": "/.well-known/agent-card.json"
                }
            ),
            "triage": AgentInfo(
                name="Triage Agent",
                url="http://localhost:8004",
                capabilities=["severity_classification", "priority_scoring", "job_queue_management"],
                endpoints={
                    "tasks": "/tasks",
                    "health": "/health",
                    "agent_card": "/.well-known/agent-card.json"
                }
            ),
            "dispatcher": AgentInfo(
                name="Dispatcher Agent",
                url="http://localhost:8005",
                capabilities=["action_generation", "communication_templates", "incident_persistence"],
                endpoints={
                    "tasks": "/tasks",
                    "health": "/health",
                    "agent_card": "/.well-known/agent-card.json",
                    "incidents": "/incidents"
                }
            )
        }
        
        # Register default agents if they don't exist
        with self._lock:
            for agent_id, agent_info in default_agents.items():
                if agent_id not in self.agents:
                    self.agents[agent_id] = agent_info
                    logger.info(f"Registered default agent: {agent_id}")
    
    def register_agent(self, agent_id: str, agent_info: AgentInfo) -> bool:
        """
        Register a new agent or update existing agent information.
        
        Args:
            agent_id: Unique identifier for the agent
            agent_info: Agent information
            
        Returns:
            True if registration successful
        """
        with self._lock:
            self.agents[agent_id] = agent_info
            logger.info(f"Registered agent: {agent_id} at {agent_info.url}")
            self._save_registry()
            return True
    
    def unregister_agent(self, agent_id: str) -> bool:
        """
        Unregister an agent.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            True if unregistration successful
        """
        with self._lock:
            if agent_id in self.agents:
                del self.agents[agent_id]
                logger.info(f"Unregistered agent: {agent_id}")
                self._save_registry()
                return True
            return False
    
    def get_agent(self, agent_id: str) -> Optional[AgentInfo]:
        """
        Get information about a specific agent.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            Agent information or None if not found
        """
        with self._lock:
            return self.agents.get(agent_id)
    
    def get_agent_by_capability(self, capability: str) -> List[AgentInfo]:
        """
        Get all agents that support a specific capability.
        
        Args:
            capability: Capability to search for
            
        Returns:
            List of agents with the capability
        """
        with self._lock:
            return [
                agent for agent in self.agents.values()
                if capability in agent.capabilities
            ]
    
    def get_healthy_agents(self) -> Dict[str, AgentInfo]:
        """
        Get all agents that are currently healthy.
        
        Returns:
            Dictionary of healthy agents
        """
        with self._lock:
            return {
                agent_id: agent
                for agent_id, agent in self.agents.items()
                if agent.status == "healthy"
            }
    
    def get_all_agents(self) -> Dict[str, AgentInfo]:
        """
        Get information about all registered agents.
        
        Returns:
            Dictionary of all agents
        """
        with self._lock:
            return dict(self.agents)
    
    def check_agent_health(self, agent_id: str) -> bool:
        """
        Check the health of a specific agent.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            True if agent is healthy
        """
        agent_info = self.get_agent(agent_id)
        if not agent_info:
            logger.warning(f"Agent not found: {agent_id}")
            return False
        
        try:
            health_url = f"{agent_info.url}/health"
            start_time = time.time()
            
            response = requests.get(health_url, timeout=10)
            check_duration = time.time() - start_time
            
            with self._lock:
                agent_info.last_check = datetime.now()
                
                if response.status_code == 200:
                    # Agent is healthy
                    agent_info.status = "healthy"
                    agent_info.consecutive_failures = 0
                    agent_info.error_count = 0
                    logger.debug(f"{agent_id} health check passed ({check_duration:.2f}s)")
                    return True
                else:
                    # Agent returned error
                    agent_info.status = "unhealthy"
                    agent_info.consecutive_failures += 1
                    agent_info.error_count += 1
                    logger.warning(f"{agent_id} health check failed: HTTP {response.status_code}")
                    return False
                    
        except requests.RequestException as e:
            with self._lock:
                agent_info.status = "offline"
                agent_info.consecutive_failures += 1
                agent_info.error_count += 1
                logger.warning(f"{agent_id} health check failed: {e}")
                return False
    
    def check_all_health(self) -> Dict[str, bool]:
        """
        Check health of all registered agents.
        
        Returns:
            Dictionary mapping agent IDs to health status
        """
        results = {}
        
        for agent_id in self.agents:
            results[agent_id] = self.check_agent_health(agent_id)
        
        return results
    
    def start_health_monitoring(self):
        """Start background health monitoring."""
        if self._running:
            logger.warning("Health monitoring already running")
            return
        
        self._running = True
        self._monitor_thread = threading.Thread(target=self._health_monitor_loop, daemon=True)
        self._monitor_thread.start()
        logger.info("Health monitoring started")
    
    def stop_health_monitoring(self):
        """Stop background health monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Health monitoring stopped")
    
    def _health_monitor_loop(self):
        """Background health monitoring loop."""
        while self._running:
            try:
                self.check_all_health()
                
                # Check for agents with too many consecutive failures
                with self._lock:
                    for agent_id, agent_info in self.agents.items():
                        if agent_info.consecutive_failures >= self.max_consecutive_failures:
                            logger.error(f"Agent {agent_id} has {agent_info.consecutive_failures} consecutive failures")
                            # Could trigger alerts or auto-restart here
                
                time.sleep(self.health_check_interval)
                
            except Exception as e:
                logger.error(f"Error in health monitoring loop: {e}")
                time.sleep(self.health_check_interval)
    
    def get_a2a_endpoint(self, agent_id: str) -> Optional[str]:
        """
        Get the A2A endpoint URL for an agent.
        
        Args:
            agent_id: Unique identifier for the agent
            
        Returns:
            A2A endpoint URL or None if agent not found/not healthy
        """
        agent_info = self.get_agent(agent_id)
        if agent_info and agent_info.status == "healthy":
            return f"{agent_info.url}/tasks"
        return None
    
    def find_agents_for_capability(self, capability: str) -> List[str]:
        """
        Find healthy agents that support a specific capability.
        
        Args:
            capability: Capability to search for
            
        Returns:
            List of agent IDs that support the capability
        """
        healthy_agents = self.get_healthy_agents()
        return [
            agent_id for agent_id, agent_info in healthy_agents.items()
            if capability in agent_info.capabilities
        ]
    
    def _save_registry(self):
        """Save registry to persistent storage."""
        try:
            data = {
                "agents": {agent_id: agent_info.to_dict() 
                          for agent_id, agent_info in self.agents.items()},
                "last_updated": datetime.now().isoformat()
            }
            
            with open(self.registry_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")
    
    def _load_registry(self):
        """Load registry from persistent storage."""
        try:
            if not os.path.exists(self.registry_file):
                return
            
            with open(self.registry_file, 'r') as f:
                data = json.load(f)
            
            for agent_id, agent_data in data.get("agents", {}).items():
                self.agents[agent_id] = AgentInfo.from_dict(agent_data)
            
            logger.info(f"Loaded {len(self.agents)} agents from registry")
            
        except Exception as e:
            logger.error(f"Failed to load registry: {e}")
    
    def get_registry_status(self) -> Dict[str, Any]:
        """Get comprehensive registry status."""
        with self._lock:
            healthy_count = sum(1 for agent in self.agents.values() if agent.status == "healthy")
            
            return {
                "total_agents": len(self.agents),
                "healthy_agents": healthy_count,
                "unhealthy_agents": len(self.agents) - healthy_count,
                "health_monitoring": self._running,
                "agents": {
                    agent_id: {
                        "name": agent_info.name,
                        "status": agent_info.status,
                        "url": agent_info.url,
                        "capabilities": agent_info.capabilities,
                        "last_check": agent_info.last_check.isoformat() if agent_info.last_check else None,
                        "error_count": agent_info.error_count,
                        "consecutive_failures": agent_info.consecutive_failures
                    }
                    for agent_id, agent_info in self.agents.items()
                }
            }
    
    def cleanup(self):
        """Clean up resources."""
        self.stop_health_monitoring()
        self._save_registry()


def main():
    """Main entry point for standalone usage."""
    import argparse
    
    parser = argparse.ArgumentParser(description="AgentFleet Agent Discovery Service")
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run as a discovery service with health monitoring"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show registry status and exit"
    )
    parser.add_argument(
        "--registry-file",
        default="agent_registry.json",
        help="Path to registry file"
    )
    parser.add_argument(
        "--check-interval",
        type=int,
        default=30,
        help="Health check interval in seconds"
    )
    
    args = parser.parse_args()
    
    # Change to the capstone directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    registry = AgentRegistry(args.registry_file)
    registry.health_check_interval = args.check_interval
    
    if args.status:
        status = registry.get_registry_status()
        print("\nAgent Registry Status:")
        print("=" * 50)
        print(f"Total Agents: {status['total_agents']}")
        print(f"Healthy Agents: {status['healthy_agents']}")
        print(f"Unhealthy Agents: {status['unhealthy_agents']}")
        print(f"Health Monitoring: {'Running' if status['health_monitoring'] else 'Stopped'}")
        print("\nAgent Details:")
        
        for agent_id, agent_data in status['agents'].items():
            status_display = f"[{agent_data['status'].upper()}]"
            if agent_data['status'] == 'healthy':
                status_display = f"\033[92m{status_display}\033[0m"  # Green
            else:
                status_display = f"\033[91m{status_display}\033[0m"  # Red
            
            print(f"  {agent_id:12} {status_display:12} {agent_data['url']}")
            if agent_data['last_check']:
                print(f"{'':15} Last check: {agent_data['last_check']}")
        
        print("=" * 50)
        return
    
    if args.serve:
        print("Starting Agent Discovery Service...")
        
        try:
            # Start health monitoring
            registry.start_health_monitoring()
            
            print("Agent Discovery Service running. Press Ctrl+C to stop.")
            
            # Run indefinitely
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                print("\nShutting down Agent Discovery Service...")
                
        except Exception as e:
            logger.error(f"Service error: {e}")
        finally:
            registry.cleanup()
    else:
        # Just run a one-time health check
        print("Running one-time health check...")
        results = registry.check_all_health()
        
        for agent_id, healthy in results.items():
            status = "HEALTHY" if healthy else "UNHEALTHY"
            color = "\033[92m" if healthy else "\033[91m"
            print(f"{agent_id}: {color}{status}\033[0m")


if __name__ == "__main__":
    main()