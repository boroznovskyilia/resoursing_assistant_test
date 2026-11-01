import os

import pytest

from resourcing_assistant.app import create_service
from resourcing_assistant.config import Settings


@pytest.fixture(autouse=True)
def isolated_settings_environment(monkeypatch):
    """Unit checks must not inherit model credentials or limits from the host shell."""
    names = {name.lower() for name in Settings.model_fields}
    for field in Settings.model_fields.values():
        alias = field.validation_alias
        if isinstance(alias, str):
            names.add(alias.lower())
        elif alias is not None:
            names.update(name.lower() for name in alias.choices)
    for name in os.environ:
        if name.lower() in names:
            monkeypatch.delenv(name)


@pytest.fixture
def store(tmp_path):
    from tests.test_agent import ScriptedGateway

    service = create_service(
        Settings(runtime=tmp_path, reference_date="2026-04-01T00:00:00Z"),
        ScriptedGateway(),
    )
    try:
        yield service
    finally:
        service.close()
