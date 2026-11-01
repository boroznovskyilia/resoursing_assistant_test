"""Idempotent local setup; does not make paid model calls or overwrite credentials."""

import os

from resourcing_assistant.config import ROOT, Settings
from resourcing_assistant.db.source import initialize
from resourcing_assistant.llm.tokens import encoding


def main():
    environment = ROOT / ".env"
    try:
        descriptor = os.open(environment, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        pass
    else:
        with os.fdopen(descriptor, "w") as stream:
            stream.write((ROOT / ".env.example").read_text())
    settings = Settings.from_env()
    encoding()
    source = initialize(settings)
    print("Local source and tokenizer ready:", source)
    print("Reference date:", settings.reference().isoformat())
    print("Azure configured:", settings.azure_configured)
    print("Existing credentials and working state preserved. No model requests made.")


if __name__ == "__main__":
    main()
