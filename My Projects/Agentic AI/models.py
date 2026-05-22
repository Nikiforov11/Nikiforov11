"""Pydantic models that define the strict shape of the extracted data.

These models are the contract between the LLM and our program. Pydantic AI
uses them as the agent ``output_type``, so the LLM is *forced* to return data
that fits these classes -- otherwise the call fails and is retried.

The ``description=`` text on every field is not just documentation: Pydantic AI
sends it to the model as part of the JSON schema, so it doubles as a per-field
extraction instruction.
"""

from enum import Enum

from pydantic import BaseModel, Field


class EmploymentType(str, Enum):
    """How the job is contracted."""

    FULL_TIME = "full-time"
    PART_TIME = "part-time"
    CONTRACT = "contract"
    INTERNSHIP = "internship"
    UNKNOWN = "unknown"


class RemoteType(str, Enum):
    """Where the work is physically done."""

    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class SalaryPeriod(str, Enum):
    """The time unit a salary figure is quoted per."""

    YEARLY = "yearly"
    MONTHLY = "monthly"
    HOURLY = "hourly"
    UNKNOWN = "unknown"


class SalaryRange(BaseModel):
    """A pay range. Every field is optional because postings often omit pay."""

    min_amount: int | None = Field(
        default=None, description="Lower bound of the salary, as a plain number."
    )
    max_amount: int | None = Field(
        default=None, description="Upper bound of the salary, as a plain number."
    )
    currency: str | None = Field(
        default=None, description="Currency code, e.g. 'USD', 'EUR', 'GBP'."
    )
    period: SalaryPeriod = Field(
        default=SalaryPeriod.UNKNOWN, description="The period the salary is quoted per."
    )


class JobPosting(BaseModel):
    """Raw structured data extracted from a single job posting.

    This is the output_type of the Extraction Agent.
    """

    job_title: str = Field(description="The job title, e.g. 'Senior Backend Engineer'.")
    company: str | None = Field(
        default=None, description="The hiring company's name."
    )
    location: str | None = Field(
        default=None, description="Job location as written, e.g. 'Berlin, Germany'."
    )
    remote: RemoteType = Field(
        default=RemoteType.UNKNOWN, description="Whether the role is remote, hybrid or onsite."
    )
    employment_type: EmploymentType = Field(
        default=EmploymentType.UNKNOWN, description="Full-time, part-time, contract, etc."
    )
    experience_level: str | None = Field(
        default=None,
        description="Required seniority/experience, e.g. 'Junior', '5+ years', 'Lead'.",
    )
    required_skills: list[str] = Field(
        default_factory=list,
        description="Concrete skills, tools and technologies required for the role.",
    )
    salary_range: SalaryRange | None = Field(
        default=None,
        description="The pay range if stated. Leave null if the posting gives no salary.",
    )
    description_summary: str | None = Field(
        default=None,
        description="A 1-3 sentence neutral summary of the role's responsibilities.",
    )
    posted_date: str | None = Field(
        default=None,
        description="When the job was posted, as written on the page (do not invent it).",
    )


class ValidatedJobPosting(BaseModel):
    """The extracted posting after a second agent has reviewed and enriched it.

    This is the output_type of the Validation/Enrichment Agent and the final
    result of the pipeline.
    """

    posting: JobPosting = Field(
        description="The job posting, with skills normalized and fields sanity-checked."
    )
    confidence_score: float = Field(
        ge=0.0,
        le=1.0,
        description="Overall confidence (0.0-1.0) that the extraction is correct and complete.",
    )
    missing_fields: list[str] = Field(
        default_factory=list,
        description="Names of fields that are empty/null because the page did not provide them.",
    )
    quality_notes: list[str] = Field(
        default_factory=list,
        description="Short notes on data quality, normalization done, or possible issues.",
    )
