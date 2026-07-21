from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_dashboard_proxy_does_not_require_authentication() -> None:
    source = _read("frontend/proxy.js")
    assert "NextResponse.redirect" not in source
    assert "return NextResponse.next()" in source


def test_public_demo_has_read_only_session_guard() -> None:
    source = _read("frontend/components/auth/SessionContext.js")
    assert "The public demo is read-only" in source
    assert "requireAuthentication" in source
    assert 'router.push("/signin")' in source


def test_registration_route_sets_session_cookies() -> None:
    source = _read("frontend/app/api/auth/register/route.js")
    assert "await setSessionCookies(payload.data)" in source


def test_next_cookie_api_is_awaited_for_authentication_routes() -> None:
    auth_source = _read("frontend/lib/server/auth.js")
    login_source = _read("frontend/app/api/auth/login/route.js")
    session_source = _read("frontend/app/api/auth/session/route.js")
    assert "const jar = await cookies()" in auth_source
    assert "await setSessionCookies(payload.data)" in login_source
    assert "let token = await getAccessToken()" in session_source


def test_auth_form_has_password_visibility_and_transition_feedback() -> None:
    source = _read("frontend/components/public/AuthForm.js")
    assert "Show password" in source
    assert "Hide password" in source
    assert "Creating your workspace" in source
    assert "Opening your dashboard" in source


def test_graph_layout_prioritises_spacing_and_legibility() -> None:
    source = _read("frontend/components/views/Graph.js")
    assert "nodeRepulsion: 620000" in source
    assert "idealEdgeLength: 205" in source
    assert '"text-valign": "center"' in source
    assert "wheelSensitivity: 0.42" in source
