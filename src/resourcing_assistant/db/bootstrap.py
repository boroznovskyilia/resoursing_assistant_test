"""Initialize only owned tables; preserve and validate existing runtime schemas."""

from sqlalchemy import MetaData, Table, inspect, update

from resourcing_assistant.db.models import AppBase, BookingAction, Request, SubjectBase


def initialize_owned(app, subject):
    AppBase.metadata.create_all(app.engine)
    SubjectBase.metadata.create_all(subject.engine, tables=[BookingAction.__table__])
    for database, tables in (
        (app, AppBase.metadata.tables.values()),
        (subject, [BookingAction.__table__]),
    ):
        inspector = inspect(database.engine)
        for table in tables:
            actual = {column["name"] for column in inspector.get_columns(table.name)}
            if actual != set(table.columns.keys()):
                raise ValueError(
                    f"Incompatible saved {table.name} schema; existing data was preserved"
                )
    with app.session(write=True) as session:
        session.execute(
            update(Request)
            .where(Request.status == "processing")
            .values(status="interrupted")
        )


def reflect_source(database):
    metadata = MetaData()
    return {
        name: Table(name, metadata, autoload_with=database.engine, resolve_fks=False)
        for name in (
            "people",
            "engagements",
            "status_lookup",
            "bookings",
            "category_assignments",
            "rate_categories",
            "person_skills",
            "skills",
            "risks",
        )
    }
