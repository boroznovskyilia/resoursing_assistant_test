"""Immutable booking actions and the atomic fixed soft-booking writer."""

import json
from uuid import uuid4

from sqlalchemy import func, insert, select

from resourcing_assistant.db.models import BookingAction, record
from resourcing_assistant.domain.calculations import utc_now
from resourcing_assistant.errors import AppError
from resourcing_assistant.telemetry import event


def action_record(row):
    result = record(row)
    result["fields"] = json.loads(result.pop("display_snapshot"))
    return result


class BookingRepository:
    def __init__(self, database, tables):
        self.database, self.tables = database, tables

    def action(self, thread, action):
        with self.database.session() as s:
            row = s.scalar(
                select(BookingAction).where(
                    BookingAction.thread_id == thread, BookingAction.action_id == action
                )
            )
            if row is None:
                raise AppError(
                    "action_not_found", "Unknown action in this conversation", 404
                )
            return action_record(row)

    def pending(self, thread):
        with self.database.session() as s:
            row = s.scalar(
                select(BookingAction).where(
                    BookingAction.thread_id == thread, BookingAction.status == "pending"
                )
            )
            return action_record(row) if row else None

    def prepare(
        self,
        thread,
        request,
        slots,
        start,
        end,
        minutes,
        describe,
        *,
        replace_pending=False,
    ):
        people, projects, bookings = (
            self.tables[name] for name in ("people", "engagements", "bookings")
        )
        with self.database.session(write=True) as s:
            old = s.scalar(
                select(BookingAction).where(
                    BookingAction.thread_id == thread,
                    BookingAction.origin_request_id == request,
                )
            )
            if old:
                return action_record(old)
            person = (
                s.execute(
                    select(people.c.person_id, people.c.display_name).where(
                        people.c.person_id == slots.person_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            project = (
                s.execute(
                    select(projects.c.engagement_id, projects.c.code).where(
                        projects.c.engagement_id == slots.engagement_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if person is None or project is None:
                raise AppError(
                    "invalid_proposal", "Person or project no longer exists", 422
                )
            pending = s.scalar(
                select(BookingAction).where(
                    BookingAction.thread_id == thread, BookingAction.status == "pending"
                )
            )
            if pending and not replace_pending:
                raise AppError(
                    "pending_action_exists",
                    "Finish the current booking before starting another",
                )
            conflicts = s.scalar(
                select(func.coalesce(func.sum(bookings.c.minutes), 0)).where(
                    bookings.c.person_id == slots.person_id,
                    bookings.c.start_ts < end,
                    bookings.c.end_ts > start,
                )
            )
            fields = describe(person, project, conflicts)
            action, now = uuid4().hex, utc_now()
            if pending:
                pending.status, pending.updated_ts, pending.decided_ts = (
                    "superseded",
                    now,
                    now,
                )
                # Release the partial unique index before adding the replacement.
                s.flush()
            row = BookingAction(
                action_id=action,
                thread_id=thread,
                origin_request_id=request,
                person_id=person["person_id"],
                engagement_id=project["engagement_id"],
                start_ts=start,
                end_ts=end,
                minutes=minutes,
                display_snapshot=json.dumps(fields),
                status="pending",
                created_ts=now,
                updated_ts=now,
            )
            s.add(row)
            s.flush()
            if pending:
                pending.superseded_by = action
            result = action_record(row)
        event("action_prepared", thread_id=thread, request_id=request, action_id=action)
        return result

    def decide(self, thread, action, decision, validate):
        with self.database.session(write=True) as s:
            row = s.scalar(
                select(BookingAction).where(
                    BookingAction.thread_id == thread, BookingAction.action_id == action
                )
            )
            if row is None:
                raise AppError(
                    "action_not_found", "Unknown action in this conversation", 404
                )
            desired = "confirmed" if decision == "confirm" else "rejected"
            if row.status == desired:
                return action_record(row)
            if row.status != "pending":
                raise AppError(
                    "action_conflict", "This action was already decided or superseded"
                )
            now = utc_now()
            booking = None
            if decision == "confirm":
                validate(action_record(row))
                status = self.tables["status_lookup"]
                statuses = s.scalars(
                    select(status.c.status_id).where(
                        status.c.domain == "booking", status.c.code == "SFT"
                    )
                ).all()
                if len(statuses) != 1:
                    raise AppError(
                        "invalid_proposal", "Soft-booking status unavailable", 422
                    )
                for name, key, value in (
                    ("people", "person_id", row.person_id),
                    ("engagements", "engagement_id", row.engagement_id),
                ):
                    table = self.tables[name]
                    if (
                        s.scalar(select(table.c[key]).where(table.c[key] == value))
                        is None
                    ):
                        raise AppError(
                            "invalid_proposal", "Subject entity no longer exists", 422
                        )
                result = s.execute(
                    insert(self.tables["bookings"]).values(
                        person_id=row.person_id,
                        engagement_id=row.engagement_id,
                        status_id=statuses[0],
                        kind="soft",
                        start_ts=row.start_ts,
                        end_ts=row.end_ts,
                        minutes=row.minutes,
                        created_ts=now,
                        updated_ts=now,
                    )
                )
                booking = result.inserted_primary_key[0]
            row.status, row.booking_id, row.updated_ts, row.decided_ts = (
                desired,
                booking,
                now,
                now,
            )
            result = action_record(row)
        event(
            "action_committed",
            thread_id=thread,
            action_id=action,
            status=desired,
            booking_id=booking,
        )
        return result
