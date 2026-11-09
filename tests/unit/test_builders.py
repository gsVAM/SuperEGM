# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: the builders' tests (U09): launch, launch-builder, record-launch, interrupt, clean, the orders and the two skill bodies; the App path (U15).

"""The builders (spec section 11): `launch` and its preconditions, `launch-builder`'s worktree,
prompt file and command line, `record-launch`, `interrupt`, `clean`, the builder orders and the
`interrupt` and `clean` skill bodies."""

import hashlib, json, os, re, shutil, subprocess
from pathlib import Path
import pytest
from superegm import store, spec_slug, DEFAULT_CONFIG
from superegm.body import fill_numbers, normalise
from conftest import make_pr
from test_builder_token import key, APP, OPENSSL, FOUR, app_api  # noqa: F401  the key fixture and the faked App API

ROOT = Path(__file__).resolve().parents[2]
REPO, BASE, UNIT, ISSUE, TRACKING, PR = "example-org/webhooks", "main", "U07", 7, 1, 70
F = "`" * 3
BODY = (f"<!-- superegm:handoff=HID unit=UID spec=SHA -->\n# UID — Worker\nSpec: `REL` @ SEVEN · `REL:1-2 (# Webhook delivery)`\n\n## Objective\nA worker exists.\n\n"
        f"## Definition of done\n1. The test for each Step was committed before its implementation (checked by superegm tdd-order)\n"
        f"2. Run `pytest tests/unit/test_worker.py -q` — the worker's cases pass\n3. Exists `src/worker.py`\n4. CI green on the head\n\n"
        f"## Steps\n1. Write the failing test `test_w` in `tests/unit/test_worker.py`:\n   {F}python\n   def test_w(): ...\n   {F}\n"
        f"   Run `pytest tests/unit/test_worker.py::test_w -q`; expected: FAIL (`ImportError`).\n"
        f"   Implement `w() -> None` in `src/worker.py`.\n   Run the same command; expected: PASS. Commit `test(S1): w` then `feat(S1): w`.\n\n"
        f"## Scope, order and risk\nScope: `src/worker.py` (create) · Blocked by: none · Shared files: none · Risk: low: new · Size: S\n"
        f"Branch: `superegm/HID/UID` · Part of #<tracking>\n")
SECTION = ("### UID: Worker\n| Field | Value |\n| --- | --- |\n| Objective | A worker exists. |\n| Scope paths | `src/worker.py` (create) |\n"
           "| Design range | `SPEC:1-2 (# title)` |\n| Blocked by | none |\n| Shared files | none |\n| Risk | low: new |\n| Size | S |\n\n"
           "Interfaces\n- Produces: w() -> None\n\n"
           "Definition of done\n1. The test for each Step was committed before its implementation (checked by superegm tdd-order)\n"
           "2. Run `pytest tests/unit/test_worker.py -q` — the worker's cases pass\n3. Exists `src/worker.py`\n4. CI green on the head\n\n"
           "Review focus (this unit)\n- UID: an empty run — nothing happens; pinned by `test_w`\n\n"
           f"Steps\n1. Write the failing test `test_w` in `tests/unit/test_worker.py`:\n   {F}python\n   def test_w(): ...\n   {F}\n"
           "   Implement `w() -> None` in `src/worker.py`.\n\nDecide before build\n- none\n")
RULESET = {"id": 1, "name": "base", "enforcement": "active", "target": "branch",
           "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}}, "rules": [{"type": "update"}],
           "bypass_actors": [{"actor_type": "RepositoryRole", "actor_id": 5, "bypass_mode": "always"}]}
SUPEREGM_RULESET = {"id": 2, "name": "superegm", "enforcement": "active", "target": "branch",
                    "conditions": {"ref_name": {"include": ["refs/heads/superegm/**"], "exclude": []}},
                    "rules": [{"type": "non_fast_forward"}, {"type": "deletion"}], "bypass_actors": []}
BOT, EMAIL = "superegm-builder[bot]", "2002+superegm-builder[bot]@users.noreply.github.com"


def git(args, cwd):
  return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True, text=True).stdout


@pytest.fixture(autouse=True)
def no_graphify(monkeypatch):
  from superegm import orient
  monkeypatch.setattr(orient, "GRAPHIFY", "superegm-no-such-tool")


@pytest.fixture(autouse=True)
def which(monkeypatch):
  """The launching machine's tools: `gh` at a fixed path, the real `openssl`, nothing else."""
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: {"gh": "/usr/local/bin/gh", "openssl": OPENSSL}.get(cmd))


# U27's helpers; imported after the two autouse fixtures, which `test_u27` imports back
from test_u27 import elephant, PONY, MCP, THREE  # noqa: E402
from superegm import launch_builder  # noqa: E402
from superegm.launch_builder import skill_names, orders_text  # noqa: E402


SPAWNED = []  # (command, log, env) of every launch `spawn_fake` stood in for


@pytest.fixture
def spawn_fake(world, monkeypatch):
  """`launch-builder` starts the wrapper itself (U24): no test starts a builder, so `start_detached` appends its
  arguments to `SPAWNED` (cleared first) and returns the pid 4242."""
  from superegm import launch_builder
  SPAWNED.clear()
  monkeypatch.setattr(launch_builder, "start_detached", lambda command, log, env: (SPAWNED.append((command, log, env)), 4242)[1])
  return SPAWNED


def put(path, text):
  """A store file as a subcommand left it (the store's folders do not exist before the first write)."""
  path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")


def configure(world, **keys):
  """Rewrite keys of the working tree's `.superegm/config.json` (`launch` reads the tree's; origin's copy stays)."""
  path = world.repo / ".superegm/config.json"
  cfg = json.loads(path.read_text(encoding="utf-8")); cfg.update(keys)
  path.write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")


def github(world, *, builder="builder-bot", me="owner", role="write", classic=None, rulesets=(RULESET,),
           branch_rules=({"type": "non_fast_forward"}, {"type": "deletion"}), team_id=9, member=False, scopes="repo, read:org"):
  """Routes on U03's fake gh (`extend("api", …)`, one handler per word): an endpoint handler takes
  (args, token, match) and returns the JSON (pages for --paginate --slurp) or (404, text); `-q .key`
  prints that key, as gh does; `-i` prints the status line and the `X-Oauth-Scopes` header (none for
  `scopes=None`, a fine-grained token) before the JSON; everything else falls through to the built-in `do_api`."""
  h = {}
  h[r"^orgs/[^/]+/teams/[^/]+$"] = lambda a, t, m: {"id": team_id} if team_id else (404, "Not Found")
  h[r"^orgs/[^/]+/teams/[^/]+/memberships/[^/]+$"] = lambda a, t, m: {"state": "active"} if member else (404, "Not Found")
  h[r"^user$"] = lambda a, t, m: {"login": builder if t else me}
  h[r"^users/([^/]+)$"] = lambda a, t, m: {"login": m.group(1), "id": {builder: 1001, BOT: 2002}.get(m.group(1), 1)}
  h[rf"^repos/{REPO}$"] = lambda a, t, m: {"permissions": {"push": True, "pull": True}, "security_and_analysis": {
      "secret_scanning_push_protection": {"status": "enabled"}, "secret_scanning_non_provider_patterns": {"status": "enabled"}}}
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
        if "-i" in args:
          return 0, "HTTP/2.0 200 OK\n" + (f"X-Oauth-Scopes: {scopes}\n" if scopes is not None else "") + "\n" + json.dumps(data), ""
        if "-q" in args:
          value = data[args[args.index('-q') + 1].lstrip('.')]
          return 0, (json.dumps(value) if isinstance(value, (dict, list)) else str(value)) + "\n", ""
        return world.gh.ok(data)
    return world.gh.do_api(args)
  world.gh.extend("api", api)


