import sys
from pathlib import Path

# Walk up until we find "capstone" folder
current = Path.cwd()
for parent in [current] + list(current.parents):
    if (parent / "capstone" / "__init__.py").exists():
        sys.path.insert(0, str(parent))
        print("📁 Project root set to:", parent)
        break

import capstone
print("✅ capstone imported successfully!")


import json
import requests
import subprocess
import time
import uuid

from google.adk.agents import Agent, LlmAgent, SequentialAgent
from google.adk.agents.remote_a2a_agent import (
    RemoteA2aAgent,
    AGENT_CARD_WELL_KNOWN_PATH,
)

from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.google_llm import Gemini
from google.adk.runners import InMemoryRunner, Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

# Hide additional warnings in the notebook
import warnings

warnings.filterwarnings("ignore")

print("✅ ADK components imported successfully.")


retry_config = types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)

ingest_agent_code = '''
import os
from typing import Any, Dict
import dotenv

from google.adk.agents import LlmAgent
from google.adk.a2a.utils.agent_to_a2a import to_a2a
from google.adk.models.google_llm import Gemini
from google.genai import types

from capstone.tools.stream_simulators import TwitterStreamSimulator, EmergencyFeedSimulator, SensorDataSimulator

def generate_single_event(source_type: str) -> Dict[str, Any]:
    """
    Generate a single event from the specified source type.

    Args:
        source_type: Type of stream source ("twitter", "emergency", "sensor")

    Returns:
        Dictionary containing the generated event data

    Raises:
        ValueError: If source_type is not supported
    """
    # Create simulator based on source type
    if source_type == "twitter":
        simulator = TwitterStreamSimulator()
    elif source_type == "emergency":
        simulator = EmergencyFeedSimulator()
    elif source_type == "sensor":
        simulator = SensorDataSimulator()
    else:
        return {
            "status": "error",
            "message": f"Unsupported source_type: {source_type}"
        }

    result = {
        "status": "success",
        "source_type": source_type,
        "event": simulator.generate_event()
    }
    return result

# Load environment variables from .env file if it exists
dotenv.load_dotenv()

# read from environment variable
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

# if missing, prompt user to enter the API key
if not GOOGLE_API_KEY:
    GOOGLE_API_KEY = input("Enter your Google API key: ")

if not GOOGLE_API_KEY:
    print("❌ Error: Google API key is required. Please set the 'GOOGLE_API_KEY' environment variable or enter it when prompted.")
else:
    os.environ["GOOGLE_GENAI_USE_VERTEXAI"] = "FALSE"
    print("✅ Google API key obtained successfully.")


retry_config = types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)

INGEST_AGENT_INSTRUCTIONS = """You are the Ingest Agent in the AgentFleet incident response system.

Your responsibilities:
1. Call `generate_single_event` to generate a single event from a specified source.
2. The event output should be described in detail for further processing.

When processing events:
- Use the `generate_single_event` tool to generate events
- If the event is successfully generated, describe the generated event in detail 
- Generate unique event IDs
- Extract all relevant information from the event source and describe it in detail

User will supply the source to extract from e.g "twitter", "emergency_feed", or "sensor_data". Pass this to the `generate_single_event` tool to generate the event.
Then describe the generated event in detail in your output.
"""

# Create the Ingest Agent
ingest_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    name="ingest_agent",
    description="Ingest agent that connects to event sources and extract imformation for processing",
    instruction=INGEST_AGENT_INSTRUCTIONS,
    tools=[generate_single_event],
    output_key="raw_event_json",
)

# Create the A2A app
app = to_a2a(
    ingest_agent, port=8001
)
'''

with open("../agents/ingest_agent.py", "w") as f:
    f.write(ingest_agent_code)

print("✅ Ingest Agent code written to capstone/agents/ingest_agent.py")


import subprocess, os
from pathlib import Path
import capstone

project_root = Path(capstone.__file__).resolve().parents[1]


# Setup to run in background
# run agent setup code in capstone/agents/ingest_agent.py for background execution

