"""
Deterministic ADK model double used by the Tier A golden contract tests.

The double subclasses ``google.adk.models.base_llm.BaseLlm`` and is injected into the
real ``LlmAgent`` that ``app.agent.agent`` builds, so the real ``Runner`` still drives
tool dispatch, session creation, and event construction. Only the remote model call is
replaced.

Turn selection is derived from the request contents rather than a call counter:

  - If the last content already carries a ``function_response`` part, the agent has
    finished executing tools and the scripted final text is returned.
  - Otherwise the first scripted tool call is returned.

Deriving the turn from the conversation makes the double stateless, so a scenario can
be replayed any number of times, in any order, without drift.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any

from google.adk.models.base_llm import BaseLlm
from google.adk.models.llm_response import LlmResponse
from google.genai import types


@dataclass(frozen=True)
class ScriptedToolCall:
    """One tool invocation the scripted model will request.

    Attributes:
        name: Registered tool name, e.g. ``query_policy``.
        args: Arguments passed to the tool. Must be JSON-serialisable.
    """

    name: str
    args: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ScriptedTurn:
    """A complete scripted conversation.

    Attributes:
        tool_calls: Tool calls emitted on the first model turn. When empty the model
            answers with ``final_text`` straight away, without invoking a tool.
        final_text: Text emitted once every tool call has been answered.
    """

    tool_calls: tuple[ScriptedToolCall, ...] = ()
    final_text: str = ""


def _last_content_has_tool_result(llm_request: Any) -> bool:
    """Return True when the most recent content already contains a tool result."""
    contents = getattr(llm_request, "contents", None) or []
    if not contents:
        return False
    last = contents[-1]
    for part in getattr(last, "parts", None) or []:
        if getattr(part, "function_response", None) is not None:
            return True
    return False


class ScriptedLlm(BaseLlm):
    """A ``BaseLlm`` that replays a fixed ``ScriptedTurn`` deterministically.

    Attributes:
        turn: The scripted conversation this instance replays.
        calls: Every ``LlmRequest`` this double received, in order. Tests assert on
            ``calls`` to prove the real runner built a real request (system
            instruction, tool declarations, conversation history).
    """

    model: str = "scripted-double"
    turn: ScriptedTurn = ScriptedTurn()
    calls: list[Any] = field(default_factory=list)

    async def generate_content_async(  # noqa: ARG002
        self,
        llm_request: Any,
        stream: bool = False,  # noqa: ARG002, FBT001, FBT002
    ) -> AsyncGenerator[LlmResponse, None]:
        """Yield the scripted response for this turn.

        Args:
            llm_request: The request the ADK runner built. Recorded on ``calls``.
            stream: Accepted for interface compatibility and ignored; the scripted
                turn is emitted as a single complete response either way.

        Yields:
            LlmResponse: Exactly one response, carrying either the scripted tool calls
            or the scripted final text.
        """
        self.calls.append(llm_request)

        if self.turn.tool_calls and not _last_content_has_tool_result(llm_request):
            parts = [
                types.Part(function_call=types.FunctionCall(name=call.name, args=dict(call.args)))
                for call in self.turn.tool_calls
            ]
            yield LlmResponse(content=types.Content(role="model", parts=parts))
            return

        yield LlmResponse(
            content=types.Content(role="model", parts=[types.Part(text=self.turn.final_text)])
        )
