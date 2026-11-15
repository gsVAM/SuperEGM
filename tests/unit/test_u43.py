# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U43's tests: `superegm next`'s first-match table, the spec-only origin check, `next wait` and `next clear`, and the frozen mode.

"""U43: `superegm next` and the frozen mode."""

import json
import subprocess

import pytest
from test_review import converged_spec, approve, spec_file, SLUG
import superegm
from superegm import handoff_store

UNITS = ("U01", "U02", "U03")
TABLE = "".join(f"| {u} | thing {u} | — | S |\n" for u in UNITS)
SPEC = f"# Sample\n\n## 1. Intent\n\nText.\n\n## 2. Units\n\n| Unit | Scope | Blocked by | Size |\n| --- | --- | --- | --- |\n{TABLE}"
LANDED = SPEC + "\nLanded: U01, U02, U03 (an earlier build)\n"
SHA = {u: str(i + 1) * 64 for i, u in enumerate(UNITS)}
RECEIPT = "c" * 64


def git(world, *args):
  return subprocess.run(["git", "-C", str(world.repo), *args], check=True, capture_output=True, text=True).stdout.strip()


def jwrite(path, obj):
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(obj), encoding="utf-8")


def jread(path):
  return json.loads(path.read_text(encoding="utf-8"))


class Chain:
  """An approved handoff of a three-unit spec whose store the test edits by hand: the tick's fetch record ok and
  `refs/superegm/tick-base` at the approval commit, the root clean on main."""

  def __init__(self, world, text=SPEC):
    self.world = world
    spec, cid, _ = converged_spec(world, text)
    code, out = approve(world, spec, cid, "--yes")
    assert code == 0, out
    self.spec = spec
    self.root = world.artifacts
    self.hid = jread(self.root / "approvals" / f"{SLUG}.json")["entries"][-1]["handoff_id"]
    self.hs = handoff_store(superegm.Store(self.root), self.hid)
    git(world, "update-ref", "refs/superegm/tick-base", "HEAD")
    self.fetch(True)
    self.state = {"handoff_id": self.hid, "design": {"path": str(spec)}, "units": {}}

  # the tick's records
  def fetch(self, ok, stderr=""):
    jwrite(self.root / "tick" / "fetch.json", {"at": "2026-11-15T00:00:00Z", "ok": ok, "stderr": stderr})

  def wait(self, **record):
    jwrite(self.root / "chain" / f"{self.hid}.json", {"since": "2026-11-15T00:00:00Z", "review": None, **record})

  # the handoff's records
  def plan(self, *units):
    jwrite(self.hs.path("units"), {"units": {u: {"body_sha256": SHA[u]} for u in units}, "order": list(units)})

  def review(self, uid, sha=None, converged="yes", rulings=()):
    folder = self.hs.path("reviews", f"plan-{uid}-c1")
    jwrite(folder / "review.json", {"kind": "plan", "artifact": uid, "cycle": 1, "reviewers": ["readiness"], "runcard": "rc",
                                    "converged": converged, "converged_round": 1 if converged == "yes" else None,
                                    "rulings": list(rulings)})
    jwrite(folder / "round-1.json", {"runcard": "rc", "artifact_sha256": sha or SHA[uid], "findings": {}, "what_ran": "completed"})

  def filed(self, uid, number, pr=None, ci=None, landed=False):
    self.state["units"][uid] = {"number": number}
    status = self.state.setdefault("status", {"units": {}, "ready": []})
    status["units"][uid] = {"pr": pr, "head": None, "ci": ci, "landed": landed}
    self.state.update(confirmed_sha256=RECEIPT, verify={"complete": True, "sha256": RECEIPT, "problems": []})

  def stopped(self, uid):
    jwrite(self.hs.path("foreman", uid), {"dispatch_id": None, "rounds": [], "decisions": [], "rulings": [],
                                          "stopped": {"at": "2026-11-15T00:00:00Z", "by": "owner"}})

  def save(self):
    jwrite(self.hs.path("state"), self.state)

  def all_filed(self, open_unit=None):
    """The plan of three reviewed, filed units; every one landed but `open_unit`."""
    self.plan(*UNITS)
    for n, uid in enumerate(UNITS, 1):
      self.review(uid)
      self.filed(uid, n, pr={"number": 10 + n}, ci="success", landed=uid != open_unit)

  def supersede(self):
    path = self.root / "approvals" / f"{SLUG}.json"
    record = jread(path)
    record["entries"].append({**record["entries"][-1], "handoff_id": "2026-11-03-sample-de-ffffff", "kind": "opening"})
    jwrite(path, record)

  def close(self):
    path = self.root / "handoffs" / f"{self.hid}.json"
    jwrite(path, {**jread(path), "closed_at": "2026-11-15T00:00:00Z"})

  def void(self):
    path = self.root / "approvals" / f"{SLUG}.json"
    record = jread(path)
    record["entries"][-1]["voided_by"] = "spec-review-c2"
    jwrite(path, record)

  def other_spec_at_tick_base(self):
    git(self.world, "checkout", "-q", "-b", "side")
    self.spec.write_text(SPEC + "\nMore.\n", encoding="utf-8")
    git(self.world, "commit", "-qam", "side")
    git(self.world, "update-ref", "refs/superegm/tick-base", "side")
    git(self.world, "checkout", "-q", "main")

  def snapshot(self):
    return {p: p.read_bytes() for p in sorted(self.world.artifacts.rglob("*")) if p.is_file()}

  def next(self):
    before = self.snapshot()
    code, out = self.world.run("next", "--handoff", self.hid)
    return code, out.rstrip("\n"), before, self.snapshot()


