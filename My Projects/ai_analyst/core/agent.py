"""The analyst agent: question in, answer + charts + trace out.

The loop, in plain words:
    1. send the system prompt, chat history and question to the model
    2. if the model asks for tools  -> run them, send the results back, go to 1
    3. if the model writes text     -> that's the answer, stop
    4. after MAX_AGENT_STEPS model calls -> force a final answer without tools

The loop doesn't call the model or the tools directly. It asks a *driver*:

  * LocalDriver   runs everything in this process (CLI, tests, Streamlit
                  "direct" mode),
  * InngestDriver (worker/functions.py) turns every model call and every
                  tool call into a durable Inngest step.

Same loop, two execution engines. That's what lets you debug the agent
locally and then run it on Inngest without changing its logic.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Callable, Literal, Optional, Protocol

import pandas as pd
from pydantic import BaseModel, Field

from core.config import settings
from core.declarations import all_declarations
from core.llm import FunctionCall, LLMClient, LLMError, LLMResponse, Message, TokenUsage, ToolResponse
from core.prompts import FINAL_ANSWER_NUDGE, MALFORMED_CALL_NUDGE, build_system_prompt
from core.schemas import DatasetProfile, ToolResult
from tools.registry import run_tool

log = logging.getLogger(__name__)

CHART_TOOL = "create_chart"
SMALL_CHART_POINTS = 15        # small charts also send their numbers to the model
EventCallback = Callable[[str, dict[str, Any]], None]


# --------------------------------------------------------------------------- #
# Result types
# --------------------------------------------------------------------------- #
class ChatTurn(BaseModel):
    """A finished question/answer pair, used as memory for follow-up questions."""
    question: str
    answer: str


class ToolCallRecord(BaseModel):
    step: int
    name: str
    args: dict[str, Any]
    ok: bool
    error: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)
    duration_ms: int = 0
    cached: bool = False


class AgentResult(BaseModel):
    question: str
    answer: str
    charts: list[dict[str, Any]] = Field(default_factory=list)   # ChartData dicts
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    llm_calls: int = 0
    usage: TokenUsage = Field(default_factory=TokenUsage)
    stop_reason: Literal["answered", "max_steps", "llm_error", "empty"] = "answered"
    error: Optional[str] = None
    duration_ms: int = 0


# --------------------------------------------------------------------------- #
# Building blocks (future Inngest steps)
# --------------------------------------------------------------------------- #
def build_messages(question: str, history: list[ChatTurn] | None) -> list[Message]:
    """Chat memory = previous questions and final answers only (no tool traces).
    That's enough for follow-ups like 'and for 2023?' and keeps prompts small."""
    messages: list[Message] = []
    for turn in (history or [])[-settings.history_turns:]:
        messages += [Message.user(turn.question), Message.assistant(turn.answer)]
    messages.append(Message.user(question))
    return messages


def model_step(llm: LLMClient, system: str, messages: list[Message],
               allow_tools: bool = True) -> LLMResponse:
    return llm.generate(system, messages, all_declarations(), allow_tools=allow_tools)


def tool_step(df: pd.DataFrame, call: FunctionCall) -> tuple[ToolResult, int]:
    start = time.perf_counter()
    result = run_tool(call.name, df, call.args)
    return result, int((time.perf_counter() - start) * 1000)


