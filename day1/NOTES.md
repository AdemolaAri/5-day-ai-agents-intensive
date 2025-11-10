# Day 1 Notes — 5-Day AI Agents Intensive

**Date:** November 9, 2025  
**Topic:** Introduction to Agents

---

## 💭 My Takeaways

Today was my first dive into Google's **Agent Development Kit (ADK)**, and I have to say — it feels refreshingly smooth compared to the typical LangChain setup I’ve used before. The framework hides a lot of the orchestration details, which makes it feel “ready for production” even though we’re still early in the learning curve.

The codelab walked through creating a basic agent powered by **Gemini**, with the ability to use **Google Search** as a tool. I liked that everything connected cleanly — no manual graph wiring or chain setup. The built-in **chat-style interface** also made testing much faster.

---

## ⚙️ What I Built

I decided to go beyond the example in the notebook and create my own small agent project:  
**The Research Assistant Agent.**

It takes a topic, runs a live Google Search, and summarizes the latest information into a short brief.  
A simple but fun start — and it shows how ADK can combine reasoning (Gemini) with real-time context (Search).

---

## 🧠 Reflections

- ADK’s abstraction is both its strength and something I want to understand better under the hood.
- The concept of **Agent Ops** from the whitepaper stood out — especially reliability, identity, and constrained policies. It’s clear Google is thinking ahead about governance and real-world deployment.
- The whitepaper and podcast together painted a good mental model for where agent frameworks are heading: interoperable, governed, and composable systems.

---

## 🔍 Next Curiosity

- How flexible is ADK when I want to customize agent communication or routing logic?
- How will Agent Ops look in practice — monitoring, versioning, etc.?
- Can I integrate my own APIs or tools into the agent graph later this week?

---

## 🚀 Mood

Excited. The framework feels polished and purposeful. I can already see use cases forming for research workflows, developer assistants, and automation tools.

Tomorrow, I’m expecting the complexity to ramp up — hopefully diving deeper into multi-agent coordination and agent policies.

---

## 📸 Demo

![ADK Web UI demo](./demo/adk-web-ui-demo.gif)

[Open demo/adk-web-ui-demo.gif](./demo/adk-web-ui-demo.gif)

---

