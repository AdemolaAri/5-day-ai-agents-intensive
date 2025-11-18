"""
Summarizer Agent for AgentFleet.

This agent is responsible for:
- Receiving verified events from the Verifier Agent via A2A protocol
- Generating concise incident briefs (max 200 words)
- Extracting key facts and structured data
- Querying Memory Bank for similar historical incidents
- Including pattern information in incident briefs
- Managing session context for incident lifecycle
- Forwarding incident briefs to the Triage Agent via A2A protocol

Requirements Satisfied:
- 3.1: Generate brief summary not exceeding 200 words
- 3.2: Include key facts, location, time, and affected entities
- 3.3: Structure output as MCP envelope with schema type "incident_brief_v1"
- 3.4: Forward incident brief to Triage Agent via A2A protocol
- 3.5: Maintain session context to correlate related events
- 8.2: Query Memory Bank for similar historical incidents
- 8.3: Include pattern information in incident brief
- 9.1: Create unique session identifier for incident lifecycle
- 9.2: Include session identifier in all message envelopes
- 9.3: Access session-specific context and history
"""

import os
import uuid
import logging
import time
import json
from datetime import datetime
from typing import Dict, Any, List, Optional
from google import genai
from google.genai import types

from capstone.models import (
    VerifiedEvent,
    IncidentBrief
)
from capstone.mcp_envelope import (
    MCPEnvelope,
    EnvelopeSchema,
    PayloadType,
    create_incident_envelope,
    parse_envelope
)
from capstone.tools.memory_tools import query_memory_bank, store_incident_memory


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_summary_tool(
    event_content: str,
    event_location: str = "",
    event_type: str = "unknown",
    reliability_score: float = 0.0,
    max_words: int = 200
) -> Dict[str, Any]:
    """
    Tool function to generate a concise incident summary.
    
    This tool creates a brief summary of the incident, ensuring it does not
    exceed the specified word limit (default 200 words). The summary includes:
    - What happened (event description)
    - Where it happened (location)
    - When it happened (time context)
    - Impact and severity indicators
    
    Args:
        event_content: The verified event content to summarize
        event_location: Location of the event
        event_type: Type of event (flooding, fire, etc.)
        reliability_score: Verification reliability score
        max_words: Maximum words allowed in summary (default: 200)
        
    Returns:
        Dictionary containing the generated summary
    """
    try:
        # Generate summary (in production, this would use LLM for better summarization)
        # For now, we'll create a structured summary
        
        # Extract key information
        content_words = event_content.split()
        
        # Create concise summary
        summary_parts = []
        
        # Add event type and location
        if event_type != "unknown":
            summary_parts.append(f"{event_type.replace('_', ' ').title()} incident")
        else:
            summary_parts.append("Incident")
        
        if event_location:
            summary_parts.append(f"reported in {event_location}")
        
        # Add main content (truncated if needed)
        if len(content_words) > max_words - 20:  # Reserve space for metadata
            truncated_content = " ".join(content_words[:max_words - 20])
            summary_parts.append(f": {truncated_content}...")
        else:
            summary_parts.append(f": {event_content}")
        
        # Add reliability indicator
        if reliability_score >= 0.7:
            summary_parts.append("(High confidence)")
        elif reliability_score >= 0.4:
            summary_parts.append("(Moderate confidence)")
        else:
            summary_parts.append("(Low confidence - requires verification)")
        
        summary = " ".join(summary_parts)
        
        # Ensure word limit
        summary_words = summary.split()
        if len(summary_words) > max_words:
            summary = " ".join(summary_words[:max_words]) + "..."
        
        word_count = len(summary.split())
        
        logger.info(f"Generated summary with {word_count} words")
        
        return {
            "success": True,
            "summary": summary,
            "word_count": word_count,
            "within_limit": word_count <= max_words
        }
    
    except Exception as e:
        logger.error(f"Error generating summary: {e}")
        return {
            "success": False,
            "error": str(e),
            "summary": ""
        }


