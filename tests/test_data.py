from datetime import UTC, datetime
from hashlib import sha256

import pytest

from resourcing_assistant.config import Settings
from resourcing_assistant.db.reader import Reader, ReadError
from resourcing_assistant.db.session import connect
from resourcing_assistant.db.source import initialize
from resourcing_assistant.domain.calculations import capacity, period, to_minutes


@pytest.fixture
def data(tmp_path):
    settings = Settings(runtime=tmp_path)
    path = initialize(settings)
    return settings, path, Reader(settings, path)


def test_clock_minutes_and_inclusive_end():
    assert to_minutes(40) == 2400
    for value in (0, -1, float("nan"), float("inf"), 0.001):
        with pytest.raises(ValueError):
            to_minutes(value)
    start, end = period("2026-04-01", "2026-04-30")
    assert datetime.fromtimestamp(end, UTC).isoformat() == "2026-05-01T00:00:00+00:00"
    assert capacity(*period("2026-03-01", "2026-05-31")) == 520
    assert capacity(*period("2026-04-04", "2026-04-05")) == 0
    assert Settings().reference().tzinfo is not None


def test_comments_cte_count_and_bindings(data):
    _, _, reader = data
    assert reader.read(
        "-- comment\nWITH a AS (SELECT person_id FROM people) SELECT COUNT(*) AS n FROM a"
    )["rows"] == [{"n": 400}]
    assert (
        reader.read(
            "SELECT person_id FROM people WHERE display_name=:name",
            {"name": "x' OR 1=1--"},
        )["rows"]
        == []
    )


def test_limit_scope_ignores_quoted_text_and_comments():
    from resourcing_assistant.db.reader import has_limit

    assert has_limit("SELECT person_id FROM people LIMIT 5")
    assert has_limit(
        "WITH sample AS (SELECT person_id FROM people LIMIT 5) SELECT * FROM sample"
    )
    assert not has_limit(
        "WITH lookup AS (SELECT currency_id FROM currencies WHERE is_primary=1 LIMIT 1) SELECT * FROM lookup",
        outer_only=True,
    )
    assert has_limit(
        "WITH lookup AS (SELECT currency_id FROM currencies LIMIT 1) SELECT * FROM lookup LIMIT 5",
        outer_only=True,
    )
    assert not has_limit(
        "SELECT 'LIMIT 5' AS note, person_id FROM people -- LIMIT 1\n/* LIMIT 2 */"
    )


def test_planner_catalogues_are_bounded_source_values(data):
    _, _, reader = data
    schema = {t["table"]: t for t in reader.schema}
    assert set(schema["people"]["values"]["location_region"]) == {
        "AMER",
        "EMEA",
        "APAC",
        "LATAM",
    }
    assert len(schema["skills"]["values"]["name"]) == 40
    assert any(
        r["domain"] == "requirement" and r["code"] == "OPN"
        for r in schema["status_lookup"]["lookup_rows"]
    )
    assert "auth_user_id" not in schema["people"]["columns"]
    assert "is_primary" in schema["currencies"]["columns"]
    assert "is_primary=1" in schema["currencies"]["notes"]
    assert all(
        len(v) <= 40 for t in reader.schema for v in t.get("values", {}).values()
    )


def test_semantic_eligibility_cannot_prefilter_meaning_or_invent_filters(data):
    _, _, reader = data
    allowed = reader.eligibility_columns(
        "project", "Which active healthcare projects have people risks?"
    )
    assert set(allowed) == {"engagements", "status_lookup"}
    with pytest.raises(ReadError) as error:
        reader.read_pages(
            "SELECT e.engagement_id FROM engagements e JOIN risks r USING(engagement_id) WHERE r.description LIKE '%people%'",
            {},
            "engagement_id",
            "bad",
            "Candidates",
            eligibility=allowed,
        )
    assert error.value.code == "invalid_sql" and "Semantic eligibility" in str(
        error.value
    )
    valid = reader.read_pages(
        "SELECT e.engagement_id FROM engagements e JOIN status_lookup s ON s.status_id=e.status_id WHERE s.domain='project' AND s.code='ACT'",
        {},
        "engagement_id",
        "all",
        "Candidates",
        eligibility=allowed,
    )
    assert len(valid[0]["rows"]) == 60
    assert "business_units" in reader.eligibility_columns(
        "project", "All active projects outside HLS business unit"
    )
    people = reader.eligibility_columns(
        "person", "Find experienced data engineers who could lead a migration"
    )
    assert people == {"people": {"person_id"}}
    assert "person_skills" in reader.eligibility_columns(
        "person", "Python in EMEA at proficiency 4"
    )
    with pytest.raises(ReadError) as error:
        reader.read("SELECT auth_user_id FROM people", eligibility=people)
    assert error.value.code == "sql_policy"


def test_compiled_eligibility_uses_source_filters_without_semantic_keywords(data):
    _, _, reader = data

    def ids(kind, question):
        sql, params = reader.simple_eligibility(kind, question, {})
        return reader.read(sql, params)["rows"]

    assert len(ids("person", "Find experienced data engineers")) == 400
    assert len(ids("project", "All active healthcare projects with people risks")) == 60
    assert len(ids("project", "All active projects outside HLS business unit")) == 49
    assert len(ids("project", "All projects with people risks")) == 150
    assert (
        reader.simple_eligibility("person", "Python in EMEA at proficiency 4", {})
        is None
    )
    assert reader.simple_eligibility("project", "Active HLS or FS projects", {}) is None


