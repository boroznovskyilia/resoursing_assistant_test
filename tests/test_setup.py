from resourcing_assistant.config import Settings
import resourcing_assistant.setup as setup


def test_setup_creates_private_env_once_and_preserves_existing_state(
    tmp_path, monkeypatch
):
    (tmp_path / ".env.example").write_text("AZURE_API_KEY=\n")
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    monkeypatch.setattr(
        Settings, "from_env", lambda: Settings(runtime=tmp_path / ".runtime")
    )
    setup.main()
    environment = tmp_path / ".env"
    assert environment.stat().st_mode & 0o077 == 0
    environment.write_text("AZURE_API_KEY=user-owned-placeholder\n")
    subject = tmp_path / ".runtime/subject.sqlite"
    initial = subject.read_bytes()
    setup.main()
    assert environment.read_text() == "AZURE_API_KEY=user-owned-placeholder\n"
    assert subject.read_bytes() == initial
