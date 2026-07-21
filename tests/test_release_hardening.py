from pathlib import Path

from fastapi.testclient import TestClient

from mnemos.core.config import Settings
from mnemos.main import app


def test_string_list_settings_accept_json_and_comma_separated_values(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", '["https://one.example", "https://two.example"]')
    monkeypatch.setenv("ALLOWED_UPLOAD_MIME_TYPES", "application/pdf,text/plain")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["https://one.example", "https://two.example"]
    assert settings.allowed_upload_mime_types == ["application/pdf", "text/plain"]


def test_string_list_settings_accept_single_origin(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ORIGINS", "https://app.example")
    settings = Settings(_env_file=None)
    assert settings.cors_origins == ["https://app.example"]


def test_service_index_exposes_only_non_sensitive_metadata() -> None:
    with TestClient(app) as client:
        response = client.get("/")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "operational"
    assert payload["health"]["live"] == "/health/live"
    serialized = response.text.lower()
    assert "database_url" not in serialized
    assert "jwt_secret" not in serialized
    assert "api_key" not in serialized


def test_public_documentation_does_not_claim_external_mcp_compatibility() -> None:
    readme = Path("README.md").read_text(encoding="utf-8")
    assert "internal governed tool-dispatch layer" in readme
    assert "protocol-level compatibility" in readme


def test_release_documentation_is_environment_neutral() -> None:
    public_docs = [
        Path("docs/architecture.md"),
        Path("docs/operations.md"),
        Path("docs/security.md"),
        Path("docs/deployment.md"),
    ]
    text = "\n".join(path.read_text(encoding="utf-8") for path in public_docs).lower()
    assert "onrender.com" not in text
    assert "mnemos-lake" not in text
    assert "hackathon" not in text
    assert "student submission" not in text


def test_public_demo_ui_remains_responsive_and_keyboard_accessible() -> None:
    graph = Path("frontend/components/views/Graph.js").read_text(encoding="utf-8")
    shell = Path("frontend/components/Shell.js").read_text(encoding="utf-8")
    assert 'min-w-[760px]' not in graph
    assert 'cytoscape' in graph
    assert 'onKeyDown=' in graph
    assert 'dashboard-page' in shell


def test_container_command_is_explicit() -> None:
    render_config = Path("render.yaml").read_text(encoding="utf-8")
    assert "dockerCommand: /app/scripts/container-entrypoint.sh migrate-and-api" in render_config


def test_repository_contains_no_live_secret_patterns() -> None:
    import re

    roots = [Path("src"), Path("frontend"), Path("scripts"), Path("docs"), Path("README.md")]
    patterns = [
        re.compile(r"gsk_[A-Za-z0-9]{24,}"),
        re.compile(r"sk-[A-Za-z0-9]{24,}"),
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ]
    for root in roots:
        files = [root] if root.is_file() else [
            path for path in root.rglob("*")
            if path.is_file() and ".next" not in path.parts and "node_modules" not in path.parts
        ]
        for path in files:
            if path.suffix not in {".py", ".js", ".md", ".json", ".yaml", ".yml", ".sh"}:
                continue
            content = path.read_text(encoding="utf-8", errors="ignore")
            assert not any(pattern.search(content) for pattern in patterns), path
