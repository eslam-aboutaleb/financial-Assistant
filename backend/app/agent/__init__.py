"""
Agent package for the OmniCare Financial backend.

Contains the Google ADK agent definition, system prompts, agent tools,
and conversation persistence helpers. The agent layer is intentionally
framework-agnostic and does not import the database directly.
"""

from app.agent.agent import omnicare_agent, run_agent, run_agent_stream, runner

__all__ = ["omnicare_agent", "runner", "run_agent", "run_agent_stream"]
