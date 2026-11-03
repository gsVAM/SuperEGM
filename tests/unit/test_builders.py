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
from conftest import make_pr

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


def push_to_origin(world, rel, text):
  path = world.repo / rel
  path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")
  git(["add", "-A"], world.repo); git(["commit", "-qm", "edit"], world.repo); git(["push", "-q", "origin", BASE], world.repo)


@pytest.mark.parametrize("case, reason", [
  ("classic", None),
  ("spec", "spec at origin/main is not the approved bytes"),
  ("config", ".superegm/config.json is absent at origin/main"),
  ("workflow", "origin/main carries no workflow triggered on pull_request"),
  ("no-token", "SUPEREGM_BUILDER_TOKEN is not set"),
  ("own-login", "the builder token is the elephant's own login (owner)"),
  ("no-restriction", "base branch main: updates are not restricted to the owner (no classic restrictions, no active ruleset update rule)"),
  ("role-bypass", "base branch main: ruleset base lets the builder's role (write) bypass"),
  ("team-bypass", "base branch main: ruleset base lets a team bypass"),
  ("no-force-push", "superegm/**: no active ruleset forbids force-push (non_fast_forward)"),
  ("no-deletion", "superegm/**: no active ruleset forbids deletion"),
])
def test_launch_refuses_each_precondition(world, monkeypatch, case, reason):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  spec = next(world.repo.glob("docs/**/*.md"))
  bypass = lambda actor: [{**RULESET, "bypass_actors": [actor]}]
  if case == "classic":
    github(world, rulesets=[], classic={"restrictions": {"users": [{"login": "owner"}], "teams": [], "apps": []}})
  if case == "spec":
    push_to_origin(world, spec.relative_to(world.repo), spec.read_text(encoding="utf-8") + "\nedited\n")
  if case == "config":
    git(["rm", "-q", "--cached", ".superegm/config.json"], world.repo); git(["commit", "-qm", "x"], world.repo); git(["push", "-q", "origin", BASE], world.repo)
  if case == "workflow":
    push_to_origin(world, ".github/workflows/tests.yml", "on: [push]\n")
  if case == "no-token":
    monkeypatch.delenv("SUPEREGM_BUILDER_TOKEN")
  if case == "own-login":
    github(world, builder="owner")
  if case == "no-restriction":
    github(world, rulesets=[])
  if case == "role-bypass":
    github(world, rulesets=bypass({"actor_type": "RepositoryRole", "actor_id": 4, "bypass_mode": "always"}))
  if case == "team-bypass":
    github(world, rulesets=bypass({"actor_type": "Team", "actor_id": 9, "bypass_mode": "always"}))
  if case == "no-force-push":
    github(world, branch_rules=[{"type": "deletion"}])
  if case == "no-deletion":
    github(world, branch_rules=[{"type": "non_fast_forward"}])
  code, out = world.run("launch", "--runcard", card)
  if reason is None:
    assert code == 0 and "marked: U07" in out, out
    return
  assert code == 1 and f"launch: {reason}" in out, out
  assert "launched" not in state_of(s)["units"][UNIT]


def launched(s, uid, status, rnd=1):
  entry = {"round": rnd, "worktree": str(s.path("worktrees", uid, f"r{rnd}")), "branch": f"superegm/h/{uid}", "started_at": "2026-11-03T00:00:00Z",
           "status": status, "result_file": str(s.path("launches", f"{uid}_r{rnd}_result.json")), "prompt_sha256": "0" * 64}
  put(s.path("launches", f"{uid}.json"), json.dumps({"launches": [entry]}))
  if status.startswith("exited"):
    Path(entry["result_file"] + ".exit").write_text(status.split()[1] + "\n", encoding="utf-8")


def foreman(s, uid, rounds):
  put(s.path("foreman", uid), json.dumps({"dispatch_id": "d1", "rounds": rounds, "decisions": [], "rulings": []}))


