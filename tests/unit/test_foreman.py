# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U10's tests of the foreman's helper subcommands.

"""U10: foreman dispatch, prepare, collect, tdd-order, review post. This file replaces U03's nine moved
prepare/collect tests (they pin `--round`, `--run-folder`, `--verdict`, `head-moved`, `launched` and `--remove`:
forms S4, S7 and S16 remove). Fixtures: conftest's `world` and `make_pr` (U03)."""
import json, re, subprocess
from pathlib import Path
from types import SimpleNamespace
import pytest
from conftest import make_pr, set_config
import superegm as core
from superegm import store, atomic_write, sha256_file, DEFAULT_CONFIG
from superegm import review as review_mod, tdd_order
from test_builder_token import APP

ROOT = Path(__file__).resolve().parents[2]
REPO, UNIT, PR = "example-org/webhooks", "U01", 70
# The section carries the section 9.1 blocks `graph.Plan` (U05) requires: Interfaces, Review focus, Steps.
SECTION = """### U01: Hooks
| Field | Value |
| --- | --- |
| Objective | The hook exists. |
| Scope paths | `src/hooks.py` (create), `tests/unit/test_hooks.py` (create) |
| Design range | `docs/designs/sample.md:13-15 (#### 1. src/webhooks/queue.ts)` |
| Blocked by | none |
| Shared files | none |
| Risk | low: small |
| Size | S |

Interfaces
- Produces: hook() -> None

Definition of done
1. The test for each Step was committed before its implementation (checked by superegm tdd-order)
2. Run `pytest tests/unit/test_hooks.py -q` — passes
3. Exists `src/hooks.py`
4. CI green on the head

Review focus (this unit)
- U01: the hook exists; pinned by `test_hook`

Steps
1. Write the failing test `test_hook` in `tests/unit/test_hooks.py`:
   ```python
   def test_hook(): ...
   ```
   Implement `hook() -> None` in `src/hooks.py`.

Decide before build
- none
"""
DOD = SECTION.split("Definition of done\n")[1].split("\nReview focus")[0]
BODY = ("# U01 — Hooks\n\n## Definition of done\n" + DOD + "\n## Steps\n"
        "1. Write the failing test `test_hook` in `tests/unit/test_hooks.py`:\n   ```python\n   def test_hook(): ...\n   ```\n"
        "   Run `pytest tests/unit/test_hooks.py::test_hook -q`; expected: FAIL (`ImportError`).\n"
        "   Implement `hook() -> None` in `src/hooks.py`.\n"
        "   Run the same command; expected: PASS. Commit `test(S1): hook` then `feat(S1): hook`.\n")
PR_BODY = "U01\n\n### DoD 2\n```\n$ pytest tests/unit/test_hooks.py -q\n1 passed\n```\n\nCloses #2\n"  # U09's DoD-results form
POSTED_R1 = {"round": 1, "runcard": "w", "launch": 1, "head": "0" * 40, "phase": "posted",
             "dispatch_id": "d1", "outcome": "revise", "posted_at": "2026-11-02T12:00:00Z"}
TWO_LAUNCHES = [{"round": 1, "status": "exited 0"}, {"round": 2, "status": "exited 0"}]


def c(cid, login, body, at="2026-11-02T13:00:00Z"):
  return {"id": cid, "user": {"login": login}, "created_at": at, "body": body}


def install_pr_api(world, *, reviews, comments, login) -> list:
  """`world.gh.extend("api", handler)` under U03's contract `handler(args, cwd, token=None) -> (code, out, err)`;
  it replaces `do_api`, so anything it does not answer falls through to `world.gh.do_api(args)`. Answers, through
  `world.gh.ok`: `api user` → `{"login": login}`; `repos/{REPO}/pulls/{PR}/reviews` → the one page `[reviews]`;
  its `-X POST` (`-F key=value` fields, `body=@<path>` read from that file) appends `{"id", "commit_id":
  world.gh.reply_commit or the field, "body", "event", "submitted_at": "2026-11-03T10:00:00Z"}` to `reviews` and
  to the returned `posted` list and echoes `"HTTP/2.0 200 OK\n\n" + json.dumps(it)`;
  `repos/{REPO}/issues/<n>/comments` → `[comments.get(n, [])]`. Sets `world.gh.reviews = reviews` (the list S11 appends to)."""
  posted = []

  def handler(args, cwd, token=None):
    endpoint = world.gh.endpoint_of(args)
    if endpoint == "user" and login is not None:  # `-q .login` renders the field as gh does; `login=None` leaves the route unanswered
      return world.gh.ok(text=login if "-q" in args else json.dumps({"login": login}))
    if endpoint == f"repos/{REPO}/pulls/{PR}/reviews":
      if "-X" in args and args[args.index("-X") + 1] == "POST":
        fields = dict(a.split("=", 1) for a in args[args.index("-F") + 1::2])
        body = fields["body"]
        body = Path(body[1:]).read_text(encoding="utf-8") if body.startswith("@") else body
        it = {"id": 100 + len(reviews), "commit_id": world.gh.reply_commit or fields["commit_id"], "body": body,
              "event": fields["event"], "submitted_at": "2026-11-03T10:00:00Z"}
        reviews.append(it); posted.append(it)
        return world.gh.ok(text="HTTP/2.0 200 OK\n\n" + json.dumps(it))
      return world.gh.ok([reviews])
    match = re.fullmatch(rf"repos/{REPO}/issues/(\d+)/comments", endpoint)
    if match:
      return world.gh.ok([comments.get(int(match.group(1)), [])])
    return world.gh.do_api(args)

  world.gh.reviews, world.gh.reply_commit = reviews, None
  world.gh.extend("api", handler)
  return posted


