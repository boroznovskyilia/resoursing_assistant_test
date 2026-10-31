"""Durable application history and transactional immutable booking actions."""

from datetime import datetime, timezone
import hashlib
import json
from uuid import uuid4
from .config import utc_now, period, to_minutes, capacity
from .data import connect
from .models import AppError
from .telemetry import event


def uid():
    return uuid4().hex


class Store:
    def __init__(self, settings, subject):
        self.settings, self.subject = settings, subject
        self.path = settings.runtime / "app.sqlite"
        with connect(self.path) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS threads(thread_id TEXT PRIMARY KEY, created_ts INTEGER NOT NULL, updated_ts INTEGER NOT NULL);
            CREATE TABLE IF NOT EXISTS requests(thread_id TEXT NOT NULL REFERENCES threads, request_id TEXT NOT NULL, text TEXT NOT NULL, fingerprint TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('processing','completed','partial','failed','interrupted')), reference_date TEXT NOT NULL, response TEXT, error TEXT, created_ts INTEGER NOT NULL, updated_ts INTEGER NOT NULL, PRIMARY KEY(thread_id,request_id));
            CREATE TABLE IF NOT EXISTS messages(message_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL REFERENCES threads, request_id TEXT NOT NULL, role TEXT NOT NULL, content TEXT NOT NULL, created_ts INTEGER NOT NULL, UNIQUE(thread_id,request_id,role));
            """)
            # A previous process may have stopped between graph stages.
            c.execute(
                "UPDATE requests SET status='interrupted' WHERE status='processing'"
            )
            c.commit()
        with connect(self.subject) as c:
            c.executescript("""
            CREATE TABLE IF NOT EXISTS booking_actions(
              action_id TEXT PRIMARY KEY, thread_id TEXT NOT NULL, origin_request_id TEXT NOT NULL,
              person_id INTEGER NOT NULL REFERENCES people, engagement_id INTEGER NOT NULL REFERENCES engagements,
              start_ts INTEGER NOT NULL, end_ts INTEGER NOT NULL, minutes INTEGER NOT NULL,
              display_snapshot TEXT NOT NULL, status TEXT NOT NULL CHECK(status IN ('pending','confirmed','rejected','superseded')),
              booking_id INTEGER UNIQUE REFERENCES bookings, superseded_by TEXT REFERENCES booking_actions,
              created_ts INTEGER NOT NULL, updated_ts INTEGER NOT NULL, decided_ts INTEGER,
              UNIQUE(thread_id,origin_request_id), CHECK(start_ts<end_ts AND minutes>0),
              CHECK((status='confirmed' AND booking_id IS NOT NULL) OR (status!='confirmed' AND booking_id IS NULL)));
            CREATE UNIQUE INDEX IF NOT EXISTS one_pending_per_thread ON booking_actions(thread_id) WHERE status='pending';
            """)

    def create_thread(self):
        thread = uid()
        now = utc_now()
        with connect(self.path) as c:
            c.execute("INSERT INTO threads VALUES(?,?,?)", (thread, now, now))
            c.commit()
        return {"thread_id": thread, "created_ts": now}

    def require_thread(self, thread):
        with connect(self.path, readonly=True) as c:
            if not c.execute(
                "SELECT 1 FROM threads WHERE thread_id=?", (thread,)
            ).fetchone():
                raise AppError("thread_not_found", "Unknown conversation", 404)

    def threads(self):
        with connect(self.path, readonly=True) as c:
            return [
                dict(r)
                for r in c.execute(
                    """SELECT t.*,(SELECT substr(content,1,80) FROM messages m WHERE m.thread_id=t.thread_id AND role='user' ORDER BY rowid LIMIT 1) AS label FROM threads t ORDER BY updated_ts DESC,rowid DESC"""
                )
            ]

    def request(self, thread, request):
        with connect(self.path, readonly=True) as c:
            row = c.execute(
                "SELECT * FROM requests WHERE thread_id=? AND request_id=?",
                (thread, request),
            ).fetchone()
        if row is None:
            raise AppError("request_not_found", "Unknown request", 404)
        return dict(row)

    def admit(self, thread, request, text, reference):
        self.require_thread(thread)
        fingerprint = hashlib.sha256(text.encode()).hexdigest()
        now = utc_now()
        with connect(self.path) as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT * FROM requests WHERE thread_id=? AND request_id=?",
                (thread, request),
            ).fetchone()
            if row:
                if row["fingerprint"] != fingerprint:
                    raise AppError(
                        "request_id_conflict",
                        "Request ID already belongs to a different message",
                    )
                return dict(row)
            interrupted = c.execute(
                "SELECT request_id FROM requests WHERE thread_id=? AND status IN ('processing','interrupted')",
                (thread,),
            ).fetchone()
            if interrupted:
                raise AppError(
                    "resume_required",
                    "Continue the interrupted request before sending another question",
                )
            c.execute(
                "INSERT INTO requests VALUES(?,?,?,?,?,?,NULL,NULL,?,?)",
                (thread, request, text, fingerprint, "processing", reference, now, now),
            )
            c.execute(
                "INSERT INTO messages VALUES(?,?,?,?,?,?)",
                (uid(), thread, request, "user", text, now),
            )
            c.execute(
                "UPDATE threads SET updated_ts=? WHERE thread_id=?", (now, thread)
            )
            c.commit()
        return self.request(thread, request)

    def resume(self, thread, request):
        self.require_thread(thread)
        row = self.request(thread, request)
        if row["status"] == "interrupted":
            with connect(self.path) as c:
                c.execute(
                    "UPDATE requests SET status='processing',updated_ts=? WHERE thread_id=? AND request_id=?",
                    (utc_now(), thread, request),
                )
                c.commit()
        return row

    def finish(self, thread, request, response):
        with connect(self.path) as c:
            c.execute("BEGIN IMMEDIATE")
            old = c.execute(
                "SELECT message_id FROM messages WHERE thread_id=? AND request_id=? AND role='assistant'",
                (thread, request),
            ).fetchone()
            message = old[0] if old else uid()
            response["response_message_id"] = message
            text = json.dumps(response, allow_nan=False)
            c.execute(
                "INSERT INTO messages VALUES(?,?,?,?,?,?) ON CONFLICT(thread_id,request_id,role) DO UPDATE SET content=excluded.content",
                (message, thread, request, "assistant", text, utc_now()),
            )
            c.execute(
                "UPDATE requests SET status=?,response=?,error=NULL,updated_ts=? WHERE thread_id=? AND request_id=?",
                (response["request_status"], text, utc_now(), thread, request),
            )
            c.execute(
                "UPDATE threads SET updated_ts=? WHERE thread_id=?", (utc_now(), thread)
            )
            c.commit()
        return self.overlay(response)

    def fail(self, thread, request, error):
        with connect(self.path) as c:
            c.execute(
                "UPDATE requests SET status='failed',error=?,updated_ts=? WHERE thread_id=? AND request_id=?",
                (
                    json.dumps(
                        {
                            "code": error.code,
                            "message": str(error),
                            "status": error.status,
                        }
                    ),
                    utc_now(),
                    thread,
                    request,
                ),
            )
            c.commit()

    def history(self, thread):
        self.require_thread(thread)
        with connect(self.path, readonly=True) as c:
            rows = [
                dict(r)
                for r in c.execute(
                    "SELECT rowid AS sequence,* FROM messages WHERE thread_id=? ORDER BY rowid",
                    (thread,),
                )
            ]
            requests = [
                dict(r)
                for r in c.execute(
                    "SELECT request_id,status,error FROM requests WHERE thread_id=? ORDER BY rowid",
                    (thread,),
                )
            ]
        for row in rows:
            if row["role"] == "assistant":
                row["content"] = self.overlay(json.loads(row["content"]))
        return {
            "thread_id": thread,
            "messages": rows,
            "requests": requests,
            "pending_action": self.pending(thread),
            "effective_reference_date": self.settings.reference().isoformat(),
        }

    def action(self, thread, action):
        with connect(self.subject, readonly=True) as c:
            row = c.execute(
                "SELECT * FROM booking_actions WHERE thread_id=? AND action_id=?",
                (thread, action),
            ).fetchone()
        if row is None:
            raise AppError(
                "action_not_found", "Unknown action in this conversation", 404
            )
        result = dict(row)
        result["fields"] = json.loads(result.pop("display_snapshot"))
        return result

    def pending(self, thread):
        with connect(self.subject, readonly=True) as c:
            row = c.execute(
                "SELECT action_id FROM booking_actions WHERE thread_id=? AND status='pending'",
                (thread,),
            ).fetchone()
        return self.action(thread, row[0]) if row else None

    def overlay(self, response):
        for block in response.get("blocks", []):
            if block["type"] == "confirmation":
                action = self.action(response["thread_id"], block["action_id"])
                block.update(
                    status=action["status"],
                    booking_id=action["booking_id"],
                    fields=action["fields"],
                )
        return response

    def prepare(self, thread, request, slots, *, replace_pending=False):
        self.require_thread(thread)
        start, end = period(slots.start_date, slots.end_date)
        minutes = to_minutes(slots.hours)
        with connect(self.subject) as c:
            c.execute("BEGIN IMMEDIATE")
            old = c.execute(
                "SELECT action_id FROM booking_actions WHERE thread_id=? AND origin_request_id=?",
                (thread, request),
            ).fetchone()
            if old:
                return self.action(thread, old[0])
            person = c.execute(
                "SELECT person_id,display_name FROM people WHERE person_id=?",
                (slots.person_id,),
            ).fetchone()
            project = c.execute(
                "SELECT engagement_id,code FROM engagements WHERE engagement_id=?",
                (slots.engagement_id,),
            ).fetchone()
            if not person or not project:
                raise AppError(
                    "invalid_proposal", "Person or project no longer exists", 422
                )
            pending = c.execute(
                "SELECT action_id FROM booking_actions WHERE thread_id=? AND status='pending'",
                (thread,),
            ).fetchone()
            if pending and not replace_pending:
                raise AppError(
                    "pending_action_exists",
                    "Finish the current booking before starting another",
                )
            action = uid()
            now = utc_now()
            warnings = []
            cap = capacity(start, end)
            if not cap or minutes / 60 > cap:
                warnings.append(
                    "Requested hours exceed estimated Mon-Fri 8h capacity; soft booking is still allowed. No holiday/FTE/leave data."
                )
            conflicts = c.execute(
                "SELECT COALESCE(SUM(minutes),0) FROM bookings WHERE person_id=? AND start_ts<? AND end_ts>?",
                (slots.person_id, end, start),
            ).fetchone()[0]
            if conflicts:
                warnings.append(
                    f"Known intersecting bookings total {conflicts / 60:g}h; daily distribution is unknown."
                )
            fields = {
                "person_id": person[0],
                "person": person[1],
                "engagement_id": project[0],
                "engagement": project[1],
                "start": slots.start_date,
                "end_inclusive": slots.end_date,
                "end_exclusive": datetime.fromtimestamp(end, timezone.utc)
                .date()
                .isoformat(),
                "hours": minutes / 60,
                "minutes": minutes,
                "warnings": warnings,
                "kind": "soft",
            }
            if pending:
                c.execute(
                    "UPDATE booking_actions SET status='superseded',updated_ts=?,decided_ts=? WHERE action_id=?",
                    (now, now, pending[0]),
                )
            c.execute(
                "INSERT INTO booking_actions VALUES(?,?,?,?,?,?,?,?,?,'pending',NULL,NULL,?,?,NULL)",
                (
                    action,
                    thread,
                    request,
                    person[0],
                    project[0],
                    start,
                    end,
                    minutes,
                    json.dumps(fields),
                    now,
                    now,
                ),
            )
            if pending:
                c.execute(
                    "UPDATE booking_actions SET superseded_by=? WHERE action_id=?",
                    (action, pending[0]),
                )
            c.commit()
        event("action_prepared", thread_id=thread, request_id=request, action_id=action)
        return self.action(thread, action)

    def decide(self, thread, action, decision):
        self.require_thread(thread)
        if decision not in {"confirm", "reject"}:
            raise AppError("invalid_request", "Decision must be confirm or reject", 422)
        with connect(self.subject) as c:
            c.execute("BEGIN IMMEDIATE")
            row = c.execute(
                "SELECT * FROM booking_actions WHERE thread_id=? AND action_id=?",
                (thread, action),
            ).fetchone()
            if row is None:
                raise AppError(
                    "action_not_found", "Unknown action in this conversation", 404
                )
            desired = "confirmed" if decision == "confirm" else "rejected"
            if row["status"] == desired:
                return self.action(thread, action)
            if row["status"] != "pending":
                raise AppError(
                    "action_conflict", "This action was already decided or superseded"
                )
            now = utc_now()
            booking = None
            if decision == "confirm":
                fields = json.loads(row["display_snapshot"])
                if (
                    period(fields["start"], fields["end_inclusive"])
                    != (row["start_ts"], row["end_ts"])
                    or to_minutes(fields["hours"]) != row["minutes"]
                    or fields["person_id"] != row["person_id"]
                    or fields["engagement_id"] != row["engagement_id"]
                ):
                    raise AppError(
                        "invalid_proposal",
                        "Stored proposal no longer matches the displayed terms",
                        422,
                    )
                status = c.execute(
                    "SELECT status_id FROM status_lookup WHERE domain='booking' AND code='SFT'"
                ).fetchall()
                if len(status) != 1:
                    raise AppError(
                        "invalid_proposal", "Soft-booking status unavailable", 422
                    )
                for table, key, value in [
                    ("people", "person_id", row["person_id"]),
                    ("engagements", "engagement_id", row["engagement_id"]),
                ]:
                    if not c.execute(
                        f"SELECT 1 FROM {table} WHERE {key}=?", (value,)
                    ).fetchone():
                        raise AppError(
                            "invalid_proposal", "Subject entity no longer exists", 422
                        )
                cursor = c.execute(
                    "INSERT INTO bookings(person_id,engagement_id,status_id,kind,start_ts,end_ts,minutes,created_ts,updated_ts) VALUES(?,?,?,'soft',?,?,?,?,?)",
                    (
                        row["person_id"],
                        row["engagement_id"],
                        status[0][0],
                        row["start_ts"],
                        row["end_ts"],
                        row["minutes"],
                        now,
                        now,
                    ),
                )
                booking = cursor.lastrowid
            c.execute(
                "UPDATE booking_actions SET status=?,booking_id=?,updated_ts=?,decided_ts=? WHERE action_id=?",
                (desired, booking, now, now, action),
            )
            c.commit()
        event(
            "action_committed",
            thread_id=thread,
            action_id=action,
            status=desired,
            booking_id=booking,
        )
        return self.action(thread, action)
