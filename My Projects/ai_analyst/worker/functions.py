"""Inngest functions.

answer-question   triggered by "analyst/question.asked". Runs the same agent
                  loop as the CLI, through InngestDriver:
                    - every tool call      -> ctx.step.run("tool-<step>-<n>-<name>")
                    - every model call     -> ctx.step.invoke("llm-<step>") of ...
llm-generate      ... this function, which is throttled to GEMINI_RPM runs per
                  minute. Every model call in the whole app goes through it,
                  so the free-tier quota is respected even with several
                  questions in flight.

What you get in the Inngest Dev Server (http://localhost:8288):
  * one run per question, with each step's input/output and timing,
  * one run per model call (prompt in, response out),
  * automatic retries: a failed tool step retries alone, a 429 from Gemini
    waits and retries without redoing the steps that already succeeded,
  * a "cancel" button, plus cancellation from the app's Stop button.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from typing import Any

import inngest
import pandas as pd

from core.agent import AgentResult, ToolExecution, run_agent_async, tool_step
from core.config import settings
from core.declarations import all_declarations
from core.llm import FunctionCall, GeminiClient, LLMError, LLMResponse, Message
from core.schemas import DatasetProfile
from data_layer.ingest import load_profile, profile_path
from data_layer.loader import load_dataset
from data_layer.store import Store
from worker.client import LLM_REQUESTED, QUESTION_ASKED, QUESTION_CANCELLED, QuestionEvent

log = logging.getLogger(__name__)

NON_RETRYABLE_STATUS = {400, 401, 403, 404}


# --------------------------------------------------------------------------- #
# Cached resources (code outside steps runs on every replay: keep it cheap)
# --------------------------------------------------------------------------- #
@lru_cache(maxsize=8)
def get_dataframe(dataset_id: str) -> pd.DataFrame:
    return load_dataset(dataset_id)


def get_profile(dataset_id: str) -> DatasetProfile:
    # Keyed on the file's modification time: when the user corrects column
    # roles in the UI, the worker picks up the new profile automatically.
    return _load_profile(dataset_id, profile_path(dataset_id).stat().st_mtime)


@lru_cache(maxsize=8)
def _load_profile(dataset_id: str, mtime: float) -> DatasetProfile:
    return load_profile(dataset_id)


@lru_cache(maxsize=1)
def get_llm() -> GeminiClient:
    # No client-side rate limit or retries here: Inngest's throttle and
    # retries do that job, and they're visible in the dashboard.
    return GeminiClient(rpm=0, max_retries=0)


@lru_cache(maxsize=1)
def get_store() -> Store:
    return Store()


# --------------------------------------------------------------------------- #
# Driver: the agent loop's model/tool calls become Inngest steps
# --------------------------------------------------------------------------- #
class InngestDriver:
    def __init__(self, ctx: inngest.Context, event: QuestionEvent, llm_fn: inngest.Function,
                 store: Store):
        self.ctx, self.event, self.llm_fn, self.store = ctx, event, llm_fn, store

    async def llm(self, step: int, system: str, messages: list[Message],
                  allow_tools: bool) -> LLMResponse:
        try:
            out = await self.ctx.step.invoke(
                f"llm-{step}",
                function=self.llm_fn,
                data={"request_id": self.event.request_id, "step": step, "system": system,
                      "messages": [m.model_dump(mode="json") for m in messages],
                      "allow_tools": allow_tools},
            )
        except inngest.StepError as e:
            # The invoked function failed after all its retries.
            raise LLMError(f"Model call failed: {e}") from e
        return LLMResponse.model_validate(out)

    async def tool(self, step: int, index: int, call: FunctionCall) -> ToolExecution:
        request_id, dataset_id, store = self.event.request_id, self.event.dataset_id, self.store

        async def handler() -> dict[str, Any]:
            store.add_event(request_id, "tool_call", {"name": call.name, "args": call.args})
            df = get_dataframe(dataset_id)
            result, duration = await asyncio.to_thread(tool_step, df, call)
            store.add_event(request_id, "tool_result",
                            {"name": call.name, "ok": result.ok, "error": result.error})
            return ToolExecution(result=result, duration_ms=duration).model_dump(mode="json")

        out = await self.ctx.step.run(f"tool-{step}-{index}-{call.name}", handler)
        return ToolExecution.model_validate(out)


# --------------------------------------------------------------------------- #
# Functions
# --------------------------------------------------------------------------- #
def _elapsed_ms(created_at: str) -> int:
    start = datetime.fromisoformat(created_at)
    return int((datetime.now(timezone.utc) - start).total_seconds() * 1000)


def create_functions(client: inngest.Inngest, store_factory=get_store) -> list[inngest.Function]:
    """Built by a factory so tests can pass a mocked client and a temp store."""

    @client.create_function(
        fn_id="llm-generate",
        name="LLM: generate",
        trigger=inngest.TriggerEvent(event=LLM_REQUESTED),
        throttle=inngest.Throttle(limit=max(settings.gemini_rpm, 1), period=timedelta(minutes=1)),
        retries=4,
    )
    async def llm_generate(ctx: inngest.Context) -> dict[str, Any]:
        data = ctx.event.data
        messages = [Message.model_validate(m) for m in data["messages"]]
        store = store_factory()

        async def generate() -> dict[str, Any]:
            store.add_event(data["request_id"], "llm_call",
                            {"step": data["step"], "attempt": ctx.attempt + 1})
            try:
                response = await asyncio.to_thread(
                    get_llm().generate, data["system"], messages, all_declarations(),
                    bool(data["allow_tools"]))
            except LLMError as e:
                if e.status == 429:
                    store.add_event(data["request_id"], "rate_limited", {"retry_in_s": 30})
                    raise inngest.RetryAfterError(str(e), retry_after=timedelta(seconds=30)) from e
                if e.status in NON_RETRYABLE_STATUS:
                    raise inngest.NonRetriableError(str(e)) from e
                raise
            return response.model_dump(mode="json")

        return await ctx.step.run("generate", generate)

    async def on_failure(ctx: inngest.Context) -> None:
        original = (ctx.event.data or {}).get("event", {}).get("data", {})
        error = (ctx.event.data or {}).get("error", {}).get("message", "unknown error")
        if original.get("request_id"):
            store_factory().finish_request(original["request_id"], "failed", error=error)

    @client.create_function(
        fn_id="answer-question",
        name="Answer question",
        trigger=inngest.TriggerEvent(event=QUESTION_ASKED),
        retries=2,
        concurrency=[inngest.Concurrency(limit=4)],
        cancel=[inngest.Cancel(event=QUESTION_CANCELLED,
                               if_exp="event.data.request_id == async.data.request_id")],
        timeouts=inngest.Timeouts(finish=timedelta(minutes=10)),
        on_failure=on_failure,
    )
    async def answer_question(ctx: inngest.Context) -> dict[str, Any]:
        event = QuestionEvent.model_validate(ctx.event.data)
        store = store_factory()

        await ctx.step.run("mark-running", lambda: store.mark_running(event.request_id))

        profile = get_profile(event.dataset_id)
        driver = InngestDriver(ctx, event, llm_generate, store)
        result: AgentResult = await run_agent_async(event.question, profile, driver, event.history)

        def save() -> dict[str, Any]:
            request = store.get_request(event.request_id)
            if request is not None:
                result.duration_ms = _elapsed_ms(request.created_at)
            payload = result.model_dump(mode="json")
            store.finish_request(event.request_id, "done", result=payload)
            store.add_event(event.request_id, "done", {"stop_reason": result.stop_reason})
            return {"stop_reason": result.stop_reason, "duration_ms": result.duration_ms}

        saved = await ctx.step.run("save-result", save)
        return {"request_id": event.request_id, "answer": result.answer, **saved,
                "tool_calls": len(result.tool_calls), "charts": len(result.charts),
                "tokens": result.usage.total}

    return [answer_question, llm_generate]
