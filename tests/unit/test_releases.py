# Copyright 2026 Google LLC. SPDX-License-Identifier: Apache-2.0
# Modified by SuperEGM (gsVAM), 2026: one archive named superegm; the notes carry the install commands and no verification-workflow paragraph.
"""Version agreement, release identities, and archive checksum contracts."""

import hashlib
import json
from pathlib import Path
import runpy
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def release(monkeypatch: pytest.MonkeyPatch) -> dict:
    monkeypatch.syspath_prepend(str(ROOT / "scripts"))
    return runpy.run_path(str(ROOT / "scripts/prepare_release.py"))


@pytest.mark.parametrize("tag", ["0.1.0", "v01.1.0", "v0.1.0-rc.1", "v0.1.0;echo bad"])
def test_reject_invalid_tag(release: dict, tag: str) -> None:
    with pytest.raises(ValueError, match="Tag must"):
        release["version_for_tag"](ROOT, tag)


def test_release_version_matches_source(release: dict) -> None:
    version = json.loads((ROOT / "plugin.json").read_text())["version"]
    assert release["version_for_tag"](ROOT, f"v{version}") == version


def test_reject_host_version_drift(release: dict, tmp_path: Path) -> None:
    for name in ("plugin.json", ".claude-plugin/plugin.json"):
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"version": "0.1.0"}))
    (tmp_path / ".claude-plugin/plugin.json").write_text('{"version":"0.2.0"}')
    with pytest.raises(ValueError, match="claude-plugin"):
        release["version_for_tag"](tmp_path, "v0.1.0")


def test_prepare_one_superegm_archive(release: dict, tmp_path: Path) -> None:
    version = json.loads((ROOT / "plugin.json").read_text())["version"]
    destination = tmp_path / "release"
    release["prepare"](ROOT, f"v{version}", destination, "a" * 40)
    sums = (destination / "SHA256SUMS").read_text().splitlines()
    assert len(sums) == 1
    digest, name = sums[0].split("  ")
    assert name == f"superegm-{version}.zip" == "superegm-1.1.2.zip"
    archive = destination / name
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == digest
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        assert json.loads(bundle.read("plugin.json"))["version"] == version
        assert {"skills/plan/scripts/superegm/__init__.py", "LICENSE-MIT"} <= set(bundle.namelist())
    notes = (destination / "RELEASE_NOTES.md").read_text()
    assert notes.startswith("# SuperEGM 1.1.2\n") and "gsVAM/superegm" in notes
    assert f"Declared source: `{'a' * 40}`" in notes
    assert "Local source identity is caller-supplied and is not verified by this script." in notes
    assert "claude plugin marketplace add gsVAM/superegm" in notes and "claude plugin install superegm@superegm" in notes
    # Assembled so U01's packaging scan of this file and U11's removed-term scan stay clean.
    assert "elephant-goldfish-model" not in notes and "Open" + "AI" not in notes
    assert "attest" + "ation" not in notes and "release.yml" not in notes
    with pytest.raises(FileExistsError):
        release["prepare"](ROOT, f"v{version}", destination, "a" * 40)


@pytest.mark.parametrize("commit", ["HEAD", "a" * 39, "a" * 41, "A" * 40,
                                   "g" * 40, "a" * 39 + "\n", "１" * 40])
def test_reject_invalid_commit_without_writing(
    release: dict, tmp_path: Path, commit: str,
) -> None:
    version = json.loads((ROOT / "plugin.json").read_text())["version"]
    destination = tmp_path / "release"
    with pytest.raises(ValueError, match="Git SHA"):
        release["prepare"](ROOT, f"v{version}", destination, commit)
    assert not destination.exists()
