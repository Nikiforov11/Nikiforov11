"""CLI orchestrator for the Strict Web Scraper & Entity Extractor.

Pipeline:
    URL  -->  fetch + clean (scraper.py)
         -->  Extraction Agent      -> JobPosting          (agents.py)
         -->  Validation Agent      -> ValidatedJobPosting  (agents.py)
         -->  pretty JSON to stdout + saved file in outputs/

Usage:
    python main.py <job-posting-url>
"""

import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

from scraper import ScrapeError, normalize_url, scrape

OUTPUT_DIR = Path(__file__).parent / "outputs"


def _slugify(url: str) -> str:
    """Turn a URL into a safe-ish filename stem."""
    slug = re.sub(r"^https?://", "", url)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", slug).strip("-").lower()
    return (slug[:80] or "job") + ".json"


def _check_api_key() -> None:
    """Exit early with a clear message if the Gemini key is not configured."""
    if not os.getenv("GEMINI_API_KEY"):
        sys.exit(
            "Error: GEMINI_API_KEY is not set.\n"
            "Copy .env.example to .env and add your key "
            "(get one free at https://aistudio.google.com/apikey)."
        )


def run(url: str) -> None:
    """Run the full pipeline for a single URL."""
    _check_api_key()

    # Importing agents here (after the key check) avoids a confusing import-time
    # failure when the key is missing.
    from agents import extract_job, validate_job

    # A LinkedIn feed/collection URL can't be scraped anonymously; rewrite it to
    # the public job-view URL, which can.
    scrape_url = normalize_url(url)
    if scrape_url != url:
        print(f"Rewrote LinkedIn URL to public job-view page: {scrape_url}")

    print(f"[1/3] Fetching and cleaning: {scrape_url}")
    try:
        page_text = scrape(scrape_url)
    except ScrapeError as exc:
        sys.exit(f"Could not scrape the page: {exc}")

    print("[2/3] Extraction Agent: pulling structured fields...")
    try:
        posting = extract_job(page_text)
    except Exception as exc:  # noqa: BLE001 - surface any agent/model failure cleanly
        sys.exit(f"Extraction Agent failed: {exc}")

    print("[3/3] Validation Agent: normalizing and scoring...")
    try:
        result = validate_job(posting)
    except Exception as exc:  # noqa: BLE001
        sys.exit(f"Validation Agent failed: {exc}")

    json_output = result.model_dump_json(indent=2)
    print("\n=== Result ===")
    print(json_output)

    OUTPUT_DIR.mkdir(exist_ok=True)
    out_path = OUTPUT_DIR / _slugify(scrape_url)
    out_path.write_text(json_output, encoding="utf-8")
    print(f"\nSaved to: {out_path}")


def main() -> None:
    load_dotenv(Path(__file__).parent / ".env")

    if len(sys.argv) != 2:
        sys.exit("Usage: python main.py <job-posting-url>")

    run(sys.argv[1])


if __name__ == "__main__":
    main()
