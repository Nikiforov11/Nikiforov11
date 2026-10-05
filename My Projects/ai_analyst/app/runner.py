"""How the UI gets a question answered.

Two runners with the same interface. Both write progress and results to the
SQLite store, and the UI only ever reads the store, so it doesn't care which
runner is active.

  DirectRunner   runs the agent in a background thread of the Streamlit
                 process. No Docker, no worker: quickest way to try the app.
  InngestRunner  sends an "analyst/question.asked" event. The worker picks it
                 up through the Inngest Dev Server. Durable, retried, throttled,
                 and every step is visible at http://localhost:8288.

Choose with ANALYST_MODE=direct|inngest (default: direct).
"""
from __future__ import annotations

import logging
import os
import threading
from typing import Protocol

from core.agent import ChatTurn, run_agent
from core.llm import GeminiClient, LLMClient, LLMError
from data_layer.ingest import load_profile
from data_layer.loader import load_dataset
from data_layer.store import Request, Store

log = logging.getLogger(__name__)


class Runner(Protocol):
    name: str

    def submit(self, session_id: str, dataset_id: str, question: str) -> Request: ...

    def cancel(self, request: Request) -> None: ...


class DirectRunner:
    name = "direct"

    def __init__(self, store: Store, llm: LLMClient | None = None):
        self.store = store
        self._llm = llm
        self._cancelled: set[str] = set()

    @property
    def llm(self) -> LLMClient:
        if self._llm is None:
            self._llm = GeminiClient()
        return self._llm

    def submit(self, session_id: str, dataset_id: str, question: str) -> Request:
        history = [ChatTurn(**t) for t in self.store.chat_history(session_id)]
        request = self.store.create_request(session_id, question)
        thread = threading.Thread(target=self._run, daemon=True,
                                  args=(request.request_id, dataset_id, question, history))
        thread.start()
        return request

    def _run(self, request_id: str, dataset_id: str, question: str, history: list[ChatTurn]) -> None:
        store = self.store
        store.mark_running(request_id)
        try:
            df, profile = load_dataset(dataset_id), load_profile(dataset_id)
            result = run_agent(question, df, profile, self.llm, history=history,
                               on_event=lambda kind, data: store.add_event(request_id, kind, data))
            store.finish_request(request_id, "done", result=result.model_dump(mode="json"))
        except LLMError as e:
            store.finish_request(request_id, "failed", error=str(e))
        except Exception as e:  # noqa: BLE001 - surface anything to the UI
            log.exception("Direct run failed")
            store.finish_request(request_id, "failed", error=f"{type(e).__name__}: {e}")

    def cancel(self, request: Request) -> None:
        # A thread can't be killed safely; we just stop waiting for it.
        # finish_request ignores the late result because 'cancelled' is final.
        self.store.finish_request(request.request_id, "cancelled", error="Stopped by user")


class InngestRunner:
    name = "inngest"

    def __init__(self, store: Store):
        from worker.client import get_client
        self.store = store
        self.client = get_client()

    def submit(self, session_id: str, dataset_id: str, question: str) -> Request:
        import inngest
        from worker.client import QUESTION_ASKED, QuestionEvent

        history = self.store.chat_history(session_id)
        request = self.store.create_request(session_id, question)
        event = QuestionEvent(request_id=request.request_id, session_id=session_id,
                              dataset_id=dataset_id, question=question, history=history)
        try:
            [event_id] = self.client.send_sync(inngest.Event(name=QUESTION_ASKED,
                                                             data=event.model_dump()))
            self.store.set_event_id(request.request_id, event_id)
        except Exception as e:  # noqa: BLE001
            self.store.finish_request(
                request.request_id, "failed",
                error=f"Could not reach the Inngest Dev Server ({e}). Is it running? "
                      "Start it, or set ANALYST_MODE=direct.")
        return self.store.get_request(request.request_id)

    def cancel(self, request: Request) -> None:
        import inngest
        from worker.client import QUESTION_CANCELLED

        self.store.finish_request(request.request_id, "cancelled", error="Stopped by user")
        try:
            self.client.send_sync(inngest.Event(name=QUESTION_CANCELLED,
                                                data={"request_id": request.request_id}))
        except Exception:  # noqa: BLE001
            log.warning("Could not send the cancel event", exc_info=True)


def make_runner(store: Store, mode: str | None = None) -> Runner:
    mode = (mode or os.getenv("ANALYST_MODE", "direct")).lower()
    return InngestRunner(store) if mode == "inngest" else DirectRunner(store)