def seed(world, *, head="a" * 40, ci="success", launches=({"round": 1, "status": "exited 0"},),
         rounds=(), base_ref="main", comments=None, reviews=(), login="builder-bot", pr_body=PR_BODY, builder=None):
  """Through U03's `store`, `Store.path` and `atomic_write`, what `locate`, `Handoff` and `require_frozen_units`
  read: the plan (conftest's heading, a `Design:` line naming `world.spec` in backticks, `## Global constraints`,
  `## Units`, SECTION) written to `world.plan` and
  byte-identical to the store's `handoff_plan`; `state` = `{"plan": str(world.plan), "repo": REPO, "handoff_id":
  f"sample-{sha256_file(world.spec)[:6]}"` (what `Handoff` derives without an approval, so `require_binding` holds)
  `, "design": {"path": <the spec>}` (what `require_runcard` reads for a wave card, as U09's seed found)
  `, "units": {UNIT: {"number": 2, "pr": {"number": PR, "head": head, "base_ref": base_ref, "base_sha": "b" * 40}}}}`;
  `unit UNIT` = SECTION, a blank line, `## Issue body as posted`, a blank line, BODY in a markdown fence; `config.reviewers.head =
  ["change-review"]`; `make_pr(world.gh, PR, head, closes=[(REPO, 2)])` updated with `baseRefName: base_ref` and
  `body: pr_body`; CI on `head`: `check_runs[head]` one `tests` run, `in_progress` when `ci == "pending"`,
  `completed` with `conclusion: ci` otherwise, none when `ci` is None, and `combined[head] = {"state": "success" if
  ci not in (None, "pending") else "pending", "statuses": []}`; `launches UNIT` = `{"launches": list(launches)}` when
  launches; `foreman UNIT` = `{"dispatch_id": f"d{len(rounds)}" if rounds else None, "rounds": list(rounds),
  "decisions": [], "rulings": []}`; `posted = install_pr_api(world, reviews=list(reviews), comments=comments or {},
  login=login)`; `builder`, when given, is the config's `builder` key. Returns `(st, card, posted)` with
  `card = world.open_card("wave", str(world.spec))`."""
  spec = world.spec.resolve()
  set_config(world, repo=REPO, banned_terms=["(?i)secret-codename"],
             reviewers={"spec": [], "plan": [], "head": ["change-review"], "integrate": []},
             **({"builder": builder} if builder else {}))
  plan = (f"# Handoff plan: Webhook delivery\n\nDesign: `{spec}`\n\n## Global constraints\n- none\n\n"
          f"## Units\n\n{SECTION}")
  world.plan.write_text(plan, encoding="utf-8")
  st = store(world.repo)
  st.handoff_id = f"sample-{sha256_file(spec)[:6]}"
  atomic_write(st.path("handoff_plan"), plan)
  atomic_write(st.path("state"), {"plan": str(world.plan), "repo": REPO, "handoff_id": st.handoff_id,
                                  "design": {"path": str(spec)},
                                  "units": {UNIT: {"number": 2, "pr": {"number": PR, "head": head, "base_ref": base_ref,
                                                                       "base_sha": "b" * 40}}}})
  atomic_write(st.path("unit", UNIT), f"{SECTION}\n## Issue body as posted\n\n```markdown\n{BODY}```\n")
  make_pr(world.gh, PR, head, closes=[(REPO, 2)]).update({"baseRefName": base_ref, "body": pr_body})
  if ci is not None:
    world.gh.check_runs[head] = [{"name": "tests", "status": "in_progress" if ci == "pending" else "completed",
                                  "conclusion": None if ci == "pending" else ci}]
  world.gh.combined[head] = {"state": "success" if ci not in (None, "pending") else "pending", "statuses": []}
  if launches:
    atomic_write(st.path("launches", UNIT), {"launches": list(launches)})
  atomic_write(st.path("foreman", UNIT), {"dispatch_id": f"d{len(rounds)}" if rounds else None, "rounds": list(rounds),
                                          "decisions": [], "rulings": []})
  posted = install_pr_api(world, reviews=list(reviews), comments=comments or {}, login=login)
  return st, world.open_card("wave", str(spec)), posted


