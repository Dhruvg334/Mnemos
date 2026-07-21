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
    assert 'fetch("/api/queries"' in panel
    assert "pollQuery" in panel
    assert 'Section title="Evidence"' in panel


def test_product_screenshots_are_versioned_and_indexed() -> None:
    screenshots = ROOT / "docs" / "screenshots"
    assert (screenshots / "README.md").is_file()
    for filename in ("dashboard.png", "investigation.png", "graph.png", "query-panel.png"):
        assert (screenshots / filename).is_file()


def test_public_header_hides_auth_actions_for_active_session() -> None:
    source = _read("frontend/components/public/PublicHeader.js")
    assert 'fetch("/api/auth/session"' in source
    assert "session.user ?" in source
    assert "Open workspace" in source
    assert "async function signOut" in source


def test_public_brand_assets_are_consistent_and_file_based() -> None:
    layout = _read("frontend/app/layout.js")
    brand = _read("frontend/components/public/Brand.js")
    assert '"/brand/mnemos-mark.svg"' in layout
    assert "M128 31L203 72V160L128 204L53 160V72L128 31Z" in brand
    assert (ROOT / "frontend" / "app" / "icon.svg").is_file()
    assert (ROOT / "frontend" / "public" / "brand" / "industrial-memory-hero.webp").is_file()


def test_public_home_has_interactive_operational_story() -> None:
    page = _read("frontend/app/page.js")
    workflow = _read("frontend/components/public/LandingWorkflow.js")
    assert "industrial-memory-hero.webp" in page
    assert "LandingWorkflow" in page
    assert "Weighted evaluation score" in page
    assert 'role="tablist"' in workflow
    assert "Evidence chain" in workflow


def test_signed_in_queries_use_the_authenticated_backend_pipeline() -> None:
    panel = _read("frontend/components/views/QueryPanel.js")
    create_route = _read("frontend/app/api/queries/route.js")
    read_route = _read("frontend/app/api/queries/[queryId]/route.js")
    assert 'fetch("/api/queries"' in panel
    assert 'fetch(`/api/queries/${encodeURIComponent(queryId)}`' in panel
    assert 'requestWithSession("/queries"' in create_route
    assert 'requestWithSession("/sites"' in create_route
    assert 'backendRequest(`/queries/${encodeURIComponent(queryId)}`' in read_route


def test_public_header_reduces_authenticated_controls_to_actions() -> None:
    source = _read("frontend/components/public/PublicHeader.js")
    assert "session.user.full_name" not in source
    assert ">Sign out</button>" in source
    assert "Open workspace" in source


def test_about_page_uses_current_team_names_and_roles() -> None:
    source = _read("frontend/app/about/page.js")
    assert "Akshhaya Isa" in source
    assert "Product engineering lead" in source
    assert "release engineering" in source