def seed(world, units=(UNIT,), max_in_flight=5, workflow="on: [push, pull_request]\n"):
  """Filed units as U07's `apply` and the owner's approval push leave them: store, plan file, issues, origin/<base>, an open wave card."""
  repo, s = world.repo, store(world.repo)
  spec = next(repo.glob("docs/**/*.md")).resolve()
  profile = repo.parent / "profile"; profile.mkdir(exist_ok=True)
  (profile / "settings.json").write_text(json.dumps({"disableClaudeAiConnectors": True, "syncClaudeAiPlugins": False}), encoding="utf-8")
  cfg =json.loads((repo / ".superegm/config.json").read_text(encoding="utf-8"))
  cfg["max_in_flight"], cfg["builder"], cfg["owners"] = max_in_flight, {**DEFAULT_CONFIG["builder"], "profile_dir": str(profile)}, ["owner"]
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
  plan_text = f"# Handoff plan: Worker\n\nDesign: `{spec}`\n\n## 1. Issue template\n\n## Global constraints\n- none\n\n## 2. Units\n\n{sections}"
  plan.write_text(plan_text, encoding="utf-8"); put(s.path("plan"), plan_text)
  writes = [["issue", "tracking", "Build", ["superegm:tracking"], "Tracking"]]
  world.gh.issues[TRACKING] = {"number": TRACKING, "id": 1000, "body": "Tracking", "labels": ["superegm:tracking"], "state": "open", "state_reason": None}
  numbers = {u: 7 + i for i, u in enumerate(units)}
  bodies = {}
  for u, n in numbers.items():
    body = BODY.replace("HID", hid).replace("UID", u).replace("SHA", sha).replace("REL", spec.relative_to(repo.resolve()).as_posix()).replace("SEVEN", sha[:7])
    bodies[u] = body
    put(s.path("unit", u), f"{SECTION.replace('UID', u).replace('SPEC', str(spec))}\n## Issue body as posted\n\n{F}markdown\n{body}{F}\n")
    writes.append(["issue", u, f"{u}: Worker", ["superegm:unit"], body])
    world.gh.issues[n] = {"number": n, "id": 1000 + n, "body": fill_numbers(body, numbers, TRACKING), "labels": ["superegm:unit"], "state": "open", "state_reason": None}
  put(s.path("approvals", f"{spec_slug(spec)}.json"), json.dumps({"path": str(spec), "sha256": sha, "commit": git(["rev-parse", "--short", "HEAD"], repo).strip(),
      "runcard": "c0", "review": "r0", "approved_at": "2026-11-03T00:00:00Z", "amended": [], "voided_by": None, "handoff_id": hid}))
  put(s.path("handoffs", hid), json.dumps({"id": hid, "spec": str(spec), "opened_at": "2026-11-03T00:00:00Z", "closed_at": None}))
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


def app_seed(world, monkeypatch, key, tmp_path, **gh):
  """`seed(world)` then the App path: `builder.app` = `APP` in the tree's config, the token variable unset, `SUPEREGM_APP_KEY`
  naming `key`, a fake real `gh` at `tmp_path/bin/gh` (prints `$GH_TOKEN`, then its arguments unless they are `auth token`),
  `shutil.which` answering that path for `gh`, `OPENSSL` for `openssl` and None otherwise, `app_api(monkeypatch)`,
  `github(world, **gh)` and origin's push URL in the SSH form. Returns `(s, card, hid, bodies, <the fake gh's path>)`."""
  s, card, hid, bodies = seed(world)
  cfg = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))
  configure(world, builder={**cfg["builder"], "app": APP})
  monkeypatch.delenv("SUPEREGM_BUILDER_TOKEN", raising=False)
  monkeypatch.setenv("SUPEREGM_APP_KEY", str(key))
  real = tmp_path / "bin/gh"
  real.parent.mkdir(exist_ok=True)
  real.write_text('#!/bin/sh\nif [ "$1 $2" = "auth token" ]; then printf "%s\\n" "$GH_TOKEN"; else printf "%s %s\\n" "$GH_TOKEN" "$*"; fi\n', encoding="utf-8")
  real.chmod(0o755)
  monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: {"gh": str(real), "openssl": OPENSSL}.get(cmd))
  app_api(monkeypatch)
  github(world, **gh)
  git(["remote", "set-url", "--push", "origin", f"git@github.com:{REPO}.git"], world.repo)
  return s, card, hid, bodies, str(real)


def state_of(s):
  return json.loads(s.path("state").read_text(encoding="utf-8"))


def remark(s, world, old, new, uid=UNIT):
  """The marker's spec sha256 `old` rewritten `new` in the unit file, the filing's body and the issue's body."""
  path = s.path("unit", uid)
  put(path, path.read_text(encoding="utf-8").replace(f"spec={old}", f"spec={new}"))
  state = state_of(s)
  for filing in state["filings"]:
    for item in filing["writes"]:
      if item[0] == "issue" and item[1] == uid:
        item[4] = item[4].replace(f"spec={old}", f"spec={new}")
  put(s.path("state"), json.dumps(state))
  issue = world.gh.issues[state["units"][uid]["number"]]
  issue["body"] = issue["body"].replace(f"spec={old}", f"spec={new}")


def launches_of(s, uid=UNIT):
  return json.loads(s.path("launches", f"{uid}.json").read_text(encoding="utf-8"))["launches"]


@pytest.mark.parametrize("path", ["account", "app"])
def test_launch_marks_ready_units_and_records_the_builder_login(world, monkeypatch, key, tmp_path, path):
  s, card, hid, _, _ = app_seed(world, monkeypatch, key, tmp_path) if path == "app" else (*seed(world), None)
  path == "account" and monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  code, out = world.run("launch", "--runcard", card)
  assert code == 0 and out.splitlines()[:2] == ["in flight: none", "marked: U07"], out
  assert state_of(s)["units"][UNIT]["launched"]["runcard"] == card
  rc = json.loads(s.path("runcards", f"{card}.json").read_text(encoding="utf-8"))
  assert rc["builder"][-1] == ({"login": BOT, "email": EMAIL, "token_env": None, "app_id": 12345} if path == "app" else
                               {"login": "builder-bot", "email": "1001+builder-bot@users.noreply.github.com", "token_env": "SUPEREGM_BUILDER_TOKEN", "app_id": None})
  assert git(["rev-parse", "refs/superegm/base"], world.repo).strip() == git(["rev-parse", "HEAD"], world.repo).strip()
  assert "ghp_builder" not in out and not any("ghp_builder" in " ".join(c) for c in world.gh.calls)
  assert "U07 marked for launch" in s.path("journal").read_text(encoding="utf-8")


def push_to_origin(world, rel, text):
  path = world.repo / rel
  path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")
  git(["add", "-A"], world.repo); git(["commit", "-qm", "edit"], world.repo); git(["push", "-q", "origin", BASE], world.repo)


