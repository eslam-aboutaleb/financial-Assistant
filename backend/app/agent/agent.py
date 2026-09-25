from __future__ import annotations

"""
Core ADK Agent definition and runner for the OmniCare Assistant.

Configures the Google ADK LlmAgent with LiteLLM for model routing,
registers all tools, and provides the async run_agent() function
for the FastAPI endpoints to call.
"""

import logging
import os
import uuid
from typing import Any
from app.database import async_session_factory
from app.models.conversation import Conversation
from sqlalchemy import select
from sqlalchemy.orm.attributes import flag_modified
from datetime import datetime, UTC

from google.adk.agents import LlmAgent
from google.adk.models.lite_llm import LiteLlm
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types

from app.agent.context import current_user_id
from app.agent.prompts import SYSTEM_INSTRUCTION
from app.agent.tools.policy_rag import query_policy
from app.agent.tools.claim_status import get_claim_status
from app.agent.tools.submit_claim import submit_claim
from app.config import settings

logger = logging.getLogger(__name__)


def configure_llm() -> None:
    """
    Configure LiteLLM environment variables from centralized settings.

    This is called explicitly during application startup (lifespan)
    rather than at module import time to avoid side-effects and ensure
    configuration is applied in a controlled, testable manner.
    """
    if settings.openai_api_key:
        os.environ["OPENAI_API_KEY"] = settings.openai_api_key
        logger.info("OpenAI API key configured for LiteLLM routing")
    if settings.openai_api_base:
        os.environ["OPENAI_API_BASE"] = settings.openai_api_base


# --- Agent Configuration -------------------------------------------

# Create the ADK agent with LiteLLM model routing
# Note: LiteLLM reads OPENAI_API_KEY / OPENAI_API_BASE from environment,
# so configure_llm() must be called before first agent invocation.
omnicare_agent = LlmAgent(
    name="omnicare_assistant",
    model=LiteLlm(model=settings.llm_model),
    instruction=SYSTEM_INSTRUCTION,
    description=(
        "OmniCare Financial customer service assistant that handles "
        "policy questions, claim lookups, and claim submissions."
    ),
    tools=[query_policy, get_claim_status, submit_claim],
)

# --- Session & Runner Setup ----------------------------------------

# InMemorySessionService for conversation state (sufficient for prototype)
session_service = InMemorySessionService()

# Runner manages the agent execution lifecycle
runner = Runner(
    agent=omnicare_agent,
    app_name="omnicare_financial",
    session_service=session_service,
)

# Track active sessions per user.
# Bounded to MAX_SESSIONS to prevent unbounded memory growth in long-running
# processes. When the limit is reached, the oldest session is evicted (FIFO).
_MAX_SESSIONS = 500
_user_sessions: dict[str, str] = {}


async def _ensure_session(user_id: str) -> str:
    """Get or create a session for a given user, evicting the oldest if at capacity."""
    if user_id not in _user_sessions:
        # Evict oldest entry when at capacity (FIFO -- dict preserves insertion order)
        if len(_user_sessions) >= _MAX_SESSIONS:
            oldest_user = next(iter(_user_sessions))
            evicted_session_id = _user_sessions.pop(oldest_user)
            logger.info(
                "Session capacity reached (%d). Evicted session '%s' for user '%s'.",
                _MAX_SESSIONS,
                evicted_session_id,
                oldest_user,
            )
            # Clean up the session object from the InMemorySessionService to
            # prevent unbounded memory growth over long-running server uptime.
            try:
                await session_service.delete_session(
                    app_name="omnicare_financial",
                    session_id=evicted_session_id,
                )
                logger.debug(
                    "Deleted evicted session '%s' from session service.",
                    evicted_session_id,
                )
            except Exception:
                logger.warning(
                    "Failed to delete evicted session '%s' from session service.",
                    evicted_session_id,
                    exc_info=True,
                )

        session_id = f"session_{uuid.uuid4().hex[:12]}"
        await session_service.create_session(
            app_name="omnicare_financial",
            user_id=user_id,
            session_id=session_id,
        )
        _user_sessions[user_id] = session_id
        logger.debug("Created session '%s' for user '%s'.", session_id, user_id)

    return _user_sessions[user_id]


