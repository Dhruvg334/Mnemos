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


def test_topbar_controls_are_interactive_and_navigable() -> None:
    source = _read("frontend/components/Topbar.js")
    assert 'setPanel("search")' in source
    assert 'setPanel("notifications")' in source
    assert 'setPanel("activity")' in source
    assert 'window.addEventListener("keydown"' in source
    assert "onNavigate(result.view" in source
    assert "Mark all as read" in source


def test_every_demo_query_has_an_accessible_result() -> None:
    source = _read("frontend/lib/data.js")
    for query_id in ("q_1", "q_2", "q_3", "q_4", "q_5"):
        assert f"  {query_id}: {{" in source
    panel = _read("frontend/components/views/QueryPanel.js")
    assert "initialQueryId" in panel
    assert "knownResult" in panel
    assert 'Section title="Evidence"' in panel


def test_product_screenshots_are_versioned_and_indexed() -> None:
    screenshots = ROOT / "docs" / "screenshots"
    assert (screenshots / "README.md").is_file()
    for filename in ("dashboard.png", "investigation.png", "graph.png", "query-panel.png"):
        assert (screenshots / filename).is_file()
