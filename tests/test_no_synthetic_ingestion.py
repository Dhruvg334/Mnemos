from pathlib import Path


def test_authenticated_ingestion_has_no_fabricated_asset_pipeline():
    source_root = Path(__file__).resolve().parents[1] / "src" / "mnemos"
    combined = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore") for path in source_root.rglob("*.py")
    )
    assert "run_production_ingestion_pipeline" not in combined
    assert "P-101 operates at 3600 RPM" not in combined
    assert "Failure mode: Excessive vibration on P-101" not in combined