def extract_key_facts_tool(
    event_content: str,
    event_data: str
) -> Dict[str, Any]:
    """
    Tool function to extract key facts from event data.
    
    This tool identifies and extracts structured information including:
    - Specific numbers and measurements
    - Named entities (people, organizations, places)
    - Temporal information
    - Causal relationships
    - Impact indicators
    
    Args:
        event_content: The event content text
        event_data: JSON string containing full event data
        
    Returns:
        Dictionary containing extracted key facts
    """
    try:
        # Parse event data
        try:
            data = json.loads(event_data)
        except json.JSONDecodeError:
            data = {}
        
        key_facts = []
        
        # Extract location
        location = data.get("location") or data.get("original_event", {}).get("location")
        if location:
            key_facts.append(f"Location: {location}")
        
        # Extract event type
        event_type = data.get("event_type") or data.get("original_event", {}).get("event_type")
        if event_type and event_type != "unknown":
            key_facts.append(f"Type: {event_type.replace('_', ' ').title()}")
        
        # Extract reliability score
        reliability_score = data.get("reliability_score")
        if reliability_score is not None:
            key_facts.append(f"Reliability: {reliability_score:.2f}")
        
        # Extract entities
        entities = data.get("entities") or data.get("original_event", {}).get("entities", [])
        if entities:
            key_facts.append(f"Affected areas: {', '.join(entities[:3])}")
        
        # Extract numbers from content (casualties, damages, etc.)
        words = event_content.split()
        numbers_found = []
        for i, word in enumerate(words):
            if any(char.isdigit() for char in word):
                # Get context around the number
                context_start = max(0, i - 2)
                context_end = min(len(words), i + 3)
                context = " ".join(words[context_start:context_end])
                numbers_found.append(context)
        
        if numbers_found:
            for num_fact in numbers_found[:2]:  # Limit to 2 numerical facts
                key_facts.append(num_fact)
        
        # Extract verified claims count
        verified_claims = data.get("verified_claims", [])
        if verified_claims:
            verified_count = sum(1 for claim in verified_claims if claim.get("verified", False))
            key_facts.append(f"Verified claims: {verified_count}/{len(verified_claims)}")
        
        logger.info(f"Extracted {len(key_facts)} key facts")
        
        return {
            "success": True,
            "key_facts": key_facts,
            "count": len(key_facts)
        }
    
    except Exception as e:
        logger.error(f"Error extracting key facts: {e}")
        return {
            "success": False,
            "error": str(e),
            "key_facts": []
        }