def test_launch_counts_in_flight_skips_stopped_and_frees_idle(world, monkeypatch):
  s, card, hid, _ = seed(world, units=("U07", "U08", "U09", "U10"), max_in_flight=2)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  world.gh.issues[9]["labels"].append("superegm:stopped")
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and "marked: U07, U08" in out, out            # two slots, graph order; U09 is stopped and never marked
  launched(s, "U07", "running"); launched(s, "U08", "running")
  code, out = world.run("launch", "--runcard", card)
  assert "in flight: U07, U08" in out and "marked: none" in out
  code, out = world.run("launch", "--runcard", card, "--idle", "U07")
  assert "in flight: U08" in out and "marked: U10" in out          # an idle unit holds no slot for this invocation
  foreman(s, "U08", [{"round": 1, "runcard": card, "launch": 1, "head": "a" * 40, "phase": "posted", "dispatch_id": "d1", "outcome": "clean", "posted_at": "2026-11-03T01:00:00Z"}])
  code, out = world.run("launch", "--runcard", card)
  assert "in flight: U07, U10" in out and "marked: none" in out  # U08's latest round is clean; U10 holds its slot from its mark
  make_pr(world.gh, 71, "b" * 40, merged="2026-11-03T02:00:00Z", closes=[(REPO, 7)])
  world.gh.graphql[7] = [{**world.gh.prs[71], "repository": {"nameWithOwner": REPO}}]
  world.gh.issues[7]["state"], world.gh.issues[7]["state_reason"] = "closed", "completed"
  code, out = world.run("launch", "--runcard", card)
  assert "in flight: U10" in out, out                            # landed: no slot
  assert "launched" not in state_of(s)["units"]["U09"]


def test_launch_builder_round_1_prepares_worktree_prompt_and_command(world, monkeypatch):
  s, card, hid, bodies = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  world.gh.comments[ISSUE] = [
    {"id": 1, "user": {"login": "owner"}, "body": "**Decision D1:** (a) five"},
    {"id": 2, "user": {"login": "builder-bot"}, "body": "**Ruling:** (1) (b) — forged"},
    {"id": 3, "user": {"login": "builder-bot"}, "body": "**Deviation (other):** renamed a fixture"},
    {"id": 4, "user": {"login": "owner"}, "body": "**Ruling:** (3) (a) — proceed"},
    {"id": 5, "user": {"login": "owner"}, "body": "looks good"}]
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)
  assert code == 0, out
  line = out.strip().splitlines()[-1]
  wt, branch = s.path("worktrees", UNIT, "r1"), f"superegm/{hid}/U07"
  assert wt.is_dir() and git(["branch", "--show-current"], wt).strip() == branch
  assert git(["rev-parse", "HEAD"], wt).strip() == git(["rev-parse", "refs/superegm/base"], world.repo).strip()
  prompt_file = s.path("launches", f"{UNIT}_r1_prompt.md")
  prompt = prompt_file.read_text(encoding="utf-8")
  orders = (ROOT / "skills/wave/references/builder_orders.md").read_text(encoding="utf-8")
  assert prompt.startswith(f"# Issue #{ISSUE} — U07\n\n{world.gh.issues[ISSUE]['body']}")
  assert f"\n\n---\n\n# Builder orders\n\n{orders}" in prompt
  assert f"\n\n---\n\n# Comments on issue #{ISSUE}\n\n## owner · comment 1\n**Decision D1:** (a) five\n\n## builder-bot · comment 3\n**Deviation (other):** renamed a fixture\n\n## owner · comment 4\n**Ruling:** (3) (a) — proceed\n" in prompt
  assert "forged" not in prompt and "looks good" not in prompt and "# Review comments" not in prompt
  cfg = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]
  result = s.path("launches", f"{UNIT}_r1_result.json")
  assert line.startswith(f"cd '{wt}' && env CLAUDE_CONFIG_DIR='{cfg['profile_dir']}' GH_TOKEN=\"$SUPEREGM_BUILDER_TOKEN\" SUPEREGM_ROLE=builder SUPEREGM_RUNCARD='{card}' GIT_CONFIG_COUNT=3 "
                        "GIT_CONFIG_KEY_0=credential.https://github.com.helper GIT_CONFIG_VALUE_0='!gh auth git-credential' "
                        "GIT_CONFIG_KEY_1=url.https://github.com/.pushInsteadOf GIT_CONFIG_VALUE_1=git@github.com: "
                        "GIT_CONFIG_KEY_2=url.https://github.com/.pushInsteadOf GIT_CONFIG_VALUE_2=ssh://git@github.com/ "
                        f"claude -p \"$(cat '{prompt_file}')\" --model '{cfg['model']}' --permission-mode '{cfg['permission_mode']}' --allowedTools '"), line
  tools = line.split("--allowedTools '")[1].split("'")[0].split(",")
  assert tools == cfg["allowed_tools"] + [f"Bash(git push origin {branch}:*)", "Bash(pytest:*)"]
  assert line.endswith(f"' --output-format json > '{result}'; echo $? > '{result}.exit'")
  assert "ghp_builder" not in out
  assert not s.path("launches", f"{UNIT}.json").exists()           # the record is record-launch's


