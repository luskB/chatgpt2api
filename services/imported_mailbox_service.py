from __future__ import annotations

import hashlib
import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from services.config import DATA_DIR


IMPORTED_MAILBOX_FILE = DATA_DIR / "imported_mailboxes.json"
STATUSES = {"unused", "leased", "used", "failed"}
_lock = threading.RLock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00" if text.endswith("Z") else text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _safe_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _as_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "on", "y"}:
        return True
    if text in {"0", "false", "no", "off", "n"}:
        return False
    return default


def _load() -> list[dict[str, Any]]:
    try:
        raw = json.loads(IMPORTED_MAILBOX_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []
    if isinstance(raw, list):
        return [_normalize_record(item) for item in raw if isinstance(item, dict)]
    if isinstance(raw, dict):
        items = raw.get("items")
        if isinstance(items, list):
            return [_normalize_record(item) for item in items if isinstance(item, dict)]
    return []


def _save(items: list[dict[str, Any]]) -> None:
    IMPORTED_MAILBOX_FILE.parent.mkdir(parents=True, exist_ok=True)
    payload = {"items": items}
    IMPORTED_MAILBOX_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _mask_secret(value: Any, head: int = 4, tail: int = 4) -> str:
    text = str(value or "")
    if not text:
        return ""
    if len(text) <= head + tail:
        return "*" * len(text)
    return f"{text[:head]}...{text[-tail:]}"


def _normalize_method(value: Any, default: str = "imap") -> str:
    method = str(value or default).strip().lower()
    return method if method in {"imap", "graph"} else default


def _defaults(source: dict[str, Any] | None = None) -> dict[str, Any]:
    raw = source if isinstance(source, dict) else {}
    return {
        "fetch_method": _normalize_method(raw.get("fetch_method") or raw.get("method"), "imap"),
        "imap_host": str(raw.get("imap_host") or raw.get("host") or "outlook.office365.com").strip(),
        "imap_port": _safe_int(raw.get("imap_port") or raw.get("port"), 993),
        "imap_ssl": _as_bool(raw.get("imap_ssl", raw.get("ssl", True)), True),
        "imap_folder": str(raw.get("imap_folder") or raw.get("folder") or "INBOX").strip() or "INBOX",
        "graph_tenant": str(raw.get("graph_tenant") or raw.get("tenant") or "consumers").strip() or "consumers",
        "client_id": str(raw.get("graph_client_id") or raw.get("client_id") or "").strip(),
        "client_secret": str(raw.get("graph_client_secret") or raw.get("client_secret") or "").strip(),
    }


def _credential_fingerprint(record: dict[str, Any]) -> str:
    if record["fetch_method"] == "graph":
        parts = [record["email"].lower(), record["fetch_method"], record.get("client_id") or "", record.get("refresh_token") or ""]
    else:
        parts = [
            record["email"].lower(),
            record["fetch_method"],
            record.get("password") or "",
            record.get("imap_host") or "",
            str(record.get("imap_port") or ""),
            record.get("imap_folder") or "",
        ]
    return hashlib.sha256("\n".join(parts).encode("utf-8", errors="replace")).hexdigest()


def _record_id(record: dict[str, Any]) -> str:
    return hashlib.sha256(_credential_fingerprint(record).encode("utf-8")).hexdigest()[:24]


def _normalize_record(value: dict[str, Any]) -> dict[str, Any]:
    created_at = str(value.get("created_at") or _now())
    status = str(value.get("status") or "unused").strip().lower()
    record = {
        "id": str(value.get("id") or "").strip(),
        "email": str(value.get("email") or value.get("address") or value.get("username") or "").strip(),
        "password": str(value.get("password") or value.get("app_password") or "").strip(),
        "client_id": str(value.get("client_id") or value.get("graph_client_id") or "").strip(),
        "client_secret": str(value.get("client_secret") or value.get("graph_client_secret") or "").strip(),
        "refresh_token": str(value.get("refresh_token") or "").strip(),
        "fetch_method": _normalize_method(value.get("fetch_method") or value.get("method"), "imap"),
        "imap_host": str(value.get("imap_host") or value.get("host") or "outlook.office365.com").strip(),
        "imap_port": _safe_int(value.get("imap_port") or value.get("port"), 993),
        "imap_ssl": _as_bool(value.get("imap_ssl", value.get("ssl", True)), True),
        "imap_folder": str(value.get("imap_folder") or value.get("folder") or "INBOX").strip() or "INBOX",
        "graph_tenant": str(value.get("graph_tenant") or value.get("tenant") or "consumers").strip() or "consumers",
        "status": status if status in STATUSES else "unused",
        "leased_until": str(value.get("leased_until") or "").strip() or None,
        "leased_at": str(value.get("leased_at") or "").strip() or None,
        "used_at": str(value.get("used_at") or "").strip() or None,
        "last_error": str(value.get("last_error") or "").strip() or None,
        "created_at": created_at,
        "updated_at": str(value.get("updated_at") or created_at),
    }
    if not record["id"] and record["email"]:
        record["id"] = _record_id(record)
    return record


def _split_text_line(line: str) -> list[str]:
    if "----" in line:
        return [item.strip() for item in line.rstrip("\r\n").split("----", 3)]
    for separator in ("\t", "|", ","):
        if separator in line:
            return [item.strip() for item in line.split(separator)]
    return [line.strip()]


def _parse_line(raw_line: str, defaults: dict[str, Any]) -> dict[str, Any] | None:
    stripped = raw_line.strip()
    if not stripped or stripped.startswith("#"):
        return None

    if stripped.startswith("{"):
        try:
            value = json.loads(stripped)
        except Exception as error:
            raise RuntimeError(f"JSON 行格式错误: {error}") from error
        if not isinstance(value, dict):
            raise RuntimeError("JSON 行必须是对象")
        parsed = dict(value)
    else:
        parts = _split_text_line(raw_line)
        if "----" in raw_line:
            if len(parts) >= 4:
                parsed = {
                    "email": parts[0],
                    "password": parts[1],
                    "client_id": parts[2],
                    "refresh_token": parts[3],
                    "fetch_method": "graph",
                }
            elif len(parts) == 2:
                parsed = {"email": parts[0], "password": parts[1], "fetch_method": "imap"}
            else:
                raise RuntimeError("---- 格式应为 email----password 或 email----password----client_id----refresh_token")
        else:
            method = _normalize_method(defaults.get("fetch_method"), "imap")
            parsed = {"email": parts[0] if parts else "", "fetch_method": method}
            if method == "graph":
                if len(parts) > 1:
                    parsed["refresh_token"] = parts[1]
                if len(parts) > 2:
                    parsed["client_id"] = parts[2]
                if len(parts) > 3:
                    parsed["graph_tenant"] = parts[3]
            else:
                if len(parts) > 1:
                    parsed["password"] = parts[1]
                if len(parts) > 2:
                    parsed["imap_host"] = parts[2]
                if len(parts) > 3:
                    parsed["imap_port"] = parts[3]

    record = _normalize_record({**defaults, **parsed})
    email = record["email"]
    if not email or "@" not in email:
        raise RuntimeError("缺少有效邮箱地址")
    if record["fetch_method"] == "imap" and not record["password"]:
        raise RuntimeError(f"{email} 缺少 IMAP 密码")
    if record["fetch_method"] == "graph" and (not record["refresh_token"] or not record["client_id"]):
        raise RuntimeError(f"{email} 缺少 Graph refresh_token 或 client_id")
    record["id"] = _record_id(record)
    return record


def _expire_leases(items: list[dict[str, Any]]) -> bool:
    changed = False
    now = datetime.now(timezone.utc)
    for item in items:
        if item.get("status") != "leased":
            continue
        leased_until = _parse_datetime(item.get("leased_until"))
        if leased_until and leased_until > now:
            continue
        item["status"] = "unused"
        item["leased_until"] = None
        item["leased_at"] = None
        item["updated_at"] = _now()
        changed = True
    return changed


def _summary(items: list[dict[str, Any]]) -> dict[str, int]:
    summary = {"total": len(items), "unused": 0, "leased": 0, "used": 0, "failed": 0}
    for item in items:
        status = str(item.get("status") or "unused")
        if status in summary:
            summary[status] += 1
    return summary


def _public_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": record["id"],
        "email": record["email"],
        "fetch_method": record["fetch_method"],
        "imap_host": record["imap_host"],
        "imap_port": record["imap_port"],
        "imap_ssl": record["imap_ssl"],
        "imap_folder": record["imap_folder"],
        "graph_tenant": record["graph_tenant"],
        "client_id": record["client_id"],
        "has_password": bool(record.get("password")),
        "has_refresh_token": bool(record.get("refresh_token")),
        "password_masked": _mask_secret(record.get("password")),
        "refresh_token_masked": _mask_secret(record.get("refresh_token"), 8, 6),
        "status": record["status"],
        "leased_until": record.get("leased_until"),
        "leased_at": record.get("leased_at"),
        "used_at": record.get("used_at"),
        "last_error": record.get("last_error"),
        "created_at": record["created_at"],
        "updated_at": record["updated_at"],
    }