server_process = subprocess.Popen(
    [
        "uvicorn",
        "capstone.agents.ingest_agent:app",
        "--host",
        "localhost",
        "--port",
        "8001",
    ],
    cwd=project_root,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    env={**os.environ},
)


print("🚀 Starting Ingest Agent A2A server in the background on port 8001.")
print("   Waiting for server to be ready...")

# Wait for the server to start
max_attempts = 20
for attempt in range(max_attempts):
    try:
        response = requests.get(
            "http://localhost:8001/.well-known/agent-card.json", timeout=1
        )
        if response.status_code == 200:
            print("✅ Ingest Agent A2A server is ready.")
            print("   Server URL: http://localhost:8001")
            print("   Agent Card URL: http://localhost:8001/.well-known/agent-card.json")
            break
    except requests.exceptions.RequestException:
        time.sleep(5)
        print(".", end="", flush=True)

else:
    print("\n⚠️  Server may not be ready yet. Check manually if needed.")

# Store the process so it can be terminated later if needed
globals()["ingest_agent_server_process"] = server_process

try:
    response = requests.get(
        "http://localhost:8001/.well-known/agent-card.json", timeout=5
    )
    if response.status_code == 200:
        agent_card = response.json()
        print("✅ Ingest Agent A2A server is reachable.")
        print(json.dumps(agent_card, indent=2))

        print("\n Key details:")
        print(f" - Name: {agent_card.get('name')}")
        print(f" - Description: {agent_card.get('description')}")
        print(f" - URL: {agent_card.get('url')}")
        print(f" - Skills: {len(agent_card.get('skills', []))} capabilities exposed")
    else:
        print(
            f"❌ Failed to reach Ingest Agent A2A server. Status code: {response.status_code}"
        )
except requests.exceptions.RequestException as e:
    print(f"❌ Error reaching Ingest Agent A2A server: {e}")

remote_ingest_agent = RemoteA2aAgent(
    name="remote_ingest_agent",
    description="Client-side proxy to interact with the Ingest Agent A2A app",
    agent_card=f"http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}",
)

print("✅ RemoteA2aAgent proxy created for Ingest Agent A2A app.")
print(f"   Connected to: http://localhost:8001")
print(f"   Agent card: http://localhost:8001{AGENT_CARD_WELL_KNOWN_PATH}")
print("   Ready to send requests to Ingest Agent.")

# setup verifier agent to receive events from the ingest agent and verify claims
from capstone.agents.verifier_agent import (
    extract_claims_tool,
    verify_claim_tool,
    score_reliability_tool
)

VERIFIER_AGENT_INSTRUCTION = """
You are the Verifier Agent in the AgentFleet incident response system.

Your responsibilities:
1. Receive event summary from the Ingest Agent
2. Extract verifiable claims from event content
3. Fact-check claims using search tools (when available)
4. Score source reliability based on verification results

When processing events:
- Use the `extract_claims_tool` to identify factual statements that can be verified
- Use the `verify_claim_tool` to check each claim (with search results if available)
- Use the `score_reliability_tool` to calculate overall reliability score (0.0 to 1.0)
- Flag events with reliability score below 0.3 as unverified
- Explain your reasoning for each claim verification and reliability score in the output

Be thorough in verification but efficient in processing.
Always include session_id for tracking incident lifecycle.
"""

verifier_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    name="verifier_agent",
    description="Verifier agent in the AgentFleet incident response system",
    instruction=VERIFIER_AGENT_INSTRUCTION,
    tools=[extract_claims_tool, verify_claim_tool, score_reliability_tool],
    output_key="verified_claims",
)

print("✅ Verifier Agent Successfully Setup")
print("   Model: gemini-2.5-flash-lite")
print("   Tools: extract_claims_tool(), verify_claim_tool(), score_reliability_tool()")
print("   Ready to verify claims from ingested events.")


from capstone.agents.summarizer_agent import extract_key_facts_tool

