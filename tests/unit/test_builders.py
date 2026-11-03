# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: the builders' tests (U09): launch, launch-builder, record-launch, interrupt, clean, the orders and the two skill bodies.

"""The builders (spec section 11): `launch` and its preconditions, `launch-builder`'s worktree,
prompt file and command line, `record-launch`, `interrupt`, `clean`, the builder orders and the
`interrupt` and `clean` skill bodies."""

import hashlib, json, re, subprocess
from pathlib import Path
import pytest
from superegm import store, spec_slug, DEFAULT_CONFIG
from superegm.body import fill_numbers, normalise

ROOT = Path(__file__).resolve().parents[2]
REPO, BASE, UNIT, ISSUE, TRACKING, PR = "example-org/webhooks", "main", "U07", 7, 1, 70
F = "`" * 3
BODY = (f"<!-- superegm:handoff=HID unit=UID spec=SHA -->\n# UID — Worker\n\n## Objective\nA worker exists.\n\n"
        f"## Definition of done\n1. The test for each Step was committed before its implementation (checked by superegm tdd-order)\n"
        f"2. Run `pytest tests/unit/test_worker.py -q` — the worker's cases pass\n3. Exists `src/worker.py`\n4. CI green on the head\n\n"
        f"## Steps\n1. Write the failing test `test_w` in `tests/unit/test_worker.py`:\n   {F}python\n   def test_w(): ...\n   {F}\n"
        f"   Run `pytest tests/unit/test_worker.py::test_w -q`; expected: FAIL (`ImportError`).\n"
        f"   Implement `w() -> None` in `src/worker.py`.\n   Run the same command; expected: PASS. Commit `test(S1): w` then `feat(S1): w`.\n\n"
        f"## Scope, order and risk\nScope: `src/worker.py` (create) · Blocked by: none · Shared files: none · Risk: low: new · Size: S\n"
        f"Branch: `superegm/HID/UID` · Part of #<tracking>\n")
SECTION = ("### UID: Worker\n| Field | Value |\n| --- | --- |\n| Objective | A worker exists. |\n| Scope paths | `src/worker.py` (create) |\n"
           "| Design range | `SPEC:1-2 (# title)` |\n| Blocked by | none |\n| Shared files | none |\n| Risk | low: new |\n| Size | S |\n\n"
           "Definition of done\n1. `pytest tests/unit/test_worker.py -q` passes.\n2. CI green.\n\nDecide before build\n- none\n")
RULESET = {"id": 1, "name": "base", "enforcement": "active", "target": "branch",
           "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}, "rules": [{"type": "update"}],
           "bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}]}


def git(args, cwd):
  return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True).stdout


def put(path, text):
  """A store file as a subcommand left it (the store's folders do not exist before the first write)."""
  path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")


def github(world, *, builder="builder-bot", me="owner", role="write", classic=None, rulesets=(RULESET,),
           branch_rules=({"type": "non_fast_forward"}, {"type": "deletion"})):
  """Routes on U03's fake gh (`extend("api", …)`, one handler per word): an endpoint handler takes
  (args, token, match) and returns the JSON (pages for --paginate --slurp) or (404, text); `-q .key`
  prints that key, as gh does; everything else falls through to the built-in `do_api`."""
  h = {}
  h[r"^user$"] = lambda a, t, m: {"login": builder if t else me}
  h[rf"^repos/{REPO}/collaborators/[^/]+/permission$"] = lambda a, t, m: {"role_name": role}
  h[rf"^repos/{REPO}/branches/{BASE}/protection$"] = lambda a, t, m: classic if classic is not None else (404, "Branch not protected")
  h[rf"^repos/{REPO}/rulesets$"] = lambda a, t, m: [list(rulesets)]
  h[rf"^repos/{REPO}/rulesets/(\d+)$"] = lambda a, t, m: next(r for r in rulesets if r["id"] == int(m.group(1)))
  h[rf"^repos/{REPO}/rules/branches/.+$"] = lambda a, t, m: list(branch_rules)
  h[rf"^repos/{REPO}/issues/(\d+)/comments$"] = lambda a, t, m: [world.gh.comments.get(int(m.group(1)), [])]
  h[rf"^repos/{REPO}/pulls/(\d+)/reviews$"] = lambda a, t, m: [world.gh.reviews.get(int(m.group(1)), [])]

  def api(args, cwd, token=None):
    endpoint = world.gh.endpoint_of(args).partition("?")[0]
    for pattern, handler in h.items():
      match = re.match(pattern, endpoint)
      if match:
        data = handler(args, token, match)
        if isinstance(data, tuple):
          return 1, "", f"gh: {data[1]} (HTTP {data[0]})"
        if "-q" in args:
          return 0, f"{data[args[args.index('-q') + 1].lstrip('.')]}\n", ""
        return world.gh.ok(data)
    return world.gh.do_api(args)
  world.gh.extend("api", api)


