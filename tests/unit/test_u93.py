# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the tests of U93, cleanup is automatic; U111's re-pin of the two kill tests on an
# unchanged `ps` start time (1.3 design section 3.10).

"""U93 (spec section 7.1): `clean` removes only registered review worktrees, kills a worktree's leftover
`node` and `python*` processes first, keeps round records, and `clean --auto` cleans every landed, merged or
stopped unit at the end of each wave and integrate invocation."""

import json, os, signal, subprocess
from pathlib import Path
import pytest
import superegm as core
import superegm.clean as clean_module
from test_builders import seed, put, launched, spawn_fake, no_graphify, which  # noqa: F401  the fixtures a seeded store runs under

ROOT = Path(__file__).resolve().parents[2]
UNIT = "U01"
REAL_PROCESS_TABLE = clean_module.process_table


@pytest.fixture(autouse=True)
def no_processes(monkeypatch):
  """No test here reads the machine's processes: the table is empty unless a test sets its own."""
  monkeypatch.setattr(clean_module, "process_table", lambda: [])


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
    assert f"{UNIT} cleaned" in out and f"{UNIT} cleaned" in journal_text(s)  # the run went on after the kept line
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

  def start(self, pid):
    """`ps -o lstart= -p <pid>`: one start time per process, unchanged while it lives (U111)."""
    return "Tue Nov 25 10:00:00 2026" if pid in self.table else None


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
  monkeypatch.setattr(clean_module, "start_time", procs.start)  # an unchanged `ps` start time (U111)
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


def section(text, heading):
  start = text.index(heading)
  stops = [i for i in (text.find("\n## ", start + 1), text.find("\n ## ", start + 1)) if i != -1]
  return text[start:min(stops)] if stops else text[start:]


@pytest.mark.parametrize("path, headings, words", [
  ("skills/wave/SKILL.md", ["## The end", "## Retries"], ["after its last launch", "never refuses"]),
  ("skills/integrate/SKILL.md", ["## Step 4: the end"], ["respec", "stalled", "listed", "never refuses"]),
])
def test_skills_run_clean_auto(path, headings, words):
  # wave: at the end of each invocation after its last launch (the retries path included); integrate: on every path to Step 4
  text = read(path)
  assert "clean --auto" in text
  for heading in headings:
    assert "clean --auto" in section(text, heading), heading
  end = section(text, headings[0])
  for word in words:
    assert word in end, word
  assert len(text.split("---", 2)[2].encode("utf-8")) <= 24000  # the skill body limit


def test_wave_skill_keeps_the_wording_u93_trimmed():
  text = read("skills/wave/SKILL.md")
  for kept in ("(zero-context, read-only, each via its own adapter), records the",
               "`status.wait_events` acked every event, so an early exit loses another unit's exit.",
               "Every `status` pass under this card rewrites the board",
               "one GitHub write per pass and none when the rows are unchanged"):
    assert kept in text, kept
  assert len(text.encode("utf-8")) < 15000


def test_clean_skill_describes_what_clean_does():
  text = read("skills/clean/SKILL.md")
  for said in ("pr<n>/worktree", "kept <path>: not a worktree", "kept <path>: uncommitted changes", "kept <path>: symlink",
               "cannot list its processes", "cannot be signalled", "SIGTERM", "SIGKILL", "<unit> killed <pid> <command>",
               "--auto", "`wave` or `integrate` card", "lsof +c 0 -a -d cwd -Fpcn", "on this unit", "without regard to case",
               "never signalled", "`worktrees/<unit>/` folder", "git's error"):
    assert said in text, said
  assert "resolves outside the store" not in text and "-d cwd -Fn`" not in text
  assert "refuses the whole run" not in text and "removes nothing" not in text


def landed(world, s, card):
  """U01 as `status` saves a landed unit: a merged view (`pr` set, `ci` null) and one terminal launch."""
  launched(s, UNIT, "exited 0")
  saved(s, record={"launched": {"at": "2026-11-03T00:00:00Z", "runcard": card, "by": "owner"}},
        view={"pr": 70, "head": "a" * 40, "ci": None, "landed": False})
  return json.loads(s.path("runcards", card).read_text(encoding="utf-8"))["artifact"]


