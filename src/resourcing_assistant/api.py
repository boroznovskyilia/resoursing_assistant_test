"""Typed local HTTP API. Sync routes run blocking graph work in FastAPI's thread pool."""

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, Response as HTTPResponse
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from .config import Settings, ROOT
from .models import (
    AppError,
    MessageInput,
    DecisionInput,
    EmptyInput,
    Response,
    ThreadCreated,
    ThreadInfo,
    History,
    Health,
    Identifier,
)
from .service import Service


def create_app(settings=None, gateway=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        app.state.service = Service(settings, gateway)
        try:
            yield
        finally:
            app.state.service.close()

    app = FastAPI(title="Resourcing Assistant", lifespan=lifespan)

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

    @app.post("/threads", response_model=ThreadCreated, status_code=201)
    def create_thread(body: EmptyInput, request: Request):
        return request.app.state.service.store.create_thread()

    @app.get("/threads", response_model=list[ThreadInfo])
    def list_threads(request: Request):
        return request.app.state.service.store.threads()

    @app.get("/threads/{thread_id}", response_model=History)
    def get_thread(thread_id: Identifier, request: Request):
        return request.app.state.service.store.history(thread_id)

    @app.post("/threads/{thread_id}/messages", response_model=Response)
    def message(
        thread_id: Identifier,
        body: MessageInput,
        request: Request,
        response: HTTPResponse,
    ):
        result = request.app.state.service.message(
            thread_id, body.request_id, body.text
        )
        if result.request_status == "processing":
            response.status_code = 202
        return result

    @app.post("/threads/{thread_id}/confirm", response_model=Response)
    def confirm(thread_id: Identifier, body: DecisionInput, request: Request):
        return request.app.state.service.decide(
            thread_id, body.action_id, body.decision
        )

    @app.post(
        "/threads/{thread_id}/requests/{request_id}/resume", response_model=Response
    )
    def resume(
        thread_id: Identifier,
        request_id: Identifier,
        body: EmptyInput,
        request: Request,
        response: HTTPResponse,
    ):
        result = request.app.state.service.resume(thread_id, request_id)
        if result.request_status == "processing":
            response.status_code = 202
        return result

    @app.get("/health", response_model=Health)
    def health(request: Request):
        return request.app.state.service.health()

    # Production build served by the same local process; Vite proxies API in dev mode.
    dist = ROOT / "frontend/dist"
    if (dist / "assets").exists():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")

    @app.get("/", include_in_schema=False)
    def home():
        if not (dist / "index.html").exists():
            return JSONResponse(
                status_code=503,
                content={
                    "error": {
                        "code": "frontend_not_built",
                        "message": "Build frontend with npm ci and npm run build in frontend/; see README",
                        "retryable": False,
                    }
                },
            )
        return FileResponse(dist / "index.html")

    return app
