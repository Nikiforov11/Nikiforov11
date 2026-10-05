"""Chat with your sales data from the terminal.

    python cli.py data/sample_sales.csv                       # interactive
    python cli.py data/sample_sales.csv -q "Top 3 regions?"   # one question
    python cli.py data/sample_sales.csv --open                # open charts in the browser

Inside the chat:  /profile  /reset  /quit

Every run is saved as JSON in data/runs/: the question, each tool call with
its arguments and errors, token usage and timing. Reading these traces is
the fastest way to understand (and fix) what the agent did.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
import webbrowser
from datetime import datetime
from pathlib import Path

from core.agent import AgentResult, ChatTurn, run_agent
from core.config import settings
from core.llm import GeminiClient, LLMError
from data_layer.ingest import ingest
from data_layer.profiler import to_prompt_context
from tools.charts import build_figure

DIM, BOLD, RED, GREEN, RESET = "\033[2m", "\033[1m", "\033[31m", "\033[32m", "\033[0m"
if not sys.stdout.isatty():
    DIM = BOLD = RED = GREEN = RESET = ""


def short_args(args: dict) -> str:
    text = ", ".join(f"{k}={json.dumps(v, ensure_ascii=False)}" for k, v in args.items())
    return text if len(text) <= 140 else text[:137] + "..."


def print_event(kind: str, data: dict) -> None:
    if kind == "llm_call":
        print(f"{DIM}  · thinking (model call {data['step']}){RESET}")
    elif kind == "tool_call":
        print(f"{DIM}  → {data['name']}({short_args(data['args'])}){RESET}")
    elif kind == "tool_result" and not data["ok"]:
        print(f"{RED}  ✗ {data['error']}{RESET}")


def save_outputs(result: AgentResult, open_charts: bool) -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    for i, chart in enumerate(result.charts, 1):
        path = settings.data_dir / "charts" / f"{stamp}-{i}.html"
        path.parent.mkdir(parents=True, exist_ok=True)
        build_figure(chart).write_html(path, include_plotlyjs="cdn")
        print(f"{GREEN}  📊 Chart saved: {path}{RESET}")
        if open_charts:
            webbrowser.open(path.resolve().as_uri())

    trace = settings.data_dir / "runs" / f"{stamp}.json"
    trace.parent.mkdir(parents=True, exist_ok=True)
    trace.write_text(result.model_dump_json(indent=2), encoding="utf-8")


def ask(question: str, df, profile, llm, history: list[ChatTurn], open_charts: bool) -> None:
    result = run_agent(question, df, profile, llm, history=history, on_event=print_event)
    print(f"\n{BOLD}{result.answer}{RESET}\n")
    save_outputs(result, open_charts)
    tools_ok = sum(t.ok for t in result.tool_calls)
    print(f"{DIM}  {result.llm_calls} model calls · {tools_ok}/{len(result.tool_calls)} tool calls ok · "
          f"{result.usage.total:,} tokens · {result.duration_ms / 1000:.1f}s · {result.stop_reason}{RESET}\n")
    if result.error:
        print(f"{RED}  {result.error}{RESET}\n")
    if result.stop_reason == "answered":
        history.append(ChatTurn(question=question, answer=result.answer))


def main() -> None:
    parser = argparse.ArgumentParser(description="Ask questions about a sales CSV.")
    parser.add_argument("csv", help="Path to the CSV file")
    parser.add_argument("-q", "--question", help="Ask one question and exit")
    parser.add_argument("--open", action="store_true", help="Open charts in the browser")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show debug logs")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")

    if not Path(args.csv).is_file():
        sys.exit(f"{RED}File not found: {args.csv}{RESET}")
    df, profile = ingest(args.csv)
    print(f"{BOLD}Loaded {profile.rows:,} rows × {profile.columns} columns{RESET} "
          f"(dataset {profile.dataset_id})")
    print(f"  main date: {profile.primary_date or '-'} · main value: {profile.primary_metric or '-'}")
    for note in profile.cleaning_notes:
        print(f"{DIM}  {note}{RESET}")

    try:
        llm = GeminiClient()
    except LLMError as e:
        sys.exit(f"{RED}{e}{RESET}")
    print(f"{DIM}  model: {llm.model} · max {settings.gemini_rpm} requests/min{RESET}\n")

    history: list[ChatTurn] = []
    if args.question:
        ask(args.question, df, profile, llm, history, args.open)
        return

    print("Ask a question about your data. Commands: /profile /reset /quit\n")
    while True:
        try:
            question = input("you › ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question:
            continue
        if question in ("/quit", "/exit"):
            break
        if question == "/reset":
            history.clear()
            print("  Conversation memory cleared.\n")
            continue
        if question == "/profile":
            print(to_prompt_context(profile) + "\n")
            continue
        ask(question, df, profile, llm, history, args.open)


if __name__ == "__main__":
    main()