def head_rid(st):
  return next(p.name for p in st.path("reviews").iterdir() if re.search(rf"(^|-)head-{UNIT}-c\d+$", p.name))


def record(world, st, rid, rnd, head, card, findings):
  for reviewer, text in findings.items():
    path = st.path("review", UNIT, f"pr{PR}") / f"r{rnd}/{reviewer}.findings"
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")
    code, out = world.run("review", "record", "--review", rid, "--round", rnd, "--sha256", head, "--reviewer", reviewer,
                          "--findings", str(path), "--isolation", "clean", "--model", "m:m", "--effort", "e:e", "--runcard", card)
    assert code == 0, out


def open_head_review(world, st, card, head, findings):
  assert world.run("review", "open", "--kind", "head", "--artifact", UNIT, "--reviewers", "change-review", "--runcard", card)[0] == 0
  rid = head_rid(st); record(world, st, rid, 1, head, card, findings); return rid


def dispatched(world, **kw):
  st, card, posted = seed(world, **kw)
  code, out = world.run("foreman", "dispatch", "--unit", UNIT, "--runcard", card)
  assert code == 0, out
  did, child = out.split()
  return st, card, child, did, posted


def test_dispatch_writes_the_round_and_opens_the_head_review(world):
  stale = {"round": 1, "runcard": "old", "launch": 1, "head": None, "phase": "prepared", "dispatch_id": "d1"}
  st, card, child, did, _ = dispatched(world, rounds=[stale])
  data = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))
  assert did == "d2" and data["dispatch_id"] == "d2" and child != card
  assert data["rounds"][0] == {**stale, "phase": "collected", "outcome": "not run (superseded)"}
  assert data["rounds"][1] == {"round": 2, "runcard": card, "launch": 1, "head": None, "phase": "fetched", "dispatch_id": "d2"}
  review = json.loads((st.path("reviews", head_rid(st)) / "review.json").read_text(encoding="utf-8"))
  assert review["kind"] == "head" and review["reviewers"][0] == "change-review"
  child_card = json.loads(st.path("runcards", child).read_text(encoding="utf-8"))
  assert child_card["parent"] == card and child_card["skill"] == "wave" and child_card["artifact"] == UNIT


@pytest.mark.parametrize("setup, reason", [
    ({"ci": "pending"}, "ci pending"),
    ({"ci": None}, "ci absent"),
    ({"launches": None}, "no launch"),
    ({"launches": [{"round": 1, "status": "running"}]}, "launch 1 not terminal"),
    ({"rounds": [{**POSTED_R1, "head": "a" * 40}]}, "round 1 posted since launch 1"),
    ({"decision": True}, "decision p3-1 pending"),
    ({"stalled": True}, "review stalled"),
])
def test_dispatch_predicate_refuses(world, setup, reason):
  setup = dict(setup); decision, stalled = setup.pop("decision", False), setup.pop("stalled", False)
  st, card, _ = seed(world, **setup)
  data = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))
  if decision:
    data["decisions"] = [{"id": "p3-1", "point": 3, "question": "q", "asked_at": "t"}]
  if stalled:  # on a head the review's rounds are these entries: two latest not completed under this card
    assert world.run("review", "open", "--kind", "head", "--artifact", UNIT, "--reviewers", "change-review", "--runcard", card)[0] == 0
    data["rounds"] = [{"round": n, "runcard": card, "launch": 1, "head": None, "phase": "collected",
                       "dispatch_id": f"d{n}", "outcome": "not run (fetch failed)"} for n in (1, 2)]
    data["dispatch_id"] = "d2"
  atomic_write(st.path("foreman", UNIT), data)
  before = st.path("foreman", UNIT).read_text(encoding="utf-8")
  code, out = world.run("foreman", "dispatch", "--unit", UNIT, "--runcard", card)
  assert (code, out.strip()) == (1, f"dispatch refused: {reason}"), out
  assert st.path("foreman", UNIT).read_text(encoding="utf-8") == before