def arrange(c, state):
  """The store for one row's state; each also meets a row below it, so the first row in table order must win."""
  if state == "handoff closed":
    c.all_filed(); c.close(); c.fetch(False, "fatal: x")
  elif state == "latest approval voided":
    c.all_filed(); c.void(); c.fetch(False, "fatal: x")
  elif state == "fetch record ok false":
    c.all_filed("U02"); c.supersede(); c.fetch(False, "fatal: unable to access")
  elif state == "tick-base absent":
    c.all_filed("U02"); c.supersede(); git(c.world, "update-ref", "-d", "refs/superegm/tick-base")
  elif state == "superseded, a filed unit open":
    c.all_filed("U02"); c.supersede(); c.wait(phase="file", question="q")
  elif state == "superseded, every filed unit landed or merged":
    c.all_filed("U02"); c.state["status"]["units"]["U02"].update(ci=None)  # merged: pr set, ci null
    c.supersede(); c.wait(phase="file", question="q")
  elif state == "superseded, no filed unit":
    c.plan(*UNITS); c.supersede(); c.wait(phase="file", question="q")
  elif state == "unanswered wait record, question with a newline":
    c.wait(phase="file", question="create 3\nissues?"); c.other_spec_at_tick_base()
  elif state == "spec at tick-base not the approved bytes":
    c.other_spec_at_tick_base(); (c.world.repo / "docs/designs/sample.md").write_text("dirty\n", encoding="utf-8")
  elif state == "root dirty, next row plan":
    (c.world.repo / "docs/designs/sample.md").write_text("dirty\n", encoding="utf-8")
  elif state == "root on another branch, next row plan":
    git(c.world, "checkout", "-q", "-b", "other")
  elif state == "answered wait record for review-plan":
    c.wait(phase="review-plan", question="q", answer="yes", by="owner", at="2026-11-15T01:00:00Z")
  elif state == "every unit row Landed":
    pass  # the spec's Landed: line names every row, and no plan
  elif state == "no plan":
    pass
  elif state == "plan review stopped, no proceed":
    c.all_filed(); c.state["units"].pop("U02")
    c.review("U02", converged="no", rulings=[{"id": "R1", "ruling": "stop", "by": "owner", "at": "2026-11-15T00:00:00Z"}])
  elif state == "review converged on other bytes":
    c.all_filed(); c.state["units"].pop("U02"); c.review("U02", sha="0" * 64)
  elif state == "reviewed unit without issue number":
    c.all_filed("U01"); c.state["units"].pop("U02")
  elif state == "a filed unit open":
    c.all_filed("U01")
  elif state == "all landed, merged or stopped":
    c.all_filed("U02"); c.state["status"]["units"]["U02"].update(ci=None)
    c.state["status"]["units"]["U03"].update(landed=False, pr=None, ci=None); c.stopped("U03")
  c.save()


