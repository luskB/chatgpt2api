from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from api.support import require_admin
from services import imported_mailbox_service


class ImportedMailboxDefaults(BaseModel):
    fetch_method: str | None = None
    imap_host: str | None = None
    imap_port: int | None = None
    imap_ssl: bool | None = None
    imap_folder: str | None = None
    graph_tenant: str | None = None
    graph_client_id: str | None = None
    client_id: str | None = None
    graph_client_secret: str | None = None
    client_secret: str | None = None


class ImportMailboxesRequest(ImportedMailboxDefaults):
    text: str = ""


def create_router() -> APIRouter:
    router = APIRouter()

    @router.get("/api/imported-mailboxes")
    async def list_imported_mailboxes(authorization: str | None = Header(default=None)):
        require_admin(authorization)
        return imported_mailbox_service.list_mailboxes()

    @router.post("/api/imported-mailboxes/import")
    async def import_imported_mailboxes(body: ImportMailboxesRequest, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        payload = body.model_dump(exclude_none=True)
        text = str(payload.pop("text", ""))
        return imported_mailbox_service.import_mailboxes(text, payload)

    @router.post("/api/imported-mailboxes/{mailbox_id}/reset")
    async def reset_imported_mailbox(mailbox_id: str, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            item = imported_mailbox_service.reset_mailbox(mailbox_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return {"item": item, **imported_mailbox_service.list_mailboxes()}

    @router.delete("/api/imported-mailboxes/{mailbox_id}")
    async def delete_imported_mailbox(mailbox_id: str, authorization: str | None = Header(default=None)):
        require_admin(authorization)
        try:
            imported_mailbox_service.delete_mailbox(mailbox_id)
        except KeyError as error:
            raise HTTPException(status_code=404, detail=str(error)) from error
        return imported_mailbox_service.list_mailboxes()

    return router
