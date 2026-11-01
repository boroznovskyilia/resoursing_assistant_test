"""Synchronous HTTP routes; blocking work runs in the framework thread pool."""

from fastapi import APIRouter, Request
from fastapi import Response as HTTPResponse

from resourcing_assistant.api.schemas import (
    DecisionInput,
    EmptyInput,
    Health,
    History,
    MessageInput,
    Response,
    ThreadCreated,
    ThreadInfo,
)
from resourcing_assistant.schemas import Identifier

router = APIRouter()


@router.post("/threads", response_model=ThreadCreated, status_code=201)
def create_thread(body: EmptyInput, request: Request):
    return request.app.state.service.conversations.create_thread()


@router.get("/threads", response_model=list[ThreadInfo])
def list_threads(request: Request):
    return request.app.state.service.conversations.threads()


@router.get("/threads/{thread_id}", response_model=History)
def get_thread(thread_id: Identifier, request: Request):
    return request.app.state.service.history(thread_id)


@router.post("/threads/{thread_id}/messages", response_model=Response)
def message(
    thread_id: Identifier,
    body: MessageInput,
    request: Request,
    response: HTTPResponse,
):
    result = request.app.state.service.message(thread_id, body.request_id, body.text)
    if result.request_status == "processing":
        response.status_code = 202
    return result


@router.post("/threads/{thread_id}/confirm", response_model=Response)
def confirm(thread_id: Identifier, body: DecisionInput, request: Request):
    return request.app.state.service.decide(thread_id, body.action_id, body.decision)


@router.post(
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


@router.get("/health", response_model=Health)
def health(request: Request):
    return request.app.state.service.health()