def create_forward_to_triage_tool(triage_url: str):
    """
    Factory function to create a forward_to_triage tool.
    
    Args:
        triage_url: URL of the Triage Agent
        
    Returns:
        Tool function for forwarding to Triage Agent
    """
    def forward_to_triage_tool(
        envelope_json: str
    ) -> Dict[str, Any]:
        """
        Tool function to forward incident briefs to the Triage Agent.
        
        Implements A2A protocol communication with retry logic and exponential backoff.
        
        Args:
            envelope_json: JSON string containing MCP envelope with incident brief
            
        Returns:
            Dictionary containing the response from Triage Agent
        """
        import httpx
        
        max_retries = 3
        initial_delay = 1.0
        backoff_multiplier = 2.0
        max_delay = 10.0
        
        try:
            envelope_data = json.loads(envelope_json)
            
            # Validate envelope before forwarding
            is_valid, error_msg = parse_envelope(envelope_data)
            if not is_valid:
                logger.error(f"Invalid envelope: {error_msg}")
                return {
                    "success": False,
                    "error": f"Invalid envelope: {error_msg}"
                }
            
            logger.info("Forwarding to Triage Agent via A2A protocol")
            
            # Retry logic with exponential backoff
            for attempt in range(max_retries):
                try:
                    with httpx.Client(timeout=30.0) as client:
                        response = client.post(
                            f"{triage_url}/tasks",
                            json=envelope_data,
                            headers={"Content-Type": "application/json"}
                        )
                        
                        if response.status_code == 200:
                            logger.info(f"Successfully forwarded to Triage Agent")
                            return {
                                "success": True,
                                "response": response.json(),
                                "status_code": response.status_code,
                                "attempts": attempt + 1
                            }
                        else:
                            logger.warning(f"Triage Agent returned status {response.status_code}")
                            if attempt == max_retries - 1:
                                return {
                                    "success": False,
                                    "error": f"HTTP {response.status_code}",
                                    "response": response.text,
                                    "attempts": attempt + 1
                                }
                
                except (httpx.ConnectError, httpx.TimeoutException, OSError) as e:
                    logger.warning(f"Connection error on attempt {attempt + 1}/{max_retries}: {e}")
                    
                    if attempt == max_retries - 1:
                        return {
                            "success": False,
                            "error": f"Connection failed after {max_retries} attempts",
                            "details": str(e),
                            "attempts": max_retries
                        }
                    
                    # Calculate delay with exponential backoff
                    delay = min(initial_delay * (backoff_multiplier ** attempt), max_delay)
                    logger.info(f"Retrying in {delay} seconds...")
                    time.sleep(delay)
            
            return {
                "success": False,
                "error": "Max retries exceeded"
            }
        
        except Exception as e:
            logger.error(f"Error forwarding to triage: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    return forward_to_triage_tool


class SummarizerAgent:
    """
    Summarizer Agent for incident brief generation with memory integration.
    
    Responsibilities:
    - Generate concise incident summaries (max 200 words)
    - Extract key facts and structured data
    - Query Memory Bank for similar incidents
    - Manage session context
    - Forward incident briefs to Triage Agent
    """
    
    def __init__(
        self,
        model_name: str = "gemini-2.0-flash-lite",
        triage_url: str = "http://localhost:8004"
    ):
        """
        Initialize the Summarizer Agent.
        
        Args:
            model_name: Name of the Gemini model to use
            triage_url: URL of the Triage Agent for A2A communication
        """
        self.model_name = model_name
        self.agent_name = "summarizer_agent"
        self.triage_url = triage_url
        
        # Session management
        self.active_sessions: Dict[str, Dict[str, Any]] = {}
        
        # Initialize Gemini client
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        self.client = genai.Client(api_key=api_key)
        
        # Agent instruction
        self.instruction = """You are the Summarizer Agent in the AgentFleet incident response system.

Your responsibilities:
1. Receive verified events from the Verifier Agent via A2A protocol
2. Generate concise incident briefs (maximum 200 words)
3. Extract key facts: location, time, affected entities, impact
4. Query Memory Bank for similar historical incidents
5. Include pattern information from historical data
6. Create incident brief envelopes with all relevant data
7. Forward incident briefs to the Triage Agent
8. Maintain session context for related events

When processing events:
- Use the generate_summary tool to create concise summaries (max 200 words)
- Use the extract_key_facts tool to identify structured information
- Use the query_memory_bank tool to find similar historical incidents
- Include similarity scores and patterns in the incident brief
- Use the forward_to_triage tool to send briefs to the next agent
- Always preserve session_id for incident lifecycle tracking

Be concise but comprehensive. Focus on actionable information.
Ensure summaries are clear and suitable for human operators.
"""
        
        # Define tools
        self.tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="generate_summary",
                        description="Generate a concise incident summary with maximum 200 words",
                        parameters={
                            "type": "object",
                            "properties": {
                                "event_content": {
                                    "type": "string",
                                    "description": "The verified event content to summarize"
                                },
                                "event_location": {
                                    "type": "string",
                                    "description": "Location of the event"
                                },
                                "event_type": {
                                    "type": "string",
                                    "description": "Type of event (flooding, fire, etc.)"
                                },
                                "reliability_score": {
                                    "type": "number",
                                    "description": "Verification reliability score (0.0 to 1.0)"
                                },
                                "max_words": {
                                    "type": "integer",
                                    "description": "Maximum words allowed in summary",
                                    "default": 200
                                }
                            },
                            "required": ["event_content"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="extract_key_facts",
                        description="Extract key facts and structured data from event",
                        parameters={
                            "type": "object",
                            "properties": {
                                "event_content": {
                                    "type": "string",
                                    "description": "The event content text"
                                },
                                "event_data": {
                                    "type": "string",
                                    "description": "JSON string containing full event data"
                                }
                            },
                            "required": ["event_content", "event_data"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="query_memory_bank",
                        description="Query Memory Bank for similar historical incidents",
                        parameters={
                            "type": "object",
                            "properties": {
                                "query_text": {
                                    "type": "string",
                                    "description": "Text describing the incident to search for"
                                },
                                "top_k": {
                                    "type": "integer",
                                    "description": "Maximum number of results to return",
                                    "default": 5
                                },
                                "min_similarity": {
                                    "type": "number",
                                    "description": "Minimum similarity threshold (0.0 to 1.0)",
                                    "default": 0.5
                                }
                            },
                            "required": ["query_text"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="forward_to_triage",
                        description="Forward incident brief envelope to the Triage Agent via A2A protocol",
                        parameters={
                            "type": "object",
                            "properties": {
                                "envelope_json": {
                                    "type": "string",
                                    "description": "JSON string containing the MCP envelope with incident brief"
                                }
                            },
                            "required": ["envelope_json"]
                        }
                    )
                ]
            )
        ]
        
        # Create the forward_to_triage tool
        self.forward_to_triage_tool = create_forward_to_triage_tool(
            self.triage_url
        )
        
        logger.info(f"Initialized Summarizer Agent with model {model_name}")
    
    def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool function."""
        if tool_name == "generate_summary":
            return generate_summary_tool(**tool_args)
        elif tool_name == "extract_key_facts":
            return extract_key_facts_tool(**tool_args)
        elif tool_name == "query_memory_bank":
            return query_memory_bank(**tool_args)
        elif tool_name == "forward_to_triage":
            return self.forward_to_triage_tool(**tool_args)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    def _get_or_create_session(self, session_id: Optional[str] = None) -> str:
        """
        Get existing session or create a new one.
        
        Args:
            session_id: Optional existing session ID
            
        Returns:
            Session ID
        """
        if session_id and session_id in self.active_sessions:
            return session_id
        
        # Create new session
        new_session_id = session_id or str(uuid.uuid4())
        self.active_sessions[new_session_id] = {
            "created_at": datetime.utcnow(),
            "last_activity": datetime.utcnow(),
            "events": [],
            "context": {}
        }
        
        logger.info(f"Created new session: {new_session_id}")
        return new_session_id
    
    def _update_session_context(self, session_id: str, event_data: Dict[str, Any]):
        """
        Update session context with event data.
        
        Args:
            session_id: Session identifier
            event_data: Event data to add to context
        """
        if session_id in self.active_sessions:
            self.active_sessions[session_id]["last_activity"] = datetime.utcnow()
            self.active_sessions[session_id]["events"].append(event_data)
            logger.info(f"Updated session {session_id} context")
    
    def process_message(self, message: str, session_id: Optional[str] = None) -> str:
        """
        Process a message using the agent.
        
        Args:
            message: User message or task description
            session_id: Optional session identifier
            
        Returns:
            Agent response
        """
        try:
            # Ensure session exists
            session_id = self._get_or_create_session(session_id)
            
            # Create chat session
            chat = self.client.chats.create(
                model=self.model_name,
                config=types.GenerateContentConfig(
                    system_instruction=self.instruction,
                    tools=self.tools,
                    temperature=0.1
                )
            )
            
            # Send message
            response = chat.send_message(message)
            
            # Handle tool calls
            while response.candidates[0].content.parts:
                part = response.candidates[0].content.parts[0]
                
                # Check if it's a function call
                if hasattr(part, 'function_call') and part.function_call:
                    function_call = part.function_call
                    tool_name = function_call.name
                    tool_args = dict(function_call.args)
                    
                    logger.info(f"Executing tool: {tool_name}")
                    
                    # Execute tool
                    tool_result = self._execute_tool(tool_name, tool_args)
                    
                    # Send tool response back
                    response = chat.send_message(
                        types.Content(
                            parts=[
                                types.Part(
                                    function_response=types.FunctionResponse(
                                        name=tool_name,
                                        response=tool_result
                                    )
                                )
                            ]
                        )
                    )
                else:
                    # Text response
                    if hasattr(part, 'text'):
                        return part.text
                    break
            
            # Extract final text response
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text'):
                        return part.text
            
            return "No response generated"
        
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return f"Error: {str(e)}"
    
    def process_event_envelope(self, envelope_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a verified event envelope from the Verifier Agent.
        
        Args:
            envelope_data: MCP envelope containing verified event
            
        Returns:
            Processing result with incident brief
        """
        try:
            # Parse and validate envelope
            envelope, error_msg = parse_envelope(envelope_data)
            if not envelope:
                logger.error(f"Invalid envelope: {error_msg}")
                return {
                    "success": False,
                    "error": f"Invalid envelope: {error_msg}"
                }
            
            # Get or create session
            session_id = self._get_or_create_session(envelope.session_id)
            
            # Extract event data
            event_data = envelope.payload.get("data", {})
            
            # Update session context
            self._update_session_context(session_id, event_data)
            
            # Extract relevant fields
            original_event = event_data.get("original_event", {})
            event_content = original_event.get("content", "")
            event_location = original_event.get("location", "")
            event_type = original_event.get("event_type", "unknown")
            reliability_score = event_data.get("reliability_score", 0.0)
            event_id = event_data.get("event_id", "unknown")
            
            # Create processing message
            message = f"""Process this verified event to create an incident brief:

Event ID: {event_id}
Content: {event_content}
Location: {event_location}
Type: {event_type}
Reliability Score: {reliability_score}

Full Event Data: {json.dumps(event_data)}

Tasks:
1. Generate a concise summary (max 200 words)
2. Extract key facts from the event
3. Query Memory Bank for similar historical incidents
4. Create incident brief envelope with all data
5. Forward to Triage Agent

Session ID: {session_id}
"""
            
            # Process with agent
            response = self.process_message(message, session_id)
            
            return {
                "success": True,
                "response": response,
                "session_id": session_id
            }
        
        except Exception as e:
            logger.error(f"Error processing event envelope: {e}")
            return {
                "success": False,
                "error": str(e)
            }


def create_summarizer_agent(
    model_name: str = "gemini-2.0-flash-lite",
    triage_url: str = "http://localhost:8004"
) -> SummarizerAgent:
    """
    Factory function to create a Summarizer Agent instance.
    
    Args:
        model_name: Name of the Gemini model to use
        triage_url: URL of the Triage Agent for A2A communication
        
    Returns:
        SummarizerAgent instance
    """
    return SummarizerAgent(model_name=model_name, triage_url=triage_url)