def add_tree(world, path):
  path.parent.mkdir(parents=True, exist_ok=True)
  git("worktree", "add", "-q", "--detach", str(path), "HEAD", cwd=world.repo)


def test_clean_keeps_a_review_link_that_resolves_outside_the_store(world, monkeypatch):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  link = s.path("review", UNIT, "pr7", "worktree")
  link.parent.mkdir(parents=True, exist_ok=True)
  link.symlink_to(world.repo)  # the owner's own checkout, which git has registered
  procs = Procs(world.repo.resolve(), False)
  monkeypatch.setattr(clean_module, "process_table", procs.listing)
  monkeypatch.setattr(clean_module, "signal_process", procs.send)
  monkeypatch.setattr(clean_module, "is_alive", procs.alive)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  assert f"kept {link}: symlink" in out
  assert procs.signals == [] and world.repo.is_dir() and link.is_symlink()
  assert f"{UNIT} cleaned" not in out


@pytest.mark.parametrize("failure, reason", [("missing", "lsof is missing"), ("exit", "lsof exited 1"), ("timeout", "lsof timed out")])
def test_clean_keeps_a_worktree_when_lsof_fails(world, monkeypatch, failure, reason):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  launched(s, UNIT, "exited 0", rnd=2)
  child, builder = s.path("review", UNIT, "pr7", "worktree"), s.path("worktrees", UNIT, "r2")
  add_tree(world, child)
  add_tree(world, builder)
  git("update-ref", "refs/superegm/pr/7", "HEAD", cwd=world.repo)
  monkeypatch.setattr(clean_module, "process_table", REAL_PROCESS_TABLE)
  real_run = subprocess.run

  def fake_run(argv, *args, **kwargs):
    if argv[0] != "lsof":
      return real_run(argv, *args, **kwargs)
    if failure == "missing":
      raise FileNotFoundError("lsof")
    if failure == "timeout":
      raise subprocess.TimeoutExpired(argv, 60)
    return subprocess.CompletedProcess(argv, 1, "", "lsof: boom")

  monkeypatch.setattr(subprocess, "run", fake_run)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  for tree in (child, builder):
    assert tree.is_dir() and f"kept {tree}: cannot list its processes ({reason})" in out
  assert git("for-each-ref", "refs/superegm/pr/7", cwd=world.repo) != ""  # nothing was removed, so its ref stays
  assert f"{UNIT} cleaned" not in out and f"{UNIT} cleaned" not in journal_text(s)


def test_clean_keeps_a_tree_whose_process_cannot_be_signalled_and_goes_on(world, monkeypatch):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  launched(s, UNIT, "exited 0", rnd=2)
  child, builder = s.path("review", UNIT, "pr7", "worktree"), s.path("worktrees", UNIT, "r2")
  add_tree(world, child)
  add_tree(world, builder)
  procs = Procs(builder.resolve(), False)

  def send(pid, sig):
    if pid == 4242:
      raise PermissionError(1, "Operation not permitted")
    procs.send(pid, sig)

  monkeypatch.setattr(clean_module, "process_table", procs.listing)
  monkeypatch.setattr(clean_module, "signal_process", send)
  monkeypatch.setattr(clean_module, "is_alive", procs.alive)
  monkeypatch.setattr(clean_module, "start_time", procs.start)  # an unchanged `ps` start time (U111)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  assert f"kept {builder}: process 4242 cannot be signalled" in out
  assert builder.is_dir() and not child.exists()  # the sweep went on: the review tree is gone
  assert "U01 killed 4242" not in journal_text(s) and f"{UNIT} cleaned" not in out


