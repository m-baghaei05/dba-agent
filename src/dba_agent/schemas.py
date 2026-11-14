"""Data shapes for the requirements phase (Intake + Interview).

These Pydantic models do two jobs at once:
1. They are the JSON Schemas the LLM must follow (sent automatically by LLMService).
2. Their validators are deterministic rules. A violation becomes an error message that is fed
   back to the model, which then retries. E.g. "the first round must cover all 7 categories"
   is enforced here by code, not just requested in the prompt.
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class Category(str, Enum):
    """The 7 interview categories required by the spec (Stage 2)."""

    ENTITIES = "entities_attributes"
    RELATIONSHIPS = "relationships_cardinality"
    VOLUME = "volume_growth"
    ACCESS = "access_patterns"
    TRANSACTIONS = "transactions_concurrency"
    SECURITY = "security_privacy"
    RULES = "business_rules"


CATEGORY_TITLES: dict[Category, str] = {
    Category.ENTITIES: "Entities and attributes",
    Category.RELATIONSHIPS: "Relationships and cardinality",
    Category.VOLUME: "Data volume and growth",
    Category.ACCESS: "Read/write patterns and reporting",
    Category.TRANSACTIONS: "Transactions and concurrency",
    Category.SECURITY: "Security, roles and privacy",
    Category.RULES: "Business rules and constraints",
}

Coverage = Literal["complete", "partial", "missing"]


def _missing_categories(present: set[Category]) -> list[str]:
    return [c.value for c in Category if c not in present]


# ---------------------------------------------------------------- Stage 1: Intake
class Actor(BaseModel):
    name: str
    description: str


class EntityCandidate(BaseModel):
    name: str = Field(description="Singular noun, e.g. 'Patient'")
    description: str
    example_attributes: list[str] = Field(default_factory=list)


class Process(BaseModel):
    name: str
    description: str
    actors: list[str] = Field(default_factory=list)


class SystemSummary(BaseModel):
    system_name: str
    domain: str
    purpose: str
    actors: list[Actor] = Field(min_length=1)
    entities: list[EntityCandidate] = Field(min_length=1)
    processes: list[Process] = Field(default_factory=list)
    unclear_points: list[str] = Field(
        default_factory=list, description="Ambiguities or gaps to resolve in the interview"
    )


# ---------------------------------------------------------------- Stage 2: Interview
class Question(BaseModel):
    category: Category
    question: str
    why: str = Field("", description="One short sentence: why the answer matters for the design")


class InitialQuestions(BaseModel):
    """First interview round: must touch every category."""

    questions: list[Question] = Field(min_length=7, max_length=14)

    @model_validator(mode="after")
    def _all_categories(self) -> "InitialQuestions":
        missing = _missing_categories({q.category for q in self.questions})
        if missing:
            raise ValueError(f"The first round must cover every category. Missing: {', '.join(missing)}")
        return self


class FollowUp(BaseModel):
    """The model's assessment after a round: coverage per category, and whether to stop."""

    coverage: dict[Category, Coverage]
    ready: bool = Field(description="True if the information is enough for a complete database design")
    reason: str = Field(description="One or two sentences explaining the decision")
    questions: list[Question] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def _consistent(self) -> "FollowUp":
        missing = _missing_categories(set(self.coverage))
        if missing:
            raise ValueError(f"`coverage` must rate every category. Missing: {', '.join(missing)}")
        if not self.ready and not self.questions:
            raise ValueError("If `ready` is false you must ask at least one question.")
        return self


class RequiredFollowUp(FollowUp):
    """Used while the mandatory follow-up round(s) have not happened yet."""

    @model_validator(mode="after")
    def _has_questions(self) -> "RequiredFollowUp":
        if not self.questions:
            raise ValueError(
                "This round must include at least one follow-up question "
                "(clarify vague or skipped answers, missing limits, cardinalities or rules)."
            )
        return self


class QA(BaseModel):
    """One interview question and its answer. answer=None: not asked yet; "": skipped."""

    round: int
    category: Category
    question: str
    why: str = ""
    answer: str | None = None


class InterviewState(BaseModel):
    rounds_done: int = 0          # rounds whose questions have all been answered
    qa: list[QA] = Field(default_factory=list)
    finished: bool = False
    stop_reason: str = ""
    coverage: dict[Category, Coverage] = Field(default_factory=dict)

    @property
    def pending(self) -> list[QA]:
        return [q for q in self.qa if q.answer is None]

    @property
    def current_round(self) -> int:
        return max((q.round for q in self.qa), default=0)


# ---------------------------------------------------------------- Requirements (end of Stage 2)
class RequirementItem(BaseModel):
    category: Category
    text: str = Field(description="One atomic, checkable requirement statement")
    source: Literal["user", "assumption"] = Field(
        description="'user' if stated by the user; 'assumption' if decided by the agent"
    )


class RequirementsDraft(BaseModel):
    overview: str = Field(description="One paragraph describing the system and its scope")
    items: list[RequirementItem] = Field(min_length=7)

    @model_validator(mode="after")
    def _every_category(self) -> "RequirementsDraft":
        missing = _missing_categories({i.category for i in self.items})
        if missing:
            raise ValueError(
                f"Every category needs at least one requirement. Missing: {', '.join(missing)}"
            )
        return self


class Requirement(RequirementItem):
    id: str  # "R-01", assigned by code (not the LLM) so IDs are always unique and ordered
