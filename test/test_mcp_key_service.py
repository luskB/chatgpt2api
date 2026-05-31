from __future__ import annotations

import json

from services.mcp_key_service import McpKeyService


def test_mcp_key_service_creates_hash_only_key_and_authenticates(tmp_path) -> None:
    service = McpKeyService(tmp_path / "mcp_keys.json")

    item, raw_key = service.create_key("Cherry")

    assert raw_key.startswith("mcp-")
    assert item["name"] == "Cherry"
    assert item["role"] == "mcp"
    assert "key_hash" not in item

    stored = json.loads((tmp_path / "mcp_keys.json").read_text(encoding="utf-8"))
    assert raw_key not in json.dumps(stored, ensure_ascii=False)
    assert stored["items"][0]["key_hash"]

    identity = service.authenticate(raw_key)
    assert identity is not None
    assert identity["role"] == "mcp"
    assert identity["id"] == item["id"]
    assert service.list_keys()[0]["last_used_at"]


def test_mcp_key_service_deletes_key_and_rejects_authentication(tmp_path) -> None:
    service = McpKeyService(tmp_path / "mcp_keys.json")
    item, raw_key = service.create_key("")

    assert service.delete_key(str(item["id"])) is True
    assert service.authenticate(raw_key) is None
    assert service.delete_key(str(item["id"])) is False