def test_forbidden_sources_writes_and_multiple_statements(data):
    _, _, reader = data
    for sql in (
        "DELETE FROM bookings",
        "CREATE TABLE evil(a)",
        "ATTACH DATABASE ':memory:' AS extra",
        "PRAGMA table_info(people)",
        "SELECT auth_user_id FROM people",
        "SELECT bytes FROM person_avatars",
        "SELECT * FROM sqlite_master",
        "SELECT load_extension('x')",
    ):
        with pytest.raises(ReadError) as error:
            reader.read(sql)
        assert error.value.code == "sql_policy"
    with pytest.raises(ReadError):
        reader.read("SELECT person_id FROM people; DELETE FROM bookings")
    with pytest.raises(ReadError):
        reader.read("SELECT 32 AS invented_answer")


def test_limits_and_source_grounding(data):
    settings, path, reader = data
    reader = Reader(Settings(**(settings.model_dump() | {"row_limit": 2})), path)
    result = reader.read("SELECT person_id FROM people ORDER BY person_id")
    assert len(result["rows"]) == 2 and result["truncated"]
    assert reader.read("SELECT COUNT(*) AS n FROM people")["rows"] == [{"n": 400}]
    reader = Reader(Settings(**(settings.model_dump() | {"sql_timeout": 0.001})), path)
    with pytest.raises(ReadError) as error:
        reader.read(
            "WITH RECURSIVE a(n) AS (SELECT 1 UNION ALL SELECT n+1 FROM a WHERE n<10000000) SELECT SUM(n) AS n FROM a CROSS JOIN people"
        )
    assert error.value.code == "sql_timeout"


def test_correct_source_grains_and_idempotent_initialization(data):
    settings, path, reader = data
    assert reader.read(
        "SELECT SUM(minutes)/60.0 AS hours FROM bookings WHERE person_id=:id AND kind='hard'",
        {"id": 348},
    )["rows"] == [{"hours": 30.0}]
    source_hash = sha256(settings.source.read_bytes()).hexdigest()
    before = sha256(path.read_bytes()).hexdigest()
    initialize(settings)
    assert sha256(path.read_bytes()).hexdigest() == before
    assert (
        source_hash
        == "8d00b91ae6aa23bbcf0d807c2e51fa6a45f7017a6557a4f51d11cfc82bfb4259"
    )


def test_candidate_pages_cover_full_set_without_expanding_privileges(data):
    settings, path, _ = data
    reader = Reader(Settings(**(settings.model_dump() | {"row_limit": 2})), path)
    pages = reader.read_pages(
        "SELECT person_id FROM people WHERE person_id<=:n",
        {"n": 5},
        "person_id",
        "eligible",
        "Candidates",
    )
    assert [row["person_id"] for page in pages for row in page["rows"]] == [
        1,
        2,
        3,
        4,
        5,
    ]
    assert len(pages) == 3 and not pages[-1]["truncated"]
    with pytest.raises(ReadError):
        reader.read_pages(
            "SELECT auth_user_id FROM people", {}, "person_id", "bad", "Bad"
        )


def test_large_single_scalar_and_byte_budget(data):
    settings, path, reader = data
    with pytest.raises(ReadError) as error:
        reader.read(
            "SELECT printf('%10000000s',display_name) AS huge FROM people LIMIT 1"
        )
    assert error.value.code == "sql_policy"
    with pytest.raises(ReadError) as error:
        reader.read(
            "SELECT group_concat(a.display_name || b.display_name || c.display_name,'') AS huge FROM people a CROSS JOIN people b CROSS JOIN people c"
        )
    assert error.value.code == "sql_limit"
    small = Reader(Settings(**(settings.model_dump() | {"byte_limit": 5000})), path)
    result = small.read("SELECT person_id,bio FROM people ORDER BY person_id")
    assert result["truncated"] and len(result["rows"]) < 400


def test_materialized_cte_reads_do_not_grant_private_objects(data):
    settings, path, _ = data
    with connect(path) as c:
        c.execute("CREATE TABLE private_values(secret TEXT)")
        c.execute("INSERT INTO private_values VALUES('private')")
        c.commit()
    reader = Reader(settings, path)
    result = reader.read(
        "WITH primary_currency AS MATERIALIZED (SELECT currency_id FROM currencies WHERE is_primary=1) SELECT COUNT(*) AS n FROM engagements e CROSS JOIN primary_currency"
    )
    assert result["rows"] == [{"n": 150}]
    assert set(result["source_tables"]) == {"currencies", "engagements"}
    for sql in (
        "SELECT COUNT(*) FROM private_values",
        "WITH x AS MATERIALIZED (SELECT * FROM private_values) SELECT COUNT(*) FROM x",
        "WITH private_values AS (SELECT person_id FROM people) SELECT COUNT(*) FROM main.private_values",
        "SELECT COUNT(*) FROM sqlite_master",
    ):
        with pytest.raises(ReadError) as error:
            reader.read(sql)
        assert error.value.code == "sql_policy"


def test_supplied_project_codes_resolve_before_interpretation(data):
    _, _, reader = data
    schema = reader.prompt_schema(question="Who logged hours for eng-2026-0001?")
    assert '"engagement_id": 1, "code": "ENG-2026-0001"' in schema
    assert "do not ask the user to supply their IDs" in schema
    assert "ENG-2099-9999" not in reader.prompt_schema(question="Unknown ENG-2099-9999")


def test_read_provenance_tracks_physical_columns_not_aliases(data):
    _, _, reader = data
    correct = reader.read(
        "WITH usage AS (SELECT SUM(b.minutes)/60.0 AS hours FROM bookings b) SELECT hours AS duration FROM usage"
    )
    wrong = reader.read("SELECT SUM(end_ts-start_ts)/60.0 AS minutes FROM bookings")
    assert "minutes" in correct["source_columns"]["bookings"]
    assert "minutes" not in wrong["source_columns"]["bookings"]
    assert {"start_ts", "end_ts"} <= set(wrong["source_columns"]["bookings"])
