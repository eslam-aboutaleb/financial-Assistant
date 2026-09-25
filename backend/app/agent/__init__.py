"""
Agent package for the InsureAssist backend.

Contains the Google ADK agent definition, system prompts, agent tools,
and conversation persistence helpers. The agent layer is intentionally
framework-agnostic and does not import the database directly.
"""

from app.agent.agent import insureassist_agent, runner, run_agent, run_agent_stream

__all__ = ["insureassist_agent", "runner", "run_agent", "run_agent_stream"]