def test_clean_keeps_a_dirty_legacy_review_tree_signals_nothing_and_goes_on(world, monkeypatch):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  launched(s, UNIT, "exited 0", rnd=1)
  pr, builder = s.path("review", UNIT, "pr7"), s.path("worktrees", UNIT, "r1")
  add_tree(world, pr)
  add_tree(world, builder)
  (pr / "scratch.txt").write_text("unsaved\n", encoding="utf-8")
  git("update-ref", "refs/superegm/pr/7", "HEAD", cwd=world.repo)
  procs = Procs(pr.resolve(), False)
  monkeypatch.setattr(clean_module, "process_table", procs.listing)
  monkeypatch.setattr(clean_module, "signal_process", procs.send)
  monkeypatch.setattr(clean_module, "is_alive", procs.alive)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  assert f"kept {pr}: uncommitted changes" in out
  assert (pr / "scratch.txt").is_file() and not builder.exists()  # the person's tree stays, the builder's goes
  assert not [pid for pid, _sig in procs.signals if pid in (4242, 4243)]  # nothing was signalled in the kept tree
  assert git("for-each-ref", "refs/superegm/pr/7", cwd=world.repo) != ""
  assert f"{UNIT} cleaned" not in out and f"{UNIT} cleaned" not in journal_text(s)


def test_clean_names_a_recorded_builder_tree_git_does_not_register(world):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  launched(s, UNIT, "exited 0", rnd=1)
  tree = s.path("worktrees", UNIT, "r1")
  tree.mkdir(parents=True)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out  # not the 1.2 abort `is not a working tree`
  assert f"kept {tree}: not a worktree" in out and tree.is_dir()


def test_parse_process_table_reads_pid_command_and_cwd():
  text = "p101\ncnode\nn/a/b\np102\ncPython\nn/c d\np103\ncvim\nn/\n"
  assert clean_module.parse_process_table(text) == [(101, "node", "/a/b"), (102, "Python", "/c d"), (103, "vim", "/")]
  assert clean_module.parse_process_table("") == []


def test_process_table_uses_an_exit_1_listing_that_has_records(monkeypatch):
  text = "p900\ncnode\nn/a\n"
  monkeypatch.setattr(subprocess, "run", lambda argv, *a, **k: subprocess.CompletedProcess(argv, 1, text, "lsof: WARNING: can't stat() fuse"))
  assert REAL_PROCESS_TABLE() == [(900, "node", "/a")]
  monkeypatch.setattr(subprocess, "run", lambda argv, *a, **k: subprocess.CompletedProcess(argv, 1, "", "lsof: boom"))
  with pytest.raises(clean_module.ListError, match="lsof exited 1"):
    REAL_PROCESS_TABLE()


def test_leftovers_asks_lsof_for_cwds_matches_case_blind_and_skips_this_process(monkeypatch, tmp_path):
  tree = tmp_path / "tree"
  tree.mkdir()
  text = "".join(f"p{pid}\nc{command}\nn{cwd}\n" for pid, command, cwd in [
    (os.getpid(), "python3", tree), (os.getppid(), "node", tree), (900, "Python", tree / "x"), (901, "node", f"{tree}-sibling"),
    (902, "nodemon", tree), (903, "python3.11", tree), (904, "NODE", tree), (905, "vim", tree)])
  calls = []
  monkeypatch.setattr(clean_module, "process_table", REAL_PROCESS_TABLE)
  monkeypatch.setattr(subprocess, "run", lambda argv, *a, **k: (calls.append(argv), subprocess.CompletedProcess(argv, 0, text, ""))[1])
  assert clean_module.leftovers(tree) == [(900, "Python"), (903, "python3.11"), (904, "NODE")]
  assert calls[0][0] == "lsof" and "-Fpcn" in calls[0] and calls[0][calls[0].index("-d") + 1] == "cwd"


