"""Conversation persistence, request admission and idempotent saved responses."""

import hashlib
import json
from uuid import uuid4

from sqlalchemy import func, literal_column, select, update
from sqlalchemy.dialects.sqlite import insert

from resourcing_assistant.db.models import Message, Request, Thread, record
from resourcing_assistant.domain.calculations import utc_now
from resourcing_assistant.errors import AppError


class ConversationRepository:
    def __init__(self, database):
        self.database = database
        self.path = database.path

    def create_thread(self):
        thread, now = uuid4().hex, utc_now()
        with self.database.session(write=True) as s:
            s.add(Thread(thread_id=thread, created_ts=now, updated_ts=now))
        return {"thread_id": thread, "created_ts": now}

    def require_thread(self, thread):
        with self.database.session() as s:
            if s.get(Thread, thread) is None:
                raise AppError("thread_not_found", "Unknown conversation", 404)

    def threads(self):
        first = (
            select(func.substr(Message.content, 1, 80))
            .where(Message.thread_id == Thread.thread_id, Message.role == "user")
            .order_by(literal_column("messages.rowid"))
            .limit(1)
            .correlate(Thread)
            .scalar_subquery()
        )
        with self.database.session() as s:
            return [
                dict(row)
                for row in s.execute(
                    select(Thread.__table__, first.label("label")).order_by(
                        Thread.updated_ts.desc(), literal_column("threads.rowid").desc()
                    )
                ).mappings()
            ]

    def request(self, thread, request):
        with self.database.session() as s:
            row = s.get(Request, (thread, request))
            if row is None:
                raise AppError("request_not_found", "Unknown request", 404)
            return record(row)

    def admit(self, thread, request, text, reference):
        self.require_thread(thread)
        fingerprint, now = hashlib.sha256(text.encode()).hexdigest(), utc_now()
        with self.database.session(write=True) as s:
            row = s.get(Request, (thread, request))
            if row:
                if row.fingerprint != fingerprint:
                    raise AppError(
                        "request_id_conflict",
                        "Request ID already belongs to a different message",
                    )
                return record(row)
            if s.scalar(
                select(Request.request_id)
                .where(
                    Request.thread_id == thread,
                    Request.status.in_(["processing", "interrupted"]),
                )
                .limit(1)
            ):
                raise AppError(
                    "resume_required",
                    "Continue the interrupted request before sending another question",
                )
            s.add(
                Request(
                    thread_id=thread,
                    request_id=request,
                    text=text,
                    fingerprint=fingerprint,
                    status="processing",
                    reference_date=reference,
                    created_ts=now,
                    updated_ts=now,
                )
            )
            s.add(
                Message(
                    message_id=uuid4().hex,
                    thread_id=thread,
                    request_id=request,
                    role="user",
                    content=text,
                    created_ts=now,
                )
            )
            s.execute(
                update(Thread).where(Thread.thread_id == thread).values(updated_ts=now)
            )
        return self.request(thread, request)

    def resume(self, thread, request):
        self.require_thread(thread)
        row = self.request(thread, request)
        if row["status"] == "interrupted":
            with self.database.session(write=True) as s:
                s.execute(
                    update(Request)
                    .where(Request.thread_id == thread, Request.request_id == request)
                    .values(status="processing", updated_ts=utc_now())
                )
        return row

    def finish(self, thread, request, response):
        with self.database.session(write=True) as s:
            old = s.scalar(
                select(Message.message_id).where(
                    Message.thread_id == thread,
                    Message.request_id == request,
                    Message.role == "assistant",
                )
            )
            message = old or uuid4().hex
            response["response_message_id"] = message
            content = json.dumps(response, allow_nan=False)
            s.execute(
                insert(Message)
                .values(
                    message_id=message,
                    thread_id=thread,
                    request_id=request,
                    role="assistant",
                    content=content,
                    created_ts=utc_now(),
                )
                .on_conflict_do_update(
                    index_elements=["thread_id", "request_id", "role"],
                    set_={"content": content},
                )
            )
            s.execute(
                update(Request)
                .where(Request.thread_id == thread, Request.request_id == request)
                .values(
                    status=response["request_status"],
                    response=content,
                    error=None,
                    updated_ts=utc_now(),
                )
            )
            s.execute(
                update(Thread)
                .where(Thread.thread_id == thread)
                .values(updated_ts=utc_now())
            )
        return response

    def fail(self, thread, request, error):
        with self.database.session(write=True) as s:
            s.execute(
                update(Request)
                .where(Request.thread_id == thread, Request.request_id == request)
                .values(
                    status="failed",
                    error=json.dumps(
                        {
                            "code": error.code,
                            "message": str(error),
                            "status": error.status,
                        }
                    ),
                    updated_ts=utc_now(),
                )
            )

    def history(self, thread):
        self.require_thread(thread)
        with self.database.session() as s:
            messages = [
                dict(row)
                for row in s.execute(
                    select(
                        literal_column("messages.rowid").label("sequence"),
                        Message.__table__,
                    )
                    .where(Message.thread_id == thread)
                    .order_by(literal_column("messages.rowid"))
                ).mappings()
            ]
            requests = [
                dict(row)
                for row in s.execute(
                    select(Request.request_id, Request.status, Request.error)
                    .where(Request.thread_id == thread)
                    .order_by(literal_column("requests.rowid"))
                ).mappings()
            ]
        for row in messages:
            if row["role"] == "assistant":
                row["content"] = json.loads(row["content"])
        return {"thread_id": thread, "messages": messages, "requests": requests}
