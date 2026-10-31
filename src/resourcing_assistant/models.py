"""Explicit typed boundaries for API and DSPy tasks."""

from typing import Any, Annotated, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


class AppError(Exception):
    def __init__(self, code, message, status=409, retryable=False):
        super().__init__(message)
        self.code, self.status, self.retryable = code, status, retryable


Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")]
Scalar = str | int | float | bool | None


class MessageInput(StrictModel):
    request_id: Identifier
    text: str = Field(min_length=1, max_length=40000)


class DecisionInput(StrictModel):
    action_id: Identifier
    decision: Literal["confirm", "reject"]


class EmptyInput(StrictModel):
    pass


class Issue(StrictModel):
    code: str
    message: str
    stage: str
    retryable: bool = False


class TextBlock(StrictModel):
    type: Literal["text"] = "text"
    text: str
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class Column(StrictModel):
    key: str
    label: str
    unit: str | None = None


class TableBlock(StrictModel):
    type: Literal["table"] = "table"
    block_id: str
    title: str
    columns: list[Column]
    rows: list[dict[str, Scalar]]
    completeness: dict[str, Any] = Field(default_factory=dict)
    evidence: list[dict[str, Any]] = Field(default_factory=list)


class ConfirmationBlock(StrictModel):
    type: Literal["confirmation"] = "confirmation"
    action_id: str
    status: Literal["pending", "confirmed", "rejected", "superseded"]
    fields: dict[str, Any]
    booking_id: int | None = None


class SqlBlock(StrictModel):
    type: Literal["sql"] = "sql"
    query_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,128}$")
    purpose: str
    sql: str
    parameters: dict[str, Scalar]


Block = Annotated[
    TextBlock | TableBlock | ConfirmationBlock | SqlBlock, Field(discriminator="type")
]


class Response(StrictModel):
    thread_id: str
    request_id: str
    response_message_id: str | None = None
    request_status: Literal[
        "processing", "completed", "partial", "interrupted", "failed"
    ]
    blocks: list[Block] = Field(default_factory=list)
    issues: list[Issue] = Field(default_factory=list)
    effective_reference_date: str
    assumptions: list[str] = Field(default_factory=list)


class BookingSlots(StrictModel):
    person: str | None = None
    person_id: int | None = Field(
        default=None,
        description="Only an explicit database person ID or a previously resolved source ID; never guess from a name.",
    )
    project: str | None = Field(
        default=None,
        description="Project name or full engagement code exactly as supplied, e.g. ENG-YYYY-NNNN. A code is a string, not an integer ID.",
    )
    engagement_id: int | None = Field(
        default=None,
        description="Only an explicit database engagement ID or a previously resolved source ID. Never convert digits from an engagement code into an ID.",
    )
    hours: float | None = None
    start_date: str | None = None
    end_date: str | None = None

    @field_validator("start_date", "end_date")
    @classmethod
    def valid_day(cls, value):
        if value is not None:
            from datetime import date

            date.fromisoformat(value)
        return value


class Interpretation(StrictModel):
    intent: Literal[
        "factual", "semantic", "booking", "mixed", "unsupported", "clarification"
    ]
    question: str
    slots: BookingSlots = Field(default_factory=BookingSlots)
    missing_fields: list[str] = Field(default_factory=list)
    clarification: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    semantic_mode: Literal["shortlist", "exhaustive"] = "shortlist"
    semantic_kind: Literal["person", "project", "risk"] = "person"
    criteria: str = ""
    requested_count: int = Field(default=10, ge=1, le=100)
    modify_pending: bool = False
    selected_position: int | None = None
    # Exact source filters remain SQL conditions, not unconstrained hidden Python filters.


class Binding(StrictModel):
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]{0,63}$")
    value: Scalar


class Query(StrictModel):
    query_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    purpose: str
    sql: str = Field(
        description="Exactly one SQLite SELECT/WITH statement; no scripts, PostgreSQL casts or shared CTE scope across queries."
    )
    parameters: list[Binding] = Field(
        description="Every :placeholder needs one {name, value} item with its actual scalar value. Name omits the colon. Use separate placeholders for IN lists; [] only when SQL has no placeholders."
    )

    @field_validator("parameters")
    @classmethod
    def unique_bindings(cls, values):
        if len({v.name for v in values}) != len(values):
            raise ValueError("Binding names must be unique")
        return values

    @property
    def bindings(self):
        return {v.name: v.value for v in self.parameters}


class ReadPlan(StrictModel):
    answer: Query = Field(
        description="Primary requested result at ONE grain, with every relevant filter. Other requested grains (such as a grand total beside a ranking) belong in additional_answers. Never a lookup/helper/intermediate query."
    )
    additional_answers: list[Query] = Field(
        default_factory=list,
        max_length=3,
        description="Only complete, independently requested extra answers such as a grand total. No helpers, ID lookup, capacity calculation or preparation steps; [] when not needed.",
    )

    @property
    def queries(self):
        return [self.answer, *self.additional_answers]


class Candidate(StrictModel):
    source_id: str
    kind: Literal["person", "project", "risk"]
    entity_id: int
    text: str
    facts: dict[str, Any]


class Assessment(StrictModel):
    source_id: str
    status: Literal["match", "no_match", "uncertain"]
    quotes: list[str] = Field(default_factory=list)
    reason: str


class ProjectChecks(StrictModel):
    summary: str | None = Field(
        description="Only the required project/client summary meaning; null when unconstrained. Exclude already checked structured filters."
    )
    summary_scope: Literal["industry", "full"] = Field(
        description="industry only for client industry conditions; full for any other summary meaning"
    )
    risk: str | None = Field(
        description="Only the required risk meaning, preserving OR within risk conditions; null when no risk constraint"
    )
    operator: Literal["all", "any"] = Field(
        description="Logical relationship between summary and risk conditions, normally all; do not convert OR inside a condition to AND"
    )


class RankItem(StrictModel):
    source_id: str
    reason: str


class ThreadCreated(StrictModel):
    thread_id: str
    created_ts: int


class ThreadInfo(ThreadCreated):
    updated_ts: int
    label: str | None = None


class HistoryMessage(StrictModel):
    sequence: int
    message_id: str
    thread_id: str
    request_id: str
    role: Literal["user", "assistant"]
    content: str | Response
    created_ts: int


class RequestInfo(StrictModel):
    request_id: str
    status: Literal["processing", "completed", "partial", "failed", "interrupted"]
    error: str | None = None


class History(StrictModel):
    thread_id: str
    messages: list[HistoryMessage]
    requests: list[RequestInfo]
    pending_action: dict[str, Any] | None = None
    effective_reference_date: str


class Health(StrictModel):
    status: str
    chat: str
    embeddings: str
    reference_date: str
