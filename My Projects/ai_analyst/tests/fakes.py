"""A scripted stand-in for Gemini.

Each script entry is either an LLMResponse or a function
(system, messages, tools, allow_tools) -> LLMResponse, so a test can
inspect what the agent sent before deciding what the "model" answers.
"""
from __future__ import annotations

from typing import Any, Callable, Union

from core.llm import FunctionCall, LLMResponse, Message, TokenUsage

Script = Union[LLMResponse, Callable[..., LLMResponse]]


def call(name: str, call_id: str = "c1", **args: Any) -> LLMResponse:
    """A model turn that requests one tool call."""
    return LLMResponse(function_calls=[FunctionCall(id=call_id, name=name, args=args)],
                       model_turn={"role": "model", "parts": [{"function_call": {"name": name}}]},
                       finish_reason="STOP", usage=TokenUsage(prompt=100, output=10, total=110))


def text(answer: str) -> LLMResponse:
    return LLMResponse(text=answer, finish_reason="STOP",
                       usage=TokenUsage(prompt=200, output=20, total=220))


class FakeLLM:
    def __init__(self, script: list[Script]):
        self.script = list(script)
        self.requests: list[dict[str, Any]] = []

    def generate(self, system: str, messages: list[Message], tools: list[dict[str, Any]],
                 allow_tools: bool = True) -> LLMResponse:
        self.requests.append({"system": system, "messages": [m.model_copy(deep=True) for m in messages],
                              "tools": tools, "allow_tools": allow_tools})
        if not self.script:
            raise AssertionError("FakeLLM ran out of scripted responses")
        step = self.script.pop(0)
        return step(system, messages, tools, allow_tools) if callable(step) else step

    def last_tool_results(self, request_index: int = -1) -> list[dict[str, Any]]:
        msgs = self.requests[request_index]["messages"]
        results = next(m for m in reversed(msgs) if m.kind == "tool_results").results
        return [r.response for r in results]


class RuleBasedFakeLLM:
    """A fake that behaves sensibly in any order, for end-to-end runs without
    an API key (integration test, `evals --fake`). It always does:
    aggregate the main metric by the first categorical column -> chart it ->
    answer with the top group taken from the tool result."""

    def generate(self, system: str, messages: list[Message], tools: list[dict[str, Any]],
                 allow_tools: bool = True) -> LLMResponse:
        import re

        metric = re.search(r"Main sales value column: (\w+)", system)
        group = re.search(r"- (\w+) \[categorical(?:, role=(?:region|category|product|channel))?\]", system)
        metric_col = metric.group(1) if metric else None
        group_col = group.group(1) if group else None
        results = [r for m in messages if m.kind == "tool_results" for r in m.results or []]

        if allow_tools and metric_col and group_col and len(results) == 0:
            return call("aggregate_data", call_id="f1", group_by=[group_col], metric=metric_col)
        if allow_tools and metric_col and group_col and len(results) == 1:
            return call("create_chart", call_id="f2", chart_type="bar",
                        title=f"{metric_col} by {group_col}", x=group_col, y=metric_col)
        if results and results[0].response.get("ok"):
            data = results[0].response["data"]
            top = data["rows"][0]
            return text(f"{top[group_col]} is the top {group_col} with "
                        f"{top[data['value_column']]:,.2f} {metric_col}.")
        return text("I could not compute an answer.")