SUMMARIZER_AGENT_INSTRUCTIONS = """
You are the Summarizer Agent in the AgentFleet incident response system.

Your responsibilities:
1. Receive verified events from the Verifier Agent
2. Generate concise incident briefs (maximum 200 words)
3. Extract key facts: location, time, affected entities, impact
4. Output incident briefs with structured key facts

When processing events:
- Generate concise summaries (max 200 words)
- Use the `extract_key_facts_tool` to identify structured information
- Include similarity scores and patterns in the incident brief
- Explain your reasoning in the output, including which facts were included and why

Be concise but comprehensive. Focus on actionable information.
Ensure summaries are clear and suitable for human operators.

Verifier Agent Event: {verified_claims?}
"""

summarizer_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    name="summarizer_agent",
    description="Summarizer agent in the AgentFleet incident response system",
    instruction=SUMMARIZER_AGENT_INSTRUCTIONS,
    tools=[extract_key_facts_tool],
    output_key="incident_brief"
)

print("✅ Summarizer Agent Successfully Setup")
print("   Model: gemini-2.5-flash-lite")
print("   Tool: extract_key_facts_tool()")
print("   Ready to summarize verified events into incident briefs.")

from capstone.agents.triage_agent import (
    classify_severity_tool,
    create_job_tool,
)


TRIAGE_AGENT_INSTRUCTION = """You are the Triage Agent in the AgentFleet incident response system.

Your responsibilities:
1. Receive incident briefs from the Summarizer Agent
2. Analyze incident content to determine severity level
3. Classify incidents as LOW, MEDIUM, HIGH, or CRITICAL based on:
   - Threat to life or safety
   - Infrastructure impact
   - Geographic scope
   - Number of people affected
   - Urgency of response needed
4. Calculate priority scores (0.0 to 1.0) for incident ordering
5. Create job queue entries for HIGH and CRITICAL incidents
6. Forward triaged incidents to the Dispatcher Agent

Severity Classification Guidelines:
- CRITICAL: Immediate threat to life, major infrastructure failure, widespread impact (>1000 affected)
- HIGH: Significant threat, infrastructure damage, regional impact (100-1000 affected)
- MEDIUM: Moderate threat, localized damage, limited impact (10-100 affected)
- LOW: Minor threat, minimal damage, very limited impact (<10 affected)

When processing incidents:
- Use the `classify_severity_tool` to analyze and classify incidents
- Use the `create_job_tool` to create job entries for HIGH and CRITICAL incidents
- Always provide clear reasoning for severity assignments
- Consider reliability scores when making classifications
- Explain your reasoning in the output, including which factors influenced the severity classification

Be decisive and consistent in your classifications.
Prioritize human safety and infrastructure integrity.

Summarizer Agent Event: {incident_brief?}
"""

triage_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    name="triage_agent",
    description="Classify incident severity as LOW, MEDIUM, HIGH, or CRITICAL with priority score",
    instruction=TRIAGE_AGENT_INSTRUCTION,
    tools=[classify_severity_tool, create_job_tool],
    output_key="triage_result"
)

print("✅ Triage Agent created to classify incident severity and create job entries.")
print("   Ready to receive incident briefs and perform triage.")
print()

from capstone.agents.dispatcher_agent import (
    generate_actions_tool,
    create_communication_template_tool,
    persist_incident_tool,
    notify_dashboard_tool,
)

DISPATCHER_AGENT_INSTRUCTION = """You are the Dispatcher Agent in the AgentFleet incident response system.

Your responsibilities:
1. Receive triaged incidents from the Triage Agent
2. Generate recommended actions with specific steps, responsible parties, and timelines
3. Create communication templates for HIGH and CRITICAL severity incidents
4. Persist complete incident data to the database
5. Update job status to COMPLETED
6. Output incident dispatch details for operator dashboard notification

Action Generation Guidelines:
- Provide specific, actionable recommendations
- Assign clear responsible parties
- Include realistic timelines based on severity
- Prioritize human safety and infrastructure protection
- Scale response appropriately to severity level

Communication Template Guidelines:
- Use professional, clear language
- Include all critical information (ID, severity, location, summary)
- List top priority actions
- Provide contact information placeholders
- Set expectations for next updates

When processing incidents:
- Use the `generate_actions_tool` to create recommended actions
- Use the `create_communication_template_tool` for HIGH/CRITICAL incidents
- Use the `persist_incident_tool` to save to database
- Use the `notify_dashboard_tool` to make incident available to operators
- Always ensure complete data persistence
- Confirm job status is updated to COMPLETED
- Explain and output your reasoning in the dispatch details

Be thorough and professional in all communications.
Ensure operators have all information needed to respond effectively.

Triage Agent Event: {triage_result?}
"""

