import pytest

from core.agent import ChatTurn, _fit_to_size, build_messages, run_agent
from core.llm import FunctionCall, LLMError, LLMResponse
from core.prompts import FINAL_ANSWER_NUDGE, MALFORMED_CALL_NUDGE, build_system_prompt
from data_layer.profiler import profile_dataset
from tests.fakes import FakeLLM, call, text


@pytest.fixture
def profile(orders):
    return profile_dataset(orders, "orders")


def run(llm, df, profile, question="q", **kw):
    return run_agent(question, df, profile, llm, **kw)


def test_direct_answer_without_tools(orders, profile):
    llm = FakeLLM([text("Hello!")])
    result = run(llm, orders, profile)
    assert (result.answer, result.stop_reason, result.llm_calls) == ("Hello!", "answered", 1)
    assert llm.requests[0]["tools"]                       # tools were offered
    assert result.usage.total == 220


def test_tool_call_result_goes_back_to_the_model(orders, profile):
    llm = FakeLLM([call("aggregate_data", group_by=["region"], metric="revenue"),
                   text("North leads with 3,010.")])
    result = run(llm, orders, profile)

    assert result.answer == "North leads with 3,010."
    [tool_result] = llm.last_tool_results()
    assert tool_result["ok"] is True
    assert tool_result["data"]["rows"][0] == {"region": "North", "sum_revenue": 3010, "share_pct": 70.33}
    second = llm.requests[1]["messages"]
    assert [m.kind for m in second] == ["user", "model_turn", "tool_results"]
    assert second[2].results[0].id == "c1"                # response id matches the call id
    assert result.tool_calls[0].ok


def test_tool_errors_are_returned_so_the_model_can_retry(orders, profile):
    llm = FakeLLM([call("aggregate_data", group_by=["regin"], metric="revenue"),
                   call("aggregate_data", call_id="c2", group_by=["region"], metric="revenue"),
                   text("ok")])
    result = run(llm, orders, profile)
    first = llm.last_tool_results(1)[0]
    assert first["ok"] is False and "Did you mean: region" in first["error"]
    assert [t.ok for t in result.tool_calls] == [False, True]


def test_parallel_calls_in_one_turn(orders, profile):
    both = LLMResponse(function_calls=[
        FunctionCall(id="a", name="distinct_values", args={"column": "product"}),
        FunctionCall(id="b", name="get_column_statistics", args={"column": "revenue"})],
        model_turn={"role": "model", "parts": []})
    llm = FakeLLM([both, text("done")])
    result = run(llm, orders, profile)
    results = llm.requests[1]["messages"][-1].results
    assert [r.id for r in results] == ["a", "b"]
    assert len(result.tool_calls) == 2


def test_chart_data_goes_to_ui_and_summary_to_model(sales):
    profile = profile_dataset(sales, "sales")
    llm = FakeLLM([call("create_chart", chart_type="line", title="Monthly revenue",
                        x="order_date", y="revenue"),
                   text("Revenue peaks in December.")])
    result = run(llm, sales, profile)

    assert len(result.charts) == 1
    assert len(result.charts[0]["records"]) == 24         # full data for the UI
    view = llm.last_tool_results()[0]
    assert view["chart_number"] == 1 and view["points"] == 24
    assert "records" not in view                          # too big to send to the model


def test_small_chart_numbers_are_shared_with_the_model(orders, profile):
    llm = FakeLLM([call("create_chart", chart_type="bar", title="t", x="region", y="revenue"),
                   text("ok")])
    run(llm, orders, profile)
    assert len(llm.last_tool_results()[0]["records"]) == 4


def test_identical_calls_are_served_from_cache(orders, profile):
    chart = dict(chart_type="bar", title="t", x="region", y="revenue")
    llm = FakeLLM([call("create_chart", **chart), call("create_chart", call_id="c2", **chart),
                   text("ok")])
    result = run(llm, orders, profile)
    assert [t.cached for t in result.tool_calls] == [False, True]
    assert len(result.charts) == 1                        # no duplicate chart
    assert "already made this exact call" in llm.last_tool_results()[0]["note"]


def test_step_limit_forces_a_final_answer_without_tools(orders, profile):
    looping = [call("distinct_values", call_id=str(i), column="product", limit=i + 1) for i in range(3)]
    llm = FakeLLM([*looping, text("Best effort answer")])
    result = run(llm, orders, profile, max_steps=3)

    assert result.stop_reason == "max_steps"
    assert result.answer == "Best effort answer"
    assert result.llm_calls == 4
    final = llm.requests[-1]
    assert final["allow_tools"] is False
    assert final["messages"][-1].text == FINAL_ANSWER_NUDGE


def test_malformed_call_gets_one_nudge(orders, profile):
    llm = FakeLLM([LLMResponse(finish_reason="MALFORMED_FUNCTION_CALL"), text("fixed")])
    result = run(llm, orders, profile)
    assert result.answer == "fixed"
    assert llm.requests[1]["messages"][-1].text == MALFORMED_CALL_NUDGE


def test_repeated_empty_responses_stop_gracefully(orders, profile):
    empty = LLMResponse(finish_reason="MALFORMED_FUNCTION_CALL")
    result = run(FakeLLM([empty, empty]), orders, profile)
    assert result.stop_reason == "empty"
    assert result.error


def test_llm_errors_become_a_friendly_result(orders, profile):
    def boom(*_):
        raise LLMError("Gemini API error 429: quota")
    result = run(FakeLLM([boom]), orders, profile)
    assert result.stop_reason == "llm_error"
    assert "429" in result.error


def test_events_are_emitted(orders, profile):
    events = []
    llm = FakeLLM([call("distinct_values", column="region"), text("ok")])
    run(llm, orders, profile, on_event=lambda kind, data: events.append(kind))
    assert events == ["llm_call", "tool_call", "tool_result", "llm_call", "done"]


def test_chat_history_is_included_and_capped():
    history = [ChatTurn(question=f"q{i}", answer=f"a{i}") for i in range(10)]
    messages = build_messages("new", history)
    assert messages[-1].text == "new"
    assert len(messages) == 6 * 2 + 1                     # HISTORY_TURNS default = 6
    assert messages[0].text == "q4"


def test_fit_to_size_shrinks_long_lists():
    data = {"rows": [{"x": i, "label": "y" * 20} for i in range(1000)]}
    small, truncated = _fit_to_size(data, 2000)
    assert truncated
    assert 0 < len(small["rows"]) < 1000
    assert _fit_to_size({"a": 1}, 2000) == ({"a": 1}, False)


def test_system_prompt_mentions_last_date(profile):
    prompt = build_system_prompt(profile)
    assert "2025-01-10" in prompt
    assert "revenue" in prompt