def list_mailboxes() -> dict[str, Any]:
    with _lock:
        items = _load()
        if _expire_leases(items):
            _save(items)
        public_items = [_public_record(item) for item in sorted(items, key=lambda value: str(value.get("created_at") or ""), reverse=True)]
        return {"items": public_items, "summary": _summary(items)}


def import_mailboxes(text: str, defaults: dict[str, Any] | None = None) -> dict[str, Any]:
    parsed_defaults = _defaults(defaults)
    errors: list[dict[str, Any]] = []
    candidates: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(str(text or "").splitlines(), start=1):
        try:
            record = _parse_line(raw_line, parsed_defaults)
            if record:
                candidates.append(record)
        except Exception as error:
            errors.append({"line": line_number, "error": str(error)})

    with _lock:
        items = _load()
        if _expire_leases(items):
            _save(items)
        existing_ids = {str(item.get("id") or "") for item in items}
        imported = 0
        skipped = 0
        for record in candidates:
            if record["id"] in existing_ids:
                skipped += 1
                continue
            items.append(record)
            existing_ids.add(record["id"])
            imported += 1
        _save(items)
        public_items = [_public_record(item) for item in sorted(items, key=lambda value: str(value.get("created_at") or ""), reverse=True)]
        return {"items": public_items, "summary": _summary(items), "imported": imported, "skipped": skipped, "errors": errors}


