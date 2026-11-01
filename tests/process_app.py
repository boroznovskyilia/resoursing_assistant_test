"""Test-only API factory; no production fake-provider switch exists."""

import os
import time
from pathlib import Path

from resourcing_assistant.app import create_app as production_app
from resourcing_assistant.config import Settings
from resourcing_assistant.errors import AppError
from tests.test_agent import ScriptedGateway


def create_app():
    runtime = Path(os.environ["TEST_RUNTIME"])

    class ProcessGateway(ScriptedGateway):
        def call(self, name, **inputs):
            with (runtime / "test-model-calls").open("a") as stream:
                stream.write(name + "\n")
            if name == "InterpretRequest" and inputs["message"] in ("book8", "book16"):
                result = super().call(name, **{**inputs, "message": "book"})
                hours, start, end = (
                    (8.0, "2026-04-02", "2026-04-02")
                    if inputs["message"] == "book8"
                    else (16.0, "2026-05-04", "2026-05-05")
                )
                return result.model_copy(
                    update={
                        "slots": result.slots.model_copy(
                            update={
                                "hours": hours,
                                "start_date": start,
                                "end_date": end,
                            }
                        )
                    }
                )
            if name == "InterpretRequest" and inputs["message"] == "fail":
                raise AppError("provider_unavailable", "Injected test-only outage", 503)
            if (
                name == "InterpretRequest"
                and inputs["message"] == "hang"
                and not (runtime / "entered").exists()
            ):
                (runtime / "entered").write_text("Interpreter entered before crash")
                time.sleep(60)
            return super().call(name, **inputs)

    return production_app(
        Settings(
            runtime=runtime,
            reference_date="2026-04-01T00:00:00Z",
            endpoint="",
            api_key="",
        ),
        ProcessGateway(),
    )
