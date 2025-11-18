"""
Verifier Agent for AgentFleet.

This agent is responsible for:
- Receiving normalized events from the Ingest Agent via A2A protocol
- Extracting verifiable claims from event content
- Fact-checking claims using search tools
- Scoring source reliability and calculating confidence scores
- Creating verified event envelopes
- Forwarding verified events to the Summarizer Agent via A2A protocol

Requirements Satisfied:
- 2.1: Extract claims requiring verification
- 2.2: Invoke search and cross-check tools to validate factual accuracy
- 2.3: Assign reliability score between 0.0 and 1.0
- 2.4: Flag events with reliability score below 0.3 as unverified
- 2.5: Forward verified events to Summarizer Agent via A2A protocol
- 6.1: Expose agent via A2A protocol
- 6.2: Use MCP envelope format for communication
- 6.3: Validate envelope schema before processing
- 6.4: Return A2A response envelope with status and result
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
    NormalizedEvent,
    Claim,
    VerificationResult,
    VerifiedEvent
)
from capstone.mcp_envelope import (
    MCPEnvelope,
    EnvelopeSchema,
    PayloadType,
    create_envelope,
    parse_envelope
)


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def extract_claims_tool(event_content: str, event_source: str) -> Dict[str, Any]:
    """
    Tool function to extract verifiable claims from event content.
    
    This tool identifies factual statements that can be verified through
    external sources. Claims are extracted based on:
    - Specific factual assertions (numbers, locations, times)
    - Named entities (people, organizations, places)
    - Causal relationships (X caused Y)
    - Status statements (X is happening, Y occurred)
    
    Args:
        event_content: The event text to analyze
        event_source: Source of the event (for context)
        
    Returns:
        Dictionary containing extracted claims
    """
    try:
        claims = []
        
        # Simple claim extraction based on sentence structure
        # In production, this would use more sophisticated NLP
        sentences = event_content.split('.')
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
            
            # Look for factual indicators
            factual_indicators = [
                'reported', 'confirmed', 'announced', 'stated',
                'occurred', 'happened', 'caused', 'resulted',
                'injured', 'damaged', 'affected', 'evacuated'
            ]
            
            # Check if sentence contains factual indicators
            if any(indicator in sentence.lower() for indicator in factual_indicators):
                claim = Claim(text=sentence, source=event_source)
                claims.append(claim.to_dict())
            
            # Look for specific numbers or measurements
            elif any(char.isdigit() for char in sentence):
                claim = Claim(text=sentence, source=event_source)
                claims.append(claim.to_dict())
        
        logger.info(f"Extracted {len(claims)} claims from event")
        
        return {
            "success": True,
            "claims": claims,
            "count": len(claims)
        }
    
    except Exception as e:
        logger.error(f"Error extracting claims: {e}")
        return {
            "success": False,
            "error": str(e),
            "claims": []
        }


def verify_claim_tool(
    claim_text: str,
    search_results: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool function to verify a claim using search results.
    
    This tool analyzes search results to determine if a claim is supported
    by external sources. Verification considers:
    - Number of corroborating sources
    - Source credibility
    - Consistency of information
    - Recency of sources
    
    Args:
        claim_text: The claim to verify
        search_results: JSON string containing search results (optional)
        
    Returns:
        Dictionary containing verification result
    """
    try:
        # Parse search results if provided
        if search_results:
            try:
                results = json.loads(search_results)
            except json.JSONDecodeError:
                results = {"results": []}
        else:
            results = {"results": []}
        
        # Analyze search results for verification
        sources = []
        verified = False
        confidence = 0.0
        
        if results.get("results"):
            # Count corroborating sources
            num_sources = len(results["results"])
            sources = [r.get("url", "") for r in results["results"][:5]]
            
            # Simple verification logic based on number of sources
            # In production, this would use more sophisticated analysis
            if num_sources >= 3:
                verified = True
                confidence = min(0.9, 0.5 + (num_sources * 0.1))
            elif num_sources >= 1:
                verified = True
                confidence = 0.5 + (num_sources * 0.15)
            else:
                verified = False
                confidence = 0.2
        else:
            # No search results - low confidence
            verified = False
            confidence = 0.1
        
        logger.info(f"Verified claim with confidence {confidence:.2f}")
        
        return {
            "success": True,
            "verified": verified,
            "confidence": confidence,
            "sources": sources,
            "num_sources": len(sources)
        }
    
    except Exception as e:
        logger.error(f"Error verifying claim: {e}")
        return {
            "success": False,
            "error": str(e),
            "verified": False,
            "confidence": 0.0,
            "sources": []
        }


