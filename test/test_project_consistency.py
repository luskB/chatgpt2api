from __future__ import annotations

import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PORT = "8866"
OLD_PORT = str(8000)


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_container_build_does_not_require_local_config_file() -> None:
    assert "COPY config.json" not in read("Dockerfile")


def test_local_service_port_references_use_project_default() -> None:
    scanned_paths = [
        ".codex/skills/chatgpt2api-search/SKILL.md",
        "test/utils.py",
        "test/test_gpt_ppt.py",
        "test/test_gpt_psd.py",
        "test/test_image_base_url_api.py",
        "test/test_v1_chat_completions.py",
        "test/test_v1_images_edits.py",
        "test/test_v1_images_generations.py",
        "test/test_v1_messages.py",
        "test/test_v1_models.py",
        "test/test_v1_responses.py",
    ]
    stale_hosts = (f"127.0.0.1:{OLD_PORT}", f"localhost:{OLD_PORT}")
    for path in scanned_paths:
        content = read(path)
        assert not any(host in content for host in stale_hosts), path

    assert f"127.0.0.1:{DEFAULT_PORT}" in read(".codex/skills/chatgpt2api-search/SKILL.md")


def test_python_entrypoint_uses_project_default_port() -> None:
    main_py = read("main.py")
    assert f"port={DEFAULT_PORT}" in main_py


def test_package_metadata_matches_project_identity() -> None:
    version = read("VERSION").strip()
    pyproject = tomllib.loads(read("pyproject.toml"))
    package_json = json.loads(read("web/package.json"))
    uv_lock = read("uv.lock")

    assert pyproject["project"]["name"] == "chatgpt2api"
    assert pyproject["project"]["version"] == version
    assert pyproject["project"]["description"] != "Add your description here"
    assert f'name = "chatgpt2api"\nversion = "{version}"' in uv_lock

    assert package_json["name"] == "chatgpt2api-web"
    assert package_json["version"] == version


def test_gitignore_does_not_reference_misspelled_compose_file() -> None:
    assert "docker-compose-local.yml" not in read(".gitignore")


def test_cloudmail_domain_copy_matches_backend_requirement() -> None:
    register_card = read("web/src/app/register/components/register-card.tsx")
    cloudmail_placeholder = re.search(
        r'placeholder=\{type === "cloudmail_gen" \? "([^"]+)"',
        register_card,
    )
    assert cloudmail_placeholder is not None
    assert "必填" in cloudmail_placeholder.group(1)
    assert "留空" not in cloudmail_placeholder.group(1)


def test_feature_status_matches_implemented_routes() -> None:
    feature_status = read("docs/feature-status.en.md")
    api_routes = read("api/ai.py")

    assert '@router.post("/v1/messages")' in api_routes
    assert "| Anthropic 协议支持 | ✅" in feature_status
    assert "/v1/complete" not in feature_status
    assert "| 图片尺寸参数 | ✅" in feature_status