@pytest.mark.parametrize("case, reason", [
  ("classic", None),
  ("spec", "spec at origin/main is neither the approved bytes nor a later link of the approval chain"),
  ("config", ".superegm/config.json is absent at origin/main"),
  ("workflow", "origin/main carries no workflow triggered on pull_request"),
  ("no-token", "SUPEREGM_BUILDER_TOKEN is not set"),
  ("own-login", "the builder token is the elephant's own login (owner)"),
  ("no-restriction", "base branch main: updates are not restricted to the owner (no classic restrictions, no active ruleset update rule)"),
  ("role-bypass", "base branch main: ruleset base lets the builder's role (write) bypass"),
  ("team-bypass", "base branch main: ruleset base lets team #9 bypass, not config.owner_team (unset)"),
  ("no-force-push", "superegm/**: no active ruleset forbids force-push (non_fast_forward)"),
  ("no-deletion", "superegm/**: no active ruleset forbids deletion"),
  ("no-owners", "config.owners is empty: set the owner logins in .superegm/config.json"),
  ("builder-owner", "the builder token's login (builder-bot) is in config.owners"),
  ("classic-stranger", "base branch main: classic restriction lets stranger push: not in config.owners"),
  ("team-owner", None),
  ("team-other", "base branch main: ruleset base lets team #8 bypass, not config.owner_team (example-org/owners)"),
  ("team-missing", "config.owner_team example-org/owners does not exist"),
  ("team-member", "base branch main: ruleset base lets example-org/owners bypass, and builder-bot is a member"),
  ("app-admin-bypass", None), ("app-rulesets", None),       # the admin-role bypass; then beside SUPEREGM_RULESET
  ("app-both-set", "builder.app is set (SUPEREGM_APP_KEY) and SUPEREGM_BUILDER_TOKEN is also set: one identity per repository"),
  ("app-no-openssl", "openssl is not on this machine's PATH"),
  ("app-bypass", "base branch main: ruleset base lets the App (#12345) bypass"), ("app-classic", "base branch main: classic restriction lets app superegm-builder push"),
])
def test_launch_refuses_each_precondition(world, monkeypatch, key, tmp_path, case, reason):
  if case.startswith("app-"):
    s, card, hid, _, _ = app_seed(world, monkeypatch, key, tmp_path, rulesets=[RULESET, SUPEREGM_RULESET] if case == "app-rulesets" else (RULESET,))
  else:
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
  if case == "no-owners":
    configure(world, owners=[])
  if case == "builder-owner":
    configure(world, owners=["owner", "builder-bot"])
  if case == "classic-stranger":
    github(world, rulesets=[], classic={"restrictions": {"users": [{"login": "owner"}, {"login": "stranger"}], "teams": [], "apps": []}})
  if case in ("team-owner", "team-other", "team-missing", "team-member"):
    configure(world, owner_team="example-org/owners")
    github(world, rulesets=bypass({"actor_type": "Team", "actor_id": 8 if case == "team-other" else 9, "bypass_mode": "always"}),
           team_id=None if case == "team-missing" else 9, member=case == "team-member")
  if case == "app-both-set":
    monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  if case == "app-no-openssl":
    monkeypatch.setattr(shutil, "which", lambda cmd, *a, **k: None)
  if case == "app-bypass":
    github(world, rulesets=bypass({"actor_type": "Integration", "actor_id": 12345, "bypass_mode": "always"}))
  if case == "app-classic":
    github(world, rulesets=[], classic={"restrictions": {"users": [{"login": "owner"}], "teams": [], "apps": [{"slug": "superegm-builder"}]}})
  code, out = world.run("launch", "--runcard", card)
  if reason is None:
    assert code == 0 and "marked: U07" in out, out
    return
  assert code == 1 and f"launch: {reason}" in out, out
  assert "launched" not in state_of(s)["units"][UNIT]


entry = lambda hid, sha: {"sha256": sha, "commit": "c", "runcard": "c0", "review": "r0", "approved_at": "t", "handoff_id": hid, "kind": "opening", "voided_by": None, "escalated": []}

@pytest.mark.parametrize("at_origin, ok", [("approved", True), ("later", True), ("earlier", False), ("other", False)])
def test_launch_accepts_the_approved_bytes_or_a_later_link(world, monkeypatch, at_origin, ok):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  spec = Path(state_of(s)["design"]["path"]); rel = spec.relative_to(world.repo).as_posix()
  texts = {"earlier": "earlier\n", "approved": spec.read_text(encoding="utf-8"), "later": spec.read_text(encoding="utf-8") + "\nlater\n", "other": "other\n"}
  entries = [entry(f"sample-{k}", hashlib.sha256(texts[k].encode()).hexdigest()) for k in ("earlier", "approved", "later")]
  entries[1]["handoff_id"] = hid
  put(s.path("approvals", "sample"), json.dumps({"path": str(spec), "entries": entries}))
  at_origin != "approved" and push_to_origin(world, rel, texts[at_origin])
  code, out = world.run("launch", "--runcard", card)
  assert (code == 0) is ok and ("launch: spec at origin/main is neither the approved bytes nor a later link of the approval chain" in out) is not ok


@pytest.mark.parametrize("case", ["entry", "rewritten", "none"])
def test_launch_builder_copies_the_cited_range_at_the_markers_sha(world, monkeypatch, spawn_fake, case):
  s, card, hid, bodies = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  spec = Path(state_of(s)["design"]["path"]); sha = hashlib.sha256(spec.read_bytes()).hexdigest()
  if case != "entry":
    record = json.loads(s.path("approvals", "sample").read_text(encoding="utf-8")); record["commit"] = "0" * 40
    put(s.path("approvals", "sample"), json.dumps(record))
  case == "none" and remark(s, world, sha, "1" * 64)
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)
  if case == "none":
    assert code == 1 and "launch-builder: spec range: no commit holds 1111111" in out and not s.path("worktrees", UNIT, "r1").exists()
    return
  prompt = s.path("launches", f"{UNIT}_r1_prompt.md").read_text(encoding="utf-8")
  assert "# Spec range\n\n" + "\n".join(spec.read_text(encoding="utf-8").splitlines()[0:2]) + "\n" in prompt


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


def test_launch_counts_a_launch_after_a_clean_round_in_flight(world, monkeypatch):
  """Defect 2: the clean verdict belongs to launch 1 (§11.1's predicate names the launch count); launch 2 holds the slot."""
  s, card, hid, _ = seed(world, units=("U07", "U08"), max_in_flight=1)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert "marked: U07" in world.run("launch", "--runcard", card)[1]
  launched(s, "U07", "exited 0")
  foreman(s, "U07", [{"round": 1, "runcard": card, "launch": 1, "head": "a" * 40, "phase": "posted", "dispatch_id": "d1", "outcome": "clean", "posted_at": "2026-11-03T01:00:00Z"}])
  launched(s, "U07", "running", rnd=2)
  code, out = world.run("launch", "--runcard", card)
  assert "in flight: U07" in out and "marked: none" in out, out


# `insteadOf`, not `pushInsteadOf`: git applies the latter only to a remote's `url` when it has no `pushurl`, so an explicit SSH push
# URL (the one these tests set on origin) would stay SSH and fail closed under GIT_SSH_COMMAND=false; `insteadOf` rewrites both.
ENTRIES = [("credential.https://github.com.helper", ""), ("credential.https://github.com.helper", "!{gh} auth git-credential"), ("url.https://github.com/.insteadOf", "git@github.com:"),
           ("url.https://github.com/.insteadOf", "ssh://git@github.com/"), ("core.askPass", ""), ("user.name", "{login}"), ("user.email", "{email}")]
PAIRS = [("GIT_CONFIG_GLOBAL", "/dev/null"), ("GIT_CONFIG_SYSTEM", "/dev/null"), ("GIT_SSH_COMMAND", "false"), ("GIT_TERMINAL_PROMPT", "0"), ("GIT_CONFIG_COUNT", "7"),
         *(p for i, (k, v) in enumerate(ENTRIES) for p in ((f"GIT_CONFIG_KEY_{i}", k), (f"GIT_CONFIG_VALUE_{i}", v)))]


