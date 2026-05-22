# Strict Web Scraper & Entity Extractor

An **Agentic AI** tool that takes a job-posting URL and returns **strictly
structured JSON** — not free-form chatbot text.

Most LLM scrapers are unreliable because the model replies with prose. This
project uses **[Pydantic AI](https://ai.pydantic.dev/)** to *constrain* the LLM:
the expected data shape is a Pydantic model, passed as the agent `output_type`,
so every reply is validated against it (and retried if it does not fit).

## How it works — 2 agents

```
URL ──► fetch + clean (plain Python, no LLM)
        │   httpx downloads the page, trafilatura strips nav/ads/boilerplate
        ▼
    [ Agent 1 — Extraction Agent ]   cleaned text ──► JobPosting
        │   pulls raw fields, constrained by output_type
        ▼
    [ Agent 2 — Validation Agent ]   JobPosting  ──► ValidatedJobPosting
        │   normalizes skills, sanity-checks salary, flags missing
        │   fields, assigns a confidence score
        ▼
    pretty JSON  →  stdout  +  outputs/<slug>.json
```

| File | Role |
|------|------|
| `models.py`  | Pydantic models — the strict data contract |
| `scraper.py` | Fetch a URL + clean HTML to text (no LLM) |
| `agents.py`  | The 2 Pydantic AI agents |
| `main.py`    | CLI orchestrator |

## Setup

From the repository's shared virtual environment:

```powershell
pip install -r "My Projects/Agentic AI/strict_web_scraper/requirements.txt"
```

Get a **free** Gemini API key at <https://aistudio.google.com/apikey>, then:

```powershell
cd "My Projects/Agentic AI/strict_web_scraper"
copy .env.example .env
# edit .env and set GEMINI_API_KEY
```

## Usage

```powershell
python main.py "<job-posting-url>"
```

The structured result is printed and saved to `outputs/`. A verified working
example (server-rendered Greenhouse posting):

```powershell
python main.py "https://job-boards.greenhouse.io/gitlab/jobs/8503792002"
```

## Example output

```json
{
  "posting": {
    "job_title": "Senior Backend Engineer",
    "company": "Acme Inc.",
    "location": "Remote (EU)",
    "remote": "remote",
    "employment_type": "full-time",
    "experience_level": "5+ years",
    "required_skills": ["Python", "PostgreSQL", "AWS", "Docker"],
    "salary_range": {
      "min_amount": 80000,
      "max_amount": 110000,
      "currency": "EUR",
      "period": "yearly"
    },
    "description_summary": "Build and scale the company's payment APIs.",
    "posted_date": "3 days ago"
  },
  "confidence_score": 0.9,
  "missing_fields": [],
  "quality_notes": ["Skill list normalized; salary range is consistent."]
}
```

When a field is genuinely absent from the page it stays `null` — the agents are
instructed never to invent data, and the second agent reports it in
`missing_fields`.

## LinkedIn URLs

LinkedIn has two kinds of job URLs:

- **Feed / collection URLs** (`.../jobs/collections/...?currentJobId=<id>`,
  `.../jobs/search/?currentJobId=<id>`) are logged-in pages — an anonymous fetch
  hits a login wall and yields almost nothing.
- **Public job-view URLs** (`.../jobs/view/<id>`) are served in full to anyone,
  and the scraper extracts them well.

Both point at the same job via the numeric id, so the tool **automatically
rewrites** a feed/collection URL to its `/jobs/view/<id>` form before scraping.
You can paste either kind.

## Scope & limitations

- **Works well on:** public, server-rendered job postings — Greenhouse
  (`job-boards.greenhouse.io/...`), Lever (`jobs.lever.co/...`), LinkedIn
  public job-view pages, and most company career pages. These return full HTML
  to a plain HTTP request.
- **Does not work on** login-walled or JavaScript-only pages (e.g. LinkedIn feed
  views that can't be mapped to a job id). Scraping behind a login would also
  breach those sites' Terms of Service.
- Some boards (e.g. RemoteOK, WeWorkRemotely) serve listing pages but return
  HTTP 403 or JavaScript-only content for individual job pages — the scraper
  reports a clear error rather than crashing.
- This is a CLI portfolio project — no web UI, no database.
