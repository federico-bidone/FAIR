from __future__ import annotations

import json
from pathlib import Path

import yaml

from fair3.engine.reporting.audit import (
    copy_seed_snapshot,
    record_checksums,
    run_audit_snapshot,
)


def test_copy_seed_snapshot_creates_default(tmp_path: Path) -> None:
    seed_path = tmp_path / "audit" / "seeds.yml"
    snapshot = copy_seed_snapshot(seed_path, audit_dir=tmp_path / "artifacts" / "audit")
    assert snapshot.exists()
    written = yaml.safe_load(seed_path.read_text(encoding="utf-8"))
    assert "seeds" in written


def test_record_checksums_appends(tmp_path: Path) -> None:
    audit_dir = tmp_path / "artifacts" / "audit"
    file_a = tmp_path / "a.txt"
    file_b = tmp_path / "b.txt"
    file_a.write_text("a", encoding="utf-8")
    file_b.write_text("b", encoding="utf-8")
    record_checksums([file_a], audit_dir=audit_dir)
    path = record_checksums([file_a, file_b], audit_dir=audit_dir)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data, list)
    assert len(data) == 2


def test_run_audit_snapshot_creates_changelog(tmp_path: Path) -> None:
    seed_path = tmp_path / "seed.yml"
    seed_path.parent.mkdir(parents=True, exist_ok=True)
    seed_path.write_text("seeds:\n  global: 1\n", encoding="utf-8")
    config = tmp_path / "config.yml"
    config.write_text("value: 1\n", encoding="utf-8")
    outputs = run_audit_snapshot(
        seed_path=seed_path,
        config_paths=[config],
        note="smoke",
        audit_dir=tmp_path / "artifacts" / "audit",
    )
    changelog = outputs["changelog"]
    assert changelog.exists()
    content = changelog.read_text(encoding="utf-8")
    assert "smoke" in content
    assert "config.yml" in content