def test_launch_frees_the_slot_of_a_unit_pending_a_decision(world, monkeypatch):
  s, card, hid, _ = seed(world, units=("U07", "U08"), max_in_flight=1); monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert "marked: U07" in world.run("launch", "--runcard", card)[1]; launched(s, "U07", "exited 0")
  data = {"dispatch_id": "d1", "rounds": [], "decisions": [{"id": "q1", "point": 3, "source": "launch 1", "question": "x"}], "rulings": []}; put(s.path("foreman", "U07"), json.dumps(data))
  out = world.run("launch", "--runcard", card)[1]; assert "in flight: none" in out and "marked: U08" in out
  put(s.path("foreman", "U07"), json.dumps({**data, "rulings": [{"decision": "q1", "ruling": "relaunch"}]})); assert "in flight: U07, U08" in world.run("launch", "--runcard", card)[1]


def test_launch_reads_a_partly_ruled_owner_decision_as_pending(world, monkeypatch):
  s, card, hid, _ = seed(world, units=("U07", "U08"), max_in_flight=1); monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert "marked: U07" in world.run("launch", "--runcard", card)[1]; launched(s, "U07", "exited 0")
  owner = {"id": "q1", "point": 1, "source": "launch 1", "question": "owner: f1 f2", "options": ["f1 allowed", "f2 allowed"]}
  data = {"dispatch_id": "d1", "rounds": [], "decisions": [owner], "rulings": [{"decision": "q1", "ruling": "f1 — fine"}]}; put(s.path("foreman", "U07"), json.dumps(data))
  out = world.run("launch", "--runcard", card)[1]; assert "in flight: none" in out and "marked: U08" in out
  put(s.path("foreman", "U07"), json.dumps({**data, "rulings": data["rulings"] + [{"decision": "q1", "ruling": "f2 — fine"}]}))
  assert "in flight: U07, U08" in world.run("launch", "--runcard", card)[1]


def test_launch_builder_round_1_prepares_worktree_prompt_and_command(world, monkeypatch, spawn_fake):
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
  line = launches_of(s)[-1]["command"]
  wt, branch = s.path("worktrees", UNIT, "r1"), f"superegm/{hid}/U07"
  assert wt.is_dir() and git(["branch", "--show-current"], wt).strip() == branch
  assert git(["rev-parse", "HEAD"], wt).strip() == git(["rev-parse", "refs/superegm/base"], world.repo).strip()
  prompt_file = s.path("launches", f"{UNIT}_r1_prompt.md")
  prompt = prompt_file.read_text(encoding="utf-8")
  orders = orders_text(DEFAULT_CONFIG["builder"]["allowed_tools"], "/usr/local/bin/gh")
  assert prompt.startswith(f"# Issue #{ISSUE} — U07\n\n{world.gh.issues[ISSUE]['body']}")
  assert f"\n\n---\n\n# Builder orders\n\n{orders}" in prompt
  assert f"\n\n---\n\n# Comments on issue #{ISSUE}\n\n## owner · comment 1\n**Decision D1:** (a) five\n\n## builder-bot · comment 3\n**Deviation (other):** renamed a fixture\n\n## owner · comment 4\n**Ruling:** (3) (a) — proceed\n" in prompt
  assert "forged" not in prompt and "looks good" not in prompt and "# Review comments" not in prompt
  cfg = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]
  result = s.path("launches", f"{UNIT}_r1_result.json")
  pairs = " ".join(f"{k}='{v.format(gh='/usr/local/bin/gh', login='builder-bot', email='1001+builder-bot@users.noreply.github.com')}'" for k, v in PAIRS)
  assert line.startswith(f"cd '{wt}' && env -u GIT_ASKPASS -u SSH_ASKPASS -u GITHUB_TOKEN CLAUDE_CONFIG_DIR='{cfg['profile_dir']}' ENABLE_CLAUDEAI_MCP_SERVERS=false GH_TOKEN=\"$SUPEREGM_BUILDER_TOKEN\" SUPEREGM_ROLE=builder SUPEREGM_RUNCARD='{card}' {pairs} claude -p "), line
  mcp_file = s.path("launches", f"{UNIT}_r1_mcp.json")
  assert f" claude -p \"$(cat '{prompt_file}')\" --model '{cfg['model']}' --permission-mode '{cfg['permission_mode']}' --setting-sources user --mcp-config '{mcp_file}' --strict-mcp-config --allowedTools '" in line, line
  tools = line.split("--allowedTools '")[1].split("'")[0].split(",")
  assert tools == [t.replace("Bash(gh ", "Bash(/usr/local/bin/gh ") for t in cfg["allowed_tools"]] + [f"Bash(git push origin {branch}:*)"]
  assert line.endswith(f"' --output-format json > '{result}'; echo $? > '{result}.exit'")
  assert "ghp_builder" not in out
  tree = git(["rev-parse", "refs/superegm/base^{tree}"], world.repo).strip()
  unit_file = s.path("orient_unit", f"{UNIT}.md").read_text(encoding="utf-8")
  assert unit_file.startswith(f"orient: tree {tree} · graphify: not installed · trimmed: nothing\n## src/worker.py (create)\nsiblings: none\ntests: none\n")
  cited = "\n".join(Path(state_of(s)["design"]["path"]).read_text(encoding="utf-8").splitlines()[0:2]) + "\n"  # the body's `Spec:` range
  assert f"\n\n---\n\n# Builder orders\n\n{orders}\n\n---\n\n# Orient\n\n{unit_file}\n\n---\n\n# Spec range\n\n{cited}\n\n---\n\n# Comments on issue #{ISSUE}\n" in prompt
  assert "read the `# Orient` section before Step 1" in orders


@pytest.mark.parametrize("case, reason", [("scripts", None), ("whitespace", "artifacts_dir {store} holds whitespace")])
def test_launch_builder_writes_the_token_helper_and_the_gh_shim(world, monkeypatch, key, tmp_path, spawn_fake, case, reason):
  s, card, hid, _, _ = app_seed(world, monkeypatch, key, tmp_path)
  assert world.run("launch", "--runcard", card)[0] == 0
  if case == "whitespace": s.root.rename(tmp_path / "art ifacts"); configure(world, artifacts_dir=str(tmp_path / "art ifacts")); s = store(world.repo)
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)
  shim = s.path("launches", f"{UNIT}_r1_bin", "gh")
  if reason:
    assert code == 1 and f"launch-builder: {reason.format(store=s.root)}" in out and not s.path("worktrees", UNIT).exists() and not shim.parent.exists(), out
    return
  helper, line = shim.parent / "superegm-token", launches_of(s)[-1]["command"]
  assert code == 0 and f" builder-token --repo '{REPO}' --app-id 12345 --key-env 'SUPEREGM_APP_KEY' --openssl '{OPENSSL}'" in helper.read_text(encoding="utf-8"), out
  assert " GH_TOKEN=superegm-no-token " in line and f"'!{shim} auth git-credential'" in line
  run = lambda *a: subprocess.run([str(shim), *a], capture_output=True, text=True, env={**os.environ, "GH_TOKEN": "superegm-no-token"})
  helper.write_text("#!/bin/sh\nprintf ghs_minted\n", encoding="utf-8")
  assert (run("pr", "create", "--draft").stdout, run("auth", "git-credential", "get").stdout) == ("ghs_minted pr create --draft\n", "ghs_minted auth git-credential get\n")
  helper.write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
  assert run("pr", "create").returncode == 1 and run("auth", "git-credential", "store").stdout == "superegm-no-token auth git-credential store\n"


