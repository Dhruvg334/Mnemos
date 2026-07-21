from pathlib import Path


def test_render_blueprint_defines_zero_card_free_profile() -> None:
    source = Path("render.yaml").read_text(encoding="utf-8")
    assert "name: mnemos-api" in source
    assert "type: web" in source
    assert "plan: free" in source
    assert "dockerCommand: /app/scripts/container-entrypoint.sh migrate-and-api" in source
    assert "healthCheckPath: /health/live" in source
    assert "name: mnemos-postgres" in source
    assert "name: mnemos-redis" in source
    assert "value: background" in source
    assert "type: worker" not in source
    assert "plan: starter" not in source
    assert "preDeployCommand:" not in source


def test_frontend_server_proxy_and_vercel_config_are_committed() -> None:
    assert Path("frontend/vercel.json").is_file()
    assert Path("frontend/lib/server/auth.js").is_file()
    gitignore = Path(".gitignore").read_text(encoding="utf-8")
    assert "\nlib/\n" not in gitignore


def test_worker_and_free_api_entrypoints_are_available() -> None:
    entrypoint = Path("scripts/container-entrypoint.sh").read_text(encoding="utf-8")
    worker = Path("src/mnemos/worker.py").read_text(encoding="utf-8")
    assert "migrate-and-api)" in entrypoint
    assert "alembic upgrade head" in entrypoint
    assert "worker)" in entrypoint
    assert "python -m mnemos.worker" in entrypoint
    assert "with_for_update(skip_locked=True)" in worker


def test_vercel_uses_pinned_node_and_stable_install_command() -> None:
    import json

    package = json.loads(Path("frontend/package.json").read_text(encoding="utf-8"))
    vercel = json.loads(Path("frontend/vercel.json").read_text(encoding="utf-8"))
    npmrc = Path("frontend/.npmrc").read_text(encoding="utf-8")

    assert package["engines"]["node"] == "20.x"
    assert package["packageManager"] == "npm@10.8.2"
    assert vercel["installCommand"] == "npm install --no-audit --no-fund --prefer-offline"
    assert vercel["buildCommand"] == "npm run build"
    assert "audit=false" in npmrc
    assert Path("frontend/.nvmrc").read_text(encoding="utf-8").strip() == "20"


def test_ci_builds_frontend_with_the_same_node_major() -> None:
    workflow = Path(".github/workflows/backend-ci.yml").read_text(encoding="utf-8")
    assert "frontend-build:" in workflow
    assert 'node-version: "20"' in workflow
    assert "cache-dependency-path: frontend/package-lock.json" in workflow
    assert "needs: [quality, evaluation-gates, frontend-build, migration]" in workflow
