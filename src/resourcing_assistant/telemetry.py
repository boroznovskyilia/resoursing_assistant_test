"""Local JSON diagnostics; never log prompts, credentials or bound source values."""

import contextvars
import json
import logging
from logging.handlers import RotatingFileHandler
import sys
import time

LOG = logging.getLogger("resourcing")
USAGE = contextvars.ContextVar("usage", default=None)


def event(name, **fields):
    trace = USAGE.get() or {}
    level = (
        "WARNING"
        if any(
            word in name
            for word in ("failed", "unavailable", "rejected", "format_error")
        )
        else "INFO"
    )
    LOG.log(
        getattr(logging, level),
        json.dumps(
            {
                "time": time.time(),
                "level": level,
                "event": name,
                "thread_id": trace.get("thread_id"),
                "request_id": trace.get("request_id"),
                **fields,
            },
            allow_nan=False,
        ),
    )


def configure_logging(runtime):
    runtime.mkdir(parents=True, exist_ok=True)
    desired = (runtime / "assistant.log").resolve()
    files = [h for h in LOG.handlers if isinstance(h, RotatingFileHandler)]
    if not files or files[0].baseFilename != str(desired):
        for handler in LOG.handlers[:]:
            LOG.removeHandler(handler)
            handler.close()
        LOG.setLevel(logging.INFO)
        LOG.propagate = False
        LOG.addHandler(logging.StreamHandler(sys.stdout))
        LOG.addHandler(
            RotatingFileHandler(desired, maxBytes=5 * 1024 * 1024, backupCount=3)
        )
    for name in ("litellm", "LiteLLM", "dspy"):
        logging.getLogger(name).setLevel(logging.ERROR)
