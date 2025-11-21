#!/usr/bin/env python3
"""
AgentFleet Agent Stop Script

This script provides functionality to stop AgentFleet agents gracefully.
It can stop all agents or specific agents by name.

Usage:
    python stop_agents.py [--agent=agent_name] [--force]
"""

import os
import sys
import signal
import logging
import argparse
import subprocess
import time
from typing import List, Optional
from pathlib import Path
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AgentStopper:
    """Handles stopping of AgentFleet agents."""
    
    def __init__(self):
        """Initialize the agent stopper."""
        self.agents = {
            "ingest": {"port": 8001, "name": "Ingest Agent"},
            "verifier": {"port": 8002, "name": "Verifier Agent"},
            "summarizer": {"port": 8003, "name": "Summarizer Agent"},
            "triage": {"port": 8004, "name": "Triage Agent"},
            "dispatcher": {"port": 8005, "name": "Dispatcher Agent"}
        }
    
    def stop_all_agents(self, force: bool = False) -> bool:
        """
        Stop all running agents.
        
        Args:
            force: Whether to force kill agents that don't respond to graceful shutdown
            
        Returns:
            True if all agents stopped successfully, False otherwise
        """
        logger.info("Stopping all AgentFleet agents...")
        success = True
        
        for agent_name in self.agents:
            if not self.stop_agent(agent_name, force):
                success = False
        
        if success:
            logger.info("All agents stopped successfully")
        else:
            logger.error("Some agents failed to stop properly")
        
        return success
    
    def stop_agent(self, agent_name: str, force: bool = False) -> bool:
        """
        Stop a specific agent.
        
        Args:
            agent_name: Name of the agent to stop
            force: Whether to force kill the agent
            
        Returns:
            True if agent stopped successfully, False otherwise
        """
        if agent_name not in self.agents:
            logger.error(f"Unknown agent: {agent_name}")
            return False
        
        agent_info = self.agents[agent_name]
        port = agent_info["port"]
        name = agent_info["name"]
        
        logger.info(f"Stopping {name} (port {port})...")
        
        try:
            if not force:
                # Try graceful shutdown first
                success = self._graceful_shutdown(agent_name, port)
                if success:
                    logger.info(f"{name} stopped gracefully")
                    return True
                else:
                    logger.warning(f"Graceful shutdown failed for {name}, trying force kill")
            
            # Force kill if graceful shutdown failed or force flag is set
            success = self._force_kill_agent(port)
            if success:
                logger.info(f"{name} force killed successfully")
                return True
            else:
                logger.error(f"Failed to stop {name}")
                return False
                
        except Exception as e:
            logger.error(f"Error stopping {name}: {e}")
            return False
    
    def _graceful_shutdown(self, agent_name: str, port: int) -> bool:
        """
        Attempt graceful shutdown via health endpoint.
        
        Args:
            agent_name: Name of the agent
            port: Port number
            
        Returns:
            True if graceful shutdown successful
        """
        try:
            # Check if agent is running
            url = f"http://localhost:{port}/health"
            response = requests.get(url, timeout=5)
            
            if response.status_code != 200:
                logger.info(f"{agent_name} is not running (HTTP {response.status_code})")
                return True
            
            # Agent is running, try to stop it
            # For now, we'll use SIGTERM to gracefully stop the process
            # In a more sophisticated setup, we could have a dedicated shutdown endpoint
            
            # Find and terminate the process
            import psutil
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and any(f":{port}" in str(arg) or f"port={port}" in str(arg) for arg in cmdline):
                        logger.info(f"Sending SIGTERM to process {proc.info['pid']} on port {port}")
                        proc.terminate()
                        return True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                    continue
            
            logger.warning(f"Could not find process for port {port}")
            return False
            
        except requests.RequestException:
            logger.info(f"{agent_name} is not responding, assuming it's already stopped")
            return True
    
    def _force_kill_agent(self, port: int) -> bool:
        """
        Force kill agent process using port.
        
        Args:
            port: Port number to kill
            
        Returns:
            True if process killed successfully
        """
        try:
            import psutil
            
            killed = False
            for proc in psutil.process_iter(['pid', 'cmdline']):
                try:
                    cmdline = proc.info['cmdline']
                    if cmdline and any(f":{port}" in str(arg) or f"port={port}" in str(arg) for arg in cmdline):
                        logger.info(f"Force killing process {proc.info['pid']} on port {port}")
                        proc.kill()
                        killed = True
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                    logger.warning(f"Could not kill process {proc.info['pid']}: {e}")
            
            if killed:
                # Wait a moment for process to actually terminate
                time.sleep(1)
                return True
            else:
                logger.warning(f"No process found for port {port}")
                return True  # Not an error if no process was running
                
        except ImportError:
            # Fallback to command line tools if psutil is not available
            logger.info(f"Using command line tools to kill port {port}")
            
            # Try to find and kill the process
            try:
                # Find process using the port
                result = subprocess.run(
                    ["lsof", "-ti", f":{port}"],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                
                if result.stdout.strip():
                    pids = result.stdout.strip().split()
                    for pid in pids:
                        try:
                            logger.info(f"Force killing PID {pid}")
                            subprocess.run(["kill", "-9", pid], timeout=5)
                        except subprocess.TimeoutExpired:
                            logger.warning(f"Kill command timed out for PID {pid}")
                    return True
                else:
                    logger.info(f"No process found using port {port}")
                    return True
                    
            except (subprocess.SubprocessError, FileNotFoundError) as e:
                logger.error(f"Failed to kill process on port {port}: {e}")
                return False
    
    def check_agent_status(self) -> Dict[str, str]:
        """
        Check status of all agents.
        
        Returns:
            Dictionary mapping agent names to their status
        """
        status = {}
        
        for agent_name, agent_info in self.agents.items():
            port = agent_info["port"]
            
            try:
                url = f"http://localhost:{port}/health"
                response = requests.get(url, timeout=3)
                
                if response.status_code == 200:
                    status[agent_name] = "running"
                else:
                    status[agent_name] = f"http_{response.status_code}"
                    
            except requests.RequestException:
                status[agent_name] = "not_running"
        
        return status
    
    def print_status(self):
        """Print status of all agents."""
        print("\nAgentFleet Agent Status:")
        print("=" * 50)
        
        status = self.check_agent_status()
        
        for agent_name, agent_info in self.agents.items():
            name = agent_info["name"]
            current_status = status.get(agent_name, "unknown")
            
            status_display = f"[{current_status.upper()}]"
            
            if current_status == "running":
                status_display = f"\033[92m{status_display}\033[0m"  # Green
            elif current_status != "running":
                status_display = f"\033[91m{status_display}\033[0m"  # Red
            
            print(f"{name:20} {status_display}")
        
        print("=" * 50)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="AgentFleet Agent Stop Tool")
    parser.add_argument(
        "--agent",
        help="Stop specific agent (ingest, verifier, summarizer, triage, dispatcher)"
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force kill agents that don't respond to graceful shutdown"
    )
    parser.add_argument(
        "--status",
        action="store_true",
        help="Show agent status and exit"
    )
    parser.add_argument(
        "--wait",
        type=int,
        default=5,
        help="Wait time in seconds before force killing (default: 5)"
    )
    
    args = parser.parse_args()
    
    # Change to the capstone directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    stopper = AgentStopper()
    
    if args.status:
        # Show status only
        stopper.print_status()
        return
    
    try:
        if args.agent:
            # Stop specific agent
            if args.agent not in stopper.agents:
                logger.error(f"Unknown agent: {args.agent}")
                print(f"Available agents: {', '.join(stopper.agents.keys())}")
                sys.exit(1)
            
            success = stopper.stop_agent(args.agent, args.force)
            if not success:
                sys.exit(1)
        else:
            # Stop all agents
            success = stopper.stop_all_agents(args.force)
            if not success:
                sys.exit(1)
    
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()