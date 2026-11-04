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


@pytest.mark.parametrize("case, trimmed", [
  ("docs", "tests, read-first"),
  ("signatures", "tests, read-first, graph-outside, graph-inside, graph-nodes, signatures:src/worker.py"),
  ("map-depth", "depth 1"),
])
def test_trimming_sequence(tmp_path, case, trimmed):
  from superegm import orient
  tree = tmp_path / "tree"
  if case == "map-depth":
    for i in range(600):
      (tree / f"d{i:03d}/e/f/g").mkdir(parents=True); (tree / f"d{i:03d}/e/f/g/x.py").write_text("x = 1\n", encoding="utf-8")
    text = orient.map_text(tree, None, T, "not installed")
    assert len(text.splitlines()) == 603 and "d000/e" not in text
  else:
    shutil.copytree(TREE, tree)
    graph = json.loads(GRAPH.read_text(encoding="utf-8"))
    if case == "docs":
      (tree / "CLAUDE.md").write_text("## src/worker.py\n\n" + "x " * 9_000 + "\n", encoding="utf-8")
    else:
      (tree / "src/worker.py").write_text("".join(f"def f{i}(): pass\n" for i in range(2_000)), encoding="utf-8")
    text = orient.unit_text(tree, [("src/worker.py", "modify"), ("src/queue.py", "modify")], None if case == "docs" else graph, T, "not installed")
    assert "## Read first" not in text and "tests:" not in text and "## src/worker.py (modify)" in text
    assert "def f1999(): pass" not in text and ("def work(job: str) -> int:" in text) == (case == "docs") and "def enqueue(job: str) -> None:" in text
  cap = 24_576 if case == "map-depth" else 16_384
  assert len(text.encode("utf-8")) <= cap and text.splitlines()[0].endswith(f" · trimmed: {trimmed}")


def test_export_tree_is_the_tracked_files_at_the_ref(world):
  import superegm
  from superegm import orient, store
  st = store(world.repo)
  (world.repo / ".gitignore").write_text("ignored.py\n", encoding="utf-8"); os.symlink("docs", world.repo / "link")
  git(["add", ".gitignore", "link"], world.repo); git(["commit", "-qm", "link"], world.repo)
  (world.repo / "untracked.py").write_text("x\n", encoding="utf-8"); (world.repo / "ignored.py").write_text("x\n", encoding="utf-8")
  (world.repo / "docs/designs/sample.md").write_text("edited\n", encoding="utf-8")
  export = st.path("orient", "export")
  assert orient.export_tree(world.repo, "HEAD", st) == git(["rev-parse", "HEAD^{tree}"], world.repo).strip()
  assert sorted(p.relative_to(export).as_posix() for p in export.rglob("*") if p.is_file()) == [".gitignore", ".superegm/config.json", "docs/designs/sample.md"]
  assert (export / "docs/designs/sample.md").read_text(encoding="utf-8") == DESIGN and not (export / "link").exists()
  (export / "stale.txt").write_text("x\n", encoding="utf-8")
  assert orient.export_tree(world.repo, "HEAD~1", st) == git(["rev-parse", "HEAD~1^{tree}"], world.repo).strip()
  assert not (export / "stale.txt").exists() and not (export / ".gitignore").exists() and not st.path("orient", "export.tar").exists()
  with pytest.raises(superegm.HandoffError, match="orient: ref nope is not in this repository"):
    orient.export_tree(world.repo, "nope", st)


