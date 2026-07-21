import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "frontend"
PROHIBITED = re.compile(
    r"(?:blue-|indigo-|cyan-|violet-|navy|#(?:081728|2f6fe0|1f4fb0|eaf2fd|bdd6f7))", re.I
)


def test_frontend_source_has_no_prohibited_decorative_blue_tokens():
    findings = []
    excluded = {"node_modules", ".next"}
    for path in ROOT.rglob("*"):
        if any(part in excluded for part in path.parts):
            continue
        if path.is_file() and path.suffix in {".js", ".css", ".svg"}:
            match = PROHIBITED.search(path.read_text(encoding="utf-8"))
            if match:
                findings.append(f"{path.relative_to(ROOT)}:{match.group(0)}")
    assert not findings, findings


def test_public_header_uses_stable_three_column_grid():
    source = (ROOT / "components/public/PublicHeader.js").read_text(encoding="utf-8")
    assert "grid-cols-[1fr_auto_1fr]" in source
    assert "justify-self-center" in source
    assert "justify-self-end" in source
