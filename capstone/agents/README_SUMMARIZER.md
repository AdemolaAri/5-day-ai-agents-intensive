# Summarizer Agent

The Summarizer Agent is responsible for generating concise incident briefs from verified events, integrating with the Memory Bank for pattern recognition, and managing session context throughout the incident lifecycle.

## Overview

The Summarizer Agent receives verified events from the Verifier Agent via A2A protocol, generates concise summaries (max 200 words), extracts key facts, queries historical incidents from the Memory Bank, and forwards incident briefs to the Triage Agent.

## Features

### Core Capabilities

1. **Incident Summarization**
   - Generates concise summaries with maximum 200-word limit
   - Includes key facts: location, time, affected entities, impact
   - Maintains clarity and actionability for human operators

2. **Key Fact Extraction**
   - Extracts structured information from event data
   - Identifies numbers, measurements, and impact indicators
   - Captures location, event type, and reliability scores

3. **Memory Bank Integration**
   - Queries for similar historical incidents
   - Includes pattern information in incident briefs
   - Supports similarity search with configurable thresholds
   - 500ms query timeout for performance

4. **Session Management**
   - Creates unique session IDs for incident lifecycle tracking
   - Maintains session context for related events
   - Propagates session_id through all MCP envelopes
   - Tracks event history within sessions

5. **A2A Communication**
   - Exposes agent via A2A protocol on port 8003
   - Validates MCP envelope schemas before processing
   - Implements retry logic with exponential backoff
   - Forwards incident briefs to Triage Agent

## Architecture

### Agent Configuration

- **Model**: `gemini-2.0-flash-lite` (fast, cost-effective)
- **Port**: 8003
- **Tools**: 
  - `generate_summary` - Creates concise summaries
  - `extract_key_facts` - Extracts structured data
  - `query_memory_bank` - Searches historical incidents
  - `forward_to_triage` - Sends briefs to Triage Agent

### Input Schema

Receives MCP envelopes with schema `verified_event_v1`:

```json
{
  "schema": "verified_event_v1",
  "session_id": "uuid",
  "timestamp": "ISO8601",
  "source_agent": "verifier_agent",
  "payload": {
    "type": "event",
    "data": {
      "event_id": "uuid",
      "original_event": { ... },
      "reliability_score": 0.85,
      "verified_claims": [ ... ]
    }
  }
}
```

### Output Schema

Produces MCP envelopes with schema `incident_brief_v1`:

```json
{
  "schema": "incident_brief_v1",
  "session_id": "uuid",
  "timestamp": "ISO8601",
  "source_agent": "summarizer_agent",
  "payload": {
    "type": "incident",
    "data": {
      "incident_id": "uuid",
      "summary": "Concise summary (max 200 words)",
      "key_facts": ["fact1", "fact2"],
      "location": "Downtown District",
      "affected_entities": ["entity1"],
      "similar_incidents": [
        {
          "incident_id": "uuid",
          "similarity_score": 0.92,
          "summary": "..."
        }
      ]
    }
  }
}
```

## Usage

### Starting the Agent Server

```bash
# Set environment variables
export GOOGLE_API_KEY="your-api-key"
export TRIAGE_AGENT_URL="http://localhost:8004"

# Start the server
python capstone/agents/summarizer_server.py
```

The server will start on `http://localhost:8003` with the following endpoints:

- `/.well-known/agent-card.json` - Agent card describing capabilities
- `/tasks` - A2A task processing endpoint
- `/health` - Health check endpoint
- `/` - Root endpoint with agent information

### Using the Agent Programmatically

```python
from capstone.agents.summarizer_agent import create_summarizer_agent
from capstone.mcp_envelope import create_envelope, EnvelopeSchema, PayloadType

# Create agent instance
agent = create_summarizer_agent(
    model_name="gemini-2.0-flash-lite",
    triage_url="http://localhost:8004"
)

# Create a verified event envelope
verified_event_data = {
    "event_id": "evt_123",
    "original_event": {
        "event_id": "evt_123",
        "source": "twitter",
        "content": "Major flooding in downtown area",
        "location": "Downtown District",
        "event_type": "flooding"
    },
    "reliability_score": 0.85,
    "verified_claims": []
}

envelope = create_envelope(
    schema=EnvelopeSchema.VERIFIED_EVENT_V1.value,
    source_agent="verifier_agent",
    payload={
        "type": PayloadType.EVENT.value,
        "data": verified_event_data
    }
)

# Process the envelope
result = agent.process_event_envelope(envelope.to_dict())

if result["success"]:
    print(f"Incident brief created for session: {result['session_id']}")
```

### Using Individual Tools

