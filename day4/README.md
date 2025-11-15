# Day 4 Notes — 5-Day AI Agents Intensive**

**Date:** November 12, 2025  
**Unit:** Agent Quality     
**Artifacts:** [Notebooks & Whitepater](#links--references)


Today’s unit was all about *quality* — not just getting an agent to “work,” but understanding why it behaves the way it does, how to debug failures, and how to evaluate whether an agent meets the expectations of a production-grade system.

---

## What I Learned Today

### **1. Quality ≠ Accuracy (It’s a System-Level Property)**
The whitepaper reframes quality as a holistic loop:
- **Instrumentation** → Log everything that matters  
- **Observability** → Build the visibility  
- **Evaluation** → Score behavior  
- **Improvement** → Iterate  

It’s a virtuous cycle. Agents don’t magically get better — you build the *feedback loops* that make them improve.

---

## Logs, 🧵 Traces, 📊 Metrics  
The three pillars of observability.

### ** Logs — “What happened?”**  
Your agent’s running diary.  
Used to capture: tool calls, errors, decisions, intermediate thoughts (when available), fallbacks.

### ** Traces — “Why did it happen?”**  
A narrative of cause → effect.  
This makes complex agent chains debuggable.

### ** Metrics — “How healthy is the system?”**  
Quantified signals like:
- tool success rate  
- latency  
- error frequency  
- fallback usage  
- hallucination rate  

In real production systems, metrics are often the first warning something is wrong.

---

## LLM-as-a-Judge & HITL Evaluation  
Two complementary ways to score agent quality.

### **LLM-a-Judge**
Use a model to “grade” your agent’s output using:
- rubrics  
- constraints  
- scenario grading  
- safety checks  
- tool correctness  

The key: **build objective rubrics**, not subjective “does this look good?”

### **HITL (Human in the Loop)**
For nuanced, high-impact, or safety-critical tasks.
Humans validate the agent’s logic or tool decision-making.

Most real systems use *both*.

---

## Codelabs Takeaways

### **Codelab 1 — Observability**
You instrument an agent with:  
- structured logs  
- tool-level logs  
- simple metrics  
- step-by-step tracing  

Then use them to debug why the agent used a wrong tool or produced a bad output.

### **Codelab 2 — Evaluation**
You implement a quality-scoring evaluator:
- accuracy score  
- adherence to instructions  
- tool usage correctness  
- explanation quality  
- safety violations  

This felt like building the “QA automation” layer of an LLM workflow.

---

## Final Thoughts
Today wasn’t about building “cooler” agents — it was about learning how **real production agent systems are maintained, debugged, and measured**.

This is the difference between:
> “It works on my machine”  

and  

> “It is reliable, observable, and safe in production.”

---

## Links & references
- Notebooks: 
    - [1-agent-observability.ipynb](./notebooks/1-agent-observability.ipynb)
- Whitepaper 
    - [Agent Quality](https://www.kaggle.com/whitepaper-agent-quality)

---

