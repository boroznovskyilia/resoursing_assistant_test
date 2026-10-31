from dataclasses import replace
from datetime import datetime, timezone
from hashlib import sha256
import pytest

from resourcing_assistant.config import Settings, period, to_minutes, capacity
from resourcing_assistant.data import initialize, Reader, ReadError


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
    assert (
        datetime.fromtimestamp(end, timezone.utc).isoformat()
        == "2026-05-01T00:00:00+00:00"
    )
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
    reader = Reader(replace(settings, row_limit=2), path)
    result = reader.read("SELECT person_id FROM people ORDER BY person_id")
    assert len(result["rows"]) == 2 and result["truncated"]
    assert reader.read("SELECT COUNT(*) AS n FROM people")["rows"] == [{"n": 400}]
    reader = Reader(replace(settings, sql_timeout=0.001), path)
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
    reader = Reader(replace(settings, row_limit=2), path)
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
    small = Reader(replace(settings, byte_limit=5000), path)
    result = small.read("SELECT person_id,bio FROM people ORDER BY person_id")
    assert result["truncated"] and len(result["rows"]) < 400