```python
from capstone.agents.summarizer_agent import (
    generate_summary_tool,
    extract_key_facts_tool
)
from capstone.tools.memory_tools import query_memory_bank

# Generate summary
summary_result = generate_summary_tool(
    event_content="Major flooding reported in downtown area",
    event_location="Downtown District",
    event_type="flooding",
    reliability_score=0.85,
    max_words=200
)

print(f"Summary: {summary_result['summary']}")
print(f"Word count: {summary_result['word_count']}")

# Extract key facts
facts_result = extract_key_facts_tool(
    event_content="Flooding with 50 people evacuated",
    event_data='{"location": "Downtown", "event_type": "flooding"}'
)

print(f"Key facts: {facts_result['key_facts']}")

# Query Memory Bank
memory_result = query_memory_bank(
    query_text="flooding in downtown area",
    top_k=5,
    min_similarity=0.5
)

print(f"Found {memory_result['count']} similar incidents")
```

## Session Management

The Summarizer Agent maintains session context for incident lifecycle tracking:

```python
# Sessions are automatically created when processing envelopes
result = agent.process_event_envelope(envelope_data)
session_id = result["session_id"]

# Session context includes:
# - created_at: Session creation timestamp
# - last_activity: Last update timestamp
# - events: List of events in this session
# - context: Additional session-specific data

# Access session data
session = agent.active_sessions[session_id]
print(f"Events in session: {len(session['events'])}")
```

## Memory Bank Integration

The agent queries the Memory Bank for similar historical incidents:

```python
from capstone.tools.memory_tools import query_memory_bank, store_incident_memory

# Query for similar incidents
similar = query_memory_bank(
    query_text="flooding in downtown area",
    top_k=5,
    min_similarity=0.5
)

# Results include similarity scores and incident details
for incident in similar["results"]:
    print(f"Incident {incident['incident_id']}: {incident['similarity_score']}")
    print(f"  Summary: {incident['summary']}")
    print(f"  Severity: {incident['severity']}")

# Store incident in Memory Bank (typically done by Dispatcher Agent)
store_incident_memory(
    incident_id="inc_123",
    summary="Major flooding in downtown area",
    severity="HIGH",
    location="Downtown District"
)
```

## Error Handling

The agent implements comprehensive error handling:

1. **Envelope Validation**: Invalid envelopes are rejected with error messages
2. **Tool Failures**: Tool errors are logged and returned in results
3. **A2A Retry Logic**: Failed forwards retry with exponential backoff (max 3 attempts)
4. **Session Management**: Missing sessions are automatically created

## Requirements Satisfied

- **3.1**: Generate brief summary not exceeding 200 words
- **3.2**: Include key facts, location, time, and affected entities
- **3.3**: Structure output as MCP envelope with schema type "incident_brief_v1"
- **3.4**: Forward incident brief to Triage Agent via A2A protocol
- **3.5**: Maintain session context to correlate related events
- **8.2**: Query Memory Bank for similar historical incidents
- **8.3**: Include pattern information in incident brief
- **9.1**: Create unique session identifier for incident lifecycle
- **9.2**: Include session identifier in all message envelopes
- **9.3**: Access session-specific context and history

## Testing

Run the test suite:

```bash
python -m pytest capstone/tests/test_summarizer_agent.py -v
```

Test coverage includes:
- Summary generation with word limits
- Key fact extraction
- Session management
- Envelope processing
- Error handling

## Monitoring

The agent provides health check and metrics:

```bash
# Health check
curl http://localhost:8003/health

# Response:
{
  "status": "healthy",
  "agent": "summarizer_agent",
  "model": "gemini-2.0-flash-lite",
  "active_sessions": 5,
  "triage_url": "http://localhost:8004"
}
```

## Integration with AgentFleet Pipeline

The Summarizer Agent is the third agent in the incident response pipeline:

```
Ingest Agent → Verifier Agent → Summarizer Agent → Triage Agent → Dispatcher Agent
```

1. Receives verified events from Verifier Agent (port 8002)
2. Generates incident briefs with memory integration
3. Forwards briefs to Triage Agent (port 8004)

## Configuration

Environment variables:

- `GOOGLE_API_KEY` - Required for Gemini API access
- `TRIAGE_AGENT_URL` - URL of Triage Agent (default: http://localhost:8004)
- `SUMMARIZER_HOST` - Host to bind to (default: 0.0.0.0)
- `SUMMARIZER_PORT` - Port to listen on (default: 8003)

## Performance

- Summary generation: < 1 second
- Memory Bank query: < 500ms (with timeout)
- End-to-end processing: < 2 seconds (p95)
- Concurrent sessions: Unlimited (memory-bound)

## Future Enhancements

- Advanced NLP for better summarization
- Multi-language support
- Configurable summary length
- Session archival and restoration
- Enhanced pattern recognition
- Real-time dashboard integration
