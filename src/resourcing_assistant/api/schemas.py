"""Public HTTP request and response contracts."""

from typing import Annotated, Any, Literal

from pydantic import Field

from resourcing_assistant.schemas import Identifier, Scalar, StrictModel


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
