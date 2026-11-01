"""Immutable source preparation and fingerprint validation."""

import hashlib
import sqlite3

from resourcing_assistant.db.session import connect


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


class SourceRepository:
    """Fixed source lookups and batched document facts; never executes model SQL."""

    def __init__(self, database, tables):
        self.database, self.tables = database, tables

    def people(self, *, person_id=None, name=None):
        from sqlalchemy import func, select

        t = self.tables["people"]
        condition = (
            t.c.person_id == person_id
            if person_id is not None
            else func.lower(t.c.display_name) == func.lower(name)
        )
        with self.database.session() as s:
            return [
                dict(r)
                for r in s.execute(
                    select(t.c.person_id, t.c.display_name, t.c.location_region).where(
                        condition
                    )
                ).mappings()
            ]

    def projects(self, *, engagement_id=None, name=None):
        from sqlalchemy import func, or_, select

        t = self.tables["engagements"]
        condition = (
            t.c.engagement_id == engagement_id
            if engagement_id is not None
            else or_(
                func.lower(t.c.code) == func.lower(name),
                func.lower(t.c.title) == func.lower(name),
            )
        )
        with self.database.session() as s:
            return [
                dict(r)
                for r in s.execute(
                    select(t.c.engagement_id, t.c.code, t.c.title).where(condition)
                ).mappings()
            ]

    def document_facts(self, kind, eligible=None):
        from collections import defaultdict

        from sqlalchemy import select

        if eligible is not None and not eligible:
            return []
        tables = self.tables
        with self.database.session() as s:
            if kind == "person":
                p, ca, rc, ps, sk = (
                    tables[n]
                    for n in (
                        "people",
                        "category_assignments",
                        "rate_categories",
                        "person_skills",
                        "skills",
                    )
                )
                query = select(
                    p.c.person_id, p.c.display_name, p.c.bio, p.c.location_region
                ).order_by(p.c.person_id)
                if eligible is not None:
                    query = query.where(p.c.person_id.in_(eligible))
                people = [dict(r) for r in s.execute(query).mappings()]
                ids = [p["person_id"] for p in people]
                if not ids:
                    return []
                roles, skills = defaultdict(list), defaultdict(list)
                for person_id, name in s.execute(
                    select(ca.c.person_id, rc.c.name)
                    .select_from(ca.join(rc, ca.c.category_id == rc.c.category_id))
                    .where(ca.c.person_id.in_(ids))
                    .order_by(ca.c.person_id, ca.c.is_default.desc(), rc.c.category_id)
                ):
                    roles[person_id].append(name)
                for person_id, name, proficiency in s.execute(
                    select(ps.c.person_id, sk.c.name, ps.c.proficiency)
                    .select_from(ps.join(sk, ps.c.skill_id == sk.c.skill_id))
                    .where(ps.c.person_id.in_(ids))
                    .order_by(ps.c.person_id, sk.c.skill_id)
                ):
                    skills[person_id].append({"name": name, "proficiency": proficiency})
                return [
                    {
                        **p,
                        "roles": roles[p["person_id"]],
                        "skills": skills[p["person_id"]],
                    }
                    for p in people
                ]
            if kind == "project":
                p, r = tables["engagements"], tables["risks"]
                query = select(
                    p.c.engagement_id, p.c.code, p.c.title, p.c.summary
                ).order_by(p.c.engagement_id)
                if eligible is not None:
                    query = query.where(p.c.engagement_id.in_(eligible))
                projects = [dict(row) for row in s.execute(query).mappings()]
                ids = [p["engagement_id"] for p in projects]
                if not ids:
                    return []
                risks = defaultdict(list)
                for row in s.execute(
                    select(
                        r.c.engagement_id, r.c.risk_id, r.c.description, r.c.severity
                    )
                    .where(r.c.engagement_id.in_(ids))
                    .order_by(r.c.engagement_id, r.c.risk_id)
                ).mappings():
                    value = dict(row)
                    risks[value.pop("engagement_id")].append(value)
                return [{**p, "risks": risks[p["engagement_id"]]} for p in projects]
            r, p = tables["risks"], tables["engagements"]
            query = (
                select(r, p.c.code)
                .select_from(r.join(p, r.c.engagement_id == p.c.engagement_id))
                .order_by(r.c.risk_id)
            )
            if eligible is not None:
                query = query.where(r.c.risk_id.in_(eligible))
            return [dict(row) for row in s.execute(query).mappings()]