def reserve_mailbox(provider_entry: dict[str, Any]) -> dict[str, Any]:
    method = _normalize_method(provider_entry.get("fetch_method"), "imap")
    lease_ttl_seconds = max(60, _safe_int(provider_entry.get("lease_ttl_seconds"), 1800))
    now = datetime.now(timezone.utc)
    with _lock:
        items = _load()
        changed = _expire_leases(items)
        for item in items:
            if item.get("fetch_method") != method:
                continue
            if item.get("status") not in {"unused"}:
                continue
            item["status"] = "leased"
            item["leased_at"] = _now()
            item["leased_until"] = datetime.fromtimestamp(now.timestamp() + lease_ttl_seconds, tz=timezone.utc).isoformat()
            item["updated_at"] = _now()
            item["last_error"] = None
            _save(items)
            return {
                "id": item["id"],
                "email": item["email"],
                "address": item["email"],
                "password": item["password"],
                "client_id": item["client_id"],
                "client_secret": item["client_secret"],
                "refresh_token": item["refresh_token"],
                "fetch_method": item["fetch_method"],
                "imap_host": item["imap_host"],
                "imap_port": item["imap_port"],
                "imap_ssl": item["imap_ssl"],
                "imap_folder": item["imap_folder"],
                "graph_tenant": item["graph_tenant"],
                "tenant": item["graph_tenant"],
            }
        if changed:
            _save(items)
    raise RuntimeError("没有可用的导入邮箱，请先在邮箱管理页面导入未使用邮箱")


def update_refresh_token(mailbox_id: str, refresh_token: str) -> None:
    if not mailbox_id or not refresh_token:
        return
    with _lock:
        items = _load()
        for item in items:
            if item.get("id") == mailbox_id:
                item["refresh_token"] = str(refresh_token).strip()
                item["updated_at"] = _now()
                _save(items)
                return


def finalize_mailbox(mailbox: dict[str, Any], consumed: bool, error: str | None = None) -> None:
    mailbox_id = str(mailbox.get("imported_id") or mailbox.get("id") or "").strip()
    if not mailbox_id:
        return
    with _lock:
        items = _load()
        for item in items:
            if item.get("id") != mailbox_id:
                continue
            if mailbox.get("refresh_token"):
                item["refresh_token"] = str(mailbox.get("refresh_token") or "").strip()
            item["leased_until"] = None
            item["leased_at"] = None
            item["updated_at"] = _now()
            if consumed:
                item["status"] = "used"
                item["used_at"] = _now()
                item["last_error"] = None
            else:
                item["status"] = "failed"
                item["last_error"] = str(error or mailbox.get("last_error") or "registration_failed")[:500]
            _save(items)
            return


def reset_mailbox(mailbox_id: str) -> dict[str, Any]:
    with _lock:
        items = _load()
        for item in items:
            if item.get("id") == mailbox_id:
                item["status"] = "unused"
                item["leased_until"] = None
                item["leased_at"] = None
                item["used_at"] = None
                item["last_error"] = None
                item["updated_at"] = _now()
                _save(items)
                return _public_record(item)
    raise KeyError("邮箱记录不存在")


def delete_mailbox(mailbox_id: str) -> None:
    with _lock:
        items = _load()
        kept = [item for item in items if item.get("id") != mailbox_id]
        if len(kept) == len(items):
            raise KeyError("邮箱记录不存在")
        _save(kept)


def delete_mailboxes(mailbox_ids: list[str]) -> dict[str, Any]:
    targets = {mailbox_id for mailbox_id in dict.fromkeys(str(item or "").strip() for item in mailbox_ids) if mailbox_id}
    with _lock:
        items = _load()
        kept = [item for item in items if str(item.get("id") or "") not in targets]
        removed = len(items) - len(kept)
        if removed:
            _save(kept)
        public_items = [_public_record(item) for item in sorted(kept, key=lambda value: str(value.get("created_at") or ""), reverse=True)]
        return {"items": public_items, "summary": _summary(kept), "removed": removed}
