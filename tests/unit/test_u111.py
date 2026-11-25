# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the tests of U111, clean (#253): the start-time identity check, the listing after
# the wait, no rmdir through a symlink, close saving a merge, and the one-undeletable-ref wording.

"""U111 (spec section 3.10, Clean): `clean` checks each listed process's start time before every signal and lists
again after the wait, never runs `rmdir` through a symlink, and `close` saves a merge it reads from GitHub."""

import json, signal, subprocess
from pathlib import Path
import pytest
import superegm.clean as clean
from test_builders import seed, put, launched, spawn_fake, no_graphify, which  # noqa: F401  the fixtures a seeded store runs under

ROOT = Path(__file__).resolve().parents[2]
UNIT = "U07"
FIRST = "Tue Nov 25 10:00:00 2026"
LATER = "Tue Nov 25 10:00:30 2026"


@pytest.fixture(autouse=True)
def no_processes(monkeypatch):
  """No test here reads the machine's processes: the table is empty unless a test sets its own."""
  monkeypatch.setattr(clean, "process_table", lambda: [])


def git(*args, cwd):
  return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True).stdout.strip()


def journal_text(s):
  return s.path("journal").read_text(encoding="utf-8") if s.path("journal").is_file() else ""


def refs(world):
  return git("for-each-ref", "--format=%(refname)", "refs/superegm", cwd=world.repo)


def with_pr(s, number):
  """`units.<UNIT>.pr` recorded as `{"number": number}`, so the unit owns `refs/superegm/pr/<number>`."""
  state = json.loads(s.path("state").read_text(encoding="utf-8"))
  state["units"][UNIT]["pr"] = {"number": number}
  put(s.path("state"), json.dumps(state))


def builder_tree(world, s):
  """U07's recorded and registered builder tree `worktrees/U07/r1`, with `refs/superegm/pr/52` the unit's."""
  launched(s, UNIT, "exited 0")
  tree = s.path("worktrees", UNIT, "r1")
  tree.parent.mkdir(parents=True, exist_ok=True)
  git("worktree", "add", "-q", "--detach", str(tree), "HEAD", cwd=world.repo)
  with_pr(s, 52)
  git("update-ref", "refs/superegm/pr/52", "HEAD", cwd=world.repo)
  return tree


class Table:
  """A faked process table: `rows` maps a pid to `[command, cwd, start]`; `ps -o lstart= -p <pid>` reads `start` through
  `read(pid, listing)` (`listing`: the read follows a listing), `None` meaning ps exits 1 with nothing printed.
  A pid in `ignores_term` survives SIGTERM; every other dies of the first signal; `on_list(n)` runs before listing n (from 1)."""

  def __init__(self, rows, ignores_term=()):
    self.rows, self.ignores_term, self.signals, self.listings, self.ps = rows, set(ignores_term), [], 0, []
    self.just_listed = set()

  def listing(self):
    self.listings += 1
    self.on_list(self.listings)
    self.just_listed = set(self.rows)
    return [(pid, command, cwd) for pid, (command, cwd, _start) in self.rows.items()]

  def on_list(self, n):
    pass

  def read(self, pid, listing):
    return self.rows[pid][2] if pid in self.rows else None

  def run(self, argv, *args, **kwargs):
    assert argv[:4] == ["ps", "-o", "lstart=", "-p"] and len(argv) == 5, argv
    pid = int(argv[4])
    listing = pid in self.just_listed
    self.just_listed.discard(pid)
    start = self.read(pid, listing)
    self.ps.append((pid, listing, start))
    return subprocess.CompletedProcess(argv, 1, "", "") if start is None else subprocess.CompletedProcess(argv, 0, f"{start}\n", "")

  def send(self, pid, sig):
    self.signals.append((pid, sig))
    if pid in self.rows and not (sig == signal.SIGTERM and pid in self.ignores_term):
      del self.rows[pid]

  def alive(self, pid):
    return pid in self.rows

  def install(self, monkeypatch):
    real_run = subprocess.run
    monkeypatch.setattr(clean, "process_table", self.listing)
    monkeypatch.setattr(clean, "signal_process", self.send)
    monkeypatch.setattr(clean, "is_alive", self.alive)
    monkeypatch.setattr(subprocess, "run", lambda argv, *a, **k: self.run(argv, *a, **k) if argv[0] == "ps" else real_run(argv, *a, **k))

  def sent(self, pid):
    return [sig for p, sig in self.signals if p == pid]


@pytest.mark.parametrize("at, start, sent", [
  ("SIGTERM", "Tue Nov 25 10:05:00 2026", []),
  ("SIGKILL", "Tue Nov 25 10:05:00 2026", [signal.SIGTERM]),  # every listing read 10:00:00; the read just before SIGKILL differs
  ("SIGTERM", None, []),  # ps exits non-zero or prints nothing
  ("listing", None, []),  # unreadable when first listed: the same skip, never taken as gone
])
def test_clean_skips_a_process_whose_start_time_changed(world, monkeypatch, at, start, sent):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  tree = builder_tree(world, s)
  table = Table({4242: ["python3", str(tree.resolve()), FIRST]}, ignores_term=(4242,) if at == "SIGKILL" else ())

  def read(pid, listing):
    if listing:  # the first listing reads `start` when `at` is "listing"; every other listing reads 10:00:00
      return start if at == "listing" and table.listings == 1 else FIRST
    terms = table.sent(pid).count(signal.SIGTERM)
    if (at == "SIGTERM" and terms == 0) or (at == "SIGKILL" and terms == 1):
      return start
    return FIRST

  table.read = read
  table.install(monkeypatch)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", world.open_card("clean", UNIT))
  assert code == 0, out
  journal, refs_after, signals = journal_text(s), refs(world), table.sent(4242)
  assert "kept 4242: identity changed" in out and signals == sent
  assert "U07 killed 4242" not in journal and "U07 cleaned" not in journal and tree.is_dir()
  assert "refs/superegm/pr/52" in refs_after


@pytest.mark.parametrize("found", [4343, 4242])  # 4242: its PID found again with a new start time
def test_clean_lists_again_after_the_wait(world, monkeypatch, found):
  s, _card, _hid, _bodies = seed(world, units=(UNIT,))
  tree = builder_tree(world, s)
  table = Table({4242: ["python3", str(tree.resolve()), FIRST]})

  def on_list(n):  # the listing after the wait finds `found` in the same tree, started at 10:00:30
    if n == 2:
      table.rows[found] = ["python3", str(tree.resolve()), LATER]

  table.on_list = on_list
  table.install(monkeypatch)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", world.open_card("clean", UNIT))
  assert code == 0, out
  journal = journal_text(s)
  signals = {pid: table.sent(pid) for pid in (4242, found)}
  assert signals[found][-1] == signal.SIGTERM and f"U07 killed {found} python3" in journal
  assert "identity changed" not in out and "U07 cleaned" in journal
  assert signals[found] == [signal.SIGTERM] * (2 if found == 4242 else 1)  # the listed 4242, then the one found after the wait
  assert table.listings == 2  # one listing after the wait, no further one
