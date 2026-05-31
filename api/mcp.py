from __future__ import annotations

import asyncio
import json
import secrets
from dataclasses import dataclass

from fastapi import APIRouter, Body, Header, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response, StreamingResponse
from pydantic import BaseModel

from api.support import require_admin, require_identity
from services.config import config
from services.log_service import LoggedCall
from services.mcp_key_service import mcp_key_service
from services.mcp_search_service import handle_mcp_batch
from services.protocol import openai_search


class McpKeyCreateRequest(BaseModel):
    name: str = ""


@dataclass
class McpSseSession:
    queue: asyncio.Queue[str]
    identity: dict[str, object]


_sse_sessions: dict[str, McpSseSession] = {}


def _require_api_key(api_key: str) -> dict[str, object]:
    api_key = str(api_key or "").strip()
    if not api_key:
        raise HTTPException(status_code=401, detail={"error": "ApiKey is required"})
    identity = mcp_key_service.authenticate(api_key)
    if identity is not None:
        return identity
    return require_identity(f"Bearer {api_key}")


def _search_handler(identity: dict[str, object]):
    def search_handler(prompt: str) -> dict:
        call = LoggedCall(identity, "/mcp", openai_search.MODEL, "MCP search", request_text=prompt)
        try:
            result = openai_search.handle({"prompt": prompt})
        except Exception as exc:
            call.log(" failed", status="failed", error=str(exc), account_email=getattr(exc, "account_email", ""))
            raise
        call.log(" completed", result)
        return result

    return search_handler


async def _handle_mcp_payload(payload: object, identity: dict[str, object]):
    return await run_in_threadpool(handle_mcp_batch, payload, _search_handler(identity), config.app_version)


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/mcp/keys")
    async def list_mcp_keys(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return {"items": mcp_key_service.list_keys()}

    @router.post("/api/mcp/keys")
    async def create_mcp_key(body: McpKeyCreateRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        item, raw_key = mcp_key_service.create_key(body.name)
        return {"item": item, "key": raw_key, "items": mcp_key_service.list_keys()}

    @router.delete("/api/mcp/keys/{key_id}")
    async def delete_mcp_key(key_id: str, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        if not mcp_key_service.delete_key(key_id):
            raise HTTPException(status_code=404, detail={"error": "MCP key not found"})
        return {"items": mcp_key_service.list_keys()}

    @router.get("/mcp")
    async def mcp_get(api_key: str = Query(default="", alias="ApiKey")):
        identity = _require_api_key(api_key)
        session_id = secrets.token_urlsafe(24)
        session = McpSseSession(queue=asyncio.Queue(), identity=identity)
        _sse_sessions[session_id] = session
        endpoint = f"/mcp/messages?session_id={session_id}"

        async def stream():
            try:
                yield f"event: endpoint\ndata: {endpoint}\n\n"
                while True:
                    try:
                        item = await asyncio.wait_for(session.queue.get(), timeout=15)
                    except asyncio.TimeoutError:
                        yield ": keepalive\n\n"
                        continue
                    yield item
            finally:
                _sse_sessions.pop(session_id, None)

        return StreamingResponse(
            stream(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @router.post("/mcp")
    async def mcp_post(
        payload: object = Body(...),
        api_key: str = Query(default="", alias="ApiKey"),
    ):
        identity = _require_api_key(api_key)
        result = await _handle_mcp_payload(payload, identity)
        if result is None:
            return Response(status_code=202)
        return JSONResponse(content=result)

    @router.post("/mcp/messages")
    async def mcp_sse_message(
        payload: object = Body(...),
        session_id: str = Query(default=""),
    ):
        session = _sse_sessions.get(str(session_id or "").strip())
        if session is None:
            raise HTTPException(status_code=404, detail={"error": "MCP SSE session not found"})

        result = await _handle_mcp_payload(payload, session.identity)
        if result is not None:
            data = json.dumps(result, ensure_ascii=False, separators=(",", ":"))
            await session.queue.put(f"event: message\ndata: {data}\n\n")
        return Response(status_code=202)

    return router