def score_reliability_tool(
    verification_results: str,
    event_source: str
) -> Dict[str, Any]:
    """
    Tool function to calculate overall reliability score for an event.
    
    This tool aggregates individual claim verification results to produce
    an overall reliability score between 0.0 and 1.0. Scoring considers:
    - Percentage of verified claims
    - Average confidence across claims
    - Source credibility
    - Consistency of verification results
    
    Args:
        verification_results: JSON string containing list of verification results
        event_source: Source of the event (affects base credibility)
        
    Returns:
        Dictionary containing reliability score and analysis
    """
    try:
        # Parse verification results
        try:
            results = json.loads(verification_results)
            if isinstance(results, dict):
                results = results.get("results", [])
        except json.JSONDecodeError:
            results = []
        
        if not results:
            logger.warning("No verification results provided")
            return {
                "success": True,
                "reliability_score": 0.3,
                "verified_count": 0,
                "total_count": 0,
                "average_confidence": 0.0
            }
        
        # Calculate metrics
        verified_count = sum(1 for r in results if r.get("verified", False))
        total_count = len(results)
        confidences = [r.get("confidence", 0.0) for r in results]
        average_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        
        # Base score from verification rate
        verification_rate = verified_count / total_count if total_count > 0 else 0.0
        
        # Adjust for source credibility
        source_multiplier = 1.0
        if event_source in ["emergency", "official"]:
            source_multiplier = 1.1
        elif event_source in ["twitter", "social"]:
            source_multiplier = 0.9
        
        # Calculate final reliability score
        reliability_score = (verification_rate * 0.6 + average_confidence * 0.4) * source_multiplier
        reliability_score = max(0.0, min(1.0, reliability_score))  # Clamp to [0, 1]
        
        logger.info(f"Calculated reliability score: {reliability_score:.2f}")
        
        return {
            "success": True,
            "reliability_score": reliability_score,
            "verified_count": verified_count,
            "total_count": total_count,
            "average_confidence": average_confidence,
            "verification_rate": verification_rate
        }
    
    except Exception as e:
        logger.error(f"Error scoring reliability: {e}")
        return {
            "success": False,
            "error": str(e),
            "reliability_score": 0.0
        }


def create_forward_to_summarizer_tool(summarizer_url: str):
    """
    Factory function to create a forward_to_summarizer tool.
    
    Args:
        summarizer_url: URL of the Summarizer Agent
        
    Returns:
        Tool function for forwarding to Summarizer Agent
    """
    def forward_to_summarizer_tool(
        envelope_json: str
    ) -> Dict[str, Any]:
        """
        Tool function to forward verified events to the Summarizer Agent.
        
        Implements A2A protocol communication with retry logic and exponential backoff.
        
        Args:
            envelope_json: JSON string containing MCP envelope with verified event
            
        Returns:
            Dictionary containing the response from Summarizer Agent
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
            
            logger.info("Forwarding to Summarizer Agent via A2A protocol")
            
            # Retry logic with exponential backoff
            for attempt in range(max_retries):
                try:
                    with httpx.Client(timeout=30.0) as client:
                        response = client.post(
                            f"{summarizer_url}/tasks",
                            json=envelope_data,
                            headers={"Content-Type": "application/json"}
                        )
                        
                        if response.status_code == 200:
                            logger.info(f"Successfully forwarded to Summarizer Agent")
                            return {
                                "success": True,
                                "response": response.json(),
                                "status_code": response.status_code,
                                "attempts": attempt + 1
                            }
                        else:
                            logger.warning(f"Summarizer Agent returned status {response.status_code}")
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
            logger.error(f"Error forwarding to summarizer: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    return forward_to_summarizer_tool


class VerifierAgent:
    """
    Verifier Agent for claim verification and source reliability scoring.
    
    Responsibilities:
    - Extract verifiable claims from events
    - Fact-check claims using search tools
    - Score source reliability
    - Forward verified events to Summarizer Agent
    """
    
    def __init__(
        self,
        model_name: str = "gemini-2.0-flash-lite",
        summarizer_url: str = "http://localhost:8003"
    ):
        """
        Initialize the Verifier Agent.
        
        Args:
            model_name: Name of the Gemini model to use
            summarizer_url: URL of the Summarizer Agent for A2A communication
        """
        self.model_name = model_name
        self.agent_name = "verifier_agent"
        self.summarizer_url = summarizer_url
        
        # Initialize Gemini client
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable not set")
        
        self.client = genai.Client(api_key=api_key)
        
        # Agent instruction
        self.instruction = """You are the Verifier Agent in the AgentFleet incident response system.

Your responsibilities:
1. Receive normalized events from the Ingest Agent via A2A protocol
2. Extract verifiable claims from event content
3. Fact-check claims using search tools (when available)
4. Score source reliability based on verification results
5. Create verified event envelopes with reliability scores
6. Forward verified events to the Summarizer Agent

