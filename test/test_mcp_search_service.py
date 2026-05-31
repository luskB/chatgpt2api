from __future__ import annotations

from services.mcp_search_service import MCP_PROTOCOL_VERSION, MCP_TOOL_NAME, handle_mcp_message


def request(method: str, params: dict | None = None, request_id: int = 1) -> dict:
    payload: dict[str, object] = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        payload["params"] = params
    return payload


def test_initialize_advertises_search_tool_capability() -> None:
    response = handle_mcp_message(request("initialize"), lambda prompt: {})

    assert response is not None
    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["protocolVersion"] == MCP_PROTOCOL_VERSION
    assert response["result"]["capabilities"] == {"tools": {"listChanged": False}}
    assert response["result"]["serverInfo"]["name"] == "chatgpt2api-search"


def test_initialized_notification_returns_no_json_rpc_response() -> None:
    response = handle_mcp_message({"jsonrpc": "2.0", "method": "notifications/initialized"}, lambda prompt: {})

    assert response is None


def test_tools_list_exposes_chatgpt_search_schema() -> None:
    response = handle_mcp_message(request("tools/list"), lambda prompt: {})

    tools = response["result"]["tools"]
    assert [tool["name"] for tool in tools] == [MCP_TOOL_NAME]
    tool = tools[0]
    assert tool["inputSchema"]["required"] == ["prompt"]
    assert tool["inputSchema"]["properties"]["prompt"]["type"] == "string"


def test_ping_returns_empty_result_for_client_health_checks() -> None:
    response = handle_mcp_message(request("ping"), lambda prompt: {})

    assert response == {"jsonrpc": "2.0", "id": 1, "result": {}}


def test_tools_call_runs_search_and_returns_text_plus_structured_content() -> None:
    prompts: list[str] = []

    def search_handler(prompt: str) -> dict:
        prompts.append(prompt)
        return {
            "answer": "The answer",
            "sources": [
                {"title": "Example", "url": "https://example.com/a", "snippet": "A source"},
                {"title": "", "url": "https://example.com/b", "snippet": ""},
            ],
            "conversation_id": "conversation-1",
            "_account_email": "hidden@example.com",
        }

    response = handle_mcp_message(
        request(
            "tools/call",
            {"name": MCP_TOOL_NAME, "arguments": {"prompt": "look this up"}},
            request_id=2,
        ),
        search_handler,
    )

    assert prompts == ["look this up"]
    result = response["result"]
    assert result["isError"] is False
    assert result["structuredContent"]["answer"] == "The answer"
    assert result["structuredContent"]["sources"][0]["url"] == "https://example.com/a"
    assert "_account_email" not in result["structuredContent"]
    text = result["content"][0]["text"]
    assert "The answer" in text
    assert "Sources:" in text
    assert "Example - https://example.com/a" in text
    assert "https://example.com/b" in text


def test_tools_call_rejects_missing_prompt_without_running_search() -> None:
    called = False

    def search_handler(prompt: str) -> dict:
        nonlocal called
        called = True
        return {}

    response = handle_mcp_message(
        request("tools/call", {"name": MCP_TOOL_NAME, "arguments": {}}),
        search_handler,
    )

    assert called is False
    assert response["error"]["code"] == -32602
    assert "prompt" in response["error"]["message"]


def test_unknown_tool_is_a_json_rpc_parameter_error() -> None:
    response = handle_mcp_message(
        request("tools/call", {"name": "other_tool", "arguments": {"prompt": "x"}}),
        lambda prompt: {},
    )

    assert response["error"]["code"] == -32602
    assert "Unknown tool" in response["error"]["message"]