def test_clean_auto_prints_one_line_per_unit_once(world):
  s, card, _hid, _bodies = seed(world, units=(UNIT,))
  artifact = landed(world, s, card)
  child, builder = s.path("review", UNIT, "pr7", "worktree"), s.path("worktrees", UNIT, "r1")
  add_tree(world, child)
  add_tree(world, builder)
  (s.path("review", UNIT, "pr7") / "r1").mkdir()
  (s.path("review", UNIT, "pr8") / "r1").mkdir(parents=True)  # a folder that holds only round records
  stray = s.path("worktrees", UNIT, "r5")  # no launch records it
  stray.mkdir()
  auto = world.open_card("integrate", artifact)
  code, out = world.run("clean", "--auto", "--runcard", auto)
  assert (code, out) == (0, "U01 cleaned\n")  # no `kept ...: not a worktree` for pr8, no line for the stray r5
  assert not child.exists() and not builder.exists() and stray.is_dir() and (s.path("review", UNIT, "pr8") / "r1").is_dir()
  assert journal_text(s).count(f"{UNIT} cleaned") == 1
  code, out = world.run("clean", "--auto", "--runcard", auto)
  assert (code, out) == (0, "")
  assert journal_text(s).count(f"{UNIT} cleaned") == 1


def test_clean_auto_prints_a_warning_it_cannot_resolve(world, monkeypatch):
  s, card, _hid, _bodies = seed(world, units=(UNIT,))
  artifact = landed(world, s, card)
  link = s.path("review", UNIT, "pr7", "worktree")
  link.parent.mkdir(parents=True, exist_ok=True)
  link.symlink_to(world.repo)
  code, out = world.run("clean", "--auto", "--runcard", world.open_card("integrate", artifact))
  assert code == 0 and f"kept {link}: symlink" in out and f"{UNIT} cleaned" not in out


def test_clean_auto_never_exits_non_zero(world, monkeypatch):
  s, card, _hid, _bodies = seed(world, units=(UNIT,))
  artifact = landed(world, s, card)
  auto = world.open_card("integrate", artifact)

  def boom(*args, **kwargs):
    raise RuntimeError("boom")

  monkeypatch.setattr(clean_module, "has_remnants", boom)
  assert world.run("clean", "--auto", "--runcard", auto) == (0, "clean --auto: U01: boom\n")
  monkeypatch.setattr(core, "locate", boom)
  assert world.run("clean", "--auto", "--runcard", auto) == (0, "clean --auto: handoff: boom\n")


def test_clean_auto_and_unit_are_exclusive(world):
  s, card, _hid, _bodies = seed(world, units=(UNIT,))
  with pytest.raises(SystemExit) as stop:
    world.run("clean", "--auto", "--unit", UNIT, "--runcard", card)
  assert stop.value.code != 0


def test_clean_auto_refuses_nothing_under_a_refused_card(world):
  seed(world, units=(UNIT,))
  code, out = world.run("clean", "--auto", "--runcard", clean_card(world))  # a clean card on the unit, not the handoff's spec
  assert code == 0 and out.startswith("clean: runcard:") and out.count("\n") == 1
  code, out = world.run("clean", "--auto", "--runcard", "no-such-card")
  assert code == 0 and out.startswith("clean: runcard:")


@pytest.mark.parametrize("where", ["review", "worktrees"])
def test_clean_keeps_a_unit_folder_that_is_a_symlink_to_another_units(world, monkeypatch, where):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  other = s.path("review", "U02", "pr7", "worktree") if where == "review" else s.path("worktrees", "U02", "r1")
  add_tree(world, other)
  folder = (lambda unit: s.path("review", unit, "pr0").parent) if where == "review" else (lambda unit: s.path("worktrees", unit))
  folder(UNIT).symlink_to(folder("U02"))
  procs = Procs(other.resolve(), False)
  monkeypatch.setattr(clean_module, "process_table", procs.listing)
  monkeypatch.setattr(clean_module, "signal_process", procs.send)
  monkeypatch.setattr(clean_module, "is_alive", procs.alive)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  assert f"kept {folder(UNIT)}: symlink" in out  # the linked unit folder itself, named once
  assert procs.signals == [] and other.is_dir()  # the other unit's tree and processes are untouched
  assert f"{UNIT} cleaned" not in out and f"{UNIT} cleaned" not in journal_text(s)