@pytest.mark.parametrize("on_pr", [True, False])
def test_dispatch_recovers_a_collected_round_already_on_the_pr(world, on_pr):
  """design-c2r5-1, readiness-c2r5-1: the recovery runs before the predicate (CI is pending here)."""
  head = "a" * 40
  entry = {"round": 1, "runcard": "w", "launch": 1, "head": head, "phase": "collected", "dispatch_id": "d1"}
  finding = "change-review-1-1 | high | src/hooks.py:1 | regression: no | no hook\n"
  on_pr_review = {"id": 5, "commit_id": head, "submitted_at": "2026-11-03T09:00:00Z",
                  "body": f"**SuperEGM review round 1 (head {head[:7]})**\n\n{finding}"}
  st, card, _ = seed(world, ci="pending", rounds=[entry], reviews=[on_pr_review] if on_pr else [])
  rid = open_head_review(world, st, card, head, {"change-review": finding, "foreman": ""})
  code, out = world.run("foreman", "dispatch", "--unit", UNIT, "--runcard", card)
  saved = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][0]
  if on_pr:
    assert (code, out.strip()) == (1, "recovered revise"), out
    assert saved["phase"] == "posted" and saved["posted_at"] == "2026-11-03T09:00:00Z" and saved["outcome"] == "revise"
    assert json.loads((st.path("reviews", rid) / "round-1.json").read_text(encoding="utf-8"))["what_ran"] == "completed"
  else:
    assert (code, out.strip()) == (1, "dispatch refused: ci pending")
    assert saved == entry


def pr_repo(world, tmp_path, monkeypatch, commits=(("test(S1): hook", "tests/unit/test_hooks.py"), ("feat(S1): hook", "src/hooks.py"))):
  """A remote with `main` and `refs/pull/70/head`; world.repo's `origin` points at it."""
  target = tmp_path / "target"
  def g(*a, cwd=target):
    return subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, text=True).stdout.strip()
  target.mkdir(); g("init", "-q", "-b", "main"); g("config", "user.email", "t@example.invalid"); g("config", "user.name", "T")
  (target / "README.md").write_text("base\n", encoding="utf-8"); g("add", "-A"); g("commit", "-qm", "base")
  base = g("rev-parse", "HEAD"); g("checkout", "-qb", "superegm/sample-42aff4/U01")
  for subject, path in commits:
    (target / path).parent.mkdir(parents=True, exist_ok=True); (target / path).write_text(subject + "\n", encoding="utf-8")
    g("add", "-A"); g("commit", "-qm", subject)
  head = g("rev-parse", "HEAD"); g("update-ref", f"refs/pull/{PR}/head", head); g("checkout", "-q", "main")
  g("remote", "set-url", "origin", str(target), cwd=world.repo)
  monkeypatch.setattr(core, "parse_remote_url", lambda url: REPO)  # prepare reads core.parse_remote_url at call time; a local path is not a GitHub URL
  return target, base, head, g


def prepared(world, tmp_path, monkeypatch, commits=None, **kw):
  target, base, head, g = pr_repo(world, tmp_path, monkeypatch, **({"commits": commits} if commits else {}))
  st, card, child, did, posted = dispatched(world, head=head, **kw)
  code, out = world.run("prepare", "--unit", UNIT, "--dispatch", did, "--runcard", child)
  assert code == 0, out
  return SimpleNamespace(st=st, card=card, child=child, did=did, posted=posted, head=head, base=base, g=g,
                         target=target, rid=head_rid(st), dir=st.path("review", UNIT, f"pr{PR}"))


@pytest.mark.parametrize("app", [False, True])
def test_prepare_reviews_the_tip_it_fetches(world, tmp_path, monkeypatch, app):
  target, base, head, g = pr_repo(world, tmp_path, monkeypatch)
  app and monkeypatch.delenv("SUPEREGM_BUILDER_TOKEN", raising=False)
  st, card, child, did, _ = dispatched(world, head="0" * 40,  # status recorded an older tip: no head-moved exit
                                       **({"builder": {**DEFAULT_CONFIG["builder"], "app": APP}, "login": None} if app else {}))
  world.gh.check_runs[head], world.gh.combined[head] = world.gh.check_runs["0" * 40], world.gh.combined["0" * 40]  # CI on the fetched tip too
  code, out = world.run("prepare", "--unit", UNIT, "--dispatch", "d9", "--runcard", child)
  assert (code, out.strip()) == (1, "dispatch: d9 is not U01's current dispatch (d1)")
  code, out = world.run("prepare", "--unit", UNIT, "--dispatch", did, "--runcard", child)
  assert (code, out.strip()) == (0, f"prepared: head {head[:7]} merge-base {base[:7]} ci green previous -"), out
  entry = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][0]
  assert entry["phase"] == "prepared" and entry["head"] == head and entry["merge_base"] == base
  d = st.path("review", UNIT, f"pr{PR}")
  assert g("rev-parse", "HEAD", cwd=d / "worktree") == head and (d / "worktree/src/hooks.py").is_file()
  assert b"+feat(S1): hook" in (d / "r1/diff").read_bytes()
  assert json.loads((d / "r1/ci.json").read_text(encoding="utf-8"))["verdict"] == "ci green"
  assert (d / "r1/pr_body.md").read_text(encoding="utf-8") == PR_BODY
  assert (d / "r1/comments.md").read_text(encoding="utf-8").startswith("builder: superegm-builder[bot]\n" if app else "builder: builder-bot\n")
  assert g("rev-parse", f"refs/superegm/pr/{PR}", cwd=world.repo) == head
  assert g("rev-parse", f"refs/superegm/pr-base/{PR}", cwd=world.repo) == base