def seed(world, units=(UNIT,), max_in_flight=5, workflow="on: [push, pull_request]\n"):
  """Filed units as U07's `apply` and the owner's approval push leave them: store, plan file, issues, origin/<base>, an open wave card."""
  repo, s = world.repo, store(world.repo)
  spec = next(repo.glob("docs/**/*.md")).resolve()
  profile = repo.parent / "profile"; profile.mkdir(exist_ok=True)
  cfg = json.loads((repo / ".superegm/config.json").read_text(encoding="utf-8"))
  cfg["max_in_flight"], cfg["builder"] = max_in_flight, {**DEFAULT_CONFIG["builder"], "profile_dir": str(profile)}
  (repo / ".superegm/config.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
  (repo / ".github/workflows").mkdir(parents=True, exist_ok=True)
  (repo / ".github/workflows/tests.yml").write_text(workflow, encoding="utf-8")
  git(["add", "-A"], repo); git(["commit", "-qm", "superegm: approve"], repo)
  sha = hashlib.sha256(spec.read_bytes()).hexdigest()
  hid = f"{spec_slug(spec)}-{sha[:6]}"
  s.handoff_id = hid
  bare = repo.parent / "origin.git"
  git(["clone", "-q", "--bare", str(repo), str(bare)], repo.parent)
  git(["remote", "set-url", "origin", str(bare)], repo)  # fetch/push hit the bare clone
  world.ns["find_remote"] = lambda root, repo: "origin"  # `remote -v` shows that path, not GitHub
  sections = "\n".join(SECTION.replace("UID", u).replace("SPEC", str(spec)) for u in units)
  plan = repo.parent / "plan.md"
  plan_text = f"# Handoff plan: Worker\n\nDesign: `{spec}`\n\n## 1. Issue template\n\n## 2. Units\n\n{sections}"
  plan.write_text(plan_text, encoding="utf-8"); put(s.path("plan"), plan_text)
  writes = [["issue", "tracking", "Build", ["superegm:tracking"], "Tracking"]]
  world.gh.issues[TRACKING] = {"number": TRACKING, "id": 1000, "body": "Tracking", "labels": ["superegm:tracking"], "state": "open", "state_reason": None}
  numbers = {u: 7 + i for i, u in enumerate(units)}
  bodies = {}
  for u, n in numbers.items():
    body = BODY.replace("HID", hid).replace("UID", u).replace("SHA", sha)
    bodies[u] = body
    put(s.path("unit", u), f"{SECTION.replace('UID', u).replace('SPEC', str(spec))}\n## Issue body as posted\n\n{F}markdown\n{body}{F}\n")
    writes.append(["issue", u, f"{u}: Worker", ["superegm:unit"], body])
    world.gh.issues[n] = {"number": n, "id": 1000 + n, "body": fill_numbers(body, numbers, TRACKING), "labels": ["superegm:unit"], "state": "open", "state_reason": None}
  put(s.path("approvals", f"{spec_slug(spec)}.json"), json.dumps({"path": str(spec), "sha256": sha, "commit": git(["rev-parse", "--short", "HEAD"], repo).strip(),
      "runcard": "c0", "review": "r0", "approved_at": "2026-11-03T00:00:00Z", "amended": [], "voided_by": None, "handoff_id": hid}))
  put(s.path("state"), json.dumps({"handoff_id": hid, "repo": REPO, "plan": str(plan), "confirmed_sha256": "x",
      "design": {"path": str(spec), "sha256": sha},
      "verify": {"complete": True, "sha256": "x", "problems": []}, "tracking": {"number": TRACKING, "id": 1000},
      "units": {u: {"number": n, "id": 1000 + n} for u, n in numbers.items()},
      "filings": [{"sha256": "x", "writes": writes, "at": "2026-11-03T00:00:00Z"}]}))
  world.gh.comments, world.gh.reviews = {}, {}
  github(world)
  code, out = world.run("runcard", "open", "--skill", "wave", "--artifact", str(spec))
  assert code == 0, out
  return s, out.split()[-1], hid, bodies


def state_of(s):
  return json.loads(s.path("state").read_text(encoding="utf-8"))


def launches_of(s, uid=UNIT):
  return json.loads(s.path("launches", f"{uid}.json").read_text(encoding="utf-8"))["launches"]


def test_launch_marks_ready_units_and_records_the_builder_login(world, monkeypatch):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and out.splitlines()[:2] == ["in flight: none", "marked: U07"], out
  assert state_of(s)["units"][UNIT]["launched"]["runcard"] == card
  rc = json.loads(s.path("runcards", f"{card}.json").read_text(encoding="utf-8"))
  assert rc["builder"][-1] == {"login": "builder-bot", "token_env": "SUPEREGM_BUILDER_TOKEN"}
  assert git(["rev-parse", "refs/superegm/base"], world.repo).strip() == git(["rev-parse", "HEAD"], world.repo).strip()
  assert "ghp_builder" not in out and not any("ghp_builder" in " ".join(c) for c in world.gh.calls)
  assert "U07 marked for launch" in s.path("journal").read_text(encoding="utf-8")
