"""Central configuration.

Every tunable value lives here and can be overridden from a `.env` file,
so you never have to hunt through the code to change a limit or a model name.
"""
import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _int(name: str, default: int) -> int:
    return int(os.getenv(name, default))


@dataclass(frozen=True)
class Settings:
    # Storage
    data_dir: Path = Path(os.getenv("DATA_DIR", PROJECT_ROOT / "data"))

    # LLM. Google renames Flash models often, so the model name is config,
    # never hard-coded. Check AI Studio for what your free key can use.
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    # Client-side rate limit: stay under your key's requests-per-minute quota.
    # (Phase 3 moves this job to Inngest's throttle.)
    gemini_rpm: int = _int("GEMINI_RPM", 10)
    llm_max_retries: int = _int("LLM_MAX_RETRIES", 3)

    # Agent loop
    max_agent_steps: int = _int("MAX_AGENT_STEPS", 6)        # model calls per question
    max_tool_response_chars: int = _int("MAX_TOOL_RESPONSE_CHARS", 8000)
    history_turns: int = _int("HISTORY_TURNS", 6)            # past Q&A pairs sent as context

    # Tool output limits: keep results small for the LLM context
    # and for Inngest step payloads.
    max_result_rows: int = _int("MAX_RESULT_ROWS", 50)
    default_top_n: int = _int("DEFAULT_TOP_N", 10)
    max_time_points: int = _int("MAX_TIME_POINTS", 400)
    max_scatter_points: int = _int("MAX_SCATTER_POINTS", 2000)

    # Data cleaning: share of values that must parse before a text
    # column is converted to numbers or dates.
    parse_threshold: float = float(os.getenv("PARSE_THRESHOLD", 0.9))
    # For dates like 03/04/2024 where no value proves the order
    # (no day > 12). European data: set DATE_DAYFIRST=true.
    date_dayfirst_default: bool = os.getenv("DATE_DAYFIRST", "false").lower() == "true"


settings = Settings()