@pytest.mark.parametrize("builder", [True, False])
def test_clean_auto_deletes_a_terminal_units_refs_whether_or_not_a_review_tree_existed(world, builder):
  s, card, _hid, _bodies = seed(world, units=(UNIT,))
  launched(s, UNIT, "exited 0")
  saved(s, record={"launched": {"at": "2026-11-03T00:00:00Z", "runcard": card, "by": "owner"},
                   "pr": {"number": 70, "head": "a" * 40, "merged_at": "2026-11-03T01:00:00Z"}},
        view={"pr": 70, "head": "a" * 40, "ci": "pass", "landed": False})
  if builder:
    add_tree(world, s.path("worktrees", UNIT, "r1"))
  for ref in ("refs/superegm/pr/70", "refs/superegm/pr-base/70"):
    git("update-ref", ref, "HEAD", cwd=world.repo)
  artifact = json.loads(s.path("runcards", card).read_text(encoding="utf-8"))["artifact"]
  auto = world.open_card("integrate", artifact)
  assert world.run("clean", "--auto", "--runcard", auto) == (0, "U01 cleaned\n")
  assert git("for-each-ref", "refs/superegm/pr/70", "refs/superegm/pr-base/70", cwd=world.repo) == ""
  assert world.run("clean", "--auto", "--runcard", auto) == (0, "")
  assert journal_text(s).count(f"{UNIT} cleaned") == 1


def test_clean_prints_git_s_error_when_a_forced_removal_fails_and_keeps_the_refs(world):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  child = s.path("review", UNIT, "pr7", "worktree")
  add_tree(world, child)
  git("worktree", "lock", str(child), cwd=world.repo)
  git("update-ref", "refs/superegm/pr/7", "HEAD", cwd=world.repo)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  line = next(l for l in out.splitlines() if l.startswith(f"kept {child}: "))
  assert "locked" in line and "uncommitted changes" not in out and child.is_dir()  # git's reason, first line
  assert git("for-each-ref", "refs/superegm/pr/7", cwd=world.repo) != "" and f"{UNIT} cleaned" not in out


def test_clean_goes_on_when_one_builder_tree_fails_removal(world):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  launched(s, UNIT, "exited 0", rnd=1)
  one = json.loads(s.path("launches", UNIT).read_text(encoding="utf-8"))["launches"]
  launched(s, UNIT, "exited 0", rnd=2)
  both = one + json.loads(s.path("launches", UNIT).read_text(encoding="utf-8"))["launches"]  # one file holds both launches
  put(s.path("launches", UNIT), json.dumps({"launches": both}))
  first, second = s.path("worktrees", UNIT, "r1"), s.path("worktrees", UNIT, "r2")
  add_tree(world, first)
  add_tree(world, second)
  git("worktree", "lock", str(first), cwd=world.repo)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  assert f"kept {first}: " in out and "locked" in out and first.is_dir()
  assert not second.exists()  # the next tree was removed, not skipped by a raise
  assert f"{UNIT} cleaned" not in out and f"{UNIT} cleaned" not in journal_text(s)


def test_resume_notes_hold_one_copy_of_the_loop_ended_sentence():
  notes = read("skills/wave/references/resume_notes.md")
  assert "`loop_ended`" not in notes.split("-->", 1)[1]  # the body; the header names the sentence that stayed
  assert "`loop_ended`" in read("skills/wave/SKILL.md")
  assert "stays in SKILL.md" in notes.split("-->", 1)[0]  # the header says what stayed


def test_clean_auto_exits_0_on_an_unparseable_card_or_config(world):
  s, card, _hid, _bodies = seed(world, units=(UNIT,))
  artifact = landed(world, s, card)
  auto = world.open_card("integrate", artifact)
  config = world.repo / ".superegm" / "config.json"
  good_config = config.read_text(encoding="utf-8")
  card_file = s.path("runcards", auto)
  good_card = card_file.read_text(encoding="utf-8")
  card_file.write_text("{ not json", encoding="utf-8")
  code, out = world.run("clean", "--auto", "--runcard", auto)
  assert code == 0 and out.startswith("clean: ") and out.count("\n") == 1, out
  with pytest.raises(ValueError):  # `--unit` keeps today's behaviour: the unparseable card is an error
    world.run("clean", "--unit", UNIT, "--runcard", auto)
  card_file.write_text(good_card, encoding="utf-8")
  config.write_text("{ not json", encoding="utf-8")
  code, out = world.run("clean", "--auto", "--runcard", auto)
  assert code == 0 and out.startswith("clean: ") and out.count("\n") == 1, out
  config.write_text(good_config, encoding="utf-8")


