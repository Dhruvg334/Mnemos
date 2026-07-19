from pathlib import Path


def test_render_blueprint_defines_api_worker_and_datastores() -> None:
    source = Path("render.yaml").read_text(encoding="utf-8")
    assert "name: mnemos-api" in source
    assert "name: mnemos-query-worker" in source
    assert "type: worker" in source
    assert "dockerCommand: worker" in source
    assert "healthCheckPath: /health/live" in source
    assert "name: mnemos-postgres" in source
    assert "name: mnemos-redis" in source
    assert "QUERY_DISPATCH_MODE" in source


def test_frontend_server_proxy_and_vercel_config_are_committed() -> None:
    assert Path("frontend/vercel.json").is_file()
    assert Path("frontend/lib/server/auth.js").is_file()
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "\nlib/\n" not in gitignore


def test_worker_entrypoint_is_available() -> None:
    entrypoint = Path("scripts/container-entrypoint.sh").read_text(encoding="utf-8")
    worker = Path("src/mnemos/worker.py").read_text(encoding="utf-8")
    assert "worker)" in entrypoint
    assert "python -m mnemos.worker" in entrypoint
    assert "with_for_update(skip_locked=True)" in worker
