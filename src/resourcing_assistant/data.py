"""Source initialization, safe reads and compact source schema."""

from contextlib import contextmanager, nullcontext
import json
import re
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
RULES = """Use subject source facts, never guessed literal answers. All names/IDs/windows/thresholds as named bound values. Exclude private columns. UTC epochs; human inclusive end day -> next midnight exclusive. Strict booking overlap start_ts<window_end AND end_ts>window_start. Hard metric uses kind='hard' including CMP, full intersecting minutes/60, no prorating, zero via LEFT JOIN/COALESCE. Capacity Mon-Fri8h; strict <60 excludes60. Display percentages on a 0-100 scale; a 0-1 proportion must be labeled ratio/fraction, never pct/percent. If capacity is zero, percentage is undefined: return hours and disclose that limit, never invent0%. Cents/100.0; reduce rate_cards to ONE consistent FX per currency before join; convert then SUM, round FINAL monetary display. Active project domain project/code ACT. Open requirements domain requirement/group open (OPN/PRT); submitted requests in requirement_requests.state. Roles via category_assignments/rate_categories; skills via person_skills/skills exact proficiency. Booked person from bookings.person_id, not allocation person. WBS effort SUM leaves only (NOT EXISTS child); actuals from time_entries via work_items. Aggregate independent many-to-many grains before join. HLS provider unit differs from industry in summary. Invoice cost centers cannot prove project attribution. Return requested total separately from top-N detail. NULL dates unknown, not1970. No filtering by created_ts to simulate a reference snapshot. No bio-based proven leadership. All/count semantic matching requires every eligible candidate. SQL detail LIMIT is not exact total. No source edits."""


