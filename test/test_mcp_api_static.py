from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_mcp_router_is_mounted_before_web_fallback() -> None:
    app_py = read("api/app.py")

    assert "mcp" in app_py
    assert "app.include_router(mcp.create_router(" in app_py
    assert app_py.index("app.include_router(mcp.create_router(") < app_py.index('@app.get("/{full_path:path}"')


def test_mcp_route_uses_query_api_key_and_search_handler() -> None:
    mcp_py = read("api/mcp.py")

    assert '@router.post("/mcp")' in mcp_py
    assert '@router.get("/mcp")' in mcp_py
    assert "ApiKey" in mcp_py
    assert 'require_identity(f"Bearer {api_key}")' in mcp_py
    assert 'openai_search.handle({"prompt": prompt})' in mcp_py
    assert "handle_mcp_batch" in mcp_py


def test_readme_documents_mcp_search_endpoint() -> None:
    readme = read("README.md")

    assert "/mcp?ApiKey=<auth-key>" in readme
    assert "chatgpt_search" in readme
