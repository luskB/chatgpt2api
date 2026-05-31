from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
MCP_KEYS_FILE = BASE_DIR / "data" / "mcp_keys.json"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_key(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


class McpKeyService:
    def __init__(self, path: Path):
        self.path = path
        self._lock = Lock()

    @staticmethod
    def _clean(value: object) -> str:
        return str(value or "").strip()

    def _load(self) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except Exception:
            return []
        if isinstance(data, dict):
            data = data.get("items")
        if not isinstance(data, list):
            return []
        return [item for raw in data if (item := self._normalize_item(raw)) is not None]

    def _save(self, items: list[dict[str, Any]]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps({"items": items}, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    def _normalize_item(self, raw: object) -> dict[str, Any] | None:
        if not isinstance(raw, dict):
            return None
        key_hash = self._clean(raw.get("key_hash"))
        if not key_hash:
            return None
        created_at = self._clean(raw.get("created_at")) or _now_iso()
        return {
            "id": self._clean(raw.get("id")) or uuid.uuid4().hex[:12],
            "name": self._clean(raw.get("name")) or "MCP Key",
            "role": "mcp",
            "key_hash": key_hash,
            "created_at": created_at,
            "last_used_at": self._clean(raw.get("last_used_at")) or None,
        }

    @staticmethod
    def _public_item(item: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "role": "mcp",
            "created_at": item.get("created_at"),
            "last_used_at": item.get("last_used_at"),
        }

    def list_keys(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._public_item(item) for item in self._load()]

    def _name_exists(self, items: list[dict[str, Any]], name: str) -> bool:
        return any(self._clean(item.get("name")) == name for item in items)

    def _build_name(self, items: list[dict[str, Any]], name: str) -> str:
        base = self._clean(name) or "MCP Key"
        if not self._name_exists(items, base):
            return base
        suffix = 2
        while True:
            candidate = f"{base} {suffix}"
            if not self._name_exists(items, candidate):
                return candidate
            suffix += 1

    @staticmethod
    def _hash_exists(items: list[dict[str, Any]], key_hash: str) -> bool:
        return any(hmac.compare_digest(str(item.get("key_hash") or ""), key_hash) for item in items)

    def create_key(self, name: str = "") -> tuple[dict[str, Any], str]:
        with self._lock:
            items = self._load()
            normalized_name = self._build_name(items, name)
            while True:
                raw_key = f"mcp-{secrets.token_urlsafe(24)}"
                key_hash = _hash_key(raw_key)
                if not self._hash_exists(items, key_hash):
                    break
            item = {
                "id": uuid.uuid4().hex[:12],
                "name": normalized_name,
                "role": "mcp",
                "key_hash": key_hash,
                "created_at": _now_iso(),
                "last_used_at": None,
            }
            items.append(item)
            self._save(items)
            return self._public_item(item), raw_key

    def delete_key(self, key_id: str) -> bool:
        normalized_id = self._clean(key_id)
        if not normalized_id:
            return False
        with self._lock:
            items = self._load()
            kept = [item for item in items if item.get("id") != normalized_id]
            if len(kept) == len(items):
                return False
            self._save(kept)
            return True

    def authenticate(self, raw_key: str) -> dict[str, Any] | None:
        candidate = self._clean(raw_key)
        if not candidate:
            return None
        candidate_hash = _hash_key(candidate)
        with self._lock:
            items = self._load()
            for index, item in enumerate(items):
                stored_hash = self._clean(item.get("key_hash"))
                if not stored_hash or not hmac.compare_digest(stored_hash, candidate_hash):
                    continue
                next_item = dict(item)
                next_item["last_used_at"] = _now_iso()
                items[index] = next_item
                self._save(items)
                return self._public_item(next_item)
        return None


mcp_key_service = McpKeyService(MCP_KEYS_FILE)
