from __future__ import annotations

from collections.abc import Callable
from typing import Any

MCP_PROTOCOL_VERSION = "2024-11-05"
MCP_SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26")
MCP_SERVER_NAME = "chatgpt2api-search"
MCP_TOOL_NAME = "chatgpt_search"

JSON_RPC_VERSION = "2.0"
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL = -32603

SearchHandler = Callable[[str], dict[str, Any]]


def handle_mcp_batch(
    payload: object,
    search_handler: SearchHandler,
    server_version: str = "1.4.0",
) -> dict[str, Any] | list[dict[str, Any]] | None:
    if isinstance(payload, list):
        if not payload:
            return _error(None, ERROR_INVALID_REQUEST, "Invalid Request: empty batch")
        responses = [
            response
            for item in payload
            if (response := handle_mcp_message(item, search_handler, server_version)) is not None
        ]
        return responses or None
    return handle_mcp_message(payload, search_handler, server_version)


def handle_mcp_message(
    message: object,
    search_handler: SearchHandler,
    server_version: str = "1.4.0",
) -> dict[str, Any] | None:
    if not isinstance(message, dict):
        return _error(None, ERROR_INVALID_REQUEST, "Invalid Request")

    request_id = message.get("id")
    is_notification = "id" not in message
    method = message.get("method")
    if is_notification:
        return None
    if message.get("jsonrpc") != JSON_RPC_VERSION or not isinstance(method, str) or not method:
        return _error(request_id, ERROR_INVALID_REQUEST, "Invalid Request")

    try:
        if method == "initialize":
            return _result(request_id, _initialize_result(server_version, message.get("params")))
        if method == "ping":
            return _result(request_id, {})
        if method == "notifications/initialized":
            return _result(request_id, {})
        if method == "tools/list":
            return _result(request_id, {"tools": [_search_tool()]})
        if method == "tools/call":
            return _result(request_id, _call_tool(message.get("params"), search_handler))
    except ValueError as exc:
        return _error(request_id, ERROR_INVALID_PARAMS, str(exc))
    except Exception as exc:
        return _error(request_id, ERROR_INTERNAL, str(exc))

    return _error(request_id, ERROR_METHOD_NOT_FOUND, f"Method not found: {method}")


def _initialize_result(server_version: str, params: object = None) -> dict[str, Any]:
    requested_version = ""
    if isinstance(params, dict):
        requested_version = str(params.get("protocolVersion") or "").strip()
    protocol_version = (
        requested_version
        if requested_version in MCP_SUPPORTED_PROTOCOL_VERSIONS
        else MCP_PROTOCOL_VERSION
    )
    return {
        "protocolVersion": protocol_version,
        "capabilities": {"tools": {"listChanged": False}},
        "serverInfo": {
            "name": MCP_SERVER_NAME,
            "version": server_version,
        },
    }


def _search_tool() -> dict[str, Any]:
    return {
        "name": MCP_TOOL_NAME,
        "description": "Search the web through the configured ChatGPT account pool and return an answer with sources.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The question or topic to search for.",
                    "minLength": 1,
                }
            },
            "required": ["prompt"],
            "additionalProperties": False,
        },
    }


def _call_tool(params: object, search_handler: SearchHandler) -> dict[str, Any]:
    if not isinstance(params, dict):
        raise ValueError("tools/call params must be an object")
    if params.get("name") != MCP_TOOL_NAME:
        raise ValueError(f"Unknown tool: {params.get('name')}")
    arguments = params.get("arguments") or {}
    if not isinstance(arguments, dict):
        raise ValueError("tools/call arguments must be an object")
    prompt = str(arguments.get("prompt") or "").strip()
    if not prompt:
        raise ValueError("prompt is required")

    search_result = search_handler(prompt)
    structured = _public_search_result(search_result)
    return {
        "content": [{"type": "text", "text": _format_search_text(structured)}],
        "structuredContent": structured,
        "isError": False,
    }


def _public_search_result(result: dict[str, Any]) -> dict[str, Any]:
    return {key: value for key, value in result.items() if not str(key).startswith("_")}


def _format_search_text(result: dict[str, Any]) -> str:
    answer = str(result.get("answer") or "").strip()
    sources = result.get("sources") if isinstance(result.get("sources"), list) else []
    lines = [answer or "No answer returned."]
    formatted_sources = [_format_source(item, index) for index, item in enumerate(sources, start=1)]
    formatted_sources = [item for item in formatted_sources if item]
    if formatted_sources:
        lines.extend(["", "Sources:", *formatted_sources])
    return "\n".join(lines)


def _format_source(value: object, index: int) -> str:
    if not isinstance(value, dict):
        return ""
    url = str(value.get("url") or "").strip()
    title = str(value.get("title") or "").strip()
    snippet = str(value.get("snippet") or "").strip()
    if not url and not title and not snippet:
        return ""
    label = f"{title} - {url}" if title and url else (url or title)
    if snippet:
        label = f"{label}: {snippet}" if label else snippet
    return f"{index}. {label}"


def _result(request_id: object, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": JSON_RPC_VERSION, "id": request_id, "result": result}


def _error(request_id: object, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": JSON_RPC_VERSION, "id": request_id, "error": {"code": code, "message": message}}
