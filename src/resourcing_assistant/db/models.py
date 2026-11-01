"""Owned persistence records; source tables are reflected, never created by ORM metadata."""

from sqlalchemy import (
    CheckConstraint,
    Column,
    ForeignKey,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class AppBase(DeclarativeBase):
    pass


class Thread(AppBase):
    __tablename__ = "threads"
    thread_id: Mapped[str] = mapped_column(Text, primary_key=True)
    created_ts: Mapped[int]
    updated_ts: Mapped[int]


class Request(AppBase):
    __tablename__ = "requests"
    __table_args__ = (
        CheckConstraint(
            "status IN ('processing','completed','partial','failed','interrupted')"
        ),
    )
    thread_id: Mapped[str] = mapped_column(
        ForeignKey("threads.thread_id"), primary_key=True
    )
    request_id: Mapped[str] = mapped_column(Text, primary_key=True)
    text: Mapped[str] = mapped_column(Text)
    fingerprint: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    reference_date: Mapped[str] = mapped_column(Text)
    response: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    created_ts: Mapped[int]
    updated_ts: Mapped[int]


class Message(AppBase):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("thread_id", "request_id", "role"),)
    message_id: Mapped[str] = mapped_column(Text, primary_key=True)
    thread_id: Mapped[str] = mapped_column(ForeignKey("threads.thread_id"))
    request_id: Mapped[str] = mapped_column(Text)
    role: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    created_ts: Mapped[int]


class Vector(AppBase):
    __tablename__ = "semantic_vectors"
    cache_key: Mapped[str] = mapped_column(Text, primary_key=True)
    model: Mapped[str] = mapped_column(Text)
    text_hash: Mapped[str] = mapped_column(Text)
    dimension: Mapped[int]
    vector: Mapped[str] = mapped_column(Text)


class Membership(AppBase):
    __tablename__ = "semantic_memberships"
    source_ref: Mapped[str] = mapped_column(Text, primary_key=True)
    cache_key: Mapped[str] = mapped_column(ForeignKey("semantic_vectors.cache_key"))


class SubjectBase(DeclarativeBase):
    pass


# Reference columns resolve own action foreign keys. Only booking_actions is created.
Table("people", SubjectBase.metadata, Column("person_id", Integer, primary_key=True))
Table(
    "engagements",
    SubjectBase.metadata,
    Column("engagement_id", Integer, primary_key=True),
)
Table("bookings", SubjectBase.metadata, Column("booking_id", Integer, primary_key=True))


class BookingAction(SubjectBase):
    __tablename__ = "booking_actions"
    __table_args__ = (
        UniqueConstraint("thread_id", "origin_request_id"),
        CheckConstraint("status IN ('pending','confirmed','rejected','superseded')"),
        CheckConstraint("start_ts<end_ts AND minutes>0"),
        CheckConstraint(
            "(status='confirmed' AND booking_id IS NOT NULL) OR (status!='confirmed' AND booking_id IS NULL)"
        ),
        Index(
            "one_pending_per_thread",
            "thread_id",
            unique=True,
            sqlite_where=text("status='pending'"),
        ),
    )
    action_id: Mapped[str] = mapped_column(Text, primary_key=True)
    thread_id: Mapped[str] = mapped_column(Text)
    origin_request_id: Mapped[str] = mapped_column(Text)
    person_id: Mapped[int] = mapped_column(ForeignKey("people.person_id"))
    engagement_id: Mapped[int] = mapped_column(ForeignKey("engagements.engagement_id"))
    start_ts: Mapped[int]
    end_ts: Mapped[int]
    minutes: Mapped[int]
    display_snapshot: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(Text)
    booking_id: Mapped[int | None] = mapped_column(
        ForeignKey("bookings.booking_id"), unique=True
    )
    superseded_by: Mapped[str | None] = mapped_column(
        ForeignKey("booking_actions.action_id")
    )
    created_ts: Mapped[int]
    updated_ts: Mapped[int]
    decided_ts: Mapped[int | None]


def record(value):
    return {
        column.key: getattr(value, column.key) for column in value.__table__.columns
    }
