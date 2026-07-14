from __future__ import annotations

import time
from unittest.mock import Mock, patch

from services.register import openai_register


def _result(email: str) -> dict[str, str]:
    return {
        "email": email,
        "password": "password",
        "access_token": "access-token",
        "refresh_token": "refresh-token",
        "id_token": "id-token",
        "source_type": "web",
        "created_at": "2026-07-14T00:00:00+00:00",
    }


def test_luckmail_worker_reuses_one_mailbox_until_retry_succeeds() -> None:
    mailbox = {
        "provider": "luckmail",
        "provider_ref": "luckmail#1",
        "address": "user@example.com",
        "retry_limit": 3,
    }
    seen_mailboxes: list[dict] = []

    class FakeRegistrar:
        def __init__(self, proxy: str):
            self.proxy = proxy

        def register(self, index: int, current_mailbox: dict) -> dict:
            seen_mailboxes.append(current_mailbox)
            if len(seen_mailboxes) < 3:
                raise RuntimeError(f"attempt-{len(seen_mailboxes)}")
            return _result(str(current_mailbox["address"]))

        def close(self) -> None:
            return None

    mark_result = Mock()
    old_stats = dict(openai_register.stats)
    openai_register.stats.update({"done": 0, "success": 0, "fail": 0, "start_time": time.time()})
    try:
        with (
            patch.object(openai_register, "create_mailbox", return_value=mailbox) as create_mailbox,
            patch.object(openai_register, "PlatformRegistrar", FakeRegistrar),
            patch.object(openai_register.mail_provider, "mark_mailbox_result", mark_result),
            patch.object(openai_register.account_service, "add_account_items"),
            patch.object(openai_register.account_service, "refresh_accounts", return_value={"errors": []}),
            patch.object(openai_register, "step"),
            patch.object(openai_register, "log"),
        ):
            result = openai_register.worker(1)
    finally:
        openai_register.stats.clear()
        openai_register.stats.update(old_stats)

    assert result["ok"] is True
    assert result["attempts"] == 3
    assert create_mailbox.call_count == 1
    assert seen_mailboxes == [mailbox, mailbox, mailbox]
    mark_result.assert_called_once_with(mailbox, success=True)


def test_outlook_worker_does_not_use_luckmail_retry_limit() -> None:
    mailbox = {
        "provider": "outlook_token",
        "provider_ref": "outlook_token#1",
        "address": "user@outlook.com",
        "retry_limit": 5,
    }
    attempts = 0

    class FakeRegistrar:
        def __init__(self, proxy: str):
            self.proxy = proxy

        def register(self, index: int, current_mailbox: dict) -> dict:
            nonlocal attempts
            attempts += 1
            raise RuntimeError("registration-failed")

        def close(self) -> None:
            return None

    mark_result = Mock()
    old_stats = dict(openai_register.stats)
    openai_register.stats.update({"done": 0, "success": 0, "fail": 0, "start_time": time.time()})
    try:
        with (
            patch.object(openai_register, "create_mailbox", return_value=mailbox),
            patch.object(openai_register, "PlatformRegistrar", FakeRegistrar),
            patch.object(openai_register.mail_provider, "mark_mailbox_result", mark_result),
            patch.object(openai_register, "step"),
            patch.object(openai_register, "log"),
        ):
            result = openai_register.worker(1)
    finally:
        openai_register.stats.clear()
        openai_register.stats.update(old_stats)

    assert result["ok"] is False
    assert attempts == 1
    mark_result.assert_called_once()
    args, kwargs = mark_result.call_args
    assert args == (mailbox,)
    assert kwargs["success"] is False
    assert "registration-failed" in str(kwargs["error"])
