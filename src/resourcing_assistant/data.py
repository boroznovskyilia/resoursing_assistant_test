"""Source initialization, safe reads and compact source schema."""

from contextlib import contextmanager, nullcontext
import json
import hashlib
from pathlib import Path
import sqlite3
import time
from .telemetry import event

SUBJECT_TABLES = frozenset(
    "approvals assignments billing_documents bookings business_units category_assignments currencies engagements org_units parties people person_skills rate_cards rate_categories requirement_requests resource_requirements risks skills status_lookup team_allocations time_entries work_item_links work_items".split()
)
PRIVATE_COLUMNS = {"people": {"auth_user_id", "avatar_url"}}
FUNCTIONS = frozenset(
    "abs avg cast char coalesce concat concat_ws count date datetime glob group_concat hex ifnull iif instr julianday length like likelihood likely lower ltrim max min nullif replace round rtrim sign strftime substr substring sum time total trim typeof unicode unixepoch unlikely upper".split()
)
RULES = """Use subject source facts, never guessed literal answers. All names/IDs/windows/thresholds as named bound values. Exclude private columns. UTC epochs; human inclusive end day -> next midnight exclusive. Strict booking overlap start_ts<window_end AND end_ts>window_start. Hard metric uses kind='hard' including CMP, full intersecting minutes/60, no prorating, zero via LEFT JOIN/COALESCE. Capacity Mon-Fri8h; strict <60 excludes60. If capacity is zero, percentage is undefined: return hours and disclose that limit, never invent0%. Cents/100.0; reduce rate_cards to ONE consistent FX per currency before join; convert then SUM, round FINAL monetary display. Active project domain project/code ACT. Open requirements domain requirement/group open (OPN/PRT); submitted requests in requirement_requests.state. Roles via category_assignments/rate_categories; skills via person_skills/skills exact proficiency. Booked person from bookings.person_id, not allocation person. WBS effort SUM leaves only (NOT EXISTS child); actuals from time_entries via work_items. Aggregate independent many-to-many grains before join. HLS provider unit differs from industry in summary. Invoice cost centers cannot prove project attribution. Return requested total separately from top-N detail. NULL dates unknown, not1970. No filtering by created_ts to simulate a reference snapshot. No bio-based proven leadership. All/count semantic matching requires every eligible candidate. SQL detail LIMIT is not exact total. No source edits."""


class ReadError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


@contextmanager
def connect(path, *, readonly=False):
    conn = sqlite3.connect(
        Path(path).resolve().as_uri() + "?mode=ro" if readonly else str(path),
        uri=readonly,
        timeout=5,
    )
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
    finally:
        conn.close()


def initialize(settings):
    settings.runtime.mkdir(parents=True, exist_ok=True)
    target = settings.runtime / "subject.sqlite"
    if target.resolve() == settings.source.resolve():
        raise ValueError("Working database cannot be original source")
    source_hash = hashlib.sha256(settings.source.read_bytes()).hexdigest()
    if (
        source_hash
        != "8d00b91ae6aa23bbcf0d807c2e51fa6a45f7017a6557a4f51d11cfc82bfb4259"
    ):
        raise ValueError(
            "Supplied mock source fingerprint does not match the assignment"
        )
    if not target.exists():
        temp = target.with_suffix(".initializing")
        with (
            connect(settings.source, readonly=True) as source,
            connect(temp) as destination,
        ):
            source.backup(destination)
            destination.execute(
                "CREATE TABLE assistant_metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL)"
            )
            destination.executemany(
                "INSERT INTO assistant_metadata VALUES(?,?)",
                [("schema_version", "1"), ("source_sha256", source_hash)],
            )
            destination.commit()
        temp.replace(target)
    with connect(target) as c:
        try:
            metadata = dict(c.execute("SELECT key,value FROM assistant_metadata"))
        except sqlite3.Error as error:
            raise ValueError(
                "Working source metadata missing; refusing to reset saved state"
            ) from error
        if (
            metadata.get("schema_version") != "1"
            or metadata.get("source_sha256") != source_hash
        ):
            raise ValueError(
                "Working source version/fingerprint incompatible; saved state preserved"
            )
        if c.execute("PRAGMA quick_check").fetchone()[0] != "ok":
            raise ValueError("Source database integrity failure")
    return target