def test_wave_and_integrate_say_clean_auto_runs_at_the_end_and_what_it_cleans():
  wave, integrate = read("skills/wave/SKILL.md"), read("skills/integrate/SKILL.md")
  said = "every landed, merged or stopped unit that has something left to remove"
  assert "(a paused one included)" not in wave  # no step leads to a paused launch; a batch that stops at step 7 does not run it
  assert said in section(wave, "## The end") and said in section(integrate, "## Step 4: the end")
  assert "every landed, merged or stopped unit, prints" not in wave + integrate


def test_clean_skill_names_the_survivor_line_and_which_builder_trees_count():
  text = read("skills/clean/SKILL.md")
  assert "kept <path>: <command> <pid> survives SIGKILL" in text
  assert "only when a launch records it and git registers it" in text


def test_clean_leaves_a_folder_that_is_not_pr_digits_alone(world, monkeypatch):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  other = s.path("review", UNIT, "private", "worktree")
  add_tree(world, other)
  procs = Procs(other.resolve(), False)
  monkeypatch.setattr(clean_module, "process_table", procs.listing)
  monkeypatch.setattr(clean_module, "signal_process", procs.send)
  monkeypatch.setattr(clean_module, "is_alive", procs.alive)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  assert other.is_dir() and procs.signals == []  # neither signalled nor removed
  assert "private" not in out


def test_clean_keeps_a_symlinked_unit_folder_and_deletes_no_ref_through_it(world):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  (s.path("review", "U02", "pr7") / "r1").mkdir(parents=True)  # round records only: no registered tree
  folder = s.path("review", UNIT, "pr0").parent
  folder.symlink_to(s.path("review", "U02", "pr0").parent)
  git("update-ref", "refs/superegm/pr/7", "HEAD", cwd=world.repo)
  git("update-ref", "refs/superegm/pr-base/7", "HEAD", cwd=world.repo)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  assert f"kept {folder}: symlink" in out
  assert git("for-each-ref", "refs/superegm/pr/7", "refs/superegm/pr-base/7", cwd=world.repo) != ""  # U02's refs stay
  assert f"{UNIT} cleaned" not in out and f"{UNIT} cleaned" not in journal_text(s)
  assert clean_module.pr_numbers(s, UNIT) == [] and clean_module.private_refs(world.repo, s, UNIT) == []


def test_clean_keeps_a_ref_git_cannot_delete_and_does_not_journal_cleaned(world):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  add_tree(world, s.path("review", UNIT, "pr7", "worktree"))
  git("update-ref", "refs/superegm/pr/7", "HEAD", cwd=world.repo)
  common = Path(git("rev-parse", "--path-format=absolute", "--git-common-dir", cwd=world.repo))
  (common / "refs/superegm/pr/7.lock").write_text("", encoding="utf-8")
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  line = next(l for l in out.splitlines() if l.startswith("kept refs/superegm/pr/7: "))
  assert "lock" in line
  assert git("for-each-ref", "refs/superegm/pr/7", cwd=world.repo) != ""
  assert f"{UNIT} cleaned" not in out and f"{UNIT} cleaned" not in journal_text(s)
  assert clean_module.has_remnants(world.repo, s, UNIT)  # the ref still counts as left


