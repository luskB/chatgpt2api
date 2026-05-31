from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_backend_accepts_post_for_bulk_imported_mailbox_delete() -> None:
    api_py = read("api/imported_mailboxes.py")
    service_py = read("services/imported_mailbox_service.py")

    assert '@router.post("/api/imported-mailboxes/delete")' in api_py
    assert "delete_imported_mailboxes" in api_py
    assert "imported_mailbox_service.delete_mailboxes(ids)" in api_py
    assert "def delete_mailboxes(" in service_py


def test_frontend_uses_post_bulk_imported_mailbox_delete_endpoint() -> None:
    api_ts = read("web/src/lib/api.ts")

    assert '"/api/imported-mailboxes/delete"' in api_ts
    assert "method: \"POST\"" in api_ts
    assert 'method: "DELETE",\n    body: { ids }' not in api_ts