def _fit_to_size(data: Any, limit: int) -> tuple[Any, bool]:
    """Shrink the longest lists in `data` until its JSON fits in `limit` chars.
    Tools already cap their output; this is a final safety net for the context."""
    if len(json.dumps(data, default=str)) <= limit:
        return data, False
    data = json.loads(json.dumps(data, default=str))   # deep copy

    def longest_list(node: Any) -> list | None:
        best = None
        stack = [node]
        while stack:
            n = stack.pop()
            if isinstance(n, dict):
                stack.extend(n.values())
            elif isinstance(n, list):
                if best is None or len(n) > len(best):
                    best = n
                stack.extend(n)
        return best

    while len(json.dumps(data)) > limit:
        lst = longest_list(data)
        if not lst or len(lst) <= 1:
            break
        del lst[len(lst) // 2:]
    return data, True


def view_for_model(name: str, result: ToolResult, chart_number: int | None) -> dict[str, Any]:
    """What the model gets back for a tool call.

    Charts are the special case: the full data goes to the UI, the model only
    gets a short confirmation (plus the numbers if the chart is small)."""
    if name == CHART_TOOL and result.ok:
        records = result.data["records"]
        view = {"ok": True, "chart_number": chart_number, "chart_type": result.data["chart_type"],
                "points": len(records),
                "note": "The chart will be shown to the user under your answer."}
        if len(records) <= SMALL_CHART_POINTS:
            view["records"] = records
        if result.warnings:
            view["warnings"] = result.warnings
        return view

    view = result.model_dump(mode="json", exclude_none=True)
    if not view.get("warnings"):
        view.pop("warnings", None)
    view, truncated = _fit_to_size(view, settings.max_tool_response_chars)
    if truncated:
        view.setdefault("warnings", []).append(
            "Result truncated to fit the context. Use filters or a smaller top_n for details.")
    return view


# --------------------------------------------------------------------------- #
# Drivers
# --------------------------------------------------------------------------- #
class ToolExecution(BaseModel):
    result: ToolResult
    duration_ms: int = 0


class AgentDriver(Protocol):
    async def llm(self, step: int, system: str, messages: list[Message],
                  allow_tools: bool) -> LLMResponse: ...

    async def tool(self, step: int, index: int, call: FunctionCall) -> ToolExecution: ...


class LocalDriver:
    """Runs model and tool calls in this process. Blocking work goes to a
    thread so the event loop (and Streamlit) stays responsive."""

    def __init__(self, df: pd.DataFrame, llm: LLMClient, on_event: EventCallback | None = None):
        self.df, self.client = df, llm
        self.emit = on_event or (lambda kind, data: None)

    async def llm(self, step: int, system: str, messages: list[Message],
                  allow_tools: bool) -> LLMResponse:
        self.emit("llm_call", {"step": step, "allow_tools": allow_tools})
        return await asyncio.to_thread(model_step, self.client, system, messages, allow_tools)

    async def tool(self, step: int, index: int, call: FunctionCall) -> ToolExecution:
        self.emit("tool_call", {"name": call.name, "args": call.args})
        result, duration = await asyncio.to_thread(tool_step, self.df, call)
        self.emit("tool_result", {"name": call.name, "ok": result.ok, "error": result.error})
        return ToolExecution(result=result, duration_ms=duration)


# --------------------------------------------------------------------------- #
# The loop
# --------------------------------------------------------------------------- #
async def run_agent_async(question: str, profile: DatasetProfile, driver: AgentDriver,
                          history: list[ChatTurn] | list[dict] | None = None,
                          max_steps: int | None = None) -> AgentResult:
    """Deterministic given the driver's outputs, which Inngest requires:
    on every replay the same step results lead to the same next step."""
    max_steps = max_steps or settings.max_agent_steps
    turns = [t if isinstance(t, ChatTurn) else ChatTurn(**t) for t in history or []]

    system = build_system_prompt(profile)
    messages = build_messages(question, turns)
    result = AgentResult(question=question, answer="")
    cache: dict[str, ToolResult] = {}       # identical calls are answered from here
    nudged_malformed = False
    llm_step = 0

    def finish(answer: str, reason: str, error: str | None = None) -> AgentResult:
        result.answer, result.stop_reason, result.error = answer, reason, error
        return result

    async def call_model(allow_tools: bool) -> LLMResponse:
        nonlocal llm_step
        llm_step += 1
        response = await driver.llm(llm_step, system, messages, allow_tools)
        result.llm_calls += 1
        result.usage = result.usage + response.usage
        return response

    try:
        for step in range(1, max_steps + 1):
            response = await call_model(allow_tools=True)

            if response.function_calls:
                messages.append(Message(kind="model_turn", raw=response.model_turn))
                responses = []
                for index, call in enumerate(response.function_calls, 1):
                    responses.append(await _execute(call, step, index, driver, result, cache))
                messages.append(Message(kind="tool_results", results=responses))
                continue

            if response.text:
                return finish(response.text, "answered")

            # Neither text nor a tool call.
            if response.finish_reason == "MALFORMED_FUNCTION_CALL" and not nudged_malformed:
                nudged_malformed = True
                messages.append(Message.user(MALFORMED_CALL_NUDGE))
                continue
            return finish("Sorry, I couldn't produce an answer for that question. "
                          "Try rephrasing it.", "empty",
                          error=f"Empty model response (finish_reason={response.finish_reason})")

        # Out of steps: one last call with tools disabled.
        messages.append(Message.user(FINAL_ANSWER_NUDGE))
        response = await call_model(allow_tools=False)
        return finish(response.text or "I couldn't finish the analysis within the step limit.",
                      "max_steps")

    except LLMError as e:
        log.error("LLM error: %s", e)
        return finish("The AI service is unavailable right now (see error). "
                      "Please try again in a minute.", "llm_error", error=str(e))


async def _execute(call: FunctionCall, step: int, index: int, driver: AgentDriver,
                   result: AgentResult, cache: dict[str, ToolResult]) -> ToolResponse:
    key = f"{call.name}:{json.dumps(call.args, sort_keys=True, default=str)}"
    cached = key in cache
    if cached:
        execution = ToolExecution(result=cache[key])
    else:
        execution = await driver.tool(step, index, call)
        cache[key] = execution.result
    tool_result = execution.result

    chart_number = None
    if call.name == CHART_TOOL and tool_result.ok and not cached:
        result.charts.append(tool_result.data)
        chart_number = len(result.charts)

    result.tool_calls.append(ToolCallRecord(
        step=step, name=call.name, args=call.args, ok=tool_result.ok, error=tool_result.error,
        warnings=tool_result.warnings, duration_ms=execution.duration_ms, cached=cached))

    view = view_for_model(call.name, tool_result, chart_number)
    if cached:
        view = {**view, "note": "You already made this exact call; this is the same result."}
    return ToolResponse(id=call.id, name=call.name, response=view)


def run_agent(question: str, df: pd.DataFrame, profile: DatasetProfile, llm: LLMClient,
              history: list[ChatTurn] | None = None, max_steps: int | None = None,
              on_event: EventCallback | None = None) -> AgentResult:
    """Synchronous entry point for the CLI, tests and Streamlit direct mode."""
    started = time.perf_counter()
    driver = LocalDriver(df, llm, on_event)
    result = asyncio.run(run_agent_async(question, profile, driver, history, max_steps))
    result.duration_ms = int((time.perf_counter() - started) * 1000)
    if on_event:
        on_event("done", {"stop_reason": result.stop_reason})
    return result
