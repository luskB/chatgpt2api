from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_mcp_router_has_admin_key_management_routes_and_authentication() -> None:
    mcp_py = read("api/mcp.py")

    assert "mcp_key_service" in mcp_py
    assert '@router.get("/api/mcp/keys")' in mcp_py
    assert '@router.post("/api/mcp/keys")' in mcp_py
    assert '@router.delete("/api/mcp/keys/{key_id}")' in mcp_py
    assert "mcp_key_service.authenticate(api_key)" in mcp_py
    assert "require_admin(authorization)" in mcp_py


def test_settings_page_includes_mcp_key_card() -> None:
    settings_page = read("web/src/app/settings/page.tsx")

    assert 'from "./components/mcp-keys-card"' in settings_page
    assert "<McpKeysCard />" in settings_page


def test_frontend_api_has_mcp_key_helpers() -> None:
    api_ts = read("web/src/lib/api.ts")

    assert "export type McpKey" in api_ts
    assert "fetchMcpKeys" in api_ts
    assert "createMcpKey" in api_ts
    assert "deleteMcpKey" in api_ts
    assert '"/api/mcp/keys"' in api_ts
