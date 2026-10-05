"""Run the eval suite: ask every case, score the answers, save a report.

    python -m evals.run                    # all cases with Gemini (uses quota!)
    python -m evals.run --only yoy_growth follow_up
    python -m evals.run --fake             # check the harness itself, no API key
    python -m evals.run --feedback         # list answers you rated in the app

Run it after every prompt or tool change and compare pass rates. Reports are
saved in data/evals/ so you can diff runs. Each case costs ~2-5 model calls:
the whole suite fits comfortably in a free-tier day, not in a minute.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.agent import ChatTurn, run_agent  # noqa: E402
from core.config import settings  # noqa: E402
from core.llm import GeminiClient, LLMClient  # noqa: E402
from data_layer.ingest import ingest  # noqa: E402
from data_layer.store import Store  # noqa: E402
from evals.cases import CASES  # noqa: E402
from evals.scoring import score  # noqa: E402
from scripts.make_sample_data import make_sales  # noqa: E402


def sample_csv() -> bytes:
    """Always the default generated dataset: the cases are written for it."""
    return make_sales().to_csv(index=False, date_format="%Y-%m-%d").encode()


def run_case(case: dict, df, profile, llm: LLMClient) -> dict:
    history: list[ChatTurn] = []
    for q in case.get("history", []):
        previous = run_agent(q, df, profile, llm, history=history)
        history.append(ChatTurn(question=q, answer=previous.answer))
    result = run_agent(case["question"], df, profile, llm, history=history)
    return result.model_dump(mode="json")


def show_feedback() -> None:
    rated = Store().rated_requests()
    if not rated:
        print("No rated answers yet. Use 👍/👎 in the app.")
        return
    for r in rated:
        mark = "👍" if (r.rating or 0) > 0 else "👎"
        answer = (r.result or {}).get("answer", r.error or "")
        print(f"{mark} {r.question}\n   {answer[:200]}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the AI analyst eval suite.")
    parser.add_argument("--only", nargs="*", help="Case ids to run")
    parser.add_argument("--fake", action="store_true", help="Use a rule-based fake LLM (no API key)")
    parser.add_argument("--min-pass", type=float, default=0.0,
                        help="Exit with code 1 if the pass rate is below this (0-1)")
    parser.add_argument("--feedback", action="store_true", help="List rated answers and exit")
    args = parser.parse_args()

    if args.feedback:
        show_feedback()
        return

    cases = [c for c in CASES if not args.only or c["id"] in args.only]
    if not cases:
        sys.exit(f"No cases match {args.only}. Known: {[c['id'] for c in CASES]}")

    if args.fake:
        from tests.fakes import RuleBasedFakeLLM
        llm: LLMClient = RuleBasedFakeLLM()
        model = "fake"
    else:
        llm = GeminiClient()
        model = llm.model

    df, profile = ingest(sample_csv())
    print(f"Running {len(cases)} cases with {model}\n")

    rows, started = [], time.perf_counter()
    for case in cases:
        t0 = time.perf_counter()
        result = run_case(case, df, profile, llm)
        verdict = score(case, case["expect"](df), result)
        seconds = time.perf_counter() - t0
        failed = [c for c in verdict.checks if not c.passed]
        print(f"{'PASS' if verdict.passed else 'FAIL'}  {case['id']:<24} {seconds:5.1f}s  "
              f"{result['usage']['total']:>6,} tok")
        for c in failed:
            print(f"        ✗ {c.name} {c.detail}")
        if failed:
            print(f"        answer: {result['answer'][:300]}")
        rows.append({"id": case["id"], "question": case["question"], "passed": verdict.passed,
                     "checks": [vars(c) for c in verdict.checks], "answer": result["answer"],
                     "tool_calls": result["tool_calls"], "usage": result["usage"],
                     "stop_reason": result["stop_reason"], "seconds": round(seconds, 1)})

    passed = sum(r["passed"] for r in rows)
    rate = passed / len(rows)
    tokens = sum(r["usage"]["total"] for r in rows)
    print(f"\n{passed}/{len(rows)} passed ({rate:.0%}), {tokens:,} tokens, "
          f"{time.perf_counter() - started:.0f}s")

    report = settings.data_dir / "evals" / f"{datetime.now():%Y%m%d-%H%M%S}-{model}.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps({"model": model, "pass_rate": rate, "tokens": tokens,
                                  "cases": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Report: {report}")
    if rate < args.min_pass:
        sys.exit(1)


if __name__ == "__main__":
    main()
