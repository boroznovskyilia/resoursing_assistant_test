"""Test-only API factory; no production fake-provider switch exists."""

import os
from pathlib import Path
import time
from resourcing_assistant.api import create_app as production_app
from resourcing_assistant.config import Settings
from resourcing_assistant.models import AppError
from tests.test_agent import ScriptedGateway


def create_app():
    runtime = Path(os.environ["TEST_RUNTIME"])

    class ProcessGateway(ScriptedGateway):
        def call(self, name, **inputs):
            with (runtime / "test-model-calls").open("a") as stream:
                stream.write(name + "\n")
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
        Settings(runtime=runtime, reference_date="2026-04-01T00:00:00Z"),
        ProcessGateway(),
    )
