# Copyright 2026 Google LLC.
# SPDX-License-Identifier: Apache-2.0
# Modified by SuperEGM (gsVAM), 2026: one host, the allow-list of section 15 and the three-file hook rule.

"""Build the runtime folder and a reproducible ZIP without development files."""

# Modified by the elephant-goldfish-model Astra fork (gsVAM), 2026: ships the
# handoff and wave skills, the shared handoff helper, the change-review
# persona and the handoff standard.

import argparse
import json
from pathlib import Path
import tempfile
import zipfile

SHARED = (
    "plugin.json", "LICENSE", "LICENSE-MIT", "README.md",
    "skills/*/SKILL.md", "skills/*/*.md", "skills/*/examples/*.md",
    "skills/*/*.sh", "skills/*/*.ts", "skills/*/*.js", "skills/*/*.dot",
    "skills/*/assets/*.svg", "skills/*/assets/*.png", "skills/*/references/*.md",
    "skills/*/scripts/*.py", "skills/*/scripts/superegm/*.py",
    "skills/*/references/*.json", "agents/*.md", "resources/*.md",
    "resources/document_standards/*.md", "docs/index.md", "docs/getting_started.md",
    "docs/claude.md", "docs/faq.md", "docs/privacy.md", "docs/releases.md",
    "docs/assets/*.svg", "docs/assets/*.png",
    "hooks/hooks.json", "hooks/run-hook.cmd", "hooks/session-start",
    ".claude-plugin/plugin.json", ".claude-plugin/icon.png",
    ".claude-plugin/agents/*.md",
)
HOOK_FILES = {"hooks/hooks.json", "hooks/run-hook.cmd", "hooks/session-start"}
MANIFEST = ".claude-plugin/plugin.json"
SKILLS = (
    "brainstorming", "draft", "review-spec", "plan", "review-plan", "file", "wave",
    "interrupt", "clean", "finishing-a-development-branch", "integrate", "judges",
    "test-driven-development", "systematic-debugging", "verification-before-completion",
    "writing-skills", "using-superegm", "drift-report",
)
IDS = (
    "design", "zoom-out", "comprehension", "codebase-details", "readiness",
    "structural", "style", "change-review", "judge", "foreman",
)
REQUIRED_SHARED = (
    "plugin.json", "LICENSE", "LICENSE-MIT", "README.md", MANIFEST,
    "docs/index.md", "docs/getting_started.md", "docs/claude.md", "docs/faq.md",
    "docs/privacy.md", "docs/releases.md",
    "resources/README.md", "resources/execution_instructions.md",
    "skills/draft/references/design_doc.md",
    "skills/plan/scripts/superegm.py",
    "skills/plan/references/handoff_plan.md",
    "skills/plan/references/issue_template.md",
    "skills/plan/references/handoff_config.md",
    "skills/wave/references/foreman_brief.md",
    "skills/wave/references/builder_orders.md",
    "skills/review-spec/references/review_loop.md",
    "skills/review-spec/references/resolve.md",
) + tuple(
    f"skills/{skill}/{name}"
    for skill in SKILLS
    for name in ("SKILL.md", "assets/icon.svg")
) + tuple(
    f"{folder}/{name}.md"
    for folder in ("agents", ".claude-plugin/agents")
    for name in IDS
) + tuple(
    f"resources/document_standards/{name}-standard.md" for name in (
        "feature-spec", "heilmeier", "implementation-readiness",
        "re-implementation", "zoom-out", "handoff",
    )
)


def build(root: Path, output: Path) -> tuple[Path, Path]:
  """Write a new runtime folder and ZIP; refuse unsafe inputs or overwrites."""
  root = root.resolve()
  folder = output.resolve() / "superegm"
  archive = folder.with_suffix(".zip")
  if any(path.exists() or path.is_symlink() for path in (folder, archive)):
    raise ValueError("Output folder or ZIP already exists")
  if folder == root or root.is_relative_to(folder):
    raise ValueError("Output must not contain the source tree")
  for path in (root / "hooks").rglob("*"):
    if path.is_file() and path.relative_to(root).as_posix() not in HOOK_FILES:
      raise ValueError("hooks/ may hold only hooks.json, run-hook.cmd and session-start")
  files = set()
  for pattern in SHARED:
    for path in root.glob(pattern):
      relative = path.relative_to(root)
      if any((root / Path(*relative.parts[:i])).is_symlink()
             for i in range(1, len(relative.parts) + 1)):
        raise ValueError(f"Symlink in runtime path: {relative}")
      if not path.resolve().is_relative_to(root):
        raise ValueError(f"Path outside source: {relative}")
      if path.is_file():
        files.add(relative)
  for name in REQUIRED_SHARED:
    if Path(name) not in files:
      raise ValueError(f"Missing required file: {name}")
  manifest = json.loads((root / MANIFEST).read_text())
  portable = json.loads((root / "plugin.json").read_text())
  if manifest.get("hooks") or portable.get("hooks"):
    raise ValueError("Directory packages cannot contain hooks")
  for metadata in (manifest, portable):
    if any(metadata.get(key) for key in ("mcpServers", "mcp", "apps")):
      raise ValueError("This runtime builder does not package MCP or app dependencies")
  agents = manifest.get("agents", [])
  if not isinstance(agents, (str, list)):
    raise ValueError(f"Invalid manifest agents: {agents!r}")
  references = [agents] if isinstance(agents, str) else list(agents)
  references.append(manifest.get("icon", "./.claude-plugin/icon.png"))
  for reference in references:
    path = Path(reference)
    if path.is_absolute() or ".." in path.parts or path not in files:
      raise ValueError(f"Unbundled manifest reference: {reference}")
  output.mkdir(parents=True, exist_ok=True)
  folder.mkdir()
  with tempfile.TemporaryDirectory(prefix=".superegm-", dir=output) as temporary:
    staged = Path(temporary) / archive.name
    with zipfile.ZipFile(staged, "x", zipfile.ZIP_DEFLATED) as bundle:
      for relative in sorted(files):
        data = (root / relative).read_bytes()
        destination = folder / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(data)
        destination.chmod(0o644)
        info = zipfile.ZipInfo(relative.as_posix(), (1980, 1, 1, 0, 0, 0))
        info.create_system = 3
        info.external_attr = 0o100644 << 16
        info.compress_type = zipfile.ZIP_DEFLATED
        bundle.writestr(info, data)
    # Windows exclusive file creation can follow a dangling symlink. Linking
    # the completed ZIP claims the final directory entry without following it.
    archive.hardlink_to(staged)
  return folder, archive


if __name__ == "__main__":
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--output", required=True, type=Path)
  args = parser.parse_args()
  runtime, bundle = build(Path(__file__).resolve().parents[1], args.output)
  print(f"Runtime: {runtime}\nZIP: {bundle}")
