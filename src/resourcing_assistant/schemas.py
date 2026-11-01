"""Shared validation primitives, independent of HTTP and persistence."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False, strict=True)


Identifier = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,100}$")]


Scalar = str | int | float | bool | None
