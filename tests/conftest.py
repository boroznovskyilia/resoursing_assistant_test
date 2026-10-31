import pytest
from resourcing_assistant.config import Settings
from resourcing_assistant.data import initialize
from resourcing_assistant.storage import Store


@pytest.fixture
def store(tmp_path):
    settings = Settings(runtime=tmp_path, reference_date="2026-04-01T00:00:00Z")
    return Store(settings, initialize(settings))