class ReadError(Exception):
    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def has_limit(sql, *, outer_only=False):
    """Output-scope check only; SQLite authorizer remains the security boundary."""
    tokens = re.findall(
        r"--[^\n]*|/\*[\s\S]*?(?:\*/|$)|'(?:''|[^'])*'|\"(?:\"\"|[^\"])*\"|`(?:``|[^`])*`|\[[^\]]*\]|[()]|[A-Za-z_][A-Za-z0-9_]*",
        sql,
    )
    depth = 0
    for token in tokens:
        if token == "(":
            depth += 1
        elif token == ")":
            depth -= 1
        elif token.upper() == "LIMIT" and (not outer_only or depth == 0):
            return True
    return False


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
            self.objects = {
                r[0]
                for r in c.execute(
                    "SELECT name FROM sqlite_schema WHERE type IN ('table','view')"
                )
            } | {
                "sqlite_master",
                "sqlite_schema",
                "sqlite_temp_master",
                "sqlite_temp_schema",
            }
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
                notes = {
                    "engagements": "planned_cost_cents is in currency_id minor units. ACTIVE means status_lookup domain=project AND code=ACT only; state_group=open also includes other states and is NOT active. Include qualifying engagement_count beside a project cost aggregate.",
                    "rate_cards": "fx_rate converts this row's currency to the reporting currency. Rates are available HERE, not in a separate FX table. Reduce to one consistent FX per currency (GROUP BY currency_id, MAX(fx_rate)) BEFORE joining money rows. Never invent rate=1 or select a fictitious default tier; tier is unrelated to FX selection.",
                    "currencies": "is_primary=1 identifies the reporting currency. Use rate_cards.fx_rate for conversion from source currency, not an assumed rate.",
                    "time_entries": "ACTUAL logged time: minutes/60.0 gives hours; entry_ts is its UTC date. Join work_items for engagement_id. Bookings/assignments are NOT logged time.",
                    "bookings": "Reserved time, NOT actual logged work. Use its direct person_id. Hard metric is kind=hard including completed rows, full intersecting minutes/60.",
                    "work_items": "Nested WBS: estimate SUM leaves only (no children), not rollups. Critical-path flag is is_critical; blocked status is task/BLK, both structured facts.",
                    "resource_requirements": "Open state is status_id -> status_lookup domain=requirement/state_group=open. request_status describes a different workflow and does not mean open.",
                }.get(table)
                if notes:
                    self.schema[-1]["notes"] = notes
                # Bounded public catalogues prevent guessed enum/status literals.
                value_columns = {
                    "people": ("location_region",),
                    "skills": ("name",),
                    "business_units": ("code",),
                    "currencies": ("iso_code",),
                    "risks": ("severity",),
                    "resource_requirements": ("request_status",),
                    "requirement_requests": ("state",),
                    "bookings": ("kind",),
                }.get(table, ())
                values = {}
                for column in value_columns:
                    found = [
                        r[0]
                        for r in c.execute(
                            f'SELECT DISTINCT "{column}" FROM "{table}" ORDER BY 1 LIMIT 41'
                        )
                    ]
                    if len(found) <= 40:
                        values[column] = found
                if values:
                    self.schema[-1]["values"] = values
                if table == "status_lookup":
                    self.schema[-1]["lookup_rows"] = [
                        dict(r)
                        for r in c.execute(
                            "SELECT status_id,domain,code,state_group FROM status_lookup ORDER BY status_id"
                        )
                    ]

    def prompt_schema(self, schema=None, *, question=""):
        lines = []
        for table in self.schema if schema is None else schema:
            lines.append(
                table["table"]
                + "("
                + ", ".join(f"{k}:{v}" for k, v in table["columns"].items())
                + ")"
            )
            if table["foreign_keys"]:
                lines.append(
                    "FK "
                    + ", ".join(
                        f"{r['from']}->{r['to_table']}.{r['to_column']}"
                        for r in table["foreign_keys"]
                    )
                )
            if table.get("values"):
                lines.append("Values " + json.dumps(table["values"]))
            if table.get("lookup_rows"):
                keys = list(table["lookup_rows"][0])
                lines.append(
                    "Lookup "
                    + ",".join(keys)
                    + ": "
                    + json.dumps([[r[k] for k in keys] for r in table["lookup_rows"]])
                )
            if table.get("notes"):
                lines.append(table["notes"])
        codes = sorted(set(re.findall(r"\bENG-\d{4}-\d+\b", question, re.I)))
        if codes:
            with connect(self.path, readonly=True) as c:
                mentions = [
                    dict(r)
                    for code in codes
                    for r in c.execute(
                        "SELECT engagement_id,code,title FROM engagements WHERE code=? COLLATE NOCASE",
                        (code,),
                    )
                ]
            lines.append(
                "Resolved supplied project codes (actual source identities; do not ask the user to supply their IDs): "
                + json.dumps(mentions)
            )
        return "\n".join(lines)

    def eligibility_columns(self, kind, question):
        """Expose structured predicates only when the user's text actually names them."""

        def mentioned(value):
            return bool(
                value and re.search(r"\b" + re.escape(value) + r"\b", question, re.I)
            )

        table, key = {
            "person": ("people", "person_id"),
            "project": ("engagements", "engagement_id"),
            "risk": ("risks", "risk_id"),
        }[kind]
        allowed = {table: {key}}
        schema = {s["table"]: s for s in self.schema}
        if kind == "person":
            with connect(self.path, readonly=True) as c:
                if any(
                    mentioned(r[0])
                    for r in c.execute("SELECT display_name FROM people")
                ):
                    allowed["people"].add("display_name")
            if any(mentioned(v) for v in schema["people"]["values"]["location_region"]):
                allowed["people"].add("location_region")
            if any(mentioned(v) for v in schema["skills"]["values"]["name"]):
                allowed["skills"] = {"skill_id", "name"}
                allowed["person_skills"] = {"person_id", "skill_id"}
                if re.search(r"\bproficiency\b", question, re.I):
                    allowed["person_skills"].add("proficiency")
            if re.search(r"booked|booking|availability|utilization", question, re.I):
                allowed["bookings"] = self.columns["bookings"]
        else:
            if kind == "risk":
                allowed["risks"].add("engagement_id")
                if any(mentioned(v) for v in schema["risks"]["values"]["severity"]):
                    allowed["risks"].add("severity")
                allowed["engagements"] = {"engagement_id"}
            if re.search(
                r"\b(active|closed|cancelled|canceled|hold|new)\b", question, re.I
            ):
                allowed.setdefault("engagements", {"engagement_id"}).add("status_id")
                allowed["status_lookup"] = self.columns["status_lookup"]
            with connect(self.path, readonly=True) as c:
                if any(
                    mentioned(r["code"]) or mentioned(r["name"])
                    for r in c.execute("SELECT code,name FROM business_units")
                ):
                    allowed.setdefault("engagements", {"engagement_id"}).add(
                        "business_unit_id"
                    )
                    allowed["business_units"] = self.columns["business_units"]
                if any(
                    mentioned(r["display_name"]) or mentioned(r["legal_name"])
                    for r in c.execute("SELECT display_name,legal_name FROM parties")
                ):
                    allowed.setdefault("engagements", {"engagement_id"}).add(
                        "client_party_id"
                    )
                    allowed["parties"] = self.columns["parties"]
            if re.search(r"\bENG-\d{4}-\d+\b", question, re.I):
                allowed.setdefault("engagements", {"engagement_id"}).add("code")
        return allowed

    def simple_eligibility(self, kind, question, slots):
        """Compile broad pools for simple exact filters; complex filters keep guarded SQL planning."""
        allowed = self.eligibility_columns(kind, question)
        if re.search(
            r"\b(previous|above|those|these|them|same|first|second|third|fourth|fifth)\b",
            question,
            re.I,
        ):
            return None
        if any(
            slots.get(k) is not None
            for k in (
                "person",
                "person_id",
                "project",
                "engagement_id",
                "start_date",
                "end_date",
            )
        ):
            return None
        if kind == "person" and allowed == {"people": {"person_id"}}:
            return "SELECT person_id FROM people ORDER BY person_id", {}
        if kind != "project" or set(allowed) - {
            "engagements",
            "status_lookup",
            "business_units",
        }:
            return None
        if allowed["engagements"] - {"engagement_id", "status_id", "business_unit_id"}:
            return None
        predicates, parameters = [], {}
        if "status_lookup" in allowed:
            if not re.search(r"\bactive\b", question, re.I) or re.search(
                r"\b(not active|inactive|closed|hold|cancelled|canceled|new)\b",
                question,
                re.I,
            ):
                return None
            predicates.append(
                "e.status_id IN (SELECT status_id FROM status_lookup WHERE domain='project' AND code='ACT')"
            )
        if "business_units" in allowed:
            matched_units = 0
            with connect(self.path, readonly=True) as c:
                for row in c.execute(
                    "SELECT code,name FROM business_units ORDER BY business_unit_id"
                ):
                    terms = [
                        v
                        for v in row
                        if re.search(r"\b" + re.escape(v) + r"\b", question, re.I)
                    ]
                    if not terms:
                        continue
                    matched_units += 1
                    if matched_units > 1:
                        return None
                    negative = any(
                        re.search(
                            r"\b(?:outside|except|excluding|exclude|other than|not(?: in)?)\s+(?:the\s+)?"
                            + re.escape(v)
                            + r"\b",
                            question,
                            re.I,
                        )
                        for v in terms
                    )
                    if not negative and re.search(
                        r"\b(outside|except|excluding|exclude|other than|not)\b",
                        question,
                        re.I,
                    ):
                        return None
                    key = "unit_" + str(len(parameters))
                    parameters[key] = row["code"]
                    predicates.append(
                        f"e.business_unit_id {'NOT IN' if negative else 'IN'} (SELECT business_unit_id FROM business_units WHERE code=:{key})"
                    )
        where = " WHERE " + " AND ".join(predicates) if predicates else ""
        return (
            "SELECT e.engagement_id FROM engagements e"
            + where
            + " ORDER BY e.engagement_id",
            parameters,
        )

    def read(
        self,
        sql,
        parameters=None,
        query_id="query",
        purpose="detail",
        *,
        connection=None,
        eligibility=None,
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
        denied, eligibility_denied, tables, derived = [], [], set(), set()

        def authorize(action, a, b, database, trigger):
            if (
                action == sqlite3.SQLITE_SELECT
                and trigger
                and trigger not in self.objects
            ):
                derived.add(trigger)
            if action == sqlite3.SQLITE_READ:
                # Materialized CTEs emit table-level reads with no database/column.
                # Never extend this exception to a real (possibly private) object.
                if (
                    database is None
                    and not b
                    and a in derived
                    and a not in self.objects
                ):
                    return sqlite3.SQLITE_OK
                # SQLite emits COUNT/table-level reads with empty column and no database.
                if (
                    database not in ("main", None)
                    or (database is None and b)
                    or a not in self.columns
                    or (b and b not in self.columns[a])
                ):
                    denied.append(True)
                    return sqlite3.SQLITE_DENY
                if eligibility is not None and (
                    a not in eligibility or (b and b not in eligibility[a])
                ):
                    eligibility_denied.append(f"{a}.{b}")
                    return sqlite3.SQLITE_DENY
                tables.add(a)
                if trigger and trigger not in self.objects:
                    derived.add(trigger)
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
                    code,
                    "Query rejected by read policy"
                    if denied
                    else "Semantic eligibility used an unrequested or free-text predicate: "
                    + ", ".join(eligibility_denied)
                    + ". Select only broad IDs using the provided eligibility schema; semantic meaning is assessed later."
                    if eligibility_denied
                    else str(error),
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

    def read_pages(self, sql, parameters, key, query_id, purpose, *, eligibility=None):
        """Page a validated SELECT over a single source snapshot, before any model call."""
        if key not in {"person_id", "engagement_id", "risk_id"}:
            raise ReadError("invalid_sql", "Unsupported candidate identity key")
        if any(name.startswith("__ra_") for name in parameters):
            raise ReadError("invalid_sql", "Reserved pagination parameter name")
        with connect(self.path, readonly=True) as conn:
            conn.execute("BEGIN")
            first = self.read(
                sql,
                parameters,
                query_id,
                purpose,
                connection=conn,
                eligibility=eligibility,
            )
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
                    eligibility=eligibility,
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