def test_launch_builder_starts_the_launch_as_its_one_behaviour(world, monkeypatch, spawn_fake):
  s, card, hid, _ = seed(world); monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder"); monkeypatch.setattr(superegm, "boot_id", lambda: "boot-1")
  assert world.run("launch", "--runcard", card)[0] == 0 and world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)[1].strip().endswith("U07 launch 1 running (pid 4242)")
  entry, (command, log, env) = launches_of(s)[0], SPAWNED[0]
  assert command == ["/bin/sh", "-c", entry["command"]] and log == s.path("launches", f"{UNIT}_r1.log") and (entry["boot_id"], entry["pid"], entry["status"]) == ("boot-1", 4242, "running")
  assert "record-launch: --exit is required: launch-builder records the launch" in world.run("record-launch", "--unit", UNIT, "--runcard", card)[1]
  monkeypatch.setattr(superegm, "boot_id", lambda: "boot-2"); assert world.run("launch-builder", "--unit", UNIT, "--round", 2, "--runcard", card)[0] == 0
  assert [e["status"] for e in launches_of(s)] == ["interrupted (reboot)", "running"]


@pytest.mark.parametrize("case, reason", [
  ("unmarked", "U07 is not marked by launch"),
  ("running", "U07 launch 1 is not terminal"),
  ("count", "--round 3 is not the next launch count (2)"),
  ("own-login", "the builder token is the elephant's own login (owner)"),
  ("profile-missing", "builder profile"),
  ("profile-claude-md", "holds CLAUDE.md"),
  ("profile-plugins", "holds plugins"),
  ("profile-hooks", "holds hooks"),
  ("body", "issue #7 body differs from the filed body"),
  ("orient", "orient: U07 is not in the plan: run graph --plan first"),
])
def test_launch_builder_refuses_each_precondition(world, monkeypatch, spawn_fake, case, reason):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  profile = Path(json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]["profile_dir"])
  rnd = 1
  if case != "unmarked":
    assert world.run("launch", "--runcard", card)[0] == 0
  if case == "running":
    launched(s, UNIT, "running"); rnd = 2
  if case == "count":
    launched(s, UNIT, "exited 0"); rnd = 3
  if case == "own-login":
    github(world, builder="owner")
  if case == "profile-missing":
    shutil.rmtree(profile)
  if case == "profile-claude-md":
    (profile / "CLAUDE.md").write_text("x\n", encoding="utf-8")
  if case == "profile-plugins":
    (profile / "plugins/synced/bucket-1/pendo").mkdir(parents=True)  # an account plugin synced on sign-in
  if case == "profile-hooks":
    (profile / "settings.json").write_text('{"hooks": {"SessionStart": []}}', encoding="utf-8")
  if case == "body":
    world.gh.issues[ISSUE]["body"] += "\nedited by hand\n"
  if case == "orient":
    s.path("plan").write_text(s.path("plan").read_text(encoding="utf-8").replace("### U07:", "### U99:"), encoding="utf-8")
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", rnd, "--runcard", card)
  assert code == 1 and "launch-builder: " in out and reason in out, out
  assert not s.path("worktrees", UNIT).exists() and not s.path("launches", f"{UNIT}_r{rnd}_prompt.md").exists()


@pytest.mark.parametrize("key, present", [(".github/PR_BLOCK.md", True), (".github/PR_BLOCK.md", False), (None, False)])
def test_launch_builder_appends_the_pr_block(world, monkeypatch, key, spawn_fake, present):
  if present:
    (world.repo / ".github").mkdir(exist_ok=True); (world.repo / ".github/PR_BLOCK.md").write_text("<!-- coord/v1 task=7 -->\n", encoding="utf-8")
  s, card, hid, _ = seed(world)                       # commits the tree and clones origin from it
  configure(world, pr_block_file=key)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)
  if key and not present:
    assert code == 1 and "launch-builder: pr_block_file .github/PR_BLOCK.md is absent at refs/superegm/base" in out, out
    assert not s.path("worktrees", UNIT).exists() and not s.path("launches", f"{UNIT}_r1_prompt.md").exists()
    return
  assert code == 0, out
  orders = orders_text(DEFAULT_CONFIG["builder"]["allowed_tools"], "/usr/local/bin/gh")
  prompt = s.path("launches", f"{UNIT}_r1_prompt.md").read_text(encoding="utf-8")
  if key:
    assert f"\n\n---\n\n# Builder orders\n\n{orders}\n\n---\n\n# PR block\n\n<!-- coord/v1 task=7 -->\n\n\n---\n\n# " in prompt
  else:
    assert "\n\n---\n\n# PR block\n\n" not in prompt
  assert "paste the `# PR block` section into the PR body right after the audit-trail line, before the DoD results" in orders


