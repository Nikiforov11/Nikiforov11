"""End-to-end check of the Inngest path, without a Gemini key.

1. Start the Dev Server in another terminal:
       npx inngest-cli@latest dev -u http://127.0.0.1:8000/api/inngest --no-discovery
2. Run:
       python scripts/e2e_inngest.py

It starts the worker (with a rule-based fake LLM instead of Gemini), sends a
question through the real Dev Server, and waits for the answer in the store.
Then open http://localhost:8288 → Runs to see the steps it produced.
"""
from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

os.environ.setdefault("DATA_DIR", tempfile.mkdtemp(prefix="analyst-e2e-"))
os.environ.setdefault("INNGEST_DEV", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402

import worker.functions as functions  # noqa: E402
from app.runner import InngestRunner  # noqa: E402
from data_layer.ingest import ingest  # noqa: E402
from data_layer.store import Store  # noqa: E402
from scripts.make_sample_data import make_sales  # noqa: E402
from tests.fakes import RuleBasedFakeLLM  # noqa: E402

PORT = int(os.getenv("WORKER_PORT", 8000))


def wait_until_synced(timeout: float = 30) -> None:
    """Events sent before the Dev Server knows our functions trigger nothing,
    so wait until it has synced the app (it polls the worker every few seconds)."""
    import httpx
    base = os.getenv("INNGEST_BASE_URL", "http://127.0.0.1:8288")
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            fns = httpx.get(f"{base}/dev", timeout=2).json().get("functions") or []
            if any(f.get("slug") == "ai-analyst-answer-question" for f in fns):
                return
        except httpx.HTTPError:
            pass
        time.sleep(1)
    sys.exit("The Dev Server never synced the worker. Is it running with "
             f"-u http://127.0.0.1:{PORT}/api/inngest ?")


def main() -> None:
    functions.get_llm.cache_clear()
    functions.get_llm = lambda: RuleBasedFakeLLM()          # no API key needed

    from worker.main import app
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.1)
    wait_until_synced()

    csv = make_sales(400).to_csv(index=False, date_format="%Y-%m-%d").encode()
    _, profile = ingest(csv)
    store = Store()
    session = store.create_session(profile.dataset_id)
    request = InngestRunner(store).submit(session.session_id, profile.dataset_id,
                                          "Which region sells the most?")
    print(f"sent request {request.request_id} (event {request.event_id})")

    deadline = time.time() + 90
    while time.time() < deadline:
        request = store.get_request(request.request_id)
        if request.is_final:
            break
        time.sleep(1)

    print("status:", request.status)
    for e in store.list_events(request.request_id):
        print("  event:", {k: v for k, v in e.items() if k != "ts"})
    if request.status != "done":
        sys.exit(f"FAILED: {request.error}")
    result = request.result
    print("answer:", result["answer"])
    print("tools:", [t["name"] for t in result["tool_calls"]], "charts:", len(result["charts"]))
    assert result["stop_reason"] == "answered" and len(result["charts"]) == 1
    print("E2E OK")
    server.should_exit = True


if __name__ == "__main__":
    main()
