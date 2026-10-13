"""Typed AI operation contract shared by adapters, the router, and callers.

Every operation is a typed request/response pair. Inputs are pre-filtered
caller payloads — provider adapters and prompts never receive credentials,
raw documents, tools, or URLs to fetch. Validation is authoritative: adapter
output is parsed through these models before anything else sees it.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ProviderName = Literal["OPENROUTER", "XAI", "GEMINI"]
OperationKind = Literal["EXTRACTION", "JOB_MATCH", "AUTOFILL", "EMAIL", "CLASSIFY"]

# Shared limits from PROVIDERS.md.
MAX_INPUT_TOKENS = 12_000
INTERACTIVE_DEADLINE = timedelta(seconds=60)
MAX_PROVIDER_ATTEMPTS = 3
OUTPUT_TOKEN_LIMITS: dict[str, int] = {
    "EXTRACTION": 2_000,
    "JOB_MATCH": 2_000,
    "AUTOFILL": 4_000,
    "EMAIL": 1_500,
    "CLASSIFY": 2_000,
}
DAILY_INTERACTIVE_OPERATIONS = 50
DAILY_TOTAL_ATTEMPTS = 150
MAX_FACTS_PER_REQUEST = 40
MAX_FORM_QUESTIONS = 10


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FactPayload(ContractModel):
    """One confirmed owner fact; sensitive facts are filtered upstream."""

    fact_key: str = Field(min_length=1, max_length=128)
    value_type: Literal["TEXT", "NUMBER", "DATE", "BOOLEAN", "URL", "JSON"]
    value: object = None


class SourceAnchor(ContractModel):
    page: int | None = Field(default=None, ge=1, le=10_000)
    block: int | None = Field(default=None, ge=0)
    excerpt: str = Field(default="", max_length=512)


class DocumentSection(ContractModel):
    section_id: int = Field(ge=0)
    heading: str = Field(default="", max_length=200)
    anchor: SourceAnchor
    text: str = Field(min_length=1, max_length=20_000)


class ExtractionInput(ContractModel):
    document_type: Literal["RESUME", "LINKEDIN_PDF", "COVER_LETTER", "SUPPORTING_DOCUMENT", "OTHER"]
    sections: list[DocumentSection] = Field(min_length=1, max_length=200)


class CandidateFact(ContractModel):
    fact_key: str = Field(min_length=1, max_length=128)
    value_type: Literal["TEXT", "NUMBER", "DATE", "BOOLEAN", "URL", "JSON"]
    value: object = None
    section_id: int = Field(ge=0)
    anchor: SourceAnchor = Field(default_factory=SourceAnchor)


class ExtractionOutput(ContractModel):
    candidates: list[CandidateFact] = Field(max_length=200)


class JobContextInput(ContractModel):
    page_excerpt: str = Field(min_length=1, max_length=20_000)
    page_url_domain: str | None = Field(default=None, max_length=255)


class FormFieldSpec(ContractModel):
    field_id: str = Field(min_length=1, max_length=128)
    label: str = Field(min_length=1, max_length=512)
    field_type: Literal["TEXT", "TEXTAREA", "SELECT", "RADIO", "CHECKBOX", "DATE", "EMAIL", "TEL"]
    options: list[str] = Field(default_factory=list, max_length=100)
    required: bool = False
    sensitive: bool = False


class JobContextOutput(ContractModel):
    employer: str | None = Field(default=None, max_length=255)
    role: str | None = Field(default=None, max_length=255)
    fields: list[FormFieldSpec] = Field(max_length=100)


class FormAnswersInput(ContractModel):
    questions: list[FormFieldSpec] = Field(min_length=1, max_length=MAX_FORM_QUESTIONS)
    facts: list[FactPayload] = Field(max_length=MAX_FACTS_PER_REQUEST)
    context_excerpt: str = Field(default="", max_length=10_000)


class DraftedAnswer(ContractModel):
    field_id: str = Field(min_length=1, max_length=128)
    answer: str | None = Field(default=None, max_length=4_000)
    option_ids: list[str] = Field(default_factory=list, max_length=100)
    used_fact_keys: list[str] = Field(default_factory=list, max_length=40)
    missing_fact: str | None = Field(default=None, max_length=255)


class FormAnswersOutput(ContractModel):
    answers: list[DraftedAnswer] = Field(max_length=MAX_FORM_QUESTIONS)


class EmailInput(ContractModel):
    recipient_email: str = Field(min_length=3, max_length=320)
    employer: str = Field(default="", max_length=255)
    role: str = Field(default="", max_length=255)
    job_excerpt: str = Field(default="", max_length=10_000)
    facts: list[FactPayload] = Field(max_length=MAX_FACTS_PER_REQUEST)
    tone_tips: list[str] = Field(default_factory=list, max_length=10)


class EmailOutput(ContractModel):
    subject: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=10_000)


class PostingInput(ContractModel):
    native_id: str = Field(min_length=1, max_length=255)
    title: str = Field(default="", max_length=512)
    employer: str = Field(default="", max_length=255)
    location: str = Field(default="", max_length=255)
    text: str = Field(default="", max_length=10_000)


class ClassificationInput(ContractModel):
    postings: list[PostingInput] = Field(min_length=1, max_length=50)
    desired_roles: list[str] = Field(default_factory=list, max_length=20)
    desired_locations: list[str] = Field(default_factory=list, max_length=20)


class PostingVerdict(ContractModel):
    native_id: str = Field(min_length=1, max_length=255)
    status: Literal["MATCHED", "UNCHANGED", "CLOSED", "UNKNOWN"]
    reason: str = Field(default="", max_length=512)


class ClassificationOutput(ContractModel):
    results: list[PostingVerdict] = Field(max_length=50)


OPERATION_INPUTS: dict[str, type[ContractModel]] = {
    "EXTRACTION": ExtractionInput,
    "JOB_MATCH": JobContextInput,
    "AUTOFILL": FormAnswersInput,
    "EMAIL": EmailInput,
    "CLASSIFY": ClassificationInput,
}
OPERATION_OUTPUTS: dict[str, type[ContractModel]] = {
    "EXTRACTION": ExtractionOutput,
    "JOB_MATCH": JobContextOutput,
    "AUTOFILL": FormAnswersOutput,
    "EMAIL": EmailOutput,
    "CLASSIFY": ClassificationOutput,
}


class ModelCapability(ContractModel):
    model_id: str
    structured_output: bool
    max_output_tokens: int


# Only evaluated, catalog-listed models may be routed to (PROVIDERS.md).
MODEL_CATALOG: dict[str, list[ModelCapability]] = {
    "OPENROUTER": [
        ModelCapability(
            model_id="deepseek/deepseek-v4-flash",
            structured_output=True,
            max_output_tokens=4_000,
        )
    ],
    "XAI": [ModelCapability(model_id="grok-4.7", structured_output=True, max_output_tokens=4_000)],
    "GEMINI": [
        ModelCapability(
            model_id="gemini-3.8-flash", structured_output=True, max_output_tokens=4_000
        )
    ],
}


def catalog_model(provider: str, model_id: str) -> ModelCapability | None:
    return next(
        (model for model in MODEL_CATALOG.get(provider, []) if model.model_id == model_id), None
    )


def output_schema_for(kind: OperationKind) -> dict[str, object]:
    """JSON Schema advertised to providers for authoritative validation."""
    return OPERATION_OUTPUTS[kind].model_json_schema()


def validate_input(kind: str, payload: dict[str, object]) -> ContractModel:
    """Authoritative input validation for an operation payload."""
    model = OPERATION_INPUTS.get(kind)
    if model is None:
        raise ValueError(f"unknown operation kind {kind}")
    return model.model_validate(payload)


def validate_output(kind: str, payload: dict[str, object]) -> ContractModel:
    """Authoritative output validation for provider-returned content."""
    model = OPERATION_OUTPUTS.get(kind)
    if model is None:
        raise ValueError(f"unknown operation kind {kind}")
    return model.model_validate(payload)


def input_token_count(kind: str, payload: dict[str, object]) -> int:
    """Rough token estimate for a validated payload (4 chars/token)."""
    validated = validate_input(kind, payload)
    return max(1, len(validated.model_dump_json()) // 4)
