"""Typed DSPy stages and one observable retry/budget boundary."""

import math
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import dspy
from pydantic import ValidationError

from resourcing_assistant.errors import AppError
from resourcing_assistant.llm.signatures import signature_for
from resourcing_assistant.llm.tokens import token_count
from resourcing_assistant.telemetry import USAGE, event


def retry_call(fn, *, stage, deployment, sleep=time.sleep):
    for attempt in range(2):
        start = time.monotonic()
        usage = USAGE.get()
        if usage is not None:
            usage[stage + "_attempts"] = usage.get(stage + "_attempts", 0) + 1
        try:
            result = fn()
            event(
                "provider_attempt",
                stage=stage,
                deployment=deployment,
                attempt=attempt + 1,
                outcome="success",
                latency_ms=round((time.monotonic() - start) * 1000),
            )
            return result
        except Exception as error:
            code = getattr(error, "status_code", None)
            transient = (
                code in (408, 429, 500, 502, 503, 504)
                or isinstance(error, (TimeoutError, ConnectionError))
                or any(
                    t in type(error).__name__.lower() for t in ("timeout", "connection")
                )
            )
            headers = getattr(getattr(error, "response", None), "headers", {}) or {}
            header = headers.get("retry-after")
            try:
                delay = (
                    float(header)
                    if header is not None
                    else float(headers.get("x-ms-retry-after-ms", 1000)) / 1000
                )
            except (ValueError, TypeError):
                try:
                    moment = parsedate_to_datetime(header)
                    if moment.tzinfo is None:
                        moment = moment.replace(tzinfo=UTC)
                    delay = (moment - datetime.now(UTC)).total_seconds()
                except (ValueError, TypeError, OverflowError):
                    delay = 1
            if not math.isfinite(delay):
                delay = 1
            event(
                "provider_attempt",
                stage=stage,
                deployment=deployment,
                attempt=attempt + 1,
                outcome="failed",
                error_class=type(error).__name__,
                status=code,
                latency_ms=round((time.monotonic() - start) * 1000),
            )
            if not transient or attempt or delay > 10:
                raise
            sleep(max(0, delay))


class BudgetLM(dspy.LM):
    def __init__(self, *args, input_token_limit, **kwargs):
        super().__init__(*args, **kwargs)
        self.input_token_limit = input_token_limit

    def __call__(self, prompt=None, *, messages=None, **kwargs):
        fmt = kwargs.get("response_format", {})
        if hasattr(fmt, "model_json_schema"):
            fmt = fmt.model_json_schema()
        if (
            token_count({"prompt": prompt, "messages": messages, "format": fmt}) + 128
            > self.input_token_limit
        ):
            raise AppError(
                "context_budget_exceeded",
                f"Rendered model input exceeds {self.input_token_limit} tokens",
                422,
            )
        result = retry_call(
            lambda: super(BudgetLM, self).__call__(prompt, messages=messages, **kwargs),
            stage="chat",
            deployment=self.model,
        )
        usage = USAGE.get()
        if usage is not None and self.history:
            tokens = self.history[-1].get("usage") or {}
            if isinstance(tokens, dict) and isinstance(tokens.get("total_tokens"), int):
                usage["chat_tokens"] = (
                    usage.get("chat_tokens", 0) + tokens["total_tokens"]
                )
        return result


class Gateway:
    def __init__(self, settings):
        self.settings = settings

    def call(self, name, *, repair=True, **inputs):
        if not self.settings.azure_configured:
            raise AppError(
                "provider_unavailable",
                "Azure endpoint/key are not configured locally",
                503,
                True,
            )
        lm = BudgetLM(
            "azure/" + self.settings.chat_deployment,
            api_base=self.settings.endpoint,
            api_key=self.settings.api_key.get_secret_value(),
            api_version=self.settings.api_version,
            timeout=self.settings.model_timeout,
            num_retries=0,
            max_retries=0,
            max_tokens=self.settings.model_output_tokens,
            input_token_limit=self.settings.model_input_tokens,
            temperature=0,
            cache=False,
            engine="litellm",
        )
        signature = signature_for(name, inputs, self.settings.summary_tokens)
        predictor = dspy.Predict(signature)
        for attempt in range(2 if repair else 1):
            try:
                with dspy.context(
                    lm=lm, adapter=dspy.JSONAdapter(use_native_function_calling=False)
                ):
                    value = predictor(**inputs).result
                return value
            except AppError:
                raise
            except (
                ValidationError,
                ValueError,
                dspy.utils.exceptions.AdapterParseError,
            ) as error:
                event(
                    "format_error",
                    stage=name,
                    error_class=type(error).__name__,
                    attempt=attempt + 1,
                )
                if attempt or not repair:
                    raise AppError(
                        "invalid_model_output",
                        "Model output did not satisfy the typed contract",
                        502,
                    ) from error
                predictor = dspy.Predict(
                    signature.with_instructions(
                        signature.instructions
                        + "\nPrevious output failed typed validation. Return exactly the required JSON fields with correct types; no extra fields or prose."
                    )
                )
            except Exception as error:
                raise AppError(
                    "provider_unavailable",
                    "Chat deployment request failed; see local diagnostics",
                    503,
                    True,
                ) from error
        raise AppError("invalid_model_output", "Invalid typed output", 502)
