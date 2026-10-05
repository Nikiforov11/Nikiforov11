"""The Inngest client and event names, shared by the worker (which runs
functions) and the Streamlit app (which sends events).

Connection settings come from environment variables the SDK reads itself:
  INNGEST_DEV=1                      talk to a local Dev Server (default here)
  INNGEST_BASE_URL=http://host:8288  where that Dev Server is (docker: http://inngest:8288)
  INNGEST_SERVE_ORIGIN=http://worker:8000  how the Dev Server reaches the worker
For Inngest Cloud you'd set INNGEST_DEV=0 plus INNGEST_EVENT_KEY / INNGEST_SIGNING_KEY.
"""
from __future__ import annotations

import logging
import os
from functools import lru_cache

import inngest
from pydantic import BaseModel, Field

APP_ID = "ai-analyst"

QUESTION_ASKED = "analyst/question.asked"
QUESTION_CANCELLED = "analyst/question.cancelled"
LLM_REQUESTED = "analyst/llm.requested"     # only used through step.invoke


class QuestionEvent(BaseModel):
    """Payload of QUESTION_ASKED. Small on purpose: ids, not data."""
    request_id: str
    session_id: str
    dataset_id: str
    question: str
    history: list[dict[str, str]] = Field(default_factory=list)


@lru_cache(maxsize=1)
def get_client() -> inngest.Inngest:
    is_production = os.getenv("INNGEST_DEV", "1").lower() in ("0", "false")
    return inngest.Inngest(app_id=APP_ID, is_production=is_production,
                           logger=logging.getLogger("uvicorn"))
