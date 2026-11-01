"""Bundled tokenizer and rendered prompt accounting."""

import hashlib
import json
import os

import dspy
import tiktoken

from resourcing_assistant.config import ROOT
from resourcing_assistant.errors import AppError
from resourcing_assistant.llm.signatures import SIGNATURES


def encoding():
    key = hashlib.sha1(
        b"https://openaipublic.blob.core.windows.net/encodings/o200k_base.tiktoken"
    ).hexdigest()
    path = ROOT / "data/tokenizer" / key
    if (
        not path.exists()
        or hashlib.sha256(path.read_bytes()).hexdigest()
        != "446a9538cb6c348e3516120d7c08b09f57c36495e2acfffe59a5bf8b0cfb1a2d"
    ):
        raise AppError(
            "tokenizer_unavailable",
            "Bundled tokenizer missing or corrupt; restore the source checkout",
            503,
        )
    os.environ["TIKTOKEN_CACHE_DIR"] = str(path.parent)
    return tiktoken.get_encoding("o200k_base")


def token_count(value):
    return len(
        encoding().encode(
            json.dumps(value, ensure_ascii=False, default=str), disallowed_special=()
        )
    )


def rendered_tokens(name, **inputs):
    adapter = dspy.JSONAdapter(use_native_function_calling=False)
    signature = SIGNATURES[name]
    return (
        token_count(
            {
                "messages": adapter.format(signature, [], inputs),
                "schema": signature.model_json_schema(),
            }
        )
        + 128
    )