@pytest.mark.parametrize("state,line", [
  ("handoff closed", "none"), ("latest approval voided", "none"),
  ("fetch record ok false", "waiting fetch: origin: fatal: unable to access"),
  ("tick-base absent", "waiting fetch: origin: refs/superegm/tick-base absent"),
  ("superseded, a filed unit open", "wave"), ("superseded, every filed unit landed or merged", "integrate"),
  ("superseded, no filed unit", "none"), ("unanswered wait record, question with a newline", "waiting file: create 3 issues?"),
  ("spec at tick-base not the approved bytes", "waiting push"), ("root dirty, next row plan", "waiting checkout: {root}: dirty"),
  ("root on another branch, next row plan", "waiting checkout: {root}: not on main"),
  ("answered wait record for review-plan", "review-plan"),
  ("every unit row Landed", "waiting plan: no unit left to plan: superegm approve-spec --void --spec {spec}"),
  ("no plan", "plan"),
  ("plan review stopped, no proceed", "waiting review-plan: {review} stopped"),
  ("review converged on other bytes", "review-plan"), ("reviewed unit without issue number", "file"),
  ("a filed unit open", "wave"), ("all landed, merged or stopped", "integrate")])
def test_next_rows_first_match(world, state, line):
  """Each state also meets rows below it; the first section 7.1 row wins and `next` writes nothing."""
  c = Chain(world, LANDED if state == "every unit row Landed" else SPEC)
  arrange(c, state)
  line = line.format(root=superegm.git_toplevel(world.repo), spec=c.spec, review="plan-U02-c1")
  code, out, before, after = c.next()
  assert (code, out) == (0, line) and before == after


def test_origin_spec_check_alone(world):
  """The spec check runs alone against the given ref; the default ref and the full check are 1.2's."""
  from superegm import launch
  c = Chain(world)
  git(world, "update-ref", "refs/superegm/base", "HEAD")
  c.other_spec_at_tick_base()
  root = superegm.git_toplevel(world.repo)
  approval, later = {**jread(c.root / "approvals" / f"{SLUG}.json")["entries"][-1], "path": str(c.spec)}, []
  assert launch.origin_problems(root, "main", approval, later, ref="refs/superegm/tick-base", spec_only=True) == [
    "spec at origin/main is neither the approved bytes nor a later link of the approval chain"]
  assert launch.origin_problems(root, "main", approval, later) == launch.origin_problems(root, "main", approval, later, ref="refs/superegm/base")
  assert launch.origin_problems(root, "main", approval, later) == ["origin/main carries no workflow triggered on pull_request"]


@pytest.mark.parametrize("record,next_without,after", [
  ({"phase": "file", "question": "q"}, "wave", None),
  ({"phase": "file", "question": "q"}, "waiting fetch: origin: x", {"phase": "file", "question": "q"}),
  ({"phase": "file", "question": "q"}, "file", {"phase": "file", "question": "q"}),
  ({"phase": "file", "question": "q", "answer": "yes", "by": "owner", "at": "t"}, "file",
   {"phase": "file", "question": "stopped at file by owner: answer to go on"})])
def test_next_clear(world, record, next_without, after):
  """Removed only on confirmed progress; a waiting row keeps it; an answer turns back into a question with a new since."""
  c = Chain(world)
  if next_without == "waiting fetch: origin: x":
    c.fetch(False, "x")
  else:
    c.all_filed("U01")
    if next_without == "file":
      c.state["units"].pop("U02")
  c.save()
  assert c.next()[1] == next_without  # what next prints with no wait record
  c.wait(**record)
  path = c.root / "chain" / f"{c.hid}.json"
  stored = jread(path)
  cid = world.open_card("file", c.spec)
  code, out = world.run("next", "clear", "--handoff", c.hid, "--runcard", cid)
  assert code == 0, out
  assert jread(superegm.Store(c.root).path("runcards", cid))["closed_at"]
  now = jread(path) if path.is_file() else None
  assert (now and {k: v for k, v in now.items() if k not in ("since", "review")}) == after
  if now:
    assert now["review"] == stored["review"]
    assert (now["since"] != stored["since"]) == ("answer" in record)  # the rewrite's time, a new since
  code, out = world.run("next", "clear", "--handoff", c.hid)
  assert (code, out.strip().removeprefix("superegm: ")) == (1, "runcard: --runcard is required")
