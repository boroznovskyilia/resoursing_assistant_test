"""Stable HTTP error responses without sensitive input values."""

from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from resourcing_assistant.errors import AppError


def register_error_handlers(app):
    @app.exception_handler(AppError)
    async def domain_error(request, error):
        return JSONResponse(
            status_code=error.status,
            content={
                "error": {
                    "code": error.code,
                    "message": str(error),
                    "retryable": error.retryable,
                },
                **{
                    k: v
                    for k, v in request.path_params.items()
                    if k in ("thread_id", "request_id")
                },
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, error):
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "invalid_request",
                    "message": "Invalid request fields: "
                    + ", ".join(
                        ".".join(str(k) for k in e["loc"]) for e in error.errors()
                    ),
                    "retryable": False,
                }
            },
        )

    @app.exception_handler(Exception)
    async def internal_error(request, error):
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "internal_error",
                    "message": "Unexpected server error; consult local diagnostics and saved state",
                    "retryable": False,
                }
            },
        )
