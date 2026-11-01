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
