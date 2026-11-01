"""Native SQLite connection boundary for protected reads."""

import sqlite3
from contextlib import contextmanager
from pathlib import Path


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


class Database:
    """Short synchronous sessions; immediate writer transactions preserve SQLite action races."""

    def __init__(self, path):
        from sqlalchemy import create_engine, event
        from sqlalchemy.pool import NullPool

        self.path = Path(path)
        self.engine = create_engine(
            "sqlite:///" + str(self.path.resolve()),
            connect_args={"check_same_thread": False, "timeout": 5},
            poolclass=NullPool,
        )

        @event.listens_for(self.engine, "connect")
        def connected(connection, _):
            connection.isolation_level = None
            connection.execute("PRAGMA foreign_keys=ON")

        @event.listens_for(self.engine, "begin")
        def begin(connection):
            connection.exec_driver_sql(
                "BEGIN IMMEDIATE"
                if connection.get_execution_options().get("sqlite_immediate")
                else "BEGIN"
            )

    @contextmanager
    def session(self, *, write=False):
        from sqlalchemy.orm import Session

        with Session(self.engine, expire_on_commit=False) as session:
            session.connection(execution_options={"sqlite_immediate": write})
            try:
                yield session
                if write:
                    session.commit()
            except Exception:
                session.rollback()
                raise

    def close(self):
        self.engine.dispose()