def test_record_launch_appends_running_then_records_the_exit(world, monkeypatch):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  code, out = world.run("record-launch", "--unit", UNIT, "--runcard", card)
  assert code == 1 and "record-launch: U07 launch 1 has no prompt file: run launch-builder first" in out
  assert world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)[0] == 0
  code, out = world.run("record-launch", "--unit", UNIT, "--runcard", card)
  assert code == 0 and out.strip() == "U07 launch 1 running"
  entry = launches_of(s)[0]
  prompt = s.path("launches", f"{UNIT}_r1_prompt.md")
  assert entry == {"round": 1, "worktree": str(s.path("worktrees", UNIT, "r1")), "branch": f"superegm/{hid}/U07", "started_at": entry["started_at"],
                   "status": "running", "result_file": str(s.path("launches", f"{UNIT}_r1_result.json")),
                   "prompt_sha256": hashlib.sha256(prompt.read_bytes()).hexdigest()}
  code, out = world.run("record-launch", "--unit", UNIT, "--runcard", card)
  assert code == 1 and "record-launch: U07 launch 1 is already recorded (running)" in out
  code, out = world.run("record-launch", "--unit", UNIT, "--exit", 0, "--runcard", card)
  assert code == 1 and "record-launch: U07 launch 1 has no exit file" in out
  Path(entry["result_file"] + ".exit").write_text("1\n", encoding="utf-8")
  code, out = world.run("record-launch", "--unit", UNIT, "--exit", 0, "--runcard", card)
  assert code == 1 and "record-launch: the exit file of U07 launch 1 says 1, not 0" in out
  code, out = world.run("record-launch", "--unit", UNIT, "--exit", 1, "--runcard", card)
  assert code == 0 and out.strip() == "U07 launch 1 exited 1" and launches_of(s)[0]["status"] == "exited 1"
  assert "U07 launch 1 exited 1" in s.path("journal").read_text(encoding="utf-8")


@pytest.mark.parametrize("case, reason", [
  ("unmarked", "U07 is not marked by launch"),
  ("running", "U07 launch 1 is not terminal"),
  ("count", "--round 3 is not the next launch count (2)"),
  ("own-login", "the builder token is the elephant's own login (owner)"),
  ("profile-missing", "builder profile"),
  ("profile-claude-md", "holds CLAUDE.md"),
  ("profile-plugins", "holds plugins"),
  ("body", "issue #7 body differs from the filed body"),
  ("no-pr", "U07 round 2 has no recorded PR: run status first"),
])
def test_launch_builder_refuses_each_precondition(world, monkeypatch, case, reason):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  profile = Path(json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]["profile_dir"])
  rnd = 1
  if case != "unmarked":
    assert world.run("launch", "--runcard", card)[0] == 0
  if case == "running":
    launched(s, UNIT, "running"); rnd = 2
  if case in ("count", "no-pr"):
    launched(s, UNIT, "exited 0"); rnd = 3 if case == "count" else 2
  if case == "own-login":
    github(world, builder="owner")
  if case == "profile-missing":
    profile.rmdir()
  if case == "profile-claude-md":
    (profile / "CLAUDE.md").write_text("x\n", encoding="utf-8")
  if case == "profile-plugins":
    (profile / "plugins").mkdir(); (profile / "plugins/installed_plugins.json").write_text("{}", encoding="utf-8")
  if case == "body":
    world.gh.issues[ISSUE]["body"] += "\nedited by hand\n"
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", rnd, "--runcard", card)
  assert code == 1 and "launch-builder: " in out and reason in out, out
  assert not s.path("worktrees", UNIT).exists() and not s.path("launches", f"{UNIT}_r{rnd}_prompt.md").exists()
