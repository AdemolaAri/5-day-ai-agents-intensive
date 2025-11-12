# Day 2 Notes — 5-Day AI Agents Intensive

**Date:** November 10, 2025  
**Unit:** Agent Tools & Interoperability with Model Context Protocol (MCP)  
**Artifacts:** `day-2a-agent-tools.ipynb`, `day-2b-agent-tools-best-practices.ipynb`

---

## TL;DR
Day 2 focused on extending agent capabilities with **tools**, standardizing tool interactions with **Model Context Protocol (MCP)**, and handling **long-running operations**. The codelabs illustrated how to attach tools (search, API callers, scrapers, timers), design well-scoped tool contracts, and use MCP to make tool outputs and agent context interoperable across models and agents.

---

## Key learnings

### 1. Tools are first-class capabilities
- Tools are explicit connectors that let agents do *work* (search, call APIs, run code, fetch files, schedule tasks).
- Good tools are small, well-defined, and return deterministic structures where possible (JSON, typed objects).
- Tools reduce hallucination risk when agents can rely on authoritative APIs instead of inventing facts.

### 2. Model Context Protocol (MCP)
- MCP standardizes how tools and models exchange structured context (metadata, payloads, tool schema).
- Using MCP makes tool outputs machine-readable and safer to chain between agents and models.
- With MCP, agents can attach typed tool results to conversation state so other agents (or the same agent later) can interpret them reliably.

### 3. Long-running operations & best practices
- Not every tool finishes instantly. Long-running ops (web crawls, heavy API analysis, external jobs) require:
  - **Async orchestration**: spawn tasks and return a job id / callback URL.
  - **Polling or webhooks**: agent polls or listens for callbacks when job finishes.
  - **Stateful persistence**: store job state with IDs so other agents can pick up results.
- Use optimistic UX: reply to the user acknowledging the job was started, then send the final result when ready.

### 4. Tool security & policy constraints
- Limit tool abilities via scoped credentials and least privilege.
- Validate tool outputs and sanitize them before passing to models / other agents.
- Instrument audit logs (who called what tool, when, with what input).

---

## What I actually built / experimented with (notes)
- Downloaded the two codelabs to work locally:
  - `day-2a-agent-tools.ipynb` — basic tool attachment (Google Search, simple HTTP tool).
  - `day-2b-agent-tools-best-practices.ipynb` — MCP examples and long-running operation patterns.
- Replaced Kaggle secrets with `.env` pattern for local runs (see repo `.env.example`).
- Implemented minimal MCP-like wrapper for a tool result (simple JSON envelope) to ensure tool outputs are normalized across agents.
- Built a quick demo showing:
  - `search_tool.search("topic")` returns structured results (title, snippet, url)
  - agent attaches `mcp_envelope = {"tool": "search", "schema": "search_v1", "payload": [...]}`
  - next agent (summarizer) uses that envelope to produce a structured brief

---

## Example patterns & snippets

### Basic tool wrapper (python pseudocode)
```python
# tool_contract.py
def search_tool(query: str) -> dict:
    """Return MCP-compliant search output."""
    results = google_search_api.search(query)  # returns list of dicts
    return {
        "tool": "google_search",
        "schema": "search_v1",
        "payload": [
            {"title": r["title"], "snippet": r["snippet"], "url": r["link"]}
            for r in results
        ],
        "meta": {"queried_at": now_iso(), "query": query}
    }
```

### Agent usage (pseudocode)
```python
# agent.py
search_output = search_tool("AI agent frameworks 2025")
# store as context
agent_context.add(search_output)
# pass to model with a prompt that expects MCP
prompt = f"""
You have a search payload in MCP format:
{json.dumps(search_output, indent=2)}
Please summarize into 4 bullet points.
"""
summary = model.complete(prompt)
```

### Long-running job pattern (job + callback)
```python
# start_job returns job_id, immediately returns to user
job_id = start_heavy_analysis(urls)
reply("Analysis started. Job id: " + job_id)

# background worker/cron or webhook completes job and writes result
# save result to persistent store (DB or object store)
# optionally notify user/channel via webhook or callback
```

---

## Current Reflections
- MCP and tool contracts are the missing “interface” layer for discoverable, interoperable agent systems — treating tools like typed RPCs reduces brittleness and debugging friction.
- Agent Ops elements (audit logs, scoped credentials, observability of long-running ops) are going to be the differentiation in production systems.
- I’m thinking about building a small demo that highlights:
  - MCP envelope exchange between 2 agents
  - a long-running job (e.g., site-wide crawl) with webhook + final summary
  - UI showing job status & agent logs

---

## To-do / follow-ups
- [ ] Harden tool wrappers (input validation & output schema tests)
- [ ] Add a persistence layer (sqlite / small Redis instance) for long-running job state
- [ ] Add metrics/tracing hooks so Agent Ops can show call counts and latencies
- [ ] Build the Day 2 project demo and export GIFs (start/poll/complete flow)

---

## Links & references
- Notebooks: 
    - [agent-tools.ipynb](./notebooks/agent-tools.ipynb)
- Whitepaper / MCP 
    - ["Agent Tools & Interoperability with MCP" whitepaper](https://www.kaggle.com/whitepaper-agent-tools-and-interoperability-with-mcp)
