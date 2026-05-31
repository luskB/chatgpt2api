from __future__ import annotations

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, Response

from api.support import require_identity
from services.config import config
from services.log_service import LoggedCall
from services.mcp_search_service import handle_mcp_batch
from services.protocol import openai_search


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/mcp")
    async def mcp_get() -> None:
        raise HTTPException(
            status_code=405,
            detail={"error": "MCP SSE is not enabled. Send JSON-RPC requests with POST."},
        )

    @router.post("/mcp")
    async def mcp_post(
        payload: object = Body(...),
        api_key: str = Query(default="", alias="ApiKey"),
    ):
        api_key = str(api_key or "").strip()
        if not api_key:
            raise HTTPException(status_code=401, detail={"error": "ApiKey is required"})
        identity = require_identity(f"Bearer {api_key}")

        def search_handler(prompt: str) -> dict:
            call = LoggedCall(identity, "/mcp", openai_search.MODEL, "MCP search", request_text=prompt)
            try:
                result = openai_search.handle({"prompt": prompt})
            except Exception as exc:
                call.log(" failed", status="failed", error=str(exc), account_email=getattr(exc, "account_email", ""))
                raise
            call.log(" completed", result)
            return result

        result = await run_in_threadpool(handle_mcp_batch, payload, search_handler, config.app_version)
        if result is None:
            return Response(status_code=202)
        return JSONResponse(content=result)

    return router
