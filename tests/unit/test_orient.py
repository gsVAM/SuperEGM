# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the orient subcommand's tests (spec section 9.3).

"""Orient: the store kinds, the names rule, the extractor on the fixture tree, the projection on
the fixture graph, the trimming sequence, the export, the graphify build against a fake CLI, the
subcommand's lines and refusals, and the callers' texts. No test runs graphify."""

import hashlib, json, os, shutil
from pathlib import Path
import pytest
from conftest import DESIGN, git

ROOT = Path(__file__).resolve().parents[2]


def test_store_orient_kinds(world):
  import superegm
  root = world.artifacts
  a = superegm.Store(root, handoff_id="sample-111111")
  assert a.path("orient", "map.md") == root / "orient/map.md" and a.path("orient", "export") == root / "orient/export"
  assert superegm.Store(root).path("orient", "graphify-out") == root / "orient/graphify-out"
  assert a.path("orient_unit", "U12.md") == root / "111111/orient/U12.md"
  assert a.kind_of(root / "orient/map.md") == "orient" and a.kind_of(root / "orient/export/x.py") == "orient"
  assert a.kind_of(root / "111111/orient/U12.md") == "orient_unit"
  with pytest.raises(superegm.HandoffError, match="no handoff in this store"):
    superegm.Store(root).path("orient_unit", "U12.md")


@pytest.mark.parametrize("path, tokens", [
  ("src/worker.py", ["src/worker.py", "worker.py", "src", "src.worker"]),
  ("skills/plan/scripts/superegm/__init__.py", ["skills/plan/scripts/superegm/__init__.py", "__init__.py", "skills/plan/scripts/superegm", "superegm"]),
  ("web/index.ts", ["web/index.ts", "index.ts", "web"]),
  ("tests/fixtures/orient/", ["tests/fixtures/orient", "orient", "tests/fixtures"]),
  ("setup.py", ["setup.py", "setup"]),
])
def test_names_rule(path, tokens):
  from superegm import orient
  assert orient.names(path) == tokens


TREE = ROOT / "tests/fixtures/orient/tree"
T = "t" * 40


@pytest.mark.parametrize("scope, expected", [
  ([("src/worker.py", "modify")], "## src/worker.py (modify)\nThe worker.\ndef work(job: str) -> int:\nclass Worker:\n  def run(self) -> None:\ntests: tests/check_worker.py\n"),
  ([("src/worker.py", "modify")], "## Read first\n### README.md · src/worker.py\nThe worker, read first.\n### CLAUDE.md · src\nThe src package holds the worker.\n### src/AGENTS.md · src\nThe src package.\n### src/AGENTS.md · worker.py\nStart with worker.py.\n"),
  ([("src/new.py", "create")], "## src/new.py (create)\nsiblings: src/__init__.py, src/queue.py, src/worker.py\n### src/__init__.py\n### src/queue.py\ndef enqueue(job: str) -> None:\n### src/worker.py\ndef work(job: str) -> int:\nclass Worker:\n  def run(self) -> None:\ntests: none\n"),
  ([("lib/x.py", "create")], "## lib/x.py (create)\nsiblings: none\ntests: none\n"),
  ([("web/index.ts", "modify")], "## web/index.ts (modify)\nexport function render(): void {}\nexport class View {}\ntests: none\n"),
  ([("notes/plain.txt", "modify")], "## notes/plain.txt (modify)\n" + "".join(f"line {i}\n" for i in range(1, 41)) + "tests: none\n"),
  ([("src/", "modify")], "## src/AGENTS.md (modify)\n"),
])
def test_unit_text_on_the_fixture_tree(scope, expected):
  from superegm import orient
  text = orient.unit_text(TREE, scope, None, T, "not installed")
  assert text.startswith(f"orient: tree {T} · graphify: not installed · trimmed: nothing\n")
  assert expected in text and "## Graph" not in text and "_hidden" not in text
  if expected.startswith("## Read first"):
    assert text.endswith(expected) and text.count("Start with worker.py.") == 1
  if scope[0][0] == "web/index.ts":
    assert "## Read first" not in text
  if scope[0][0] == "src/":
    assert [l for l in text.splitlines() if l.startswith("## ")] == ["## src/AGENTS.md (modify)", "## src/__init__.py (modify)", "## src/queue.py (modify)", "## src/worker.py (modify)", "## Read first"]
  assert text == orient.unit_text(TREE, scope, None, T, "not installed")
