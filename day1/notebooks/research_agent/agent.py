from google.adk.agents.llm_agent import Agent
from google.adk.tools import google_search

root_agent = Agent(
    name="ResearchAssistant",
    model="gemini-2.5-flash-lite",
    description="Fetches and summarizes latest info on a given topic.",
    instruction="You are a research assistant. Given a particular topic, use Google Search for current info and summarize the search results into a concise 4-bullet brief.",
    tools=[google_search],
)
