"""Batched local vector cache and source memberships."""

import json

from sqlalchemy import select
from sqlalchemy.dialects.sqlite import insert

from resourcing_assistant.db.models import Membership, Vector


class VectorRepository:
    def __init__(self, database):
        self.database = database

    def get_many(self, keys):
        result = {}
        keys = list(set(keys))
        with self.database.session() as s:
            for offset in range(0, len(keys), 500):
                for row in s.scalars(
                    select(Vector).where(
                        Vector.cache_key.in_(keys[offset : offset + 500])
                    )
                ):
                    result[row.cache_key] = (json.loads(row.vector), row.dimension)
        return result

    def save(self, model, vectors):
        with self.database.session(write=True) as s:
            for key, text_hash, vector in vectors:
                s.execute(
                    insert(Vector)
                    .values(
                        cache_key=key,
                        model=model,
                        text_hash=text_hash,
                        dimension=len(vector),
                        vector=json.dumps(vector),
                    )
                    .on_conflict_do_nothing(index_elements=["cache_key"])
                )

    def memberships(self, records):
        with self.database.session(write=True) as s:
            for reference, key in records.items():
                s.execute(
                    insert(Membership)
                    .values(source_ref=reference, cache_key=key)
                    .on_conflict_do_update(
                        index_elements=["source_ref"], set_={"cache_key": key}
                    )
                )