def test_prepare_after_launch_fetched_the_base_ref(world, tmp_path, monkeypatch):
  """1.1.1 fix: `launch` fetches origin/<base> into `refs/superegm/base` and git refuses a ref nested under an
  existing one, so the round's base ref is `refs/superegm/pr-base/<n>`: both live in one clone."""
  target, base, head, g = pr_repo(world, tmp_path, monkeypatch)
  g("fetch", "--no-write-fetch-head", "origin", "+refs/heads/main:refs/superegm/base", cwd=world.repo)  # launch.py's fetch
  st, card, child, did, _ = dispatched(world, head=head)
  code, out = world.run("prepare", "--unit", UNIT, "--dispatch", did, "--runcard", child)
  assert code == 0, out
  assert g("rev-parse", "refs/superegm/base", cwd=world.repo) == base
  assert g("rev-parse", f"refs/superegm/pr-base/{PR}", cwd=world.repo) == base


def test_prepare_refuses_a_pr_whose_base_is_not_base(world, tmp_path, monkeypatch):
  target, base, head, g = pr_repo(world, tmp_path, monkeypatch)
  st, card, child, did, _ = dispatched(world, head=head, base_ref="release")
  code, out = world.run("prepare", "--unit", UNIT, "--dispatch", did, "--runcard", child)
  assert (code, out.strip()) == (1, "base: PR #70 targets release, not main")
  assert subprocess.run(["git", "-C", str(world.repo), "rev-parse", f"refs/superegm/pr/{PR}"], capture_output=True).returncode != 0
  assert json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][0]["phase"] == "fetched"


@pytest.mark.parametrize("body, aged, kept", [
    ("**Deviation (dod):** item 3 cannot be met\n- (a) drop it\n- (b) keep it\n**Builder status:** BLOCKED", True, True),
    ("**Decision D1:** (a) by default", True, True),
    ("**Ruling:** change-review-1-1 finding upheld (fix it)", True, True),
    ("**Reply change-review-1-1:** fixed", True, False),
    ("**Reply change-review-1-1:** fixed", False, True),
])
def test_prepare_writes_comments_after_posted_at_plus_the_aged_kinds(world, tmp_path, monkeypatch, body, aged, kept):
  at = "2026-11-01T12:00:00Z" if aged else "2026-11-02T13:00:00Z"   # POSTED_R1.posted_at is 2026-11-02T12:00:00Z
  comments = {70: [c(12, "builder-bot", body, at)], 2: [c(13, "owner", "looks fine", "2026-11-02T14:00:00Z")]}
  w = prepared(world, tmp_path, monkeypatch, rounds=[POSTED_R1], launches=TWO_LAUNCHES, comments=comments)
  text = (w.dir / "r2/comments.md").read_text(encoding="utf-8")
  assert text.startswith("builder: builder-bot\n")
  assert "### issue #2 comment 13 by owner at 2026-11-02T14:00:00Z\nlooks fine\n" in text
  assert (f"### pr #70 comment 12 by builder-bot at {at}\n{body}\n" in text) is kept


DEV = "**Deviation (dod):** item 3 is wrong\n- (a) drop it\n- (b) keep it\n**Builder status:** BLOCKED"
CASES = {
    "clean": ({}, []),
    "ci": ({"ci": "failure"}, ["ci | regression: no | CI not green on this head: ci red (tests)"]),
    "exists": ({"commits": [("test(S1): hook", "tests/unit/test_hooks.py")]},
               ["src/hooks.py | regression: no | Exists item 3: path absent",
                "tests/unit/test_hooks.py | regression: no | tdd-order: S1: no feat(S1) commit touches src/hooks.py"]),
    "run": ({"pr_body": "U01\n\nCloses #2\n"}, ["pr_body.md | regression: no | Run item 2: no fenced output"]),
    "scope": ({"commits": [("test(S1): hook", "tests/unit/test_hooks.py"), ("feat(S1): hook", "src/hooks.py"), ("feat(S1): more", "src/other.py")]},
              ["src/other.py | regression: no | changed path outside Scope paths"]),
    "tdd-order": ({"commits": [("feat(S1): hook", "src/hooks.py"), ("test(S1): hook", "tests/unit/test_hooks.py")]},
                  ["tests/unit/test_hooks.py | regression: no | tdd-order: S1: feat(S1) precedes test(S1)"]),
    "deviation": ({"comments": {2: [c(12, "builder-bot", DEV)]}}, ["issue #2 comment 12 | regression: no | deviation (dod) unruled"]),
    "deviation-ruled": ({"comments": {2: [c(12, "builder-bot", DEV), c(13, "owner", "**Ruling:** (12) (a) — drop it")]}}, []),
    "deviation-ruled-by-builder": ({"comments": {2: [c(12, "builder-bot", DEV), c(13, "builder-bot", "**Ruling:** (12) (a) — drop it")]}},
                                   ["issue #2 comment 12 | regression: no | deviation (dod) unruled"]),
    "contested": ({"prior": True, "comments": {70: [c(14, "builder-bot", "**Reply change-review-1-1:** contested — the test covers it")]}},
                  ["pr #70 comment 14 | regression: no | contested change-review-1-1: the test covers it"]),
    "upheld": ({"prior": True, "comments": {2: [c(15, "owner", "**Ruling:** change-review-1-1 finding upheld (fix it)")]}},
               ["issue #2 comment 15 | regression: no | upheld change-review-1-1: no `fixed` reply"]),
    "ci-reply-ignored": ({"prior": True, "comments": {70: [c(16, "builder-bot", "**Reply foreman-1-1:** contested — flaky")]}}, []),
}


