"""Gemini client tests. No network: we build SDK objects by hand and
replace the HTTP client with a tiny fake."""
from types import SimpleNamespace

import pytest
from google.genai import errors, types

import core.llm as llm_module
from core.config import Settings
from core.declarations import all_declarations
from core.llm import GeminiClient, LLMError, Message, RateLimiter, ToolResponse


# ---- declarations --------------------------------------------------------- #
def test_declarations_are_self_contained():
    decls = all_declarations()
    assert {d["name"] for d in decls} >= {"aggregate_data", "create_chart"}

    def schema_keys(node, inside_properties=False):
        """All schema keywords used (property *names* like 'title' don't count)."""
        if isinstance(node, dict):
            for k, v in node.items():
                if not inside_properties:
                    yield k
                yield from schema_keys(v, inside_properties=(k == "properties" and not inside_properties))
        elif isinstance(node, list):
            for v in node:
                yield from schema_keys(v)

    keys = set(schema_keys([d["parameters"] for d in decls]))
    assert not keys & {"$ref", "$defs", "title"}


def test_filter_schema_is_inlined():
    agg = next(d for d in all_declarations() if d["name"] == "aggregate_data")
    filter_item = agg["parameters"]["properties"]["filters"]["items"]
    assert set(filter_item["properties"]["operator"]["enum"]) >= {"==", "in", "between"}


def test_chart_title_property_is_preserved():
    chart = next(d for d in all_declarations() if d["name"] == "create_chart")["parameters"]
    assert "title" in chart["properties"]
    assert "title" in chart["required"]


def test_config_accepts_our_declarations():
    config = GeminiClient.build_config("system", all_declarations(), allow_tools=True)
    assert len(config.tools[0].function_declarations) == len(all_declarations())
    assert config.tool_config.function_calling_config.mode.name == "AUTO"
    off = GeminiClient.build_config("system", all_declarations(), allow_tools=False)
    assert off.tool_config.function_calling_config.mode.name == "NONE"


# ---- message conversion ---------------------------------------------------- #
def test_messages_become_gemini_contents():
    model_turn = types.Content(role="model", parts=[types.Part(
        function_call=types.FunctionCall(id="x1", name="aggregate_data", args={"a": 1}),
        thought_signature=b"\x00\xffsig")]).model_dump(mode="json", exclude_none=True)
    messages = [
        Message.user("old question"), Message.assistant("old answer"),
        Message.user("q"),
        Message(kind="model_turn", raw=model_turn),
        Message(kind="tool_results", results=[ToolResponse(id="x1", name="aggregate_data",
                                                           response={"ok": True})]),
        Message.user("nudge"),
    ]
    contents = GeminiClient.to_contents(messages)
    assert [c.role for c in contents] == ["user", "model", "user", "model", "user"]
    assert contents[3].parts[0].thought_signature == b"\x00\xffsig"   # survives JSON round trip
    last = contents[-1]                                                # tool results + nudge merged
    assert last.parts[0].function_response.id == "x1"
    assert last.parts[1].text == "nudge"


def make_response(parts, finish="STOP"):
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(role="model", parts=parts),
                                    finish_reason=finish)],
        usage_metadata=types.GenerateContentResponseUsageMetadata(
            prompt_token_count=100, candidates_token_count=20, thoughts_token_count=5,
            total_token_count=125))


def test_parse_function_calls_and_ignore_thoughts():
    resp = make_response([
        types.Part(text="internal reasoning", thought=True),
        types.Part(function_call=types.FunctionCall(id="1", name="time_series",
                                                    args={"date_column": "d"})),
    ])
    parsed = GeminiClient.parse_response(resp)
    assert parsed.text is None
    assert parsed.function_calls[0].name == "time_series"
    assert parsed.function_calls[0].args == {"date_column": "d"}
    assert parsed.model_turn["role"] == "model"
    assert parsed.usage.total == 125 and parsed.usage.thoughts == 5


def test_parse_text_answer():
    parsed = GeminiClient.parse_response(make_response([types.Part(text="Answer.")]))
    assert parsed.text == "Answer." and not parsed.function_calls


def test_parse_empty_response():
    parsed = GeminiClient.parse_response(types.GenerateContentResponse(candidates=[]))
    assert parsed.text is None and parsed.finish_reason == "NO_CANDIDATES"


# ---- calling, retries, rate limit ------------------------------------------ #
class FakeModels:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0

    def generate_content(self, **kwargs):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def client_with(outcomes, **kw):
    fake = SimpleNamespace(models=FakeModels(outcomes))
    return GeminiClient(client=fake, rpm=0, **kw), fake.models


def quota_error():
    return errors.ClientError(429, {"error": {"code": 429, "message": "Quota exceeded"}})


@pytest.fixture
def no_sleep(monkeypatch):
    sleeps = []
    monkeypatch.setattr(llm_module.time, "sleep", lambda s: sleeps.append(s))
    return sleeps


def test_retries_on_quota_errors(no_sleep):
    client, models = client_with([quota_error(), make_response([types.Part(text="ok")])],
                                 max_retries=2)
    assert client.generate("s", [Message.user("q")], all_declarations()).text == "ok"
    assert models.calls == 2
    assert no_sleep == [15]


def test_gives_up_after_max_retries(no_sleep):
    client, models = client_with([quota_error()] * 3, max_retries=2)
    with pytest.raises(LLMError, match="429"):
        client.generate("s", [Message.user("q")], [])
    assert models.calls == 3


def test_does_not_retry_bad_requests(no_sleep):
    bad = errors.ClientError(400, {"error": {"code": 400, "message": "Invalid schema"}})
    client, models = client_with([bad])
    with pytest.raises(LLMError, match="Invalid schema"):
        client.generate("s", [Message.user("q")], [])
    assert models.calls == 1


def test_missing_api_key(monkeypatch):
    monkeypatch.setattr(llm_module, "settings", Settings(gemini_api_key=""))
    with pytest.raises(LLMError, match="GEMINI_API_KEY"):
        GeminiClient()


def test_rate_limiter_spaces_calls(no_sleep):
    limiter = RateLimiter(rpm=60)          # one call per second
    for _ in range(3):
        limiter.wait()
    assert len(no_sleep) == 2 and all(0.9 < s <= 2.0 for s in no_sleep)