dispatcher_agent = LlmAgent(
    name="dispatcher_agent",
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    description="Dispatcher agent in the AgentFleet incident response system",
    instruction=DISPATCHER_AGENT_INSTRUCTION,
    tools=[
        generate_actions_tool,
        create_communication_template_tool,
        persist_incident_tool,
        notify_dashboard_tool,
    ],
    output_key="dispatch_result",
)

print("✅ Dispatcher Agent created to generate actions, persist incidents, and notify dashboard.")
print("   Ready to receive triaged incidents and perform dispatching.")


DASHBOARD_AGENT_INSTRUCTION = """You are the Dashboard Agent in the AgentFleet incident response system.

Your responsibilities:
1. Access the INCIDENT_CACHE from the Dispatcher Agent to get current incident data
2. Create and maintain an incident dashboard with all current incidents
3. Display incident information in a clear, organized markdown table format
4. Include all relevant fields: incident ID, severity, status, location, priority score, actions, and timestamps
5. Update the dashboard with new incidents as they are dispatched

Dashboard Requirements:
- Create a markdown table with the following columns:
  - Incident ID
  - Severity Level (LOW/MEDIUM/HIGH/CRITICAL)
  - Status (DISPATCHED, IN_PROGRESS, RESOLVED, etc.)
  - Priority Score (0.0-1.0)
  - Location (if available)
  - Summary (brief description)
  - Actions Required (count of recommended actions)
  - Dispatched At (timestamp)
- Sort incidents by severity (CRITICAL → HIGH → MEDIUM → LOW) and then by priority score (highest first)
- Include all dispatched incidents in the dashboard
- Format timestamps in a readable format (YYYY-MM-DD HH:MM UTC)
- Keep summaries concise (max 50 characters)
- Display the dashboard as markdown output that can be rendered in notebooks
- Highlight critical and high-priority incidents with detailed action items
- Include communication templates for critical/high incidents

When processing incidents:
- Use the `create_dashboard_markdown_tool` to generate the dashboard from cache
- The tool automatically accesses the INCIDENT_CACHE from the Dispatcher Agent
- Focus on presenting information clearly for human operator review
- Ensure critical incidents are prominently displayed with action items
- OUTPUT the complete markdown dashboard

Be thorough in presenting all incident information clearly.
Focus on readability and actionable information for operators.

The dashboard will automatically reflect the current state of all dispatched incidents.
"""

from capstone.agents.dashboard_agent import create_dashboard_markdown_tool

dashboard_agent = LlmAgent(
    model=Gemini(model="gemini-2.5-flash-lite", retry_options=retry_config),
    name="dashboard_agent",
    description="Dashboard agent to create and maintain incident response dashboard",
    instruction=DASHBOARD_AGENT_INSTRUCTION,
    tools=[create_dashboard_markdown_tool],
    output_key="dashboard_output"
)

print("✅ Dashboard Agent created to create and maintain incident response dashboard.")
print("   Model: gemini-2.5-flash-lite")
print("   Tool: create_dashboard_markdown_tool()")
print("   Ready to create markdown dashboards from dispatched incidents.")

# Create complete end-to-end coordinator agent
root_agent = SequentialAgent(
    name="root_agent",
    description="Complete end-to-end AgentFleet incident response system coordinator",
    sub_agents=[remote_ingest_agent, verifier_agent, summarizer_agent, triage_agent, dispatcher_agent, dashboard_agent],
)

print("✅ Root Agent created to coordinate the complete AgentFleet system.")
print("   Agents in sequence: Ingest → Verifier → Summarizer → Triage → Dispatcher → Dashboard")
print("   Ready to process events from ingestion to dashboard display.")
print()
print("🚀 AgentFleet System Setup Complete!")
print("   All 6 agents are ready for coordinated incident response operations.")