@pytest.mark.parametrize("name", list(CASES))
def test_collect_records_foreman_findings(world, tmp_path, monkeypatch, name):
  kw, expected = dict(CASES[name][0]), CASES[name][1]
  prior = kw.pop("prior", False)
  if prior:
    kw.update(rounds=[POSTED_R1], launches=TWO_LAUNCHES)
  if prior:  # the last posted round: one change-review high and the CI finding
    st0, card0, _ = seed(world, **{k: v for k, v in kw.items() if k != "commits"})
    open_head_review(world, st0, card0, "0" * 40, {
        "change-review": "change-review-1-1 | high | src/hooks.py:1 | regression: no | no hook\n",
        "foreman": "foreman-1-1 | high | ci | regression: no | CI not green on this head: ci red (tests)\n"})
  w = prepared(world, tmp_path, monkeypatch, **kw)
  r = 2 if prior else 1
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, f"collected: {len(expected)} foreman findings"), out
  lines = (w.dir / f"r{r}/foreman.findings").read_text(encoding="utf-8").splitlines()
  assert lines == [f"foreman-{r}-{i} | high | {e}" for i, e in enumerate(expected, 1)]
  rnd = json.loads((w.st.path("reviews", w.rid) / f"round-{r}.json").read_text(encoding="utf-8"))
  assert rnd["builder_contested"] == ([{"fid": f"foreman-{r}-1", "reason": "the test covers it"}] if name == "contested" else [])
  assert rnd["what_ran"].startswith("not run")
  assert json.loads(w.st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][-1]["phase"] == "collected"


@pytest.mark.parametrize("phase, outcome, ok", [
    ("fetched", None, True), ("prepared", None, True), ("collected", None, True),
    ("posted", "revise", False), ("collected", "not run (superseded)", False)])
def test_collect_not_run_accepts_any_non_terminal_round(world, phase, outcome, ok):
  entry = {"round": 1, "runcard": "w", "launch": 1, "head": None, "phase": phase, "dispatch_id": "d1",
           **({"outcome": outcome} if outcome else {})}
  st, card, _ = seed(world, rounds=[entry])
  child = world.run("runcard", "open", "--skill", "wave", "--artifact", UNIT, "--parent", card)[1].strip()
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", "d1", "--runcard", child, "--not-run", "fetch failed")
  saved = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][0]
  if ok:
    assert (code, out.strip()) == (0, "U01 round 1: collected (not run (fetch failed))"), out
    assert saved == {**entry, "phase": "collected", "outcome": "not run (fetch failed)"}
  else:
    assert code == 1 and f"U01 round 1 is terminal (`{phase}`)" in out and saved == entry


@pytest.mark.parametrize("commits, failures", [
    ([("test(S1): hook", "tests/unit/test_hooks.py"), ("feat(S1): hook", "src/hooks.py")], []),
    ([("feat(S1): hook", "src/hooks.py"), ("test(S1): hook", "tests/unit/test_hooks.py")], ["S1: feat(S1) precedes test(S1)"]),
    ([("test(S1): hook", "src/hooks.py"), ("feat(S1): hook", "src/hooks.py")],
     ["S1: no test(S1) commit touches tests/unit/test_hooks.py", "test(S1) touches src/hooks.py: not a test path the Steps name nor a test file by name"]),
    ([("test(S1): hook", "tests/unit/test_hooks.py")], ["S1: no feat(S1) commit touches src/hooks.py"]),
])
def test_tdd_order(world, tmp_path, monkeypatch, commits, failures):
  w = prepared(world, tmp_path, monkeypatch, commits=commits)
  code, out = world.run("tdd-order", "--unit", UNIT, "--dispatch", w.did)
  assert (code, out.strip().splitlines()) == ((1, failures) if failures else (0, ["tdd-order: ok"]))
  assert tdd_order.check(BODY, [(s, [p]) for s, p in commits]) == failures


