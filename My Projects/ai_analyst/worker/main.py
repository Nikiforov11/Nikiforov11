"""The worker: a FastAPI app that serves the Inngest functions.

    uvicorn worker.main:app --port 8000

The Inngest Dev Server calls POST /api/inngest to run steps; you never call
it yourself. /health is for docker-compose.
"""
from __future__ import annotations

import logging
import os

import inngest.fast_api
from fastapi import FastAPI

from worker.client import get_client
from worker.functions import create_functions

logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"),
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")

app = FastAPI(title="AI Analyst worker")
client = get_client()
functions = create_functions(client)
inngest.fast_api.serve(app, client, functions)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
