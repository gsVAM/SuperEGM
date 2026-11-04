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


def test_map_text_on_the_fixture_tree():
  from superegm import orient
  text = orient.map_text(TREE, None, T, "not installed")
  assert text == (f"orient: tree {T} · graphify: not installed · trimmed: nothing\n## Map\n"
                  ". | 10 files | .py | - | README.md: Demo; CLAUDE.md: Rules\n"
                  "notes | 1 files | .txt | - | -\n"
                  "src | 4 files | .py | __init__.py | AGENTS.md: src\n"
                  "tests | 2 files | .py | - | -\n"
                  "web | 1 files | .ts | index.ts | -\n")


GRAPH = ROOT / "tests/fixtures/orient/graph.json"


def test_graph_projection_on_the_fixture_graph():
  from superegm import orient
  graph = json.loads(GRAPH.read_text(encoding="utf-8"))
  unit = orient.unit_text(TREE, [("src/worker.py", "modify"), ("lib/x.py", "create")], graph, T, "a" * 64)
  assert unit.startswith(f"orient: tree {T} · graphify: {'a' * 64} · trimmed: nothing\n")
  assert ("## Graph: src/worker.py\nnode work (src/worker.py:L6) community 0\nnode Worker (src/worker.py:L15) community 0\nnode worker.py (src/worker.py) community 0\n"
          "edge calls Worker (src/worker.py:L15) -> work (src/worker.py:L6)\nedge calls enqueue (src/queue.py:L3) -> work (src/worker.py:L6)\n"
          "other INFERRED 0.5 uses work (src/worker.py:L6) -> render (web/index.ts:L1)\n"
          "other AMBIGUOUS 0.2 calls test_work (tests/check_worker.py:L1) -> work (src/worker.py:L6)\n## Graph: lib/x.py\nnone\n## Read first\n") in unit
  assert unit.index("## Graph: src/worker.py") > unit.index("## lib/x.py (create)")
  head = orient.map_text(TREE, graph, T, "a" * 64).split("## Map\n")[0]
  assert head.endswith("## Graph\nnodes 6 · edges 4 · communities 2 · extracted 2/4\n"
                       "community 0: 4 nodes · src/worker.py, tests/check_worker.py\ncommunity 1: 2 nodes · src/queue.py, web/index.ts\n")
