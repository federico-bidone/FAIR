from pathlib import Path

from fair3.engine.utils import artifact_path, compute_checksums, sha256_file, write_yaml
from fair3.engine.utils.io import ensure_dir, safe_path_segment


def test_artifact_path_creates_directory(tmp_path: Path) -> None:
    root = tmp_path / "artifacts"
    path = artifact_path("audit", "checksums.json", root=root)
    assert path.parent.exists()
    assert path.parent == root / "audit"


def test_checksum_deterministic(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.txt"
    file_path.write_text("fair3", encoding="utf-8")
    first = sha256_file(file_path)
    second = sha256_file(file_path)
    assert first == second


def test_compute_checksums_skips_missing(tmp_path: Path) -> None:
    existing = tmp_path / "exists.yml"
    write_yaml({"a": 1}, existing)
    missing = tmp_path / "missing.yml"
    checksums = compute_checksums([existing, missing])
    assert str(existing) in checksums
    assert str(missing) not in checksums


def test_safe_path_segment_replaces_invalid_characters(tmp_path: Path) -> None:
    unsafe = "2024-01:2024-03"
    safe = safe_path_segment(unsafe)
    assert ":" not in safe
    assert safe == "2024-01-2024-03"

    created = ensure_dir(tmp_path / safe)
    assert created.exists()
    assert created.name == safe


def test_safe_path_segment_strips_trailing_dots_and_spaces() -> None:
    unsafe = "report ."
    safe = safe_path_segment(unsafe)
    assert safe == "report"
