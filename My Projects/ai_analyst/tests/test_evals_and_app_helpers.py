import pytest

from app.report import build_report, markdown_to_html
from app.suggestions import suggest_questions
from data_layer.ingest import ingest
from data_layer.profiler import apply_overrides, profile_dataset
from data_layer.store import Request
from evals.cases import CASES
from evals.run import sample_csv
from evals.scoring import contains_number, extract_numbers, score
from core.schemas import ColumnRole


# ---- scoring --------------------------------------------------------------- #
@pytest.mark.parametrize("text, expected", [
    ("Revenue was $1,140,726.75", 1140726.75),
    ("Ingresos: 1.140.726,75 €", 1140726.75),
    ("about 1.14 million", 1140000),
    ("roughly 1.1M", 1100000),
    ("grew 15.7%", 15.7),
    ("2,5 millones", 2500000),
])
def test_numbers_are_found_in_any_common_format(text, expected):
    assert any(abs(n - expected) < 1e-6 for n in extract_numbers(text))


def test_contains_number_tolerance():
    assert contains_number("about 1.14 million", 1140726.75, rel_tol=0.01)
    assert not contains_number("about 1.3 million", 1140726.75, rel_tol=0.01)


def test_score_combines_checks():
    case = {"id": "x"}
    result = {"answer": "East leads with 1,000.", "stop_reason": "answered", "charts": [],
              "tool_calls": [{"name": "aggregate_data", "ok": True}]}
    good = score(case, {"numbers": [1000], "mentions": ["east"],
                        "uses_tools_any": ["aggregate_data"], "chart": False}, result)
    assert good.passed
    bad = score(case, {"numbers": [2000], "chart": True}, result)
    assert not bad.passed and len([c for c in bad.checks if not c.passed]) == 2


def test_every_eval_case_computes_its_expectations(tmp_settings):
    df, _ = ingest(sample_csv())
    ids = [c["id"] for c in CASES]
    assert len(ids) == len(set(ids))
    for case in CASES:
        expected = case["expect"](df)
        assert expected, case["id"]


# ---- report ---------------------------------------------------------------- #
def test_markdown_to_html_basics():
    out = markdown_to_html("**East** leads.\n\n- one\n- *two*\n<script>")
    assert "<strong>East</strong>" in out
    assert "<ul><li>one</li><li><em>two</em></li></ul>" in out
    assert "&lt;script&gt;" in out


def test_report_includes_answers_and_charts():
    chart = {"chart_type": "bar", "title": "t", "x_field": "r", "y_field": "v",
             "color_field": None, "records": [{"r": "a", "v": 1}]}
    done = Request(request_id="1", session_id="s", question="Q?", status="done", created_at="t",
                   result={"answer": "A.", "charts": [chart],
                           "tool_calls": [{"name": "aggregate_data", "args": {}, "ok": True}]})
    failed = Request(request_id="2", session_id="s", question="Q2?", status="failed", created_at="t")
    page = build_report([done, failed], "data.csv")
    assert "Q?" in page and "<p>A.</p>" in page and "plotly" in page and "No answer" in page


# ---- suggestions & overrides ------------------------------------------------ #
def test_suggestions_use_real_column_meanings(sales):
    questions = suggest_questions(profile_dataset(sales, "s"))
    assert any("revenue" in q and "region" in q for q in questions)
    assert any("2023 to 2024" in q for q in questions)


def test_role_overrides(sales):
    profile = profile_dataset(sales, "s")
    updated = apply_overrides(profile, {"channel": "region"}, primary_metric="unit_price")
    assert updated.column("channel").role == ColumnRole.REGION
    assert updated.primary_metric == "unit_price"
    assert profile.column("channel").role == ColumnRole.CHANNEL     # original untouched
    assert apply_overrides(profile, primary_date="").primary_date is None
