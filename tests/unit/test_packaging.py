# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0
# Modified by SuperEGM (gsVAM), 2026: one host; the bundle test, palettes and required files of section 15;
# three-file hook rule, hook hash, effects checks.

"""Exercise distributable contents, unsafe paths, and reproducible output."""

# Modified by the elephant-goldfish-model Astra fork (gsVAM), 2026: the handoff
# and wave skills, their palettes and the shared handoff helper.

import json
from pathlib import Path
import runpy
import shutil
from xml.etree import ElementTree
import zipfile

import pytest

ROOT = Path(__file__).resolve().parents[2]
build = runpy.run_path(str(ROOT / "scripts/pack_plugin.py"))["build"]
BLUE, ORANGE = ("#1b6ef3", "#7cacf8"), ("#e86e00", "#ff8d41")
# Assembled at runtime so the scan of this file does not match its own word list.
BANNED = tuple("".join(parts) for parts in (
    ("boot", "strap"), ("synthes", "izer"), ("distri", "butions/"), (".codex", "-plugin"),
    ("open", "ai"), ("--tar", "get"),
))
PALETTES = [(skill, *BLUE) for skill in (
    "brainstorming", "draft", "plan", "file", "writing-skills", "using-superegm",
    "test-driven-development", "systematic-debugging", "verification-before-completion",
    "finishing-a-development-branch", "orient", "inbox",
)] + [(skill, *ORANGE) for skill in (
    "review-spec", "review-plan", "wave", "interrupt", "clean", "integrate", "judges", "drift-report", "driver",
)]


@pytest.fixture
def source(tmp_path: Path) -> Path:
  root = tmp_path / "source"
  root.mkdir()
  for name in ("plugin.json", "LICENSE", "LICENSE-MIT", "README.md", "pyproject.toml"):
    shutil.copyfile(ROOT / name, root / name)
  for name in ("skills", "agents", "resources", "docs", ".claude-plugin", "hooks"):
    shutil.copytree(ROOT / name, root / name)
  return root


def test_runtime_bundle_ships_exactly_the_kept_files(source: Path, tmp_path: Path) -> None:
  for name in ("tests/secret.txt", ".github/workflows/a.yml", "docs/experimental-host.md",
               "docs/designs/x.md", ".agents/plugins/marketplace.json"):
    file = source / name
    file.parent.mkdir(parents=True, exist_ok=True)
    file.write_text("must not ship")
  first, archive = build(source, tmp_path / "first")
  _, repeated = build(source, tmp_path / "second")
  assert first.name == "superegm" and archive.name == "superegm.zip"
  assert archive.read_bytes() == repeated.read_bytes()
  with zipfile.ZipFile(archive) as bundle:
    assert bundle.testzip() is None
    names = set(bundle.namelist())
    assert len([p for p in names if p.endswith("/SKILL.md")]) == 21
    for skill in source.glob("skills/*/SKILL.md"):
      icon = skill.parent / "assets/icon.svg"
      data = bundle.read(icon.relative_to(source).as_posix())
      assert data == icon.read_bytes()
      assert ElementTree.fromstring(data).tag == "{http://www.w3.org/2000/svg}svg"
    for name in ("LICENSE", "LICENSE-MIT", "README.md", "plugin.json", ".claude-plugin/plugin.json",
                 ".claude-plugin/icon.png", ".claude-plugin/agents/foreman.md", "agents/judge.md",
                 "skills/plan/scripts/superegm.py", "skills/wave/references/builder_orders.md",
                 "skills/test-driven-development/writing-good-tests.md",
                 "skills/systematic-debugging/find-polluter.sh", "skills/writing-skills/render-graphs.js",
                 "skills/writing-skills/references/skill_discovery_optimization.md",
                 "resources/document_standards/handoff-standard.md", "docs/claude.md"):
      assert name in names, name
    package = ("__init__", "apply", "approve_spec", "body", "clean", "close", "collect", "decide", "decision",
               "doctor", "dry_run", "foreman", "gate", "graph", "init", "interrupt", "judges", "launch", "launch_builder",
               "prepare", "record_launch", "report", "review", "review_plan", "runcard", "scan", "status", "tdd_order",
               "verify")
    package += ("orient", "builder_token")
    package += ("inbox",)
    package += ("driver", "register")
    assert sorted(p for p in names if p.endswith(".py")) == sorted(
        ["skills/plan/scripts/superegm.py", *(f"skills/plan/scripts/superegm/{m}.py" for m in package)])
    assert not any(p.startswith(("tests/", ".github/", ".agents/", "docs/designs/"))
                   or p.endswith(("test_scenarios.yaml", "marketplace.json", "pyproject.toml"))
                   for p in names)
    assert "docs/experimental-host.md" not in names
    for info in bundle.infolist():
      assert info.date_time == (1980, 1, 1, 0, 0, 0) and info.external_attr >> 16 == 0o100644
      assert bundle.read(info) == (first / info.filename).read_bytes()
  check_links = runpy.run_path(str(ROOT / "tests/unit/test_link_integrity.py"))[
      "test_relative_markdown_links_resolve_on_disk"]
  check_links(first)
  for path in ("scripts/pack_plugin.py", "scripts/prepare_release.py", "tests/unit/test_packaging.py",
               "tests/unit/test_harnesses.py", "tests/unit/test_releases.py"):
    text = (ROOT / path).read_text(encoding="utf-8").lower()
    hits = [w for w in BANNED if w in text]
    assert hits == [], (path, hits)


