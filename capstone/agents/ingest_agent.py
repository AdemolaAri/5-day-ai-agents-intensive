
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
