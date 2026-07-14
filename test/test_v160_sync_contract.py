from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_release_is_exactly_v160() -> None:
    assert read("VERSION").strip() == "1.6.0"
    assert 'version = "1.6.0"' in read("pyproject.toml")
    assert '"version": "1.6.0"' in read("web/package.json")


def test_local_identity_and_deployment_are_preserved() -> None:
    update_check = read("web/src/hooks/use-version-check.ts")
    assert '"8866:80"' in read("docker-compose.yml")
    assert "--port 8866" in read("start.bat")
    assert "https://github.com/luskB/chatgpt2api" in read("README.md")
    assert "https://github.com/luskB/chatgpt2api" in read("web/src/components/header-actions.tsx")
    assert "raw.githubusercontent.com/luskB/chatgpt2api" in update_check
    assert "raw.githubusercontent.com/basketikun/chatgpt2api" not in update_check


def test_luckmail_and_outlook_token_are_both_available() -> None:
    provider = read("services/register/mail_provider.py")
    register_ui = read("web/src/app/register/components/register-card.tsx")
    assert "class LuckMailProvider" in provider
    assert 'entry["type"] == "luckmail"' in provider
    assert "class OutlookTokenProvider" in provider
    assert 'entry["type"] == "outlook_token"' in provider
    assert '<SelectItem value="luckmail">' in register_ui
    assert '<SelectItem value="outlook_token">' in register_ui


def test_luckmail_retries_reuse_the_purchased_mailbox() -> None:
    register = read("services/register/openai_register.py")
    assert 'str(mailbox.get("provider") or "") == "luckmail"' in register
    assert 'retry_limit = max(1, int(mailbox.get("retry_limit") or 1))' in register
    assert "result = registrar.register(index, mailbox)" in register


def test_upstream_outlook_replaces_imported_mailbox_runtime() -> None:
    app = read("api/app.py")
    nav = read("web/src/components/top-nav.tsx")
    register_ui = read("web/src/app/register/components/register-card.tsx")
    assert "imported_mailboxes" not in app
    assert "imported_mailbox" not in register_ui
    assert 'href: "/mailboxes"' not in nav
    assert not (ROOT / "api/imported_mailboxes.py").exists()
    assert not (ROOT / "services/imported_mailbox_service.py").exists()
    assert not (ROOT / "web/src/app/mailboxes/page.tsx").exists()


def test_mcp_customization_is_preserved() -> None:
    app = read("api/app.py")
    settings = read("web/src/app/settings/page.tsx")
    service = read("services/mcp_search_service.py")
    assert "mcp.create_router()" in app
    assert "McpKeysCard" in settings
    assert 'server_version: str = "1.6.0"' in service
    assert "1.4.0" not in service
    assert (ROOT / "api/mcp.py").exists()
    assert (ROOT / "services/mcp_key_service.py").exists()
    assert (ROOT / "services/mcp_search_service.py").exists()
