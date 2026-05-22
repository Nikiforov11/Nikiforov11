"""Fetch a web page and reduce it to clean text.

This module is deliberately *not* agentic -- it is plain Python. The LLM agents
should only ever see compact, boilerplate-free text, never raw HTML. That keeps
token usage (and cost) low and makes extraction far more accurate.
"""

from urllib.parse import parse_qs, urlparse

import httpx
import trafilatura
from bs4 import BeautifulSoup

# A real browser User-Agent. Many sites return 403 to the default httpx agent.
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
}

# Cap the text we hand to the LLM. Job pages rarely need more than this, and a
# hard cap protects us against a pathological page blowing up token cost.
_MAX_TEXT_CHARS = 12_000


class ScrapeError(Exception):
    """Raised when a page cannot be fetched or yields no usable text."""


def normalize_url(url: str) -> str:
    """Rewrite a LinkedIn feed/collection URL into its public job-view URL.

    LinkedIn has two kinds of job URLs:
      - .../jobs/collections/... or .../jobs/search/?currentJobId=<id>
        These are logged-in feed pages -- anonymous fetches hit a login wall.
      - .../jobs/view/<id>
        The public job-view page -- served in full to anonymous visitors.

    Both reference the same job via the numeric id, so when we see the former
    we rewrite it to the latter. Non-LinkedIn URLs are returned unchanged.
    """
    parsed = urlparse(url)
    if "linkedin.com" not in parsed.netloc.lower():
        return url

    # The job id lives in the currentJobId query parameter on feed/search URLs.
    job_ids = parse_qs(parsed.query).get("currentJobId")
    if job_ids and job_ids[0].isdigit():
        return f"https://www.linkedin.com/jobs/view/{job_ids[0]}"

    return url


def fetch_url(url: str) -> str:
    """Download a URL and return its raw HTML.

    Raises ScrapeError on timeouts, network errors, or non-2xx responses
    (e.g. 403 bot-block, 404 not found).
    """
    try:
        response = httpx.get(
            url,
            headers=_HEADERS,
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        raise ScrapeError(
            f"Site returned HTTP {exc.response.status_code} for {url}. "
            "The page may be blocked, removed, or require a login."
        ) from exc
    except httpx.TimeoutException as exc:
        raise ScrapeError(f"Timed out while fetching {url}.") from exc
    except httpx.HTTPError as exc:
        raise ScrapeError(f"Network error while fetching {url}: {exc}") from exc

    return response.text


def clean_html_to_text(html: str) -> str:
    """Strip nav, ads and boilerplate from HTML, returning clean main-content text.

    Uses trafilatura for content extraction and falls back to a plain
    BeautifulSoup text dump if trafilatura finds nothing. The result is
    truncated to _MAX_TEXT_CHARS.
    """
    text = trafilatura.extract(
        html,
        include_comments=False,
        include_tables=True,
        favor_recall=True,
    )

    if not text:
        # Fallback: drop scripts/styles and take the visible text.
        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator="\n", strip=True)

    text = (text or "").strip()
    if not text:
        raise ScrapeError("Page fetched, but no readable text could be extracted.")

    return text[:_MAX_TEXT_CHARS]


def scrape(url: str) -> str:
    """Convenience wrapper: fetch a URL and return its cleaned text."""
    return clean_html_to_text(fetch_url(url))
