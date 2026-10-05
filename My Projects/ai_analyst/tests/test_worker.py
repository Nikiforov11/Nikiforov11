"""Worker tests with Inngest's mocked client: functions run in-process,
`step.invoke` results are stubbed, no Dev Server needed.
(scripts/e2e_inngest.py covers the real Dev Server.)"""
import asyncio
from types import SimpleNamespace

import inngest
import pytest
from inngest.experimental import mocked

import worker.functions as wf
from core.llm import FunctionCall, LLMError, Message
from data_layer.ingest import ingest
from data_layer.store import Store
from scripts.make_sample_data import make_sales
from tests.fakes import call, text
from worker.client import LLM_REQUESTED, QUESTION_ASKED, QuestionEvent


@pytest.fixture
def env(tmp_settings, monkeypatch):
    for module in ("data_layer.store", "worker.functions"):
        monkeypatch.setattr(f"{module}.settings", tmp_settings, raising=False)
    wf.get_dataframe.cache_clear()
    wf._load_profile.cache_clear()
    csv = make_sales(300).to_csv(index=False, date_format="%Y-%m-%d").encode()
    _, profile = ingest(csv)
    store = Store(tmp_settings.data_dir / "test.db")
    session = store.create_session(profile.dataset_id)
    client = mocked.Inngest(app_id="test")
    answer_fn, llm_fn = wf.create_functions(client, store_factory=lambda: store)
    return SimpleNamespace(store=store, session=session, profile=profile, client=client,
                           answer_fn=answer_fn, llm_fn=llm_fn)


def ask(env, question="Which region sells most?", stubs=None):
    request = env.store.create_request(env.session.session_id, question)
    event = QuestionEvent(request_id=request.request_id, session_id=env.session.session_id,
                          dataset_id=env.profile.dataset_id, question=question)
    run = mocked.trigger(env.answer_fn, inngest.Event(name=QUESTION_ASKED, data=event.model_dump()),
                         env.client, step_stubs=stubs or {})
    return run, env.store.get_request(request.request_id)


def stub(response):
    return response.model_dump(mode="json")


def test_answer_question_runs_tools_as_steps_and_saves_result(env):
    run, request = ask(env, stubs={
        "llm-1": stub(call("aggregate_data", group_by=["region"], metric="revenue")),
        "llm-2": stub(call("create_chart", call_id="c2", chart_type="bar", title="t",
                           x="region", y="revenue")),
        "llm-3": stub(text("East sells the most.")),
    })
    assert run.status == mocked.Status.COMPLETED
    assert run.output["answer"] == "East sells the most."
    assert request.status == "done"
    assert request.result["stop_reason"] == "answered"
    assert len(request.result["charts"]) == 1
    kinds = [e["kind"] for e in env.store.list_events(request.request_id)]
    assert kinds == ["tool_call", "tool_result", "tool_call", "tool_result", "done"]


def test_tool_errors_do_not_fail_the_run(env):
    run, request = ask(env, stubs={
        "llm-1": stub(call("aggregate_data", group_by=["regionn"], metric="revenue")),
        "llm-2": stub(text("Sorry.")),
    })
    assert run.status == mocked.Status.COMPLETED
    assert request.result["tool_calls"][0]["ok"] is False


def llm_event():
    return inngest.Event(name=LLM_REQUESTED, data={
        "request_id": "r1", "step": 1, "system": "s",
        "messages": [Message.user("q").model_dump(mode="json")], "allow_tools": True})


@pytest.mark.parametrize("status, error_type", [
    (429, inngest.RetryAfterError),      # quota: retry later
    (400, inngest.NonRetriableError),    # bad request: retrying won't help
    (503, LLMError),                     # server hiccup: normal retries
])
def test_llm_generate_maps_errors_to_retry_behaviour(env, monkeypatch, status, error_type):
    class Failing:
        def generate(self, *a, **k):
            raise LLMError("boom", status=status)
    monkeypatch.setattr(wf, "get_llm", lambda: Failing())
    run = mocked.trigger(env.llm_fn, llm_event(), env.client)
    assert run.status == mocked.Status.FAILED
    assert isinstance(run.error, error_type)


def test_llm_generate_returns_serialized_response(env, monkeypatch):
    class Ok:
        def generate(self, system, messages, tools, allow_tools=True):
            assert tools and messages[0].text == "q"
            return text("hi")
    monkeypatch.setattr(wf, "get_llm", lambda: Ok())
    run = mocked.trigger(env.llm_fn, llm_event(), env.client)
    assert run.status == mocked.Status.COMPLETED and run.output["text"] == "hi"
    assert env.store.list_events("r1")[0]["kind"] == "llm_call"


def test_failed_model_step_becomes_llm_error(env):
    """When the invoked llm-generate run fails for good, the driver raises
    LLMError so the agent can finish with a friendly 'llm_error' result."""
    class FailingStep:
        async def invoke(self, *a, **k):
            raise inngest.StepError("quota", "RetryAfterError", None)
    ctx = SimpleNamespace(step=FailingStep())
    event = QuestionEvent(request_id="r", session_id="s", dataset_id="d", question="q")
    driver = wf.InngestDriver(ctx, event, env.llm_fn, env.store)
    with pytest.raises(LLMError, match="quota"):
        asyncio.run(driver.llm(1, "s", [Message.user("q")], True))


def test_on_failure_marks_request_failed(env):
    request = env.store.create_request(env.session.session_id, "q")
    failure = inngest.Event(name="inngest/function.failed", data={
        "event": {"data": {"request_id": request.request_id}},
        "error": {"message": "worker crashed"}})
    on_failure = env.answer_fn._opts.on_failure
    asyncio.run(on_failure(SimpleNamespace(event=failure)))
    stored = env.store.get_request(request.request_id)
    assert stored.status == "failed" and stored.error == "worker crashed"


def test_tool_step_ids_are_unique_per_call(env):
    """Two tool calls in the same model turn must get different step ids."""
    calls = [FunctionCall(id="a", name="distinct_values", args={"column": "region"}),
             FunctionCall(id="b", name="distinct_values", args={"column": "channel"})]
    from core.llm import LLMResponse
    both = LLMResponse(function_calls=calls, model_turn={"role": "model", "parts": []})
    run, request = ask(env, stubs={"llm-1": stub(both), "llm-2": stub(text("ok"))})
    assert run.status == mocked.Status.COMPLETED
    assert [t["args"]["column"] for t in request.result["tool_calls"]] == ["region", "channel"]