@pytest.mark.parametrize("skill,base,facet", PALETTES)
def test_skill_icon_palette(skill: str, base: str, facet: str) -> None:
  svg = ElementTree.parse(ROOT / "skills" / skill / "assets/icon.svg").getroot()
  assert svg.get("viewBox") == "0 0 24 24"
  assert svg.findtext("{http://www.w3.org/2000/svg}title")
  colors = {
      value.lower() for element in svg.iter()
      for key, value in element.attrib.items()
      if key in ("fill", "stroke") and value != "none"
  }
  assert colors == {base, facet}


def test_bundles_readme_images(source: Path, tmp_path: Path) -> None:
  image_dir = source / "docs/assets"
  image_dir.mkdir(exist_ok=True)
  image = image_dir / "readme-header.svg"
  image.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
  (image_dir / "private.txt").write_text("must not ship")
  readme = source / "README.md"
  readme.write_text(readme.read_text() + '\n![Header](docs/assets/readme-header.svg)\n')
  _, archive = build(source, tmp_path / "output")
  with zipfile.ZipFile(archive) as bundle:
    assert bundle.read("docs/assets/readme-header.svg") == image.read_bytes()
    assert "docs/assets/private.txt" not in bundle.namelist()


@pytest.mark.parametrize("directory", [False, True])
def test_rejects_symlinked_runtime_paths(
    source: Path, tmp_path: Path, directory: bool,
) -> None:
  victim = source / ("agents" if directory else "skills/plan/assets/icon.svg")
  outside = tmp_path / "outside"
  shutil.move(str(victim), outside)
  victim.symlink_to(outside, target_is_directory=directory)
  with pytest.raises(ValueError, match="Symlink"):
    build(source, tmp_path / "output")


@pytest.mark.parametrize("agents", [
    "./.claude-plugin/agents/style.md", ["./.claude-plugin/agents/style.md"],
])
def test_claude_agent_reference_forms(
    source: Path, tmp_path: Path, agents: str | list[str],
) -> None:
  path = source / ".claude-plugin/plugin.json"
  manifest = json.loads(path.read_text())
  manifest["agents"] = agents
  path.write_text(json.dumps(manifest))
  folder, archive = build(source, tmp_path / "output")
  reference = ".claude-plugin/agents/style.md"
  assert (folder / reference).read_bytes() == (source / reference).read_bytes()
  assert (folder / ".claude-plugin/plugin.json").read_bytes() == path.read_bytes()
  with zipfile.ZipFile(archive) as bundle:
    assert bundle.read(reference) == (source / reference).read_bytes()
    assert bundle.read(".claude-plugin/plugin.json") == path.read_bytes()


@pytest.mark.parametrize("agents", [
    None, 5, True, {}, {"./agents/style.md": None}, 1.5,
])
def test_rejects_invalid_manifest_agents(
    source: Path, tmp_path: Path, agents: object,
) -> None:
  path = source / ".claude-plugin/plugin.json"
  manifest = json.loads(path.read_text())
  manifest["agents"] = agents
  path.write_text(json.dumps(manifest))
  output = tmp_path / "output"
  with pytest.raises(ValueError) as error:
    build(source, output)
  assert str(error.value) == f"Invalid manifest agents: {agents!r}"
  assert not output.exists()


@pytest.mark.parametrize("reference", [
    "./.claude-plugin/agents/missing.md", "../escape.md", "/tmp/agent.md",
])
def test_rejects_escaping_or_missing_scalar_agent_references(
    source: Path, tmp_path: Path, reference: str,
) -> None:
  path = source / ".claude-plugin/plugin.json"
  manifest = json.loads(path.read_text())
  manifest["agents"] = reference
  path.write_text(json.dumps(manifest))
  output = tmp_path / "output"
  with pytest.raises(ValueError) as error:
    build(source, output)
  assert str(error.value) == f"Unbundled manifest reference: {reference}"
  assert not output.exists()


def test_refuses_hooks_and_overwrites(source: Path, tmp_path: Path) -> None:
  output = tmp_path / "output"
  build(source, output)
  with pytest.raises(ValueError, match="already exists"):
    build(source, output)
  path = source / ".claude-plugin/plugin.json"
  manifest = json.loads(path.read_text())
  manifest["hooks"] = {"PreToolUse": []}
  path.write_text(json.dumps(manifest))
  with pytest.raises(ValueError, match="hooks"):
    build(source, tmp_path / "other")


