"""Booking proposal rules, immutable displayed terms and explicit decisions."""

from datetime import UTC, datetime

from resourcing_assistant.domain.calculations import capacity, period, to_minutes
from resourcing_assistant.errors import AppError


class BookingService:
    def __init__(self, repository, conversations):
        self.repository, self.conversations = repository, conversations

    def action(self, thread, action):
        return self.repository.action(thread, action)

    def pending(self, thread):
        return self.repository.pending(thread)

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
        self.conversations.require_thread(thread)
        start, end = period(slots.start_date, slots.end_date)
        minutes = to_minutes(slots.hours)

        def describe(person, project, conflicts):
            warnings = []
            cap = capacity(start, end)
            if not cap or minutes / 60 > cap:
                warnings.append(
                    "Requested hours exceed estimated Mon-Fri 8h capacity; soft booking is still allowed. No holiday/FTE/leave data."
                )
            if conflicts:
                warnings.append(
                    f"Known intersecting bookings total {conflicts / 60:g}h; daily distribution is unknown."
                )
            return {
                "person_id": person["person_id"],
                "person": person["display_name"],
                "engagement_id": project["engagement_id"],
                "engagement": project["code"],
                "start": slots.start_date,
                "end_inclusive": slots.end_date,
                "end_exclusive": datetime.fromtimestamp(end, UTC).date().isoformat(),
                "hours": minutes / 60,
                "minutes": minutes,
                "warnings": warnings,
                "kind": "soft",
            }

        return self.repository.prepare(
            thread,
            request,
            slots,
            start,
            end,
            minutes,
            describe,
            replace_pending=replace_pending,
        )

    def decide(self, thread, action, decision):
        self.conversations.require_thread(thread)
        if decision not in {"confirm", "reject"}:
            raise AppError("invalid_request", "Decision must be confirm or reject", 422)
        return self.repository.decide(thread, action, decision, self.validate_snapshot)

    @staticmethod
    def validate_snapshot(action):
        fields = action["fields"]
        if (
            period(fields["start"], fields["end_inclusive"])
            != (action["start_ts"], action["end_ts"])
            or to_minutes(fields["hours"]) != action["minutes"]
            or fields["person_id"] != action["person_id"]
            or fields["engagement_id"] != action["engagement_id"]
        ):
            raise AppError(
                "invalid_proposal",
                "Stored proposal no longer matches the displayed terms",
                422,
            )