def test_tdd_order_accepts_the_test_paths_the_steps_name():
  """1.1.1 fix: a `test(S<n>)` commit may touch the test paths the Steps name, colocated or not; since 1.1.3 also any
  test file by name (§9.3), and nothing else."""
  body = BODY.replace("tests/unit/test_hooks.py", "src/x.spec.ts").replace("src/hooks.py", "src/x.ts")
  assert tdd_order.check(body, [("test(S1): x", ["src/x.spec.ts"]), ("feat(S1): x", ["src/x.ts"])]) == []
  assert tdd_order.check(body, [("test(S1): x", ["src/x.spec.ts", "src/x.ts"]), ("feat(S1): x", ["src/x.ts"])]) == [
      "test(S1) touches src/x.ts: not a test path the Steps name nor a test file by name"]


def test_tdd_order_reads_test_sn_subjects_only():
  """1.1.2 fix: an adopted branch's own history enters `commits_of` in full, so a pre-existing `test(…)` commit
  touching a non-Step path is not the builder's; the test-paths rule reads `test(S<n>)` subjects only."""
  legacy = ("test(legacy): old suite", ["src/old_test.py", "src/old.py"])
  assert tdd_order.check(BODY, [legacy, ("test(S1): hook", ["tests/unit/test_hooks.py"]), ("feat(S1): hook", ["src/hooks.py"])]) == []
  fixtures = ["tests/unit/test_hooks.py", "conftest.py", "tests/fixtures/orient/tree.json", "src/hooks_test.py"]  # test files by name (§9.3) ride along
  assert tdd_order.check(BODY, [legacy, ("test(S1): hook", fixtures), ("feat(S1): hook", ["src/hooks.py"])]) == []
  assert tdd_order.check(BODY, [legacy, ("test(S1): hook", ["tests/unit/test_hooks.py", "src/hooks.py"]), ("feat(S1): hook", ["src/hooks.py"])]) == [
      "test(S1) touches src/hooks.py: not a test path the Steps name nor a test file by name"]


@pytest.mark.parametrize("findings, word", [("", "clean"), ("change-review-1-1 | high | src/hooks.py:1 | regression: no | no hook\n", "revise")])
def test_review_post_binds_the_review_to_the_reviewed_commit(world, tmp_path, monkeypatch, findings, word):
  w = prepared(world, tmp_path, monkeypatch)
  assert world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)[0] == 0
  record(world, w.st, w.rid, 1, w.head, w.child, {"change-review": findings})
  code, out = world.run("review", "post", "--unit", UNIT, "--round", 1, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, f"posted {word}"), out
  assert len(w.posted) == 1 and w.posted[0]["commit_id"] == w.head and w.posted[0]["event"] == "COMMENT"
  assert w.posted[0]["body"].startswith(f"**SuperEGM review round 1 (head {w.head[:7]})**\n")
  assert findings.strip() in w.posted[0]["body"] and "CI: ci green" in w.posted[0]["body"]
  assert not any(c[:2] == ["pr", "review"] for c in world.gh.calls)
  entry = json.loads(w.st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][0]
  assert entry["phase"] == "posted" and entry["outcome"] == word and entry["posted_at"] == "2026-11-03T10:00:00Z"
  assert json.loads((w.st.path("reviews", w.rid) / "round-1.json").read_text(encoding="utf-8"))["what_ran"] == "completed"
  assert (f"{UNIT} awaiting merge" in w.st.path("journal").read_text(encoding="utf-8")) is (word == "clean")


@pytest.mark.parametrize("case", ["header-present", "stale-dispatch", "mention", "commit-differs"])
def test_review_post_guards(world, tmp_path, monkeypatch, case):
  w = prepared(world, tmp_path, monkeypatch)
  assert world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)[0] == 0
  claim = "ping @alice" if case == "mention" else "no hook"
  record(world, w.st, w.rid, 1, w.head, w.child, {"change-review": f"change-review-1-1 | high | src/hooks.py:1 | regression: no | {claim}\n"})
  if case == "header-present":
    world.gh.reviews.append({"id": 5, "commit_id": w.head, "submitted_at": "2026-11-03T09:00:00Z",
                             "body": f"**SuperEGM review round 1 (head {w.head[:7]})**\n\nx"})
  if case == "commit-differs":
    world.gh.reply_commit = "f" * 40
  did = "d9" if case == "stale-dispatch" else w.did
  code, out = world.run("review", "post", "--unit", UNIT, "--round", 1, "--dispatch", did, "--runcard", w.child)
  entry = json.loads(w.st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][0]
  expected = {"header-present": (0, "posted revise (already on the PR)", "posted", 0),
              "stale-dispatch": (1, "dispatch: d9 is not U01's current dispatch (d1)", "collected", 0),
              "mention": (1, "comment:3: bare mention @alice", "collected", 0),
              "commit-differs": (1, f"posted on {'f' * 7}, not {w.head[:7]}: round 1 not counted", "collected", 1)}[case]
  assert (code, entry["phase"], len(w.posted)) == (expected[0], expected[2], expected[3]), out
  assert out.strip().splitlines()[0].startswith(expected[1]), out
  if case == "header-present":
    assert entry["posted_at"] == "2026-11-03T09:00:00Z"


