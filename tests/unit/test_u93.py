# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the tests of U93, cleanup is automatic.

"""U93 (spec section 7.1): `clean` removes only registered review worktrees, kills a worktree's leftover
`node` and `python*` processes first, keeps round records, and `clean --auto` cleans every landed, merged or
stopped unit at the end of each wave and integrate invocation."""

import json, signal, subprocess
from pathlib import Path
import pytest
from test_builders import seed, put, launched, spawn_fake, no_graphify, which  # noqa: F401  the fixtures a seeded store runs under

ROOT = Path(__file__).resolve().parents[2]
UNIT = "U01"


def git(*args, cwd):
  return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True).stdout.strip()


def journal_text(s):
  return s.path("journal").read_text(encoding="utf-8") if s.path("journal").is_file() else ""


def clean_card(world, skill="clean", artifact=UNIT):
  return world.open_card(skill, artifact)


def read(path):
  return (ROOT / path).read_text(encoding="utf-8")


@pytest.mark.parametrize("layout, removed, printed", [
  ("review/U01/pr7/worktree registered, dirty", "review/U01/pr7/worktree", None),
  ("review/U01/pr7 registered (legacy)", "review/U01/pr7", None),
  ("review/U01/pr7 not registered", None, "kept {store}/review/U01/pr7: not a worktree"),
])
def test_clean_removes_the_registered_review_worktree(world, layout, removed, printed):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  pr = s.path("review", UNIT, "pr7")
  repo = world.repo
  git("update-ref", "refs/superegm/pr/7", "HEAD", cwd=repo)
  git("update-ref", "refs/superegm/pr-base/7", "HEAD", cwd=repo)
  if layout.startswith("review/U01/pr7/worktree"):
    git("worktree", "add", "-q", "--detach", str(pr / "worktree"), "HEAD", cwd=repo)
    (pr / "worktree" / "scratch.txt").write_text("unsaved\n", encoding="utf-8")
  elif layout.endswith("(legacy)"):
    pr.parent.mkdir(parents=True, exist_ok=True)
    git("worktree", "add", "-q", "--detach", str(pr), "HEAD", cwd=repo)
  for record in ("r1", "r2"):
    if not layout.endswith("(legacy)"):
      (pr / record).mkdir(parents=True, exist_ok=True)
      (pr / record / "round.json").write_text("{}\n", encoding="utf-8")
  result = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  code, out = result
  assert code == 0, out
  base = pr.parent.parent.parent  # the handoff's store directory, the parent of `review/`
  assert removed is None or not (base / removed).exists()
  assert layout.endswith("(legacy)") or (pr / "r1").is_dir() and (pr / "r2").is_dir()
  if printed:
    assert printed.format(store=base) in out
  assert git("for-each-ref", "refs/superegm/pr/7", "refs/superegm/pr-base/7", cwd=repo) == "" or printed
  assert "/review/" not in git("worktree", "list", "--porcelain", cwd=repo) or printed  # no review worktree stays registered


class Procs:
  """The process table and the signals `clean` sends: the `node` pid 4242 ignores SIGTERM, and dies of SIGKILL unless `survives`."""

  def __init__(self, tree, survives):
    elsewhere = str(tree) + "-sibling"  # a sibling whose path merely starts with the worktree's: never inside it
    self.table = {4242: ("node", str(tree / "web")), 4243: ("python3.11", str(tree)), 4244: ("node", elsewhere),
                  4245: ("vim", str(tree)), 4246: ("node", str(tree.parent))}
    self.survives, self.signals = survives, []

  def listing(self):
    return [(pid, command, cwd) for pid, (command, cwd) in self.table.items()]

  def send(self, pid, sig):
    self.signals.append((pid, sig))
    if pid in self.table and (sig == signal.SIGKILL or pid != 4242) and not (pid == 4242 and self.survives):
      del self.table[pid]

  def alive(self, pid):
    return pid in self.table


