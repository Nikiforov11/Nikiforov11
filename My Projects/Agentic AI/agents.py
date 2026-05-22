"""The two Pydantic AI agents that power the pipeline.

Agent 1 -- Extraction Agent:  cleaned page text  ->  JobPosting
Agent 2 -- Validation Agent:  JobPosting         ->  ValidatedJobPosting

Both use Google Gemini. Pydantic AI's Google provider reads the API key from
the GEMINI_API_KEY (or GOOGLE_API_KEY) environment variable, which main.py
loads from .env.

The key idea: passing a Pydantic model as ``output_type`` makes Pydantic AI
inject that model's JSON schema into the request and validate the reply against
it. If the model returns something off-shape, the call is retried automatically.
That is what turns an unreliable chatbot into a strict data extractor.

The agents are built lazily (see ``_get_agents``) so this module can be
imported before the API key is loaded -- construction touches the provider and
would otherwise fail without a key.
"""

from functools import cache

from pydantic_ai import Agent

from models import JobPosting, ValidatedJobPosting

# One model name, reused by both agents. Flash is fast and free-tier friendly.
_MODEL = "google:gemini-2.5-flash"

_EXTRACTION_PROMPT = (
    "You extract structured data from the text of a single job posting.\n"
    "Rules:\n"
    "- Use ONLY information present in the text. Never guess or invent values.\n"
    "- If a field is genuinely not stated, leave it null/empty or use 'unknown'.\n"
    "- 'required_skills' must be concrete skills, tools and technologies "
    "(e.g. 'Python', 'AWS', 'SQL') -- not soft skills or full sentences.\n"
    "- For salary, only fill SalaryRange if the page actually states pay.\n"
    "- 'description_summary' must be a short, neutral paraphrase, not a copy."
)

_VALIDATION_PROMPT = (
    "You review and enrich a JobPosting that another agent extracted.\n"
    "Tasks:\n"
    "- Normalize 'required_skills': fix casing, remove duplicates and "
    "near-duplicates, drop anything that is not a real skill.\n"
    "- Sanity-check the salary range (min should not exceed max; flag if odd).\n"
    "- List in 'missing_fields' every field that is empty/null/unknown "
    "because the source page did not provide it.\n"
    "- Set 'confidence_score' (0.0-1.0): high when key fields are present and "
    "coherent, low when much is missing or looks unreliable.\n"
    "- Put short, useful observations in 'quality_notes'.\n"
    "Do not invent data. Keep correct fields unchanged inside 'posting'."
)


@cache
def _get_agents() -> tuple[Agent[None, JobPosting], Agent[None, ValidatedJobPosting]]:
    """Build both agents once, on first use (after the API key is loaded)."""
    extraction_agent = Agent(
        _MODEL,
        output_type=JobPosting,
        retries=2,
        system_prompt=_EXTRACTION_PROMPT,
    )
    validation_agent = Agent(
        _MODEL,
        output_type=ValidatedJobPosting,
        retries=2,
        system_prompt=_VALIDATION_PROMPT,
    )
    return extraction_agent, validation_agent


def extract_job(page_text: str) -> JobPosting:
    """Run the Extraction Agent on cleaned page text."""
    extraction_agent, _ = _get_agents()
    result = extraction_agent.run_sync(
        f"Extract the job posting from the following page text:\n\n{page_text}"
    )
    return result.output


def validate_job(posting: JobPosting) -> ValidatedJobPosting:
    """Run the Validation Agent on an already-extracted JobPosting."""
    _, validation_agent = _get_agents()
    result = validation_agent.run_sync(
        "Review, normalize and score this extracted job posting "
        f"(JSON):\n\n{posting.model_dump_json(indent=2)}"
    )
    return result.output