def test_clean_skill_and_docstring_name_the_three_auto_error_lines():
  text, doc = read("skills/clean/SKILL.md"), clean_module.clean_auto.__doc__
  for said in ("`clean: <error>`", "`clean --auto: handoff: <error>`", "ends the sweep", "`clean --auto: <unit>: <error>`",
               "cannot be read", "kept <path>: not a builder tree"):
    assert said in text, said
  for said in ("clean: <error>", "clean --auto: handoff: <error>", "ends the sweep", "clean --auto: <unit>: <error>"):
    assert said in doc, said
  assert "`clean --auto: <unit or handoff>: <error>`" not in text and "<unit or handoff>" not in doc


def test_clean_names_an_entry_of_the_builder_folder_that_is_not_a_builder_tree(world):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  launched(s, UNIT, "exited 0", rnd=2)
  builder = s.path("worktrees", UNIT, "r2")
  add_tree(world, builder)
  scratch, loose, odd = (s.path("worktrees", UNIT, name) for name in ("scratch", "notes.txt", "r2x"))
  scratch.mkdir()
  loose.write_text("keep\n", encoding="utf-8")
  odd.mkdir()
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  for entry in (scratch, loose, odd):
    assert entry.exists() and f"kept {entry}: not a builder tree" in out  # said, and left alone
  assert not builder.exists() and f"kept {builder}:" not in out


def test_clean_auto_leaves_out_the_routine_not_a_builder_tree_line(world):
  s, card, _hid, _bodies = seed(world, units=(UNIT,))
  artifact = landed(world, s, card)
  builder = s.path("worktrees", UNIT, "r1")
  add_tree(world, builder)
  scratch = s.path("worktrees", UNIT, "scratch")
  scratch.mkdir()
  code, out = world.run("clean", "--auto", "--runcard", world.open_card("integrate", artifact))
  assert (code, out) == (0, "U01 cleaned\n") and scratch.is_dir() and not builder.exists()


def test_clean_prints_the_os_error_and_does_not_journal_cleaned_when_the_unit_folder_cannot_be_removed(world, monkeypatch):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  launched(s, UNIT, "exited 0", rnd=2)
  folder = s.path("worktrees", UNIT)
  add_tree(world, folder / "r2")
  git("update-ref", "refs/superegm/pr/7", "HEAD", cwd=world.repo)
  (s.path("review", UNIT, "pr7") / "r1").mkdir(parents=True)
  real_rmdir = Path.rmdir

  def rmdir(self, *args, **kwargs):
    if self == folder:
      raise OSError(13, "Permission denied")
    return real_rmdir(self, *args, **kwargs)

  monkeypatch.setattr(Path, "rmdir", rmdir)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  assert f"kept {folder}: [Errno 13] Permission denied" in out
  assert f"{UNIT} cleaned" not in out and f"{UNIT} cleaned" not in journal_text(s)
  assert git("for-each-ref", "refs/superegm/pr/7", cwd=world.repo) != ""  # nothing is reported cleaned, so its ref stays


def test_clean_keeps_a_symlinked_pr_folder_and_deletes_no_ref_through_it(world):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  (s.path("review", "U02", "pr7") / "r1").mkdir(parents=True)  # round records only: no registered tree
  link = s.path("review", UNIT, "pr7")
  link.parent.mkdir(parents=True, exist_ok=True)
  link.symlink_to(s.path("review", "U02", "pr7"))
  git("update-ref", "refs/superegm/pr/7", "HEAD", cwd=world.repo)
  git("update-ref", "refs/superegm/pr-base/7", "HEAD", cwd=world.repo)
  assert clean_module.pr_numbers(s, UNIT) == [] and not clean_module.has_remnants(world.repo, s, UNIT)  # not selectable under --auto
  code, out = world.run("clean", "--unit", UNIT, "--runcard", clean_card(world))
  assert code == 0, out
  assert f"kept {link}: symlink" in out
  assert git("for-each-ref", "refs/superegm/pr/7", "refs/superegm/pr-base/7", cwd=world.repo) != ""  # U02's refs stay
  assert (s.path("review", "U02", "pr7") / "r1").is_dir() and link.is_symlink()
  assert f"{UNIT} cleaned" not in out and f"{UNIT} cleaned" not in journal_text(s)