@pytest.mark.parametrize("where", ["worktrees/U01/r2", "review/U01/pr7/worktree"])
@pytest.mark.parametrize("survives, kept", [(False, False), (True, True)])
def test_clean_kills_leftover_processes(world, monkeypatch, where, survives, kept):
  import superegm.clean as clean_module
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  launched(s, UNIT, "exited 0", rnd=2)
  base = s.path("review", UNIT, "pr7").parent.parent.parent
  tree = base / where
  tree.parent.mkdir(parents=True, exist_ok=True)
  git("worktree", "add", "-q", "--detach", str(tree), "HEAD", cwd=world.repo)
  (tree / "scratch.txt").write_text("unsaved\n", encoding="utf-8")
  procs = Procs(tree.resolve(), survives)
  monkeypatch.setattr(clean_module, "process_table", procs.listing)
  monkeypatch.setattr(clean_module, "signal_process", procs.send)
  monkeypatch.setattr(clean_module, "is_alive", procs.alive)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  assert "U01 killed 4243 python3.11" in journal_text(s)
  assert ("U01 killed 4242 node" in journal_text(s)) is not survives
  assert [sig for pid, sig in procs.signals if pid == 4242] == [signal.SIGTERM, signal.SIGKILL]  # SIGTERM, 5 s, SIGKILL
  assert sum(world.sleeps) >= 5
  assert {pid for pid, _sig in procs.signals} == {4242, 4243}  # a sibling path, a `vim` and the parent's `node` are left alone
  assert tree.exists() is kept
  assert ("4242" in out and "node" in out and f"kept {tree}" in out) is survives


def saved(s, **changes):
  """Merge `changes` into the handoff's state: `units.U01`, `status.units.U01` (the saved view) or both."""
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["units"][UNIT].update(changes.get("record", {}))
  state["status"] = {"ready": [], "units": {UNIT: changes.get("view", {})}}
  put(s.path("state"), json.dumps(state))


@pytest.mark.parametrize("skill", ["wave", "integrate"])
@pytest.mark.parametrize("unit, cleaned", [
  ("landed", True), ("merged_at set, issue open", True), ("stopped", True),
  ("live launch", False), ("active", False),
])
def test_clean_auto_cleans_terminal_units(world, skill, unit, cleaned):
  s, card, _hid, _bodies = seed(world, units=(UNIT,))
  launch = {"launched": {"at": "2026-11-03T00:00:00Z", "runcard": card, "by": "owner"}}
  view = {"pr": 70, "head": "a" * 40, "ci": "pass", "landed": False}
  launched(s, UNIT, "running" if unit == "live launch" else "exited 0")
  tree = s.path("worktrees", UNIT, "r1")
  tree.parent.mkdir(parents=True, exist_ok=True)
  git("worktree", "add", "-q", "--detach", str(tree), "HEAD", cwd=world.repo)
  if unit in ("landed", "live launch"):
    view = {**view, "ci": None}  # a merged view: `pr` set, `ci` null; the live launch keeps it from being cleaned
  elif unit == "merged_at set, issue open":
    launch["pr"] = {"number": 70, "head": "a" * 40, "merged_at": "2026-11-03T01:00:00Z"}  # the view still reads its CI
  elif unit == "stopped":
    view = {"pr": None, "head": None, "ci": None, "landed": False}
    put(s.path("foreman", UNIT), json.dumps({"dispatch_id": "d1", "rounds": [], "decisions": [], "rulings": [],
                                             "stopped": {"by": "owner", "reason": "given up", "brief": None}}))
  elif unit == "active":
    view = {**view, "ci": "pending"}
  saved(s, record=launch, view=view)
  artifact = json.loads(s.path("runcards", card).read_text(encoding="utf-8"))["artifact"]
  auto_card = card if skill == "wave" else world.open_card("integrate", artifact)
  code, out = world.run("clean", "--auto", "--runcard", auto_card)
  assert code == 0, out
  assert tree.exists() is not cleaned
  assert (s.path("worktrees", UNIT)).exists() is not cleaned
  assert (f"{UNIT} cleaned" in out) is cleaned
  assert (f"{UNIT} cleaned" in journal_text(s)) is cleaned


@pytest.mark.parametrize("path", ["skills/wave/SKILL.md", "skills/integrate/SKILL.md"])
def test_skills_run_clean_auto(path):
  # wave: at the end of each invocation after its last launch; integrate: after its filing
  text = read(path)
  assert "clean --auto" in text
  assert len(text.split("---", 2)[2].encode("utf-8")) <= 24000  # the skill body limit