@pytest.mark.parametrize("field", ["apps", "mcpServers"])
def test_refuses_unbundled_services(source: Path, tmp_path: Path, field: str) -> None:
  path = source / "plugin.json"
  manifest = json.loads(path.read_text())
  manifest[field] = "./missing.json"
  path.write_text(json.dumps(manifest))
  with pytest.raises(ValueError, match="dependencies"):
    build(source, tmp_path / "output")


@pytest.mark.parametrize("missing", [
    "skills",
    "skills/plan/SKILL.md",
    "skills/plan/scripts/superegm.py",
    "skills/judges/assets/icon.svg",
    "skills/review-spec/references/review_loop.md",
    "agents/design.md",
    ".claude-plugin/agents/foreman.md",
    "resources/execution_instructions.md",
    "resources/document_standards/zoom-out-standard.md",
    "docs/claude.md",
    "LICENSE-MIT",
])
def test_incomplete_source_fails_before_output(
    source: Path, tmp_path: Path, missing: str,
) -> None:
  path = source / missing
  if path.is_dir():
    shutil.rmtree(path)
  else:
    path.unlink()
  output = tmp_path / "output"
  with pytest.raises(ValueError, match="Missing required file"):
    build(source, output)
  assert not output.exists()


@pytest.mark.parametrize("suffix", ["", ".zip"])
def test_rejects_dangling_output_symlinks(
    source: Path, tmp_path: Path, suffix: str,
) -> None:
  output = tmp_path / "output"
  output.mkdir()
  outside = tmp_path / "outside"
  link = output / f"superegm{suffix}"
  link.symlink_to(outside, target_is_directory=not suffix)
  with pytest.raises(ValueError, match="already exists"):
    build(source, output)
  assert link.is_symlink()
  assert not outside.exists()
  assert list(output.iterdir()) == [link]


@pytest.mark.parametrize("claim", ["file", "dangling-symlink", "symlink"])
def test_archive_claimed_after_preflight_is_not_overwritten(
    source: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, claim: str,
) -> None:
  output = tmp_path / "output"
  archive = output / "superegm.zip"
  outside = tmp_path / "outside.zip"
  if claim == "symlink":
    outside.write_bytes(b"outside file must not change")
  original_zipfile = zipfile.ZipFile

  def claim_archive(*args, **kwargs):
    if claim != "file":
      archive.symlink_to(outside)
    else:
      archive.write_bytes(b"another build owns this file")
    return original_zipfile(*args, **kwargs)

  monkeypatch.setattr(zipfile, "ZipFile", claim_archive)
  with pytest.raises(FileExistsError):
    build(source, output)
  if claim != "file":
    assert archive.is_symlink()
    if claim == "symlink":
      assert outside.read_bytes() == b"outside file must not change"
    else:
      assert not outside.exists()
  else:
    assert archive.read_bytes() == b"another build owns this file"
  assert not list(output.glob(".superegm-*"))


HOOK_FILES = {"hooks/hooks.json", "hooks/run-hook.cmd", "hooks/session-start"}


def test_bundle_ships_exactly_the_three_hook_files(source: Path, tmp_path: Path) -> None:
  _, archive = build(source, tmp_path / "out")
  with zipfile.ZipFile(archive) as bundle:
    names = set(bundle.namelist())
  assert {n for n in names if n.startswith("hooks/")} == HOOK_FILES


@pytest.mark.parametrize("damage,message", [
    ("extra", "Hooks: hooks/hooks-cursor.json is not one of the three hook files"),
    ("hash", "Hooks: hook_sha256 does not match hooks/session-start"),
    ("missing", "Hooks: hook_sha256 missing from .claude-plugin/plugin.json"),
    ("entries", "Hooks: hooks.json must declare one SessionStart command hook"),
])
def test_build_refuses_hook_violations(
    source: Path, tmp_path: Path, damage: str, message: str,
) -> None:
  if damage == "extra":
    (source / "hooks/hooks-cursor.json").write_text("{}")
  elif damage == "hash":
    (source / "hooks/session-start").write_text("#!/usr/bin/env bash\nexit 0\n")
  elif damage == "missing":
    path = source / ".claude-plugin/plugin.json"
    manifest = json.loads(path.read_text())
    del manifest["superegm"]
    path.write_text(json.dumps(manifest))
  else:
    path = source / "hooks/hooks.json"
    hooks = json.loads(path.read_text())
    hooks["hooks"]["PreToolUse"] = []
    path.write_text(json.dumps(hooks))
  output = tmp_path / "out"
  with pytest.raises(ValueError) as error:
    build(source, output)
  assert str(error.value) == message
  assert not output.exists()


def test_build_refuses_effects_violation(source: Path, tmp_path: Path) -> None:
  path = source / "skills/clean/SKILL.md"
  path.write_text(path.read_text().replace("disable-model-invocation: true\n", "", 1))
  output = tmp_path / "out"
  with pytest.raises(ValueError) as error:
    build(source, output)
  assert str(error.value) == "Effects: clean: external but not disable-model-invocation: true"
  assert not output.exists()
