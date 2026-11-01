"""Azure embedding transport with bounded retries and observable availability."""

import math
from contextlib import closing

from openai import AzureOpenAI

from resourcing_assistant.errors import AppError
from resourcing_assistant.llm.gateway import retry_call
from resourcing_assistant.telemetry import USAGE, event


def normalize(vector):
    if not vector or not all(
        isinstance(v, (float, int)) and math.isfinite(v) for v in vector
    ):
        raise ValueError("Invalid embedding vector")
    norm = math.sqrt(sum(v * v for v in vector))
    if norm == 0:
        raise ValueError("Zero embedding vector")
    return [v / norm for v in vector]


class EmbeddingClient:
    def __init__(self, settings, client_factory=AzureOpenAI):
        self.settings, self.client_factory = settings, client_factory
        self.status = "unknown" if settings.azure_configured else "not_configured"

    def embed(self, texts):
        if not self.settings.azure_configured:
            raise AppError(
                "embedding_unavailable", "Embedding deployment is not configured", 503
            )
        with closing(
            self.client_factory(
                azure_endpoint=self.settings.endpoint,
                api_key=self.settings.api_key.get_secret_value(),
                api_version=self.settings.api_version,
                max_retries=0,
                timeout=self.settings.model_timeout,
            )
        ) as client:
            output = retry_call(
                lambda: client.embeddings.create(
                    model=self.settings.embedding_deployment, input=texts
                ),
                stage="embedding",
                deployment=self.settings.embedding_deployment,
            )
        usage = USAGE.get()
        used = getattr(getattr(output, "usage", None), "total_tokens", None)
        if usage is not None and isinstance(used, int):
            usage["embedding_tokens"] = usage.get("embedding_tokens", 0) + used
        ordered = sorted(output.data, key=lambda item: item.index)
        if [v.index for v in ordered] != list(range(len(texts))):
            raise ValueError("Embedding response omitted documents")
        vectors = [normalize(item.embedding) for item in ordered]
        if self.status == "degraded":
            event("embedding_recovered", deployment=self.settings.embedding_deployment)
        self.status = "healthy"
        return vectors
