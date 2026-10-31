"""Local conversational resourcing assistant."""

import os

# The assignment permits only model endpoints as external runtime services.
os.environ["LANGCHAIN_TRACING_V2"] = "false"
os.environ["LANGSMITH_TRACING"] = "false"
os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