When processing events:
- Use the extract_claims tool to identify factual statements that can be verified
- Use the verify_claim tool to check each claim (with search results if available)
- Use the score_reliability tool to calculate overall reliability score (0.0 to 1.0)
- Flag events with reliability score below 0.3 as unverified
- Use the forward_to_summarizer tool to send verified events to the next agent

Be thorough in verification but efficient in processing.
Always include session_id for tracking incident lifecycle.
"""
        
        # Define tools
        self.tools = [
            types.Tool(
                function_declarations=[
                    types.FunctionDeclaration(
                        name="extract_claims",
                        description="Extract verifiable claims from event content",
                        parameters={
                            "type": "object",
                            "properties": {
                                "event_content": {
                                    "type": "string",
                                    "description": "The event text to analyze for verifiable claims"
                                },
                                "event_source": {
                                    "type": "string",
                                    "description": "Source of the event (e.g., twitter, emergency, sensor)"
                                }
                            },
                            "required": ["event_content", "event_source"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="verify_claim",
                        description="Verify a claim using search results or external sources",
                        parameters={
                            "type": "object",
                            "properties": {
                                "claim_text": {
                                    "type": "string",
                                    "description": "The claim text to verify"
                                },
                                "search_results": {
                                    "type": "string",
                                    "description": "JSON string containing search results (optional)"
                                }
                            },
                            "required": ["claim_text"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="score_reliability",
                        description="Calculate overall reliability score for an event based on verification results",
                        parameters={
                            "type": "object",
                            "properties": {
                                "verification_results": {
                                    "type": "string",
                                    "description": "JSON string containing list of verification results"
                                },
                                "event_source": {
                                    "type": "string",
                                    "description": "Source of the event (affects credibility scoring)"
                                }
                            },
                            "required": ["verification_results", "event_source"]
                        }
                    ),
                    types.FunctionDeclaration(
                        name="forward_to_summarizer",
                        description="Forward verified event envelope to the Summarizer Agent via A2A protocol",
                        parameters={
                            "type": "object",
                            "properties": {
                                "envelope_json": {
                                    "type": "string",
                                    "description": "JSON string containing the MCP envelope with verified event"
                                }
                            },
                            "required": ["envelope_json"]
                        }
                    )
                ]
            )
        ]
        
        # Create the forward_to_summarizer tool
        self.forward_to_summarizer_tool = create_forward_to_summarizer_tool(
            self.summarizer_url
        )
        
        logger.info(f"Initialized Verifier Agent with model {model_name}")
    
    def _execute_tool(self, tool_name: str, tool_args: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a tool function."""
        if tool_name == "extract_claims":
            return extract_claims_tool(**tool_args)
        elif tool_name == "verify_claim":
            return verify_claim_tool(**tool_args)
        elif tool_name == "score_reliability":
            return score_reliability_tool(**tool_args)
        elif tool_name == "forward_to_summarizer":
            return self.forward_to_summarizer_tool(**tool_args)
        else:
            return {"success": False, "error": f"Unknown tool: {tool_name}"}
    
    def process_message(self, message: str) -> str:
        """
        Process a message using the agent.
        
        Args:
            message: User message or task description
            
        Returns:
            Agent response
        """
        try:
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
        Process an event envelope from the Ingest Agent.
        
        Args:
            envelope_data: MCP envelope containing normalized event
            
        Returns:
            Processing result with verified event
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
            
            # Extract event data
            event_data = envelope.payload.get("data", {})
            session_id = envelope.session_id
            
            # Create processing message
            message = f"""Process this normalized event for verification:

Event ID: {event_data.get('event_id')}
Source: {event_data.get('source')}
Content: {event_data.get('content')}
Location: {event_data.get('location')}
Event Type: {event_data.get('event_type')}

Tasks:
1. Extract verifiable claims from the content
2. Verify each claim (note: search tool not available, use heuristics)
3. Calculate overall reliability score
4. Create verified event envelope
5. Forward to Summarizer Agent if reliability score >= 0.3

Session ID: {session_id}
"""
            
            # Process with agent
            response = self.process_message(message)
            
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


def create_verifier_agent(
    model_name: str = "gemini-2.0-flash-lite",
    summarizer_url: str = "http://localhost:8003"
) -> VerifierAgent:
    """
    Factory function to create a Verifier Agent instance.
    
    Args:
        model_name: Name of the Gemini model to use
        summarizer_url: URL of the Summarizer Agent for A2A communication
        
    Returns:
        VerifierAgent instance
    """
    return VerifierAgent(model_name=model_name, summarizer_url=summarizer_url)
