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
    assert "setSessionCookies(payload.data)" in source