class Reader:
    def __init__(self, settings, path):
        self.settings, self.path = settings, Path(path)
        self.columns = {}
        self.schema = []
        with connect(path, readonly=True) as c:
            for table in sorted(SUBJECT_TABLES):
                columns = [
                    dict(r)
                    for r in c.execute(f'PRAGMA table_info("{table}")')
                    if r["name"] not in PRIVATE_COLUMNS.get(table, set())
                ]
                self.columns[table] = {r["name"] for r in columns}
                foreign = [
                    dict(r) for r in c.execute(f'PRAGMA foreign_key_list("{table}")')
                ]
                self.schema.append(
                    {
                        "table": table,
                        "columns": {r["name"]: r["type"] for r in columns},
                        "foreign_keys": [
                            {
                                "from": r["from"],
                                "to_table": r["table"],
                                "to_column": r["to"],
                            }
                            for r in foreign
                        ],
                    }
                )

    def read(
        self,
        sql,
        parameters=None,
        query_id="query",
        purpose="detail",
        *,
        connection=None,
    ):
        if (
            not isinstance(sql, str)
            or len(sql) > 50000
            or not isinstance(parameters or {}, dict)
        ):
            raise ReadError("invalid_sql", "Invalid SQL plan")
        start = time.monotonic()
        digest = hashlib.sha256(sql.encode()).hexdigest()
        event("sql_started", query_id=query_id, sql_sha256=digest)
        denied, tables = [], set()

        def authorize(action, a, b, database, trigger):
            if action == sqlite3.SQLITE_READ:
                # SQLite emits COUNT/table-level reads with empty column and no database.
                if (
                    database not in ("main", None)
                    or (database is None and b)
                    or a not in self.columns
                    or (b and b not in self.columns[a])
                ):
                    denied.append(True)
                    return sqlite3.SQLITE_DENY
                tables.add(a)
            elif action == sqlite3.SQLITE_FUNCTION:
                if (b or a or "").lower() not in FUNCTIONS:
                    denied.append(True)
                    return sqlite3.SQLITE_DENY
            elif action not in (sqlite3.SQLITE_SELECT, sqlite3.SQLITE_RECURSIVE):
                denied.append(True)
                return sqlite3.SQLITE_DENY
            return sqlite3.SQLITE_OK

        with (
            connect(self.path, readonly=True)
            if connection is None
            else nullcontext(connection)
        ) as c:
            c.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, self.settings.byte_limit)
            c.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 50000)
            c.set_authorizer(authorize)
            c.set_progress_handler(
                lambda: int(time.monotonic() - start > self.settings.sql_timeout), 1000
            )
            try:
                cur = c.execute(sql, parameters or {})
                keys = [r[0] for r in cur.description or []]
                if len(set(keys)) != len(keys):
                    raise ReadError("invalid_sql", "Result columns need unique aliases")
                rows, size, truncated = [], 2, False
                while True:
                    row = cur.fetchone()
                    if row is None:
                        break
                    item = dict(row)
                    encoded = json.dumps(
                        item, ensure_ascii=False, allow_nan=False
                    ).encode()
                    if (
                        len(rows) >= self.settings.row_limit
                        or size + len(encoded) + 1 > self.settings.byte_limit
                    ):
                        truncated = True
                        break
                    size += len(encoded) + 1
                    rows.append(item)
                if not tables:
                    raise ReadError(
                        "sql_policy",
                        "Source-derived answers must read allowed subject records",
                    )
            except ReadError as error:
                event(
                    "sql_rejected",
                    query_id=query_id,
                    code=error.code,
                    sql_sha256=digest,
                )
                raise
            except sqlite3.Error as error:
                code = (
                    "sql_policy"
                    if denied
                    else (
                        "sql_timeout"
                        if time.monotonic() - start > self.settings.sql_timeout
                        else (
                            "sql_limit"
                            if isinstance(error, sqlite3.DataError)
                            else "invalid_sql"
                        )
                    )
                )
                event(
                    "sql_failed",
                    query_id=query_id,
                    code=code,
                    sql_sha256=digest,
                    latency_ms=round((time.monotonic() - start) * 1000),
                )
                raise ReadError(
                    code, "Query rejected by read policy" if denied else str(error)
                ) from error
        event(
            "sql_completed",
            query_id=query_id,
            sql_sha256=digest,
            rows=len(rows),
            truncated=truncated,
            latency_ms=round((time.monotonic() - start) * 1000),
        )
        return {
            "query_id": query_id,
            "purpose": purpose,
            "sql": sql,
            "parameters": parameters or {},
            "columns": keys,
            "rows": rows,
            "truncated": truncated,
            "source_tables": sorted(tables),
        }

    def read_pages(self, sql, parameters, key, query_id, purpose):
        """Page a validated SELECT over a single source snapshot, before any model call."""
        if key not in {"person_id", "engagement_id", "risk_id"}:
            raise ReadError("invalid_sql", "Unsupported candidate identity key")
        if any(name.startswith("__ra_") for name in parameters):
            raise ReadError("invalid_sql", "Reserved pagination parameter name")
        with connect(self.path, readonly=True) as conn:
            conn.execute("BEGIN")
            first = self.read(sql, parameters, query_id, purpose, connection=conn)
            if key not in first["columns"]:
                raise ReadError(
                    "invalid_sql", "Candidate query omitted source identity"
                )
            if not first["truncated"]:
                return [first]
            # Original SQL has already passed the single-statement/authorizer policy.
            original = sql.rstrip().removesuffix(";")
            wrapped = f'SELECT * FROM (\n{original}\n) AS candidate_page WHERE (:__ra_cursor IS NULL OR "{key}">:__ra_cursor) ORDER BY "{key}" LIMIT :__ra_size'
            pages = []
            cursor = None
            while True:
                page = self.read(
                    wrapped,
                    {
                        **parameters,
                        "__ra_cursor": cursor,
                        "__ra_size": self.settings.row_limit + 1,
                    },
                    query_id + f"_page{len(pages) + 1}",
                    purpose,
                    connection=conn,
                )
                values = [r[key] for r in page["rows"]]
                if any(type(value) is not int for value in values):
                    raise ReadError(
                        "invalid_sql", "Candidate IDs must be source integers"
                    )
                pages.append(page)
                if not page["truncated"]:
                    break
                if not values or (cursor is not None and max(values) <= cursor):
                    raise ReadError("invalid_sql", "Candidate cursor did not advance")
                cursor = max(values)
            return pages