def test_launch_builder_carries_the_audit_trail_line(world, monkeypatch, spawn_fake):
  """Owner ruling 2026-11-04: the PR body's line after the unit id is `Launched by <owner login> · run card <id>
  · unit U<n> · handoff <handoff id>`, the login of the session that ran `launch` (not the builder's), with no `@`
  so it mentions nobody; the prompt carries it under `# Audit trail`, the orders keep it verbatim, the mention scan passes it."""
  from superegm.launch_builder import AUDIT_LINE
  from superegm.scan import scan_text
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  assert state_of(s)["units"][UNIT]["launched"]["by"] == "owner"       # `gh api user` in the launching session
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)
  assert code == 0, out
  assert AUDIT_LINE == "Launched by {owner} · run card {runcard} · unit {unit} · handoff {handoff}"
  line = f"Launched by owner · run card {card} · unit U07 · handoff {hid}"
  prompt = s.path("launches", f"{UNIT}_r1_prompt.md").read_text(encoding="utf-8")
  assert f"\n\n---\n\n# Audit trail\n\n{line}\n\n---\n\n# Builder orders\n\n" in prompt
  assert "@" not in line and "builder-bot" not in line
  cfg = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))
  assert scan_text(line, cfg, "body") == []
  orders = (ROOT / "skills/wave/references/builder_orders.md").read_text(encoding="utf-8")
  assert "line 2 is the `Launched by` line of your prompt's `# Audit trail` section, kept verbatim" in orders
  # A unit marked by a pre-upgrade `launch` (no `launched.by`): the line says `unknown`; launch-builder does not raise.
  Path(launches_of(s)[0]["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  head = git(["rev-parse", "refs/superegm/base"], world.repo).strip()
  git(["update-ref", f"refs/pull/{PR}/head", head], world.repo.parent / "origin.git")
  state = state_of(s); del state["units"][UNIT]["launched"]["by"]; state["units"][UNIT]["pr"] = {"number": PR, "head": head, "base_ref": BASE}
  s.path("state").write_text(json.dumps(state), encoding="utf-8")
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 2, "--runcard", card)
  assert code == 0, out
  assert f"# Audit trail\n\nLaunched by unknown · run card {card} · unit U07 · handoff {hid}\n" in s.path("launches", f"{UNIT}_r2_prompt.md").read_text(encoding="utf-8")


def test_launch_builder_round_2_detaches_the_earlier_worktree_and_carries_the_review(world, monkeypatch, spawn_fake):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  assert world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)[0] == 0
  r1, branch = s.path("worktrees", UNIT, "r1"), f"superegm/{hid}/U07"
  (r1 / "src").mkdir(); (r1 / "src/worker.py").write_text("def w(): pass\n", encoding="utf-8")
  git(["add", "-A"], r1); git(["commit", "-qm", "feat(S1): w"], r1); git(["push", "-q", "origin", branch], r1)
  head = git(["rev-parse", "HEAD"], r1).strip()
  git(["update-ref", f"refs/pull/{PR}/head", head], world.repo.parent / "origin.git")
  (r1 / "scratch.txt").write_text("unsaved\n", encoding="utf-8")
  Path(launches_of(s)[0]["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  assert world.run("record-launch", "--unit", UNIT, "--exit", 0, "--runcard", card)[0] == 0
  make_pr(world.gh, PR, head, branch=branch, closes=[(REPO, ISSUE)])
  state = state_of(s); state["units"][UNIT]["pr"] = {"number": PR, "head": head, "base_ref": BASE}
  s.path("state").write_text(json.dumps(state), encoding="utf-8")
  world.gh.reviews[PR] = [{"id": 9, "user": {"login": "owner"}, "commit_id": head, "body": "**Review round 1 (head " + head[:7] + ")**\n- change-review-1-1 | high | src/worker.py:1 | regression: no | w does nothing"},
                          {"id": 10, "user": {"login": "builder-bot"}, "commit_id": head, "body": "self review"}]
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 2, "--runcard", card)
  assert code == 0, out
  assert git(["branch", "--show-current"], r1).strip() == "" and (r1 / "scratch.txt").is_file()   # detached, nothing removed
  r2 = s.path("worktrees", UNIT, "r2")
  assert git(["branch", "--show-current"], r2).strip() == branch and git(["rev-parse", "HEAD"], r2).strip() == head
  prompt = s.path("launches", f"{UNIT}_r2_prompt.md").read_text(encoding="utf-8")
  unit_file = s.path("orient_unit", f"{UNIT}.md").read_text(encoding="utf-8")
  assert unit_file.startswith(f"orient: tree {git(['rev-parse', head + '^{tree}'], world.repo).strip()}") and "## src/worker.py (create)\ndef w(): pass\ntests: none\n" in unit_file
  assert f"\n\n---\n\n# Review comments on PR #{PR}\n\n## owner · review 9 on {head[:7]}\n**Review round 1" in prompt and "self review" not in prompt
  assert launches_of(s)[-1]["command"].startswith(f"cd '{r2}' && env ")


def test_launch_builder_relaunches_from_the_local_branch_when_no_pr_is_recorded(world, monkeypatch, spawn_fake):
  """Decision point 3's `relaunch` after an exit with no PR (spec sections 11, 13.2): round 2 is accepted without a
  recorded PR and starts from the retained local unit branch (the earlier worktree detached, nothing removed), the
  orient covering that tree, so the new launch opens the first PR."""
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  assert world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)[0] == 0
  r1, branch = s.path("worktrees", UNIT, "r1"), f"superegm/{hid}/U07"
  (r1 / "src").mkdir(); (r1 / "src/worker.py").write_text("def w(): pass\n", encoding="utf-8")
  git(["add", "-A"], r1); git(["commit", "-qm", "feat(S1): w"], r1)      # committed, never pushed: the builder exited before its PR
  head = git(["rev-parse", "HEAD"], r1).strip()
  Path(launches_of(s)[0]["result_file"] + ".exit").write_text("1\n", encoding="utf-8")
  assert world.run("record-launch", "--unit", UNIT, "--exit", 1, "--runcard", card)[0] == 0
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 2, "--runcard", card)
  assert code == 0, out
  assert git(["branch", "--show-current"], r1).strip() == "" and (r1 / "src/worker.py").is_file()   # detached, nothing removed
  r2 = s.path("worktrees", UNIT, "r2")
  assert git(["branch", "--show-current"], r2).strip() == branch and git(["rev-parse", "HEAD"], r2).strip() == head
  assert "# Review comments" not in s.path("launches", f"{UNIT}_r2_prompt.md").read_text(encoding="utf-8")
  assert "## src/worker.py (create)\ndef w(): pass\n" in s.path("orient_unit", f"{UNIT}.md").read_text(encoding="utf-8")


def test_launch_builder_loads_the_builder_profile_settings_only():
  """A builder is a session in the target repository, so `claude -p` would run that repository's project settings and
  SessionStart hooks; the launched command carries `--setting-sources user`: the builder profile's settings alone (spec section 11)."""
  from superegm.launch_builder import command_line
  cfg = {"builder": {**DEFAULT_CONFIG["builder"], "profile_dir": "/p"}}
  line = command_line(cfg, "/wt", "/prompt.md", "/result.json", "wave-0001", ["Read"], "/usr/local/bin/gh", "b", "b@x", [], "/m.json")
  assert " --permission-mode 'acceptEdits' --setting-sources user --mcp-config '/m.json' --strict-mcp-config --allowedTools 'Read' " in line, line


def test_command_line_carries_the_dirs_the_mcp_file_and_the_switch():
  from superegm.launch_builder import command_line
  cfg = {"builder": {**DEFAULT_CONFIG["builder"], "profile_dir": "/p"}}
  call = lambda dirs, mcp, **kw: command_line(cfg, "/wt", "/prompt.md", "/result.json", "wave-0001", ["Read"], "/usr/local/bin/gh", "b", "b@x", dirs, mcp, **kw)
  line = call(["/c/ponytail/5.3.3", "/c/x/1"], "/l/U07_r1_mcp.json")
  assert " CLAUDE_CONFIG_DIR='/p' ENABLE_CLAUDEAI_MCP_SERVERS=false GH_TOKEN=" in line, line
  assert " --setting-sources user --plugin-dir '/c/ponytail/5.3.3' --plugin-dir '/c/x/1' --mcp-config '/l/U07_r1_mcp.json' --strict-mcp-config --allowedTools 'Read' " in line, line
  assert " --setting-sources user --mcp-config '/m.json' --strict-mcp-config --allowedTools 'Read' " in call([], "/m.json")
  assert " --session-id 's' " in call([], "/m.json", session_id="s") and " --session-id" not in call([], "/m.json")


@pytest.mark.parametrize("case", ["none", "listed", "missing"])
def test_launch_builder_writes_the_mcp_file_and_the_plugins_record(world, monkeypatch, tmp_path, case):
  s, card, hid, _ = seed(world)
  home, d = elephant(tmp_path, monkeypatch, ["user"] if case == "listed" else ["project"], {"hooks/hooks.json": THREE})
  cfg = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))["builder"]
  rules = ["Skill(ponytail:ponytail)", "Skill(ponytail:ponytail *)", "mcp__context7__*"]
  case != "none" and configure(world, builder={**cfg, "plugins": [PONY], "mcp": MCP, "allowed_tools": [*cfg["allowed_tools"], *rules]})
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder"); monkeypatch.setattr(launch_builder, "start_detached", lambda command, log, env: 4242)
  assert world.run("launch", "--runcard", card)[0] == 0
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)
  record, mcp, managed = (s.path("launches", f"{UNIT}_r1_{n}.json") for n in ("plugins", "mcp", "managed"))
  if case == "missing":
    assert code == 1 and f"launch-builder: plugin {PONY} not installed" in out and not record.exists() and not mcp.exists() and not s.path("worktrees", UNIT).exists(), out
    return
  listed = case == "listed"
  assert code == 0 and not managed.exists() and json.loads(mcp.read_text(encoding="utf-8")) == {"mcpServers": MCP if listed else {}}, out
  assert json.loads(record.read_text(encoding="utf-8")) == {"plugins": [{"id": PONY, "version": "5.3.3", "dir": str(d), "hooks": THREE}] if listed else [], "managed": [], "mcp": ["context7"] if listed else []}
  assert f"Your skills, named by your allow-list: {'ponytail:ponytail' if listed else 'none'}. You have no subagents" in s.path("launches", f"{UNIT}_r1_prompt.md").read_text(encoding="utf-8")
  assert skill_names(["Read", *rules, "Skill(superegm:orient)"]) == ["ponytail:ponytail", "superegm:orient"]


