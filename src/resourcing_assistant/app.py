"""Application composition, lifespan and local static asset serving."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from resourcing_assistant.agent.context import ContextBuilder
from resourcing_assistant.agent.graph import Agent
from resourcing_assistant.agent.reads import ReadService
from resourcing_assistant.api.errors import register_error_handlers
from resourcing_assistant.api.routes import router
from resourcing_assistant.config import ROOT, Settings
from resourcing_assistant.db.bookings import BookingRepository
from resourcing_assistant.db.bootstrap import initialize_owned, reflect_source
from resourcing_assistant.db.conversations import ConversationRepository
from resourcing_assistant.db.reader import Reader
from resourcing_assistant.db.session import Database
from resourcing_assistant.db.source import SourceRepository, initialize
from resourcing_assistant.db.vectors import VectorRepository
from resourcing_assistant.llm.embeddings import EmbeddingClient
from resourcing_assistant.llm.gateway import Gateway
from resourcing_assistant.services.bookings import BookingService
from resourcing_assistant.services.conversations import ConversationService
from resourcing_assistant.services.documents import SourceDocuments
from resourcing_assistant.services.retrieval import RetrievalService
from resourcing_assistant.telemetry import configure_logging


def create_app(settings=None, gateway=None):
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app):
        app.state.service = create_service(settings, gateway)
        try:
            yield
        finally:
            app.state.service.close()

    app = FastAPI(title="Resourcing Assistant", lifespan=lifespan)
    register_error_handlers(app)
    app.include_router(router)
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


def create_service(settings, gateway=None):
    configure_logging(settings.runtime)
    subject = initialize(settings)
    app_db = Database(settings.runtime / "app.sqlite")
    subject_db = Database(subject)
    try:
        initialize_owned(app_db, subject_db)
        tables = reflect_source(subject_db)
        conversations = ConversationRepository(app_db)
        bookings = BookingService(BookingRepository(subject_db, tables), conversations)
        reader = Reader(settings, subject)
        source = SourceRepository(subject_db, tables)
        gateway = gateway or Gateway(settings)
        retrieval = RetrievalService(
            settings,
            SourceDocuments(source),
            VectorRepository(app_db),
            EmbeddingClient(settings),
            gateway,
        )
        context = ContextBuilder(settings, conversations, bookings, reader, gateway)
        reads = ReadService(settings, reader, gateway)
        agent = Agent(
            settings,
            conversations,
            bookings,
            reader,
            source,
            gateway,
            retrieval,
            context,
            reads,
        )
        return ConversationService(settings, conversations, bookings, agent, subject)
    except Exception:
        app_db.close()
        subject_db.close()
        raise
