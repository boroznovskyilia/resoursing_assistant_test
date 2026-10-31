"""Idempotent local setup; does not make paid model calls or overwrite credentials."""

from .config import ROOT, Settings
from .data import initialize
from .llm import encoding


def main():
    environment = ROOT / ".env"
    if not environment.exists():
        environment.write_text((ROOT / ".env.example").read_text())
    settings = Settings.from_env()
    encoding()
    source = initialize(settings)
    print("Local source and tokenizer ready:", source)
    print("Reference date:", settings.reference().isoformat())
    print("Azure configured:", bool(settings.endpoint and settings.api_key))
    print("Existing credentials and working state preserved. No model requests made.")


if __name__ == "__main__":
    main()
