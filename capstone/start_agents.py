#!/usr/bin/env python3
"""
AgentFleet Master Startup Script

This script orchestrates the startup of all AgentFleet agents, manages their lifecycle,
and provides health monitoring and discovery capabilities.

Requirements Satisfied:
- 12.2: Create master startup script with health check polling and graceful shutdown
- 12.3: Implement agent discovery and registration with health check endpoints

Usage:
    python start_agents.py [--mode=dev|prod] [--config=config.json]
"""

import os
import sys
import json
import time
import signal
import logging
import argparse
import subprocess
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from pathlib import Path
import requests
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class AgentConfig:
    """Configuration for an individual agent."""
    name: str
    module: str
    server_file: str
    port: int
    host: str = "0.0.0.0"
    env_vars: Dict[str, str] = None
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.env_vars is None:
            self.env_vars = {}
        if self.dependencies is None:
            self.dependencies = []


@dataclass
class AgentStatus:
    """Status information for an agent."""
    name: str
    status: str  # "stopped", "starting", "running", "healthy", "unhealthy", "error"
    pid: Optional[int] = None
    port: Optional[int] = None
    url: Optional[str] = None
    last_check: Optional[datetime] = None
    error_message: Optional[str] = None
    startup_time: Optional[datetime] = None


class AgentOrchestrator:
    """Orchestrates the startup, monitoring, and shutdown of all agents."""
    
    def __init__(self, config_file: Optional[str] = None):
        """
        Initialize the orchestrator.
        
        Args:
            config_file: Path to configuration file (optional)
        """
        self.agents = self._load_agent_configs()
        self.processes: Dict[str, subprocess.Popen] = {}
        self.statuses: Dict[str, AgentStatus] = {}
        self.health_check_interval = 5  # seconds
        self.health_check_timeout = 30  # seconds
        self.max_startup_time = 60  # seconds
        self.shutdown_event = threading.Event()
        
        # Set up signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        # Initialize status for all agents
        for agent_name in self.agents:
            self.statuses[agent_name] = AgentStatus(
                name=agent_name,
                status="stopped"
            )
    
    def _load_agent_configs(self) -> Dict[str, AgentConfig]:
        """Load agent configurations."""
        base_url = "http://localhost"
        
        configs = {
            "ingest": AgentConfig(
                name="Ingest Agent",
                module="capstone.agents.ingest_agent",
                server_file="capstone/agents/ingest_server.py",
                port=8001,
                env_vars={
                    "INGEST_PORT": "8001",
                    "VERIFIER_URL": f"{base_url}:8002"
                }
            ),
            "verifier": AgentConfig(
                name="Verifier Agent",
                module="capstone.agents.verifier_agent",
                server_file="capstone/agents/verifier_server.py",
                port=8002,
                env_vars={
                    "VERIFIER_PORT": "8002",
                    "VERIFIER_HOST": "0.0.0.0",
                    "SUMMARIZER_URL": f"{base_url}:8003"
                }
            ),
            "summarizer": AgentConfig(
                name="Summarizer Agent",
                module="capstone.agents.summarizer_agent",
                server_file="capstone/agents/summarizer_server.py",
                port=8003,
                env_vars={
                    "SUMMARIZER_PORT": "8003",
                    "SUMMARIZER_HOST": "0.0.0.0",
                    "TRIAGE_AGENT_URL": f"{base_url}:8004"
                }
            ),
            "triage": AgentConfig(
                name="Triage Agent",
                module="capstone.agents.triage_agent",
                server_file="capstone/agents/triage_server.py",
                port=8004,
                env_vars={
                    "TRIAGE_PORT": "8004",
                    "TRIAGE_HOST": "0.0.0.0",
                    "DISPATCHER_AGENT_URL": f"{base_url}:8005",
                    "DATABASE_PATH": "./capstone/data/agentfleet.db"
                }
            ),
            "dispatcher": AgentConfig(
                name="Dispatcher Agent",
                module="capstone.agents.dispatcher_agent",
                server_file="capstone/agents/dispatcher_server.py",
                port=8005,
                env_vars={
                    "DISPATCHER_PORT": "8005",
                    "DISPATCHER_HOST": "0.0.0.0",
                    "DATABASE_PATH": "./capstone/data/agentfleet.db"
                }
            )
        }
        
        return configs
    
    def start_all_agents(self) -> bool:
        """
        Start all agents in dependency order.
        
        Returns:
            True if all agents started successfully, False otherwise
        """
        logger.info("Starting AgentFleet orchestrator...")
        
        # Start agents in dependency order
        start_order = ["ingest", "verifier", "summarizer", "triage", "dispatcher"]
        
        success = True
        for agent_name in start_order:
            if not self.start_agent(agent_name):
                logger.error(f"Failed to start {agent_name}, stopping orchestration")
                success = False
                break
        
        if success:
            logger.info("All agents started successfully")
            # Start health monitoring in background
            self._start_health_monitoring()
        else:
            logger.error("Some agents failed to start, shutting down")
            self.stop_all_agents()
        
        return success
    
    def start_agent(self, agent_name: str) -> bool:
        """
        Start a single agent.
        
        Args:
            agent_name: Name of the agent to start
            
        Returns:
            True if agent started successfully, False otherwise
        """
        if agent_name not in self.agents:
            logger.error(f"Unknown agent: {agent_name}")
            return False
        
        config = self.agents[agent_name]
        status = self.statuses[agent_name]
        
        logger.info(f"Starting {agent_name} agent...")
        status.status = "starting"
        status.startup_time = datetime.now()
        
        try:
            # Prepare environment variables
            env = os.environ.copy()
            env.update(config.env_vars)
            
            # Start the agent process
            script_path = Path(__file__).parent / config.server_file
            process = subprocess.Popen(
                [sys.executable, str(script_path)],
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            self.processes[agent_name] = process
            status.pid = process.pid
            status.port = config.port
            status.url = f"http://localhost:{config.port}"
            
            logger.info(f"{agent_name} started with PID {process.pid}")
            
            # Wait a moment for the agent to start
            time.sleep(2)
            
            # Check if process is still running
            if process.poll() is not None:
                stdout, stderr = process.communicate()
                logger.error(f"{agent_name} process terminated unexpectedly")
                logger.error(f"STDOUT: {stdout}")
                logger.error(f"STDERR: {stderr}")
                status.status = "error"
                status.error_message = f"Process terminated: {stderr}"
                return False
            
            # Wait for health check
            if self._wait_for_health(agent_name):
                status.status = "healthy"
                logger.info(f"{agent_name} is healthy and ready")
                return True
            else:
                status.status = "unhealthy"
                status.error_message = "Health check failed"
                logger.error(f"{agent_name} failed health check")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start {agent_name}: {e}")
            status.status = "error"
            status.error_message = str(e)
            return False
    
    def _wait_for_health(self, agent_name: str) -> bool:
        """
        Wait for an agent to become healthy.
        
        Args:
            agent_name: Name of the agent to check
            
        Returns:
            True if agent becomes healthy, False if timeout
        """
        config = self.agents[agent_name]
        url = f"http://localhost:{config.port}/health"
        
        start_time = time.time()
        while time.time() - start_time < self.health_check_timeout:
            try:
                response = requests.get(url, timeout=5)
                if response.status_code == 200:
                    logger.info(f"{agent_name} health check passed")
                    return True
            except requests.RequestException:
                pass
            
            time.sleep(2)
        
        logger.error(f"{agent_name} health check timeout")
        return False
    
    def _start_health_monitoring(self):
        """Start background health monitoring."""
        def health_monitor():
            while not self.shutdown_event.is_set():
                self._check_all_health()
                self.shutdown_event.wait(self.health_check_interval)
        
        monitor_thread = threading.Thread(target=health_monitor, daemon=True)
        monitor_thread.start()
        logger.info("Health monitoring started")
    
    def _check_all_health(self):
        """Check health of all running agents."""
        for agent_name, process in self.processes.items():
            if process.poll() is None:  # Process is still running
                self._check_agent_health(agent_name)
    
    def _check_agent_health(self, agent_name: str):
        """Check health of a specific agent."""
        status = self.statuses[agent_name]
        config = self.agents[agent_name]
        
        try:
            url = f"http://localhost:{config.port}/health"
            response = requests.get(url, timeout=5)
            
            if response.status_code == 200:
                status.status = "healthy"
                status.last_check = datetime.now()
                status.error_message = None
            else:
                status.status = "unhealthy"
                status.last_check = datetime.now()
                status.error_message = f"HTTP {response.status_code}"
                
        except requests.RequestException as e:
            status.status = "unhealthy"
            status.last_check = datetime.now()
            status.error_message = str(e)
    
    def stop_all_agents(self):
        """Stop all running agents gracefully."""
        logger.info("Stopping all agents...")
        self.shutdown_event.set()
        
        for agent_name, process in self.processes.items():
            if process.poll() is None:  # Process is still running
                logger.info(f"Stopping {agent_name} (PID {process.pid})...")
                try:
                    process.terminate()
                    process.wait(timeout=10)
                    logger.info(f"{agent_name} stopped")
                except subprocess.TimeoutExpired:
                    logger.warning(f"Force killing {agent_name}")
                    process.kill()
                except Exception as e:
                    logger.error(f"Error stopping {agent_name}: {e}")
        
        self.processes.clear()
        logger.info("All agents stopped")
    
    def get_agent_status(self) -> Dict[str, Any]:
        """Get status of all agents."""
        status_summary = {}
        for name, status in self.statuses.items():
            status_summary[name] = {
                "name": self.agents[name].name,
                "status": status.status,
                "pid": status.pid,
                "port": status.port,
                "url": status.url,
                "last_check": status.last_check.isoformat() if status.last_check else None,
                "error_message": status.error_message,
                "startup_time": status.startup_time.isoformat() if status.startup_time else None
            }
        return status_summary
    
    def print_status(self):
        """Print current status of all agents."""
        print("\nAgentFleet Agent Status:")
        print("=" * 50)
        
        for name, status in self.statuses.items():
            agent_info = self.agents[name]
            status_info = f"[{status.status.upper()}]"
            
            if status.status == "healthy":
                status_info = f"\033[92m{status_info}\033[0m"  # Green
            elif status.status in ["unhealthy", "error"]:
                status_info = f"\033[91m{status_info}\033[0m"  # Red
            elif status.status == "starting":
                status_info = f"\033[93m{status_info}\033[0m"  # Yellow
            
            print(f"{agent_info.name:20} {status_info:12} PID: {status.pid or 'N/A':>6} Port: {status.port or 'N/A':>5}")
            
            if status.error_message:
                print(f"{'':22} Error: {status.error_message}")
        
        print("=" * 50)
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.shutdown_event.set()
        self.stop_all_agents()
        sys.exit(0)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AgentFleet Agent Orchestrator")
    parser.add_argument(
        "--mode",
        choices=["dev", "prod"],
        default="dev",
        help="Operation mode (default: dev)"
    )
    parser.add_argument(
        "--config",
        help="Configuration file path"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show agent status and exit"
    )
    parser.add_argument(
        "--stop",
        action="store_true",
        help="Stop all running agents"
    )
    
    args = parser.parse_args()
    
    # Change to the capstone directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    orchestrator = AgentOrchestrator(args.config)
    
    if args.status:
        # Show status only
        print("Checking agent status...")
        orchestrator._check_all_health()
        orchestrator.print_status()
        return
    
    if args.stop:
        # Stop all agents
        print("Stopping all agents...")
        orchestrator.stop_all_agents()
        return
    
    try:
        # Start all agents
        print("Starting AgentFleet agents...")
        success = orchestrator.start_all_agents()
        
        if not success:
            logger.error("Failed to start all agents")
            sys.exit(1)
        
        # Print status
        orchestrator.print_status()
        
        # Wait for shutdown signal
        print("\nAgentFleet is running. Press Ctrl+C to stop.")
        try:
            while not orchestrator.shutdown_event.is_set():
                orchestrator.shutdown_event.wait(1)
        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")
    
    except Exception as e:
        logger.error(f"Orchestrator error: {e}")
        sys.exit(1)
    finally:
        orchestrator.stop_all_agents()


if __name__ == "__main__":
    main()