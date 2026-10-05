import time

import pytest

from app.runner import DirectRunner, make_runner
from data_layer.ingest import ingest
from data_layer.store import Store
from scripts.make_sample_data import make_sales
from tests.fakes import FakeLLM, RuleBasedFakeLLM, text


@pytest.fixture
def store(tmp_path):
    return Store(tmp_path / "t.db")


def test_request_lifecycle_and_history(store):
    s = store.create_session("ds1", title="My chat")
    r1 = store.create_request(s.session_id, "q1")
    assert store.get_request(r1.request_id).status == "queued"
    store.mark_running(r1.request_id)
    store.finish_request(r1.request_id, "done", result={"answer": "a1", "stop_reason": "answered"})
    r2 = store.create_request(s.session_id, "q2")
    store.finish_request(r2.request_id, "failed", error="x")

    assert store.chat_history(s.session_id) == [{"question": "q1", "answer": "a1"}]
    assert [r.status for r in store.list_requests(s.session_id)] == ["done", "failed"]
    assert store.list_sessions("ds1")[0].title == "My chat"


def test_first_final_status_wins(store):
    s = store.create_session("ds")
    r = store.create_request(s.session_id, "q")
    store.finish_request(r.request_id, "cancelled", error="Stopped by user")
    store.finish_request(r.request_id, "done", result={"answer": "late"})
    assert store.get_request(r.request_id).status == "cancelled"


def test_events_and_feedback(store):
    s = store.create_session("ds")
    r = store.create_request(s.session_id, "q")
    store.add_event(r.request_id, "tool_call", {"name": "aggregate_data"})
    assert store.list_events(r.request_id)[0]["name"] == "aggregate_data"
    store.set_feedback(r.request_id, 1)
    store.set_feedback(r.request_id, -1, "wrong year")
    assert store.get_request(r.request_id).rating == -1
    assert [x.request_id for x in store.rated_requests()] == [r.request_id]


def wait_final(store, request_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        request = store.get_request(request_id)
        if request.is_final:
            return request
        time.sleep(0.05)
    raise AssertionError("request never finished")


@pytest.fixture
def dataset(tmp_settings):
    csv = make_sales(200).to_csv(index=False, date_format="%Y-%m-%d").encode()
    _, profile = ingest(csv)
    return profile


def test_direct_runner_answers_and_records_progress(store, dataset):
    runner = DirectRunner(store, llm=RuleBasedFakeLLM())
    session = store.create_session(dataset.dataset_id)
    request = runner.submit(session.session_id, dataset.dataset_id, "top region?")
    done = wait_final(store, request.request_id)
    assert done.status == "done"
    assert "top region" in done.result["answer"]
    kinds = [e["kind"] for e in store.list_events(request.request_id)]
    assert kinds[0] == "llm_call" and kinds[-1] == "done"


def test_direct_runner_sends_chat_history(store, dataset):
    llm = FakeLLM([text("first"), text("second")])
    runner = DirectRunner(store, llm=llm)
    session = store.create_session(dataset.dataset_id)
    wait_final(store, runner.submit(session.session_id, dataset.dataset_id, "q1").request_id)
    wait_final(store, runner.submit(session.session_id, dataset.dataset_id, "and q2?").request_id)
    texts = [m.text for m in llm.requests[1]["messages"]]
    assert texts == ["q1", "first", "and q2?"]


def test_direct_runner_reports_crashes(store, dataset):
    def crash(*_):
        raise RuntimeError("kaboom")
    runner = DirectRunner(store, llm=FakeLLM([crash]))
    session = store.create_session(dataset.dataset_id)
    done = wait_final(store, runner.submit(session.session_id, dataset.dataset_id, "q").request_id)
    assert done.status == "failed" and "kaboom" in done.error


def test_cancel_wins_over_late_result(store, dataset):
    def slow(*_):
        time.sleep(0.5)
        return text("too late")
    runner = DirectRunner(store, llm=FakeLLM([slow]))
    session = store.create_session(dataset.dataset_id)
    request = runner.submit(session.session_id, dataset.dataset_id, "q")
    runner.cancel(request)
    time.sleep(0.8)
    assert store.get_request(request.request_id).status == "cancelled"


def test_make_runner_defaults_to_direct(store, monkeypatch):
    monkeypatch.delenv("ANALYST_MODE", raising=False)
    assert make_runner(store).name == "direct"
