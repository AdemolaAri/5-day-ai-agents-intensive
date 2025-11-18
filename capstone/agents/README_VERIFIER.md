# Verifier Agent

The Verifier Agent is the second agent in the AgentFleet incident response pipeline. It receives normalized events from the Ingest Agent, extracts verifiable claims, fact-checks them, and scores source reliability before forwarding to the Summarizer Agent.

## Architecture

### Agent Configuration
- **Model**: `gemini-2.0-flash-lite` (fast, cost-effective)
- **Port**: 8002
- **Upstream**: Ingest Agent (port 8001)
- **Downstream**: Summarizer Agent (port 8003)

### Tools
1. **extract_claims**: Identifies verifiable factual statements from event content
2. **verify_claim**: Validates claims using search results or heuristics
3. **score_reliability**: Calculates overall reliability score (0.0 to 1.0)
4. **forward_to_summarizer**: Sends verified events to Summarizer Agent via A2A

## Requirements Satisfied

### Requirement 2.1: Claim Extraction
- Extracts verifiable claims from event content
- Identifies factual assertions, named entities, and causal relationships
- Returns structured claim objects with source attribution

### Requirement 2.2: Claim Verification
- Validates claims using search tools (when available)
- Falls back to heuristic verification when search unavailable
- Assigns confidence scores (0.0 to 1.0) to each claim

### Requirement 2.3: Reliability Scoring
- Aggregates claim verification results
- Calculates overall reliability score between 0.0 and 1.0
- Considers source credibility in scoring

### Requirement 2.4: Unverified Event Flagging
- Flags events with reliability score < 0.3 as unverified
- Logs reason for low reliability
- Still forwards to next agent for transparency

### Requirement 2.5: A2A Forwarding
- Forwards verified events to Summarizer Agent via A2A protocol
- Includes retry logic with exponential backoff
- Maintains session context through pipeline

### Requirements 6.1-6.5: A2A Protocol
- Exposes agent card at `/.well-known/agent-card.json`
- Accepts A2A requests at `/tasks` endpoint
- Validates MCP envelope schema before processing
- Returns A2A response envelopes with status and result
- Implements retry logic with exponential backoff (3 attempts, 1s initial delay)

## MCP Envelope Flow

### Input Envelope (from Ingest Agent)
```json
{
  "schema": "event_v1",
  "session_id": "uuid",
  "timestamp": "ISO8601",
  "source_agent": "ingest_agent",
  "payload": {
    "type": "event",
    "data": {
      "event_id": "uuid",
      "source": "twitter|emergency|sensor",
      "content": "event text",
      "entities": ["entity1", "entity2"],
      "location": "location string",
      "event_type": "flooding|fire|etc"
    }
  }
}
```

### Output Envelope (to Summarizer Agent)
```json
{
  "schema": "verified_event_v1",
  "session_id": "uuid",
  "timestamp": "ISO8601",
  "source_agent": "verifier_agent",
  "payload": {
    "type": "verified_event",
    "data": {
      "event_id": "uuid",
      "reliability_score": 0.85,
      "verified_claims": [
        {
          "claim": {"text": "claim text", "source": "source"},
          "verified": true,
          "confidence": 0.9,
          "sources": ["url1", "url2"]
        }
      ],
      "verification_timestamp": "ISO8601"
    }
  }
}
```

## Running the Agent

### As a Standalone Server
```bash
# Set environment variables
export GOOGLE_API_KEY="your-api-key"
export SUMMARIZER_URL="http://localhost:8003"

# Run the server
python capstone/agents/verifier_server.py
```

The server will start on port 8002 and expose:
- Agent card: `http://localhost:8002/.well-known/agent-card.json`
- Task endpoint: `http://localhost:8002/tasks`
- Health check: `http://localhost:8002/health`
- Metrics: `http://localhost:8002/metrics`

### As Part of AgentFleet
```bash
# Start all agents
python start_agents.py
```

## Testing

### Unit Tests
```bash
PYTHONPATH=. python capstone/tests/test_verifier_agent.py
```

Tests:
- Claim extraction from event content
- Claim verification logic
- Reliability scoring calculation
- MCP envelope processing

### Integration Tests
```bash
PYTHONPATH=. python capstone/tests/test_verifier_integration.py
```

Tests:
- End-to-end envelope processing
- Complete verification workflow
- A2A communication patterns

## Verification Logic

### Claim Extraction
Claims are extracted based on:
- Factual indicators (reported, confirmed, occurred, etc.)
- Numeric data (counts, measurements)
- Named entities (locations, organizations)
- Causal relationships

### Verification Scoring
Confidence scores are calculated based on:
- Number of corroborating sources (more sources = higher confidence)
- Source credibility (official sources weighted higher)
- Consistency of information across sources
- Recency of verification data

### Reliability Calculation
Overall reliability score formula:
```
reliability = (verification_rate * 0.6 + avg_confidence * 0.4) * source_multiplier

where:
- verification_rate = verified_claims / total_claims
- avg_confidence = average of all claim confidence scores
- source_multiplier = 1.1 for official sources, 0.9 for social media
```

## Error Handling

### A2A Communication Errors
- Retry up to 3 times with exponential backoff
- Initial delay: 1.0 seconds
- Backoff multiplier: 2.0
- Max delay: 10.0 seconds
- Graceful degradation on failure

### Tool Invocation Errors
- Log errors with full context
- Continue processing with reduced confidence
- Return partial results when possible

### Envelope Validation Errors
- Return HTTP 400 with error details
- Log validation failures
- Reject malformed envelopes

## Observability

### Logging
- Structured logs with agent name, operation, and session_id
- Tool invocation logging with inputs/outputs
- Error logging with stack traces

### Metrics
- `agent_requests_total`: Total A2A requests received
- `agent_request_duration_seconds`: Request processing latency
- `agent_errors_total`: Total errors encountered
- `tool_invocations_total`: Total tool calls made

## Future Enhancements

1. **Google Search Integration**: Connect to actual search API for real fact-checking
2. **Advanced NLP**: Use more sophisticated claim extraction with entity recognition
3. **Source Credibility Database**: Maintain database of known reliable/unreliable sources
4. **Caching**: Cache verification results for repeated claims
5. **Batch Processing**: Process multiple events in parallel for better throughput

## Dependencies

- `google-genai`: Gemini API client
- `fastapi`: Web framework for A2A endpoints
- `uvicorn`: ASGI server
- `httpx`: HTTP client for A2A communication
- `pydantic`: Data validation

## Related Files

- `capstone/agents/verifier_agent.py`: Agent implementation
- `capstone/agents/verifier_server.py`: A2A server
- `capstone/models.py`: Data models (Claim, VerificationResult, VerifiedEvent)
- `capstone/mcp_envelope.py`: MCP envelope utilities
- `capstone/tests/test_verifier_agent.py`: Unit tests
- `capstone/tests/test_verifier_integration.py`: Integration tests
