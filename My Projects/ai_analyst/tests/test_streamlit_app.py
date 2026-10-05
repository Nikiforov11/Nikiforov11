"""Drive the real Streamlit page headlessly with AppTest (no browser)."""
import time
from pathlib import Path

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import app.runner as runner_module
from tests.fakes import RuleBasedFakeLLM

APP = str(Path(__file__).resolve().parent.parent / "app" / "streamlit_app.py")


@pytest.fixture
def at(tmp_settings, monkeypatch):
    monkeypatch.setattr("data_layer.store.settings", tmp_settings)
    monkeypatch.setenv("ANALYST_MODE", "direct")
    monkeypatch.setattr(runner_module, "GeminiClient", lambda: RuleBasedFakeLLM())
    st.cache_resource.clear()
    st.cache_data.clear()
    app = AppTest.from_file(APP, default_timeout=30)
    app.run()
    return app


def wait_for_answer(at, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        at.run()
        if not at.chat_input[0].disabled:
            return
        time.sleep(0.2)
    raise AssertionError("no answer in time")


def test_empty_state(at):
    assert not at.exception
    assert at.title[0].value == "Sales analyst"


def test_sample_data_question_and_answer(at):
    at.sidebar.button[0].click().run()                       # "Use sample data"
    assert at.title[0].value == "sample_sales.csv"
    suggestions = [b for b in at.button if (b.key or "").startswith("suggest-")]
    assert len(suggestions) >= 3

    at.chat_input[0].set_value("Which region sells the most?").run()
    wait_for_answer(at)
    assert not at.exception
    texts = [m.value for m in at.markdown]
    assert "Which region sells the most?" in texts
    assert any("top region" in t for t in texts)
    assert len(at.get("plotly_chart")) == 1
    assert len(at.sidebar.get("download_button")) == 1


def test_new_conversation_starts_empty(at):
    at.sidebar.button[0].click().run()
    at.chat_input[0].set_value("q1").run()
    wait_for_answer(at)
    new = next(b for b in at.sidebar.button if b.label == "New conversation")
    new.click().run()
    assert len(at.chat_message) == 0