@pytest.mark.parametrize("case, token", [
  ("absent", "not installed"),
  ("ok", hashlib.sha256(GRAPH.read_bytes()).hexdigest()),
  ("fails", "failed: boom: no graph"),
  ("exit", "failed: exit 3"),
  ("silent", "failed: no graph.json written"),
  ("not-json", "failed: graph.json is not JSON"),
  ("timeout", "failed: timeout"),
])
def test_build_graph_absent_present_failing_timeout(tmp_path, monkeypatch, case, token):
  from superegm import orient
  export, out, log = tmp_path / "export", tmp_path / "graphify-out", tmp_path / "log"
  export.mkdir(); out.mkdir(); (out / "graph.json").write_text("stale\n", encoding="utf-8")
  fake = tmp_path / "graphify"
  fake.write_text(f"#!/bin/sh\necho \"$* $GRAPHIFY_OUT\" > '{log}'\n" + {
    "ok": f"mkdir -p \"$GRAPHIFY_OUT\" && cp '{GRAPH}' \"$GRAPHIFY_OUT/graph.json\"\n",
    "fails": "echo 'warning: x' >&2; echo 'boom: no graph' >&2; exit 1\n", "exit": "exit 3\n",
    "silent": "exit 0\n", "not-json": "echo '{' > \"$GRAPHIFY_OUT/graph.json\"\n", "timeout": "sleep 5\n"}.get(case, ""), encoding="utf-8")
  fake.chmod(0o755)
  monkeypatch.setattr(orient, "GRAPHIFY", "superegm-no-such-tool" if case == "absent" else str(fake))
  monkeypatch.setattr(orient, "TIMEOUT", 1 if case == "timeout" else 600)
  graph, got = orient.build_graph(export, out)
  assert got == token and (graph is None) == (case != "ok") and (out / "graph.json").exists() == (case in ("ok", "not-json"))
  assert (not log.exists()) if case == "absent" else log.read_text(encoding="utf-8").strip() == f"update {export.resolve()} {out}"


@pytest.fixture
def no_graphify(monkeypatch):
  from superegm import orient
  monkeypatch.setattr(orient, "GRAPHIFY", "superegm-no-such-tool")


def test_orient_writes_the_map_and_every_unfiled_unit(world, no_graphify):
  from superegm import store
  st, card = store(world.repo), world.card("plan")
  first = lambda ref: f"orient: tree {git(['rev-parse', ref + '^{tree}'], world.repo).strip()} · graphify: not installed · trimmed: nothing"
  line = lambda p: f"{p} {p.stat().st_size}"
  code, out = world.run("orient", "--spec", world.spec, "--runcard", card)
  assert code == 0 and out.splitlines() == [line(st.path("orient", "map.md"))], out
  text = st.path("orient", "map.md").read_text(encoding="utf-8")
  assert text.splitlines()[0] == first("HEAD") and ". | 2 files | .json | - | -" in text and not list(st.root.glob("*/orient"))
  assert world.run("graph", "--plan", world.plan)[0] == 0
  st = store(world.repo)
  code, out = world.run("orient", "--spec", world.spec, "--runcard", card)
  files = [st.path("orient", "map.md")] + [st.path("orient_unit", f"{u}.md") for u in ("U01", "U02", "U03")]
  assert code == 0 and out.splitlines() == [line(p) for p in files], out
  u02 = st.path("orient_unit", "U02.md").read_text(encoding="utf-8")
  assert u02.startswith(first("HEAD") + "\n## src/webhooks/deliver.ts (create)\nsiblings: none\ntests: none\n") and "## Read first" not in u02
  assert "## src/webhooks/queue.ts (modify)\nsiblings: none\ntests: none\n" in u02 and "## Graph" not in u02
  (world.repo / "README.md").write_text("# Hooks\n", encoding="utf-8"); git(["add", "README.md"], world.repo); git(["commit", "-qm", "readme"], world.repo)
  code, out = world.run("orient", "--spec", world.spec, "--unit", "U02", "--ref", "HEAD~1", "--runcard", card)
  assert code == 0 and out.splitlines() == [line(st.path("orient_unit", "U02.md"))], out
  assert st.path("orient_unit", "U02.md").read_text(encoding="utf-8") == u02 and "README.md" not in st.path("orient", "map.md").read_text(encoding="utf-8")
  assert world.run("orient", "--spec", world.spec, "--runcard", world.card("review-plan"))[0] == 0
  assert "README.md: Hooks" in st.path("orient", "map.md").read_text(encoding="utf-8") and st.path("orient_unit", "U02.md").read_text(encoding="utf-8").splitlines()[0] == first("HEAD")