@pytest.mark.parametrize("merge_pr", [False, True])
def test_review_post_target_moved(world, tmp_path, monkeypatch, merge_pr):
  w = prepared(world, tmp_path, monkeypatch)
  assert world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)[0] == 0
  if merge_pr:   # the base now contains the head: the merge base moved onto it
    w.g("merge", "-q", "--ff-only", w.head)
  else:          # an unrelated commit on the base branch leaves the merge base unchanged
    (w.target / "NOTES.md").write_text("later\n", encoding="utf-8"); w.g("add", "-A"); w.g("commit", "-qm", "unrelated")
  code, out = world.run("review", "post", "--unit", UNIT, "--round", 1, "--dispatch", w.did, "--runcard", w.child)
  entry = json.loads(w.st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][0]
  if merge_pr:
    assert (code, out.strip(), len(w.posted)) == (3, "target-moved", 0)
    assert entry["phase"] == "collected" and entry["outcome"] == "not run (target-moved)"
  else:
    assert (code, len(w.posted)) == (0, 1) and entry["phase"] == "posted"


@pytest.mark.parametrize("status_exit, contested, word", [
    (3, ["foreman-2-1", "foreman-2-3"], "contested: foreman-2-1, foreman-2-3"),
    (2, ["foreman-2-1"], "contested: foreman-2-1"),
    (0, [], "clean"), (2, [], "cap-reached"), (3, [], "revise"), (5, [], "revise")])
def test_outcome_word_order(status_exit, contested, word):
  assert review_mod.outcome_word(status_exit, contested) == word


def test_foreman_adapter_frontmatter_and_tools():
  text = (ROOT / ".claude-plugin/agents/foreman.md").read_text(encoding="utf-8")
  assert text.startswith("---\nname: foreman\n")
  fm = text.split("---\n")[1]
  for line in ("tools: [Agent, Bash, Read, Grep, Glob]", "model: inherit", "omitClaudeMd: true"):
    assert line in fm.splitlines(), line
  assert "memory" not in fm and "${CLAUDE_PLUGIN_ROOT}/skills/wave/references/foreman_brief.md" in text
  assert "Modified by SuperEGM (gsVAM), 2026" in text or "Added by SuperEGM (gsVAM), 2026" in text


@pytest.mark.parametrize("line", [
    "superegm prepare --unit <unit-id> --dispatch <dispatch-id> --runcard <child-card>",
    "`change-review` first",
    "without `name`",
    "superegm review record --review <review-id> --round <n> --sha256 <head> --reviewer <id> --findings <file>",
    "superegm collect --unit <unit-id> --dispatch <dispatch-id> --runcard <child-card>",
    "--not-run \"<reason>\"",
    "superegm review post --unit <unit-id> --round <n> --dispatch <dispatch-id> --runcard <child-card>",
    "clean | revise | contested: <ids> | cap-reached | target-moved | error",
    "`target-moved` when `review post` exited 3",
    "`error` otherwise",
    "never merges, never approves, never edits the owner's working tree, never removes a worktree, never launches a session, never convenes the judges, never infers that a builder died",
])
def test_foreman_brief_carries_the_round(line):
  assert line in (ROOT / "skills/wave/references/foreman_brief.md").read_text(encoding="utf-8"), line


FILES = [".claude-plugin/agents/foreman.md", "skills/wave/references/foreman_brief.md",
         "skills/plan/scripts/superegm/foreman.py", "skills/plan/scripts/superegm/prepare.py",
         "skills/plan/scripts/superegm/collect.py"]
TERMS = ["head-moved", "astra", "Astra", "run folder", "run_folder", "`launched`", "inspect", "Blocker", "Major",
         "wave_round_", "pr_comment_", "wave_dispositions", "egm-change-review", "refs/egm/", "foreman_<unit-id>_state.json",
         "--verdict", ".egm/handoff.json", "handoff_state.json", "new triple", "require_reviewed_pair", "unit_file_text",
         "record-launch", "SendMessage"]


@pytest.mark.parametrize("term", TERMS)
@pytest.mark.parametrize("file", FILES)
def test_removed_mechanisms_are_not_named(file, term):
  assert term not in (ROOT / file).read_text(encoding="utf-8"), (file, term)