@pytest.mark.parametrize("path", ["app", "account"])
def test_launch_builder_derives_the_app_identity_on_a_fresh_card(world, monkeypatch, key, tmp_path, spawn_fake, path):
  """A re-typed `wave` relaunching while `launch` is held off (a capacity gate): its card has no `builder` entry. On the
  App path the identity is derived from the config as every reader does (spec section 11): `<slug>[bot]` and the bot
  user's noreply address; the token path still refuses, its login being read by `launch` alone."""
  s, card, hid, _, _ = app_seed(world, monkeypatch, key, tmp_path) if path == "app" else (*seed(world), None)
  path == "account" and monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  code, out = world.run("runcard", "open", "--skill", "wave", "--artifact", str(next(world.repo.glob("docs/**/*.md"))))
  fresh = out.split()[-1]
  assert code == 0 and "builder" not in json.loads(s.path("runcards", f"{fresh}.json").read_text(encoding="utf-8")), out
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", fresh)
  if path == "account":
    assert code == 1 and "launch-builder: the wave card records no builder: run launch first" in out, out
    return
  assert code == 0, out
  assert f"GIT_CONFIG_KEY_5='user.name' GIT_CONFIG_VALUE_5='{BOT}' GIT_CONFIG_KEY_6='user.email' GIT_CONFIG_VALUE_6='{EMAIL}'" in launches_of(s)[-1]["command"], out


import superegm  # the harness reloads the package per test: read HandoffError at call time
from superegm.launch_builder import allowed_tools

@pytest.mark.parametrize("configured, expect", [
  (["Read", "Edit", "Bash(git add:*)"], ["Read", "Edit", "Bash(git add:*)", "Bash(git push origin superegm/h/U07:*)", "Bash(pytest:*)"]),
  (["Bash(pytest:*)", "Read"], ["Bash(pytest:*)", "Read", "Bash(git push origin superegm/h/U07:*)"]),
  (["Read", "Agent"], "Agent"),
  (["Read", "Skill"], "Skill"),
  (["Read", "Bash"], "Bash"),
  (["Read", "Bash(*)"], "Bash(*)"),
])
def test_allowed_tools_composition(configured, expect):
  body = BODY.replace("HID", "h").replace("UID", "U07")
  if isinstance(expect, str):
    with pytest.raises(superegm.HandoffError, match=re.escape(f"allowed_tools carries {expect}: a builder never spawns, never invokes skills, never runs unrestricted Bash")):
      allowed_tools(configured, "superegm/h/U07", body, "/usr/local/bin/gh")
  else:
    assert allowed_tools(configured, "superegm/h/U07", body, "/usr/local/bin/gh") == expect


def test_interrupt_records_a_launch_or_marks_a_prepared_round(world):
  s, card, hid, _ = seed(world)
  launched(s, UNIT, "running")
  foreman(s, UNIT, [{"round": 1, "runcard": card, "launch": 1, "head": "a" * 40, "phase": "prepared", "dispatch_id": "d1", "outcome": None, "posted_at": None}])
  code, out = world.run("runcard", "open", "--skill", "interrupt", "--artifact", UNIT)
  assert code == 0, out
  icard = out.split()[-1]
  code, out = world.run("interrupt", "--unit", UNIT, "--launch", 1, "--runcard", icard)
  assert code == 0 and out.strip() == "U07 launch 1 interrupted" and launches_of(s)[0]["status"] == "interrupted"
  code, out = world.run("interrupt", "--unit", UNIT, "--launch", 1, "--runcard", icard)
  assert code == 1 and "interrupt: U07 launch 1 is already terminal (interrupted)" in out
  code, out = world.run("interrupt", "--unit", UNIT, "--round", 1, "--runcard", icard)
  rounds = json.loads(s.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"]
  assert code == 0 and (rounds[0]["phase"], rounds[0]["outcome"]) == ("collected", "not run (interrupted: owner)")
  code, out = world.run("interrupt", "--unit", UNIT, "--round", 1, "--runcard", icard)
  assert code == 1 and "interrupt: U07 round 1 is not a prepared round (collected)" in out
  code, out = world.run("interrupt", "--unit", UNIT, "--round", 2, "--runcard", icard)
  assert code == 1 and "interrupt: U07 has no round 2" in out
  journal = s.path("journal").read_text(encoding="utf-8")
  assert "U07 launch 1 interrupted" in journal and "U07 round 1 interrupted: owner" in journal


def test_clean_refuses_until_terminal_then_removes_what_it_can_prove(world, monkeypatch, spawn_fake):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  assert world.run("launch", "--runcard", card)[0] == 0
  assert world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card)[0] == 0
  r1 = s.path("worktrees", UNIT, "r1")
  code, out = world.run("runcard", "open", "--skill", "clean", "--artifact", UNIT)
  ccard = out.split()[-1]
  code, out = world.run("clean", "--unit", UNIT, "--runcard", ccard)
  assert code == 1 and "clean: U07 launch 1 is not terminal" in out and r1.is_dir()
  Path(launches_of(s)[0]["result_file"] + ".exit").write_text("0\n", encoding="utf-8")
  assert world.run("record-launch", "--unit", UNIT, "--exit", 0, "--runcard", card)[0] == 0
  foreman(s, UNIT, [{"round": 1, "runcard": card, "launch": 1, "head": "a" * 40, "phase": "prepared", "dispatch_id": "d1", "outcome": None, "posted_at": None}])
  code, out = world.run("clean", "--unit", UNIT, "--runcard", ccard)
  assert code == 1 and "clean: U07 round 1 is not terminal (prepared)" in out and r1.is_dir()
  foreman(s, UNIT, [{"round": 1, "runcard": card, "launch": 1, "head": "a" * 40, "phase": "posted", "dispatch_id": "d1", "outcome": "clean", "posted_at": "2026-11-03T01:00:00Z"}])
  review = s.path("review", UNIT, f"pr{PR}")
  review.parent.mkdir(parents=True, exist_ok=True)
  git(["worktree", "add", "-q", "--detach", str(review), "HEAD"], world.repo)
  git(["update-ref", f"refs/superegm/pr/{PR}", "HEAD"], world.repo)
  (review / "scratch.txt").write_text("unsaved\n", encoding="utf-8")
  (r1 / "scratch.txt").write_text("unsaved\n", encoding="utf-8")
  stray = s.path("worktrees", UNIT, "r9")
  git(["worktree", "add", "-q", "--detach", str(stray), "HEAD"], world.repo)
  code, out = world.run("clean", "--unit", UNIT, "--runcard", ccard)
  assert code == 1 and "uncommitted changes" in out and review.is_dir() and r1.is_dir()   # EGM's dirty refusal on a review worktree; nothing removed
  (review / "scratch.txt").unlink()
  code, out = world.run("clean", "--unit", UNIT, "--runcard", ccard)
  assert code == 0, out
  assert not review.exists() and not r1.exists()                      # a builder worktree goes dirty or not: the typed skill is the owner's decision
  assert stray.is_dir() and f"kept {stray}: no launch records it" in out   # keeps what it cannot prove
  assert subprocess.run(["git", "-C", str(world.repo), "rev-parse", "--verify", "-q", f"refs/superegm/pr/{PR}"], capture_output=True).returncode != 0
  assert "worktrees" not in git(["worktree", "list", "--porcelain"], world.repo).replace(str(stray), "")
  assert "U07 cleaned" in s.path("journal").read_text(encoding="utf-8")


