"""Streamlit interface.

    streamlit run app/streamlit_app.py                           # direct mode
    ANALYST_MODE=inngest streamlit run app/streamlit_app.py      # through the worker

The page never runs the agent itself. It asks a Runner to submit the
question, then reads progress and results from the SQLite store. That's why
the same UI works with the in-process runner and with Inngest.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))   # allow `streamlit run app/...`

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402

from app.report import build_report  # noqa: E402
from app.runner import Runner, make_runner  # noqa: E402
from app.suggestions import suggest_questions  # noqa: E402
from core.config import settings  # noqa: E402
from core.schemas import ColumnKind, ColumnRole, DatasetProfile  # noqa: E402
from data_layer.ingest import ingest, load_profile, save_profile  # noqa: E402
from data_layer.loader import load_dataset  # noqa: E402
from data_layer.profiler import apply_overrides  # noqa: E402
from data_layer.store import Request, Store  # noqa: E402
from scripts.make_sample_data import make_sales  # noqa: E402
from tools.charts import build_figure  # noqa: E402

st.set_page_config(page_title="Sales analyst", page_icon="📈", layout="wide")

TOOL_LABELS = {
    "aggregate_data": "Grouping and totalling",
    "time_series": "Building a time series",
    "compare_periods": "Comparing periods",
    "distinct_values": "Checking the exact values",
    "get_column_statistics": "Summarizing a column",
    "create_chart": "Drawing a chart",
}
INNGEST_DASHBOARD = os.getenv("INNGEST_DASHBOARD_URL", "http://localhost:8288")


# --------------------------------------------------------------------------- #
# Resources
# --------------------------------------------------------------------------- #
@st.cache_resource
def get_store() -> Store:
    return Store()


@st.cache_resource
def get_runner() -> Runner:
    return make_runner(get_store())


@st.cache_data(show_spinner=False)
def get_dataframe(dataset_id: str) -> pd.DataFrame:
    return load_dataset(dataset_id)


store, runner = get_store(), get_runner()
state = st.session_state
state.setdefault("dataset_id", None)
state.setdefault("dataset_name", None)
state.setdefault("session_id", None)
state.setdefault("pending", None)
state.setdefault("upload_id", None)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def md_safe(text: str) -> str:
    """'$' starts LaTeX in Streamlit markdown, which mangles '$1,200 and $300'."""
    return text.replace("$", r"\$")


def open_dataset(raw: bytes, name: str) -> None:
    with st.spinner("Reading and profiling the file…"):
        _, profile = ingest(raw)
    if profile.dataset_id != state.dataset_id:
        state.dataset_id, state.dataset_name = profile.dataset_id, name
        sessions = store.list_sessions(profile.dataset_id)
        state.session_id = sessions[0].session_id if sessions else \
            store.create_session(profile.dataset_id).session_id
        state.pending = None


def submit(question: str) -> None:
    if not store.list_requests(state.session_id):
        store.set_session_title(state.session_id, question[:60])
    request = runner.submit(state.session_id, state.dataset_id, question)
    state.pending = None if request.is_final else request.request_id


def describe_event(e: dict) -> str | None:
    kind = e["kind"]
    if kind == "llm_call":
        retry = f" (attempt {e['attempt']})" if e.get("attempt", 1) > 1 else ""
        return f"Thinking{retry}…"
    if kind == "tool_call":
        return f"{TOOL_LABELS.get(e['name'], e['name'])}…"
    if kind == "tool_result" and not e.get("ok"):
        return f"⚠️ {e.get('error')} Retrying with corrected arguments."
    if kind == "rate_limited":
        return f"Free-tier limit reached. Waiting {e.get('retry_in_s', 30)}s before retrying."
    return None


# --------------------------------------------------------------------------- #
# Sidebar
# --------------------------------------------------------------------------- #
def sidebar(profile: DatasetProfile | None) -> None:
    with st.sidebar:
        st.header("Your data")
        uploaded = st.file_uploader("Upload a sales CSV", type=["csv", "txt"])
        if uploaded is not None and uploaded.file_id != state.upload_id:
            state.upload_id = uploaded.file_id
            open_dataset(uploaded.getvalue(), uploaded.name)
            st.rerun()
        if st.button("Use sample data", width="stretch"):
            raw = make_sales().to_csv(index=False, date_format="%Y-%m-%d").encode()
            open_dataset(raw, "sample_sales.csv")
            st.rerun()

        if profile is None:
            return

        st.caption(f"**{state.dataset_name}**: {profile.rows:,} rows, {profile.columns} columns")
        if profile.cleaning_notes:
            with st.expander("What I changed while reading the file"):
                for note in profile.cleaning_notes:
                    st.markdown(f"- {md_safe(note)}")
        column_meanings(profile)
        conversations(profile)
        engine_info()


def column_meanings(profile: DatasetProfile) -> None:
    with st.expander("Column meanings"):
        st.caption("The assistant relies on these. Fix any that are wrong.")
        table = pd.DataFrame([{"column": c.name, "type": c.kind.value, "meaning": c.role.value}
                              for c in profile.column_profiles])
        edited = st.data_editor(
            table, hide_index=True, disabled=["column", "type"], key=f"roles-{profile.dataset_id}",
            column_config={"meaning": st.column_config.SelectboxColumn(
                options=[r.value for r in ColumnRole], required=True)})
        dates = [c.name for c in profile.column_profiles if c.kind == ColumnKind.DATETIME]
        numbers = [c.name for c in profile.column_profiles if c.kind == ColumnKind.NUMERIC]
        main_date = st.selectbox("Main date", [None, *dates],
                                 index=([None, *dates].index(profile.primary_date)
                                        if profile.primary_date in dates else 0))
        main_metric = st.selectbox("Main sales value", [None, *numbers],
                                   index=([None, *numbers].index(profile.primary_metric)
                                          if profile.primary_metric in numbers else 0))
        if st.button("Save column meanings", width="stretch"):
            roles = dict(zip(edited["column"], edited["meaning"]))
            save_profile(apply_overrides(profile, roles, main_date or "", main_metric or ""))
            st.toast("Column meanings saved.")
            st.rerun()


def conversations(profile: DatasetProfile) -> None:
    st.subheader("Conversations")
    sessions = store.list_sessions(profile.dataset_id)
    labels = {s.session_id: (s.title or "New conversation") for s in sessions}
    if sessions:
        ids = list(labels)
        current = ids.index(state.session_id) if state.session_id in ids else 0
        chosen = st.radio("Conversations", ids, index=current, format_func=labels.get,
                          label_visibility="collapsed")
        if chosen != state.session_id:
            state.session_id, state.pending = chosen, None
            st.rerun()
    if st.button("New conversation", width="stretch"):
        state.session_id = store.create_session(profile.dataset_id).session_id
        state.pending = None
        st.rerun()

    requests = store.list_requests(state.session_id) if state.session_id else []
    if any(r.status == "done" for r in requests):
        st.download_button("Download report (HTML)", width="stretch",
                           data=build_report(requests, state.dataset_name or profile.dataset_id),
                           file_name="sales-analysis.html", mime="text/html")


def engine_info() -> None:
    st.divider()
    if runner.name == "inngest":
        st.caption("Questions run on the Inngest worker.")
        st.link_button("Open the Inngest dashboard", INNGEST_DASHBOARD, width="stretch")
    else:
        st.caption("Questions run inside this app. Set ANALYST_MODE=inngest to use the worker.")
        if not settings.gemini_api_key:
            st.warning("GEMINI_API_KEY is missing. Add it to your .env file and restart.")


# --------------------------------------------------------------------------- #
# Chat
# --------------------------------------------------------------------------- #
def render_answer(request: Request) -> None:
    result = request.result
    st.markdown(md_safe(result["answer"]))
    for i, chart in enumerate(result.get("charts", [])):
        st.plotly_chart(build_figure(chart), key=f"chart-{request.request_id}-{i}")

    calls = result.get("tool_calls", [])
    if calls:
        with st.expander("How this was calculated"):
            for c in calls:
                status = "✓" if c["ok"] else "✗"
                cached = " (reused)" if c.get("cached") else ""
                st.markdown(f"{status} **{TOOL_LABELS.get(c['name'], c['name'])}**{cached} "
                            f"`{c['name']}`")
                st.code(json.dumps(c["args"], indent=2, ensure_ascii=False), language="json")
                if c.get("error"):
                    st.caption(md_safe(c["error"]))
                for w in c.get("warnings", []):
                    st.caption(md_safe(w))

    usage = result.get("usage", {})
    seconds = (result.get("duration_ms") or 0) / 1000
    left, right = st.columns([4, 1])
    left.caption(f"{result.get('llm_calls', 0)} model calls, {len(calls)} tool calls, "
                 f"{usage.get('total', 0):,} tokens, {seconds:.1f}s")
    with right:
        default = None if request.rating is None else (1 if request.rating > 0 else 0)
        choice = st.feedback("thumbs", key=f"fb-{request.request_id}", default=default)
        if choice is not None and choice != default:
            store.set_feedback(request.request_id, 1 if choice == 1 else -1)


@st.fragment(run_every=1.0)
def live_progress(request_id: str) -> None:
    request = store.get_request(request_id)
    if request is None or request.is_final:
        state.pending = None
        st.rerun()
        return
    lines = [d for d in (describe_event(e) for e in store.list_events(request_id)) if d]
    label = lines[-1] if lines else ("Waiting for the worker…" if runner.name == "inngest"
                                     else "Starting…")
    with st.status(label, expanded=False):
        for line in lines:
            st.write(line)
    if st.button("Stop", key=f"stop-{request_id}"):
        runner.cancel(request)
        state.pending = None
        st.rerun()


def render_request(request: Request) -> None:
    with st.chat_message("user"):
        st.markdown(md_safe(request.question))
    with st.chat_message("assistant", avatar="📈"):
        if request.status in ("queued", "running"):
            if request.request_id == state.pending:
                live_progress(request.request_id)
            else:
                st.caption("Still running in the background. Refresh to check.")
        elif request.status == "failed":
            st.error(f"This question failed: {request.error}")
        elif request.status == "cancelled":
            st.caption("Stopped.")
        else:
            render_answer(request)


def empty_state(profile: DatasetProfile) -> None:
    st.markdown("Ask anything about this data. Some ideas:")
    for i, q in enumerate(suggest_questions(profile)):
        if st.button(q, key=f"suggest-{i}"):
            submit(q)
            st.rerun()


def main() -> None:
    profile = load_profile(state.dataset_id) if state.dataset_id else None
    sidebar(profile)

    if profile is None:
        st.title("Sales analyst")
        st.markdown("Upload a sales CSV in the sidebar, or try the sample data. "
                    "Then ask questions in plain language and get answers, tables and charts "
                    "computed from your file.")
        return

    st.title(state.dataset_name or "Sales analyst")
    with st.expander("Preview the data"):
        st.dataframe(get_dataframe(state.dataset_id).head(100), hide_index=True)

    requests = store.list_requests(state.session_id)
    pending = next((r for r in requests if r.request_id == state.pending), None)
    if state.pending and (pending is None or pending.is_final):
        state.pending = None          # finished while we weren't looking (e.g. a sidebar click)
    if not requests:
        empty_state(profile)
    for request in requests:
        render_request(request)

    question = st.chat_input("Ask about your sales", disabled=state.pending is not None)
    if question:
        submit(question)
        st.rerun()


main()