async def run_agent(user_id: str, message: str) -> dict[str, Any]:
    """
    Run the OmniCare agent with a user message and collect the response.

    Args:
        user_id: Unique user identifier for session management.
        message: The user's chat message.

    Returns:
        Dict with keys: response (str), sources (list), tool_calls (list)
    """
    session_id = await _ensure_session(user_id)

    # SECURE: Bind the authenticated user_id to the async context so tools can access it safely
    import uuid
    current_user_id.set(uuid.UUID(user_id))

    # Wrap user message in ADK Content format
    user_content = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )

    # Collect response data
    final_text_parts: list[str] = []
    sources: list[str] = []
    tool_calls: list[dict] = []

    # Run the agent and iterate through events
    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_content,
    ):
        # Collect function call events (tool invocations)
        function_calls = event.get_function_calls()
        if function_calls:
            for fc in function_calls:
                tool_call_info = {
                    "name": fc.name if hasattr(fc, "name") else str(fc),
                    "arguments": fc.args if hasattr(fc, "args") else {},
                }
                tool_calls.append(tool_call_info)

        # Collect function response events (tool results)
        function_responses = event.get_function_responses()
        if function_responses:
            for fr in function_responses:
                result = fr.response if hasattr(fr, "response") else {}
                # Extract sources from RAG tool results
                if isinstance(result, dict) and "sources" in result:
                    for src in result["sources"]:
                        if isinstance(src, dict):
                            section = src.get("section", "")
                            source_file = src.get("source", "")
                            sources.append(f"{section} ({source_file})")
                        elif isinstance(src, str):
                            sources.append(src)

                # Extract claim citations from claim tool results
                if isinstance(result, dict) and "citation" in result:
                    sources.append(result["citation"])

                # Attach result to the most recent matching tool call
                for tc in reversed(tool_calls):
                    if tc.get("name") == (fr.name if hasattr(fr, "name") else ""):
                        tc["result"] = result
                        break

        # Collect final text response
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_text_parts.append(part.text)

    response_text = (
        "\n".join(final_text_parts)
        if final_text_parts
        else "I'm sorry, I couldn't generate a response. Please try again."
    )

    # Save to database continuously for absolute data durability
    try:
        async with async_session_factory() as db_session:
            conv = (
                await db_session.execute(
                    select(Conversation).where(
                        Conversation.session_id == session_id
                    )
                )
            ).scalar_one_or_none()

            new_msgs = [
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": message,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "sources": sources,
                    "tool_calls": tool_calls,
                },
            ]

            if conv is None:
                title = message[:40] + ("..." if len(message) > 40 else "")
                conv = Conversation(
                    user_id=uuid.UUID(user_id),
                    session_id=session_id,
                    title=title,
                    messages=new_msgs,
                )
                db_session.add(conv)
            else:
                conv.messages.extend(new_msgs)
                flag_modified(conv, "messages")

            await db_session.commit()
    except Exception as e:
        logger.error(
            "Failed to auto-save conversation to DB: %s", e, exc_info=True
        )

    return {
        "response": response_text,
        "sources": sources,
        "tool_calls": tool_calls,
    }


def reset_user_session(user_id: str) -> None:
    """Clear the session for a user (e.g., for 'New Chat')."""
    _user_sessions.pop(user_id, None)


from collections.abc import AsyncGenerator
from google.adk.agents.run_config import RunConfig, StreamingMode

async def run_agent_stream(user_id: str, message: str) -> AsyncGenerator[str, None]:
    session_id = await _ensure_session(user_id)

    # SECURE: Bind the authenticated user_id to the async context so tools can access it safely
    import uuid
    current_user_id.set(uuid.UUID(user_id))

    # Wrap user message in ADK Content format
    user_content = types.Content(
        role="user",
        parts=[types.Part(text=message)],
    )

    # We collect the full response to save to the DB at the end
    final_text_parts: list[str] = []
    sources: list[str] = []
    tool_calls: list[dict] = []

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=user_content,
        run_config=RunConfig(streaming_mode=StreamingMode.SSE),
    ):
        if event.is_final_response() and event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    final_text_parts.append(part.text)

        # Collect function call events (tool invocations)
        function_calls = event.get_function_calls()
        if function_calls:
            for fc in function_calls:
                tool_call_info = {
                    "name": fc.name if hasattr(fc, "name") else str(fc),
                    "arguments": fc.args if hasattr(fc, "args") else {},
                }
                tool_calls.append(tool_call_info)

        # Collect function response events (tool results)
        function_responses = event.get_function_responses()
        if function_responses:
            for fr in function_responses:
                result = fr.response if hasattr(fr, "response") else {}
                if isinstance(result, dict) and "sources" in result:
                    for src in result["sources"]:
                        if isinstance(src, dict):
                            section = src.get("section", "")
                            source_file = src.get("source", "")
                            sources.append(f"{section} ({source_file})")
                        elif isinstance(src, str):
                            sources.append(src)

                if isinstance(result, dict) and "citation" in result:
                    sources.append(result["citation"])

                for tc in reversed(tool_calls):
                    if tc.get("name") == (fr.name if hasattr(fr, "name") else ""):
                        tc["result"] = result
                        break

        # Yield ADK's built-in formatted SSE JSON string
        sse_event = event.model_dump_json(exclude_none=True, by_alias=True)
        yield f"data: {sse_event}\n\n"

    response_text = (
        "\n".join(final_text_parts)
        if final_text_parts
        else "I'm sorry, I couldn't generate a response."
    )

    # Save to database
    try:
        async with async_session_factory() as db_session:
            conv = (
                await db_session.execute(
                    select(Conversation).where(
                        Conversation.session_id == session_id
                    )
                )
            ).scalar_one_or_none()
            new_msgs = [
                {
                    "id": str(uuid.uuid4()),
                    "role": "user",
                    "content": message,
                    "timestamp": datetime.now(UTC).isoformat(),
                },
                {
                    "id": str(uuid.uuid4()),
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": datetime.now(UTC).isoformat(),
                    "sources": sources,
                    "tool_calls": tool_calls,
                },
            ]

            if conv is None:
                title = message[:40] + ("..." if len(message) > 40 else "")
                conv = Conversation(
                    user_id=uuid.UUID(user_id),
                    session_id=session_id,
                    title=title,
                    messages=new_msgs,
                )
                db_session.add(conv)
            else:
                conv.messages.extend(new_msgs)
                flag_modified(conv, "messages")

            await db_session.commit()
    except Exception as e:
        logger.error(
            "Failed to auto-save conversation to DB: %s", e, exc_info=True
        )
