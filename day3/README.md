# Day 3 Notes — 5-Day AI Agents Intensive

**Date:** November 11, 2025  
**Unit:** Context Engineering: Sessions & Memory
**Artifacts:** [Notebooks & Whitepater](#links--references)

---

##  What I Learned

Today’s focus was on context engineering — how to manage what an agent remembers across turns, tasks, or even sessions.
While stateless agents can be powerful, stateful ones feel more “human”—they build continuity and awareness over time.

Key concepts explored:

- Sessions: Keeping a consistent thread of interaction so the agent knows what’s been discussed.

- Memory: Storing and recalling relevant information to make the agent contextually aware.

- Vector stores: Using embeddings to retrieve related facts from previous interactions.

- Context windowing: Avoiding overload by selecting what to remember, and what to forget.

- Design trade-offs: More memory improves continuity but adds complexity in retrieval and privacy.

## What I Built

Using the two Kaggle labs:

- Agent Sessions: Built an agent that keeps a running session context so it can recall earlier queries.

- Agent Memory: Implemented short-term and long-term memory layers using embeddings and persistent context stores.

Together, they form the foundation for “learning agents” — systems that improve or adapt as they interact.

## Personal Reflection

This unit clicked for me because it bridges two worlds — LLMs as chatbots and LLMs as autonomous collaborators.

I realized that good context engineering is more than adding memory — it’s teaching your agent to forget wisely.

I also started seeing parallels with how I design state management in frontend work (Angular + signals): what state belongs locally (session) vs globally (memory). The same architecture thinking applies here — just with language and embeddings.

## Project Idea

“Project Recall” — a personalized research companion

- Builds on your previous “single-agent” base.
- Adds:
    - Session persistence (using a lightweight JSON or SQLite store).
    - Memory retrieval (embedding-based similarity search).
    - A context summarizer to condense prior sessions.
- The agent helps you remember facts, summarize past chats, and build continuity over time — like an evolving notebook that remembers you.

## Links & references
- Notebooks: 
    - [agent-sessions.ipynb](./notebooks/1-agent-sessions.ipynb)
    - [agent-memory.ipynb](./notebooks/2-agent-memory.ipynb)
- Whitepaper / MCP 
    - [Context Engineering: Sessions & Memory](https://www.kaggle.com/whitepaper-context-engineering-sessions-and-memory)