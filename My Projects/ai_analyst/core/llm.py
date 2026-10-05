"""The only module that talks to Gemini.

Everything else uses the small, provider-neutral types defined here
(Message, LLMResponse, FunctionCall). Three benefits:
  * tests run against a FakeLLM: no API key, no quota, fully deterministic;
  * the conversation is plain JSON, so in Phase 3 it can be stored between
    Inngest steps;
  * switching to another provider (or to Google's newer Interactions API)
    means rewriting this file only.

About `model_turn`: Gemini 3 models attach "thought signatures" to their
turns, and they must be sent back unchanged for multi-step tool use to work.
So we keep the model's turn as an opaque JSON blob and replay it as-is.
"""
from __future__ import annotations

import logging
import threading
import time
from typing import Any, Literal, Optional, Protocol

from pydantic import BaseModel, Field

from core.config import settings

log = logging.getLogger(__name__)

RETRYABLE_STATUS = {429, 500, 502, 503, 504}


# --------------------------------------------------------------------------- #
# Provider-neutral types
# --------------------------------------------------------------------------- #
class FunctionCall(BaseModel):
    id: Optional[str] = None
    name: str
    args: dict[str, Any] = Field(default_factory=dict)


class ToolResponse(BaseModel):
    id: Optional[str] = None
    name: str
    response: dict[str, Any]


class Message(BaseModel):
    """One entry of the conversation sent to the model.

    kind:
      user          a user question (text)
      assistant     a previous final answer (text), used for chat memory
      model_turn    a model turn with function calls (opaque provider JSON in `raw`)
      tool_results  our answers to those function calls
    """
    kind: Literal["user", "assistant", "model_turn", "tool_results"]
    text: Optional[str] = None
    raw: Optional[dict[str, Any]] = None
    results: Optional[list[ToolResponse]] = None

    @classmethod
    def user(cls, text: str) -> "Message":
        return cls(kind="user", text=text)

    @classmethod
    def assistant(cls, text: str) -> "Message":
        return cls(kind="assistant", text=text)


class TokenUsage(BaseModel):
    prompt: int = 0
    output: int = 0
    thoughts: int = 0
    total: int = 0

    def __add__(self, other: "TokenUsage") -> "TokenUsage":
        return TokenUsage(**{f: getattr(self, f) + getattr(other, f) for f in type(self).model_fields})


class LLMResponse(BaseModel):
    text: Optional[str] = None
    function_calls: list[FunctionCall] = Field(default_factory=list)
    model_turn: Optional[dict[str, Any]] = None   # replay this unchanged in the next request
    finish_reason: Optional[str] = None
    usage: TokenUsage = Field(default_factory=TokenUsage)


class LLMError(Exception):
    """The model could not be reached or returned something unusable.

    `status` is the HTTP status when there was one (429 = quota). The Inngest
    worker uses it to decide between "retry later" and "don't retry"."""

    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class LLMClient(Protocol):
    def generate(self, system: str, messages: list[Message], tools: list[dict[str, Any]],
                 allow_tools: bool = True) -> LLMResponse: ...


# --------------------------------------------------------------------------- #
# Rate limiter
# --------------------------------------------------------------------------- #
class RateLimiter:
    """Spaces calls evenly: at most `rpm` requests per minute.
    Simple and enough for one user; Inngest's throttle replaces it in Phase 3."""

    def __init__(self, rpm: int):
        self.interval = 60.0 / rpm if rpm > 0 else 0.0
        self._next = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delay = self._next - now
            self._next = max(now, self._next) + self.interval
        if delay > 0:
            log.info("Rate limit: waiting %.1fs", delay)
            time.sleep(delay)


# --------------------------------------------------------------------------- #
# Gemini
# --------------------------------------------------------------------------- #
class GeminiClient:
    def __init__(self, api_key: str | None = None, model: str | None = None,
                 rpm: int | None = None, max_retries: int | None = None, client: Any = None):
        from google import genai   # imported here so tests without the SDK still import this module

        self.model = model or settings.gemini_model
        self.max_retries = settings.llm_max_retries if max_retries is None else max_retries
        self.limiter = RateLimiter(settings.gemini_rpm if rpm is None else rpm)
        if client is not None:
            self.client = client
        else:
            key = api_key or settings.gemini_api_key
            if not key:
                raise LLMError("GEMINI_API_KEY is not set. Add it to your .env file.")
            self.client = genai.Client(api_key=key)

    # ---- conversion: neutral -> Gemini ------------------------------------ #
    @staticmethod
    def to_contents(messages: list[Message]) -> list[Any]:
        from google.genai import types

        contents = []
        for m in messages:
            if m.kind == "user":
                contents.append(types.Content(role="user", parts=[types.Part(text=m.text)]))
            elif m.kind == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part(text=m.text)]))
            elif m.kind == "model_turn":
                contents.append(types.Content.model_validate(m.raw))
            elif m.kind == "tool_results":
                contents.append(types.Content(role="user", parts=[
                    types.Part(function_response=types.FunctionResponse(
                        id=r.id, name=r.name, response=r.response))
                    for r in m.results or []
                ]))

        # Two user turns in a row (e.g. tool results followed by a nudge)
        # are merged into one turn with several parts.
        merged: list[Any] = []
        for c in contents:
            if merged and c.role == "user" and merged[-1].role == "user":
                merged[-1] = types.Content(role="user", parts=[*merged[-1].parts, *c.parts])
            else:
                merged.append(c)
        return merged

    @staticmethod
    def build_config(system: str, tools: list[dict[str, Any]], allow_tools: bool) -> Any:
        from google.genai import types

        declarations = [
            types.FunctionDeclaration(name=t["name"], description=t["description"],
                                      parameters_json_schema=t["parameters"])
            for t in tools
        ]
        return types.GenerateContentConfig(
            system_instruction=system,
            tools=[types.Tool(function_declarations=declarations)] if declarations else None,
            # We run tools ourselves: each tool call must be visible (and,
            # in Phase 3, its own Inngest step).
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
            tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(
                mode="AUTO" if allow_tools else "NONE")) if declarations else None,
        )

    # ---- conversion: Gemini -> neutral ------------------------------------ #
    @staticmethod
    def parse_response(response: Any) -> LLMResponse:
        usage = TokenUsage()
        meta = getattr(response, "usage_metadata", None)
        if meta is not None:
            usage = TokenUsage(prompt=meta.prompt_token_count or 0,
                               output=meta.candidates_token_count or 0,
                               thoughts=meta.thoughts_token_count or 0,
                               total=meta.total_token_count or 0)

        candidates = response.candidates or []
        if not candidates:
            reason = getattr(getattr(response, "prompt_feedback", None), "block_reason", None)
            return LLMResponse(finish_reason=f"BLOCKED:{reason}" if reason else "NO_CANDIDATES",
                               usage=usage)

        cand = candidates[0]
        finish = cand.finish_reason.name if cand.finish_reason is not None else None
        content = cand.content
        if content is None or not content.parts:
            return LLMResponse(finish_reason=finish, usage=usage)

        texts, calls = [], []
        for part in content.parts:
            if part.function_call is not None:
                fc = part.function_call
                calls.append(FunctionCall(id=fc.id, name=fc.name, args=dict(fc.args or {})))
            elif part.text and not part.thought:
                texts.append(part.text)

        return LLMResponse(
            text="".join(texts).strip() or None,
            function_calls=calls,
            model_turn=content.model_dump(mode="json", exclude_none=True),
            finish_reason=finish,
            usage=usage,
        )

    # ---- the call ---------------------------------------------------------- #
    def generate(self, system: str, messages: list[Message], tools: list[dict[str, Any]],
                 allow_tools: bool = True) -> LLMResponse:
        from google.genai import errors

        contents = self.to_contents(messages)
        config = self.build_config(system, tools, allow_tools)

        for attempt in range(self.max_retries + 1):
            self.limiter.wait()
            try:
                response = self.client.models.generate_content(
                    model=self.model, contents=contents, config=config)
                return self.parse_response(response)
            except errors.APIError as e:
                retryable = e.code in RETRYABLE_STATUS
                if not retryable or attempt == self.max_retries:
                    raise LLMError(f"Gemini API error {e.code}: {e.message}", status=e.code) from e
                # Quota errors need a longer pause than a hiccup on Google's side.
                delay = (15 if e.code == 429 else 2) * 2 ** attempt
                log.warning("Gemini %s, retrying in %ss (attempt %d/%d)",
                            e.code, delay, attempt + 1, self.max_retries)
                time.sleep(delay)
        raise LLMError("unreachable")  # pragma: no cover