from superegm.launch_builder import DOD_RESULT_RE

def test_builder_orders_carry_the_discipline_and_the_dod_results_form():
  text = (ROOT / "skills/wave/references/builder_orders.md").read_text(encoding="utf-8")
  assert text.startswith("<!-- From superpowers 7.0.0 (MIT); modified by SuperEGM (gsVAM), 2026: the implementer prompt, receiving-code-review and test-driven-development absorbed into the builder orders. -->\n")
  for form in ("follow the Steps in order", "test first", "one `test(S<n>)` commit then one `feat(S<n>)` commit per Step",
               "paste each item's output in the PR body under its item number", "`git push origin <branch>`", "never to any other branch",
               "**draft** pull request", "`Closes #<issue>`", "never retarget or close it", "**Deviation (<kind>):**", "interface | dod | test | other",
               "verify each review finding against the code before changing anything", "**Reply <fid>:** fixed | contested — <reason>",
               "finding upheld", "finding overruled", "**Builder status:** DONE | DONE_WITH_CONCERNS | BLOCKED | NEEDS_CONTEXT",
               "- (a) <option>", "the first the builder's own proposal", "never spawn", "never touches files outside its scope paths", "never merges",
               "### DoD <n>", "pytest <test path>::<test name> -q", "pytest <test path> -k <test name> -q",
               "test(S<n>): <test name>", "feat(S<n>): <test name>"):
    assert form in text, form
  assert "ask your human partner" not in text and "You're absolutely right" not in text
  sample = f"U07\n\n### DoD 1\n{F}\nchecked by superegm tdd-order\n{F}\n\n### DoD 2\n{F}\n$ pytest tests/unit/test_worker.py -q\n1 passed\n{F}\n\nCloses #7\n"
  assert [(m.group(1), m.group(2).splitlines()[-1]) for m in DOD_RESULT_RE.finditer(sample)] == [("1", "checked by superegm tdd-order"), ("2", "1 passed")]
  assert sample.splitlines()[0] == "U07" and sample.rstrip().splitlines()[-1] == "Closes #7"


@pytest.mark.parametrize("skill, line, sentence", [
  ("interrupt", "superegm interrupt --unit <unit> (--launch <n> | --round <n>) --runcard <id>", "an owner's decision is not a guess"),
  ("clean", "superegm clean --unit <unit> --runcard <id>", "refuses while any launch or round of the unit is not terminal, and keeps what it cannot prove"),
])
def test_interrupt_and_clean_skill_bodies(skill, line, sentence):
  text = (ROOT / f"skills/{skill}/SKILL.md").read_text(encoding="utf-8")
  body = text.split("---", 2)[2]
  assert len(body.encode("utf-8")) <= 24_000 and "stub" not in body.lower()
  assert "In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first." in body
  assert f"superegm runcard open --skill {skill} --artifact <unit>" in body and line in body and "superegm runcard close <id>" in body
  assert sentence in body and "every effect refuses without an open run card" in body


REMOVED = re.compile(r"run_folder|run-folder|--not-run|--wave\b|\begm[-/_]|foreman_<|head-moved|\bdefer\b|whoever picks|merge locally|"
                     r"completion notice|Astra inspect|claudex|no-teams|dangerous|publish")

@pytest.mark.parametrize("path", ["skills/plan/scripts/superegm/launch.py", "skills/plan/scripts/superegm/launch_builder.py",
                                  "skills/plan/scripts/superegm/record_launch.py", "skills/plan/scripts/superegm/interrupt.py",
                                  "skills/plan/scripts/superegm/clean.py", "skills/wave/references/builder_orders.md",
                                  "skills/interrupt/SKILL.md", "skills/clean/SKILL.md"])
def test_no_removed_mechanism_is_named_in_this_units_files(path):
  hits = [l for l in (ROOT / path).read_text(encoding="utf-8").splitlines() if REMOVED.search(l)]
  assert hits == [], hits


@pytest.mark.parametrize("argv", [
  ["launch"], ["launch-builder", "--unit", UNIT, "--round", "1"], ["record-launch", "--unit", UNIT],
  ["interrupt", "--unit", UNIT, "--launch", "1"], ["clean", "--unit", UNIT],
])
def test_every_writing_subcommand_refuses_without_its_card(world, monkeypatch, spawn_fake, argv):
  s, card, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  launched(s, UNIT, "running")
  code, out = world.run("runcard", "open", "--skill", "plan", "--artifact", str(next(world.repo.glob("docs/**/*.md"))))
  other = out.split()[-1]
  code, out = world.run(*argv, "--runcard", other)
  assert code == 1 and out.startswith("superegm: runcard: "), out
  code, out = world.run(*argv, "--runcard", "c-missing")
  assert code == 1 and out.startswith("superegm: runcard: "), out
  assert launches_of(s)[0]["status"] == "running" and "launched" not in state_of(s)["units"][UNIT]


@pytest.mark.parametrize("layout, held", [
    ("bare", False), ("installed-empty", False), ("installed-listed", True), ("installed-managed", False), ("synced", True), ("trash", False), ("marketplace", False), ("cache", False)])
def test_plugins_held_reads_claude_code_s_own_files_as_no_plugin(tmp_path, layout, held):
  """1.1.3 fix: Claude Code writes installed_plugins.json, known_marketplaces.json, its default marketplace clones and
  store/ on every start (and .trash/ under syncClaudeAiPlugins: false); only an installed entry, a synced plugin
  directory is the owner's plugin; the organization's managed plugins and their cache copies are policy, recorded per launch."""
  from superegm import launch_builder
  plugins = tmp_path / "plugins"
  (plugins / "marketplaces").mkdir(parents=True); (plugins / "store").mkdir()
  (plugins / "store/cc-plugin-agents-md_builtin-b049b47b3618.json").write_text("{}", encoding="utf-8")
  entries = {"installed-empty": '{"version": 2, "plugins": {}}', "installed-listed": '{"version": 2, "plugins": {"x@m": [{"scope": "user"}]}}',
             "installed-managed": '{"version": 2, "plugins": {"data@kw": [{"scope": "managed"}], "finance@kw": [{"scope": "managed"}]}}'}
  if layout in entries:
    (plugins / "installed_plugins.json").write_text(entries[layout], encoding="utf-8")
  if layout == "synced":
    (plugins / "synced/bucket-1/pendo").mkdir(parents=True); (plugins / "synced/.bucket-1").mkdir()
  if layout == "trash":
    (plugins / ".trash/pendo").mkdir(parents=True); (plugins / "synced/.bucket-1").mkdir(parents=True)
  if layout == "marketplace":  # a clone of a default marketplace, written on every start: a catalog, not a plugin
    (plugins / "marketplaces/claude-plugins-official/.git").mkdir(parents=True); (plugins / "known_marketplaces.json").write_text("{}", encoding="utf-8")
  if layout == "cache":
    (plugins / "cache/m/x/1.0.0").mkdir(parents=True)
  if layout == "cache":
    (plugins / "installed_plugins.json").write_text(entries["installed-managed"], encoding="utf-8")  # the managed copies
  assert launch_builder.plugins_held(plugins) is held
  assert launch_builder.managed_plugins(plugins) == (["data@kw", "finance@kw"] if layout in ("installed-managed", "cache") else [])
  assert (launch_builder.profile_problem(tmp_path) == f"builder profile {tmp_path} holds plugins") is held
