# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U10's tests of the foreman's helper subcommands.
# Modified by SuperEGM (gsVAM), 2026: collect reads rulings through `ruling_of` and the record (U22).

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
from superegm import foreman as foreman_mod
from superegm.prepare import cut_diff, prior_round_text
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


@pytest.fixture(autouse=True)
def builder_token(monkeypatch):
  """The machine account's token, so `review ingest` can name the builder's login (the fake `gh` answers `builder-bot`)."""
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")


def seed(world, *, head="a" * 40, ci="success", launches=({"round": 1, "status": "exited 0"},),
         rounds=(), base_ref="main", comments=None, reviews=(), login="builder-bot", pr_body=PR_BODY, builder=None, astra=None, marker=True, owners=None,
         decisions=(), rulings=()):
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
  login=login)`; `builder`, when given, is the config's `builder` key. The unit file's body is BODY prefixed with
  the marker line (the spec's sha256, or `1` * 64 when `marker` is false: no commit holds it) and a `Spec:` line
  citing SECTION's design range (lines 13-15 of conftest's fixture spec). Returns `(st, card, posted)` with
  `card = world.open_card("wave", str(world.spec))`."""
  spec = world.spec.resolve()
  set_config(world, repo=REPO, banned_terms=["(?i)secret-codename"],
             reviewers={"spec": [], "plan": [], "head": ["change-review"], "integrate": []},
             **({"builder": builder} if builder else {}), **({"astra": astra} if astra else {}),
             owners=owners or ["owner"])
  plan = (f"# Handoff plan: Webhook delivery\n\nDesign: `{spec}`\n\n## Global constraints\n- none\n\n"
          f"## Units\n\n{SECTION}")
  world.plan.write_text(plan, encoding="utf-8")
  st = store(world.repo)
  st.handoff_id = f"sample-{sha256_file(spec)[:6]}"
  atomic_write(st.path("handoffs", st.handoff_id), {"id": st.handoff_id, "spec": str(spec), "opened_at": "2026-11-02T00:00:00Z", "closed_at": None})
  atomic_write(st.path("handoff_plan"), plan)
  atomic_write(st.path("state"), {"plan": str(world.plan), "repo": REPO, "handoff_id": st.handoff_id,
                                  "design": {"path": str(spec)},
                                  "units": {UNIT: {"number": 2, "pr": {"number": PR, "head": head, "base_ref": base_ref,
                                                                       "base_sha": "b" * 40}}}})
  sha = sha256_file(spec)
  cited = (f"<!-- superegm:handoff={st.handoff_id} unit={UNIT} spec={sha if marker else '1' * 64} -->\n"
           f"Spec: `docs/designs/sample.md` @ {sha[:7]} · `docs/designs/sample.md:13-15 (#### 1. src/webhooks/queue.ts)`\n")
  atomic_write(st.path("unit", UNIT), f"{SECTION}\n## Issue body as posted\n\n```markdown\n{cited}{BODY}```\n")
  make_pr(world.gh, PR, head, closes=[(REPO, 2)]).update({"baseRefName": base_ref, "body": pr_body})
  if ci is not None:
    world.gh.check_runs[head] = [{"name": "tests", "status": "in_progress" if ci == "pending" else "completed",
                                  "conclusion": None if ci == "pending" else ci}]
  world.gh.combined[head] = {"state": "success" if ci not in (None, "pending") else "pending", "statuses": []}
  if launches:
    atomic_write(st.path("launches", UNIT), {"launches": list(launches)})
  atomic_write(st.path("foreman", UNIT), {"dispatch_id": f"d{len(rounds)}" if rounds else None, "rounds": list(rounds),
                                          "decisions": list(decisions), "rulings": list(rulings)})
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


def prepared(world, tmp_path, monkeypatch, commits=None, incomplete=0, **kw):
  target, base, head, g = pr_repo(world, tmp_path, monkeypatch, **({"commits": commits} if commits else {}))
  st, card, child, did, posted = dispatched(world, head=head, **kw)
  if incomplete:  # the lane's incomplete runs so far, as `review record` counts them
    path = st.path("reviews", head_rid(st)) / "review.json"
    atomic_write(path, {**json.loads(path.read_text(encoding="utf-8")), "astra_incomplete": incomplete})
  code, out = world.run("prepare", "--unit", UNIT, "--dispatch", did, "--runcard", child)
  assert code == 0, out
  return SimpleNamespace(st=st, card=card, child=child, did=did, posted=posted, head=head, base=base, g=g,
                         target=target, rid=head_rid(st), dir=st.path("review", UNIT, f"pr{PR}"), out=out)


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
  assert (code, out.strip()) == (0, f"prepared: head {head[:7]} merge-base {base[:7]} ci green previous - astra: off"), out
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
    ("**Reply change-review-1-1:** fixed", True, True),  # 1.1.3: a reply posted before the last posted round still answers its ruling
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


@pytest.mark.parametrize("astra, runner, incomplete, state, brief", [
  ({"enabled": False}, None, 0, "astra: off", False),
  ({"enabled": True}, "/x/runner.py", 0, "astra: ok /x/runner.py", True),
  ({"enabled": True}, None, 0, "astra: not installed", True),
  ({"enabled": True}, "/x/runner.py", 2, "astra: stopped", False)])
def test_prepare_writes_the_astra_brief_and_prints_the_lane_state(world, tmp_path, monkeypatch, astra, runner, incomplete, state, brief):
  monkeypatch.setattr(foreman_mod, "runner_path", lambda: runner)
  w = prepared(world, tmp_path, monkeypatch, astra=astra, incomplete=incomplete, rounds=[POSTED_R1], launches=TWO_LAUNCHES)
  assert w.out.strip().endswith(state) and (w.dir / "r2/astra_brief.md").is_file() is brief
  if brief:
    text = (w.dir / "r2/astra_brief.md").read_text(encoding="utf-8")
    assert re.findall(r"^# ([^\n]+)\n\n````\n", text, re.M) == ["Unit body", "Spec range", "Diff", "CI", "PR body", "Comments", "Prior round"]
    assert BODY in text and PR_BODY in text and "+feat(S1): hook" in text
  assert cut_diff(b"x" * 400_001).endswith("\n(diff cut at 400 KB)\n") and cut_diff(b"x" * 400_000) == "x" * 400_000


def test_the_brief_cut_note_names_the_limit_it_cut_at():
  assert cut_diff(b"x" * 11, limit=10).endswith("\n(diff cut at 10 bytes)\n") and cut_diff(b"x" * 400_001).endswith("(diff cut at 400 KB)\n")


@pytest.mark.parametrize("holds", [True, False])
def test_prepare_writes_spec_range_md_from_the_chain(world, tmp_path, monkeypatch, holds):
  target, base, head, g = pr_repo(world, tmp_path, monkeypatch)
  st, card, child, did, _ = dispatched(world, head=head, marker=holds)
  code, out = world.run("prepare", "--unit", UNIT, "--dispatch", did, "--runcard", child)
  d = st.path("review", UNIT, f"pr{PR}")
  if holds:
    assert code == 0 and (d / "r1/spec_range.md").read_text(encoding="utf-8") == "\n".join(world.spec.read_text(encoding="utf-8").splitlines()[12:15]) + "\n"
  else:
    assert (code, out.strip()) == (1, "spec range: no commit holds 1111111") and not (d / "r1/spec_range.md").exists() and not (d / "worktree").exists()


def test_the_prior_round_lists_findings_with_astras_dispositions(world):
  st = store(world.repo)
  assert prior_round_text(st, None, None) == "none"
  f1 = {"id": "change-review-1-1", "severity": "high", "location": "a.py:1", "regression": "no", "claim": "c1", "disposition": "fixed"}
  f2 = {"id": "astra-1-1", "severity": "medium", "location": "b.py:2", "regression": "yes", "claim": "c2", "disposition": "contested"}
  atomic_write(st.path("reviews", "rv", "round-1.json"), {"reviewers": {"change-review": {"findings": [f1]}, "astra": {"findings": [f2]}}})
  assert sorted(prior_round_text(st, "rv", 1).splitlines()) == [  # the store sorts reviewer keys
    "astra-1-1 | medium | b.py:2 | regression: yes | c2 -> contested",
    "change-review-1-1 | high | a.py:1 | regression: no | c1"]


def test_collect_records_the_brief_sha256_on_the_lane_record(world, tmp_path, monkeypatch):
  monkeypatch.setattr(foreman_mod, "runner_path", lambda: None)
  w = prepared(world, tmp_path, monkeypatch, astra={"enabled": True})
  record(world, w.st, w.rid, 1, w.head, w.child, {"change-review": ""})
  assert world.run("review", "record", "--review", w.rid, "--round", 1, "--sha256", w.head, "--reviewer", "astra", "--not-run", "not installed", "--runcard", w.child)[0] == 0
  assert world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)[0] == 0
  rnd = json.loads((w.st.path("reviews", w.rid) / "round-1.json").read_text(encoding="utf-8"))
  assert rnd["reviewers"]["astra"]["brief_sha256"] == sha256_file(w.dir / "r1/astra_brief.md")


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
TWO = "**Deviation (dod):** item 3 is wrong\n**Deviation (test):** the fence pins a typo\nWhich way?\n- (a) drop both\n- (b) keep both\n**Builder status:** BLOCKED"
TDD = "foreman-1-2 | high | tests/unit/test_hooks.py | regression: no | tdd-order: S1: feat(S1) precedes test(S1)\n"
CASES |= {"deviation-ruled-by-stranger": ({"comments": {2: [c(12, "builder-bot", DEV), c(13, "passer-by", "**Ruling:** (12) (a) — drop it")]}},
               ["issue #2 comment 12 | regression: no | deviation (dod) unruled"]),
  "folded-deviations": ({"comments": {2: [c(12, "builder-bot", TWO)]}},
                        ["issue #2 comment 12 | regression: no | deviation (dod) unruled", "issue #2 comment 12 | regression: no | deviation (test) unruled"]),
  "folded-deviations-ruled": ({"comments": {2: [c(12, "builder-bot", TWO), c(13, "owner", "**Ruling:** (12) (a) drop both — fine")]}}, []),
  "deviation-ruled-by-the-record": ({"comments": {2: [c(12, "builder-bot", DEV), c(13, "owner", "**Ruling:** (12) (a) — drop it\n(judges p-1, leavemealone)")]},
                                     "decisions": [{"id": "q1", "point": 3, "source": "comment 12"}],
                                     "rulings": [{"decision": "q1", "ruling": "(a)", "by": "judges:p-1", "reason": None, "posted": "comment 13", "posted_at": "t"}]}, []),
  "tdd-order-allowed": ({"prior": True, "prior_foreman": TDD, "commits": [("feat(S1): hook", "src/hooks.py"), ("test(S1): hook", "tests/unit/test_hooks.py")],
                         "comments": {2: [c(15, "owner", "**Ruling:** foreman-1-2 allowed — an adopted history")]}}, [])}
UPHELD_Q1 = {"decisions": [{"id": "q1", "point": 1, "source": "review r round 1"}],
             "rulings": [{"decision": "q1", "ruling": "change-review-1-1 finding upheld", "by": "owner", "reason": None, "posted": "comment 15", "posted_at": "t"}]}
CASES |= {  # round 2 (PR #96 review): the record wins over an edit of its comment and over a later comment on its fid
  "recorded-upheld-edited": ({"prior": True, "comments": {2: [c(15, "owner", "**Ruling:** change-review-1-1 finding overruled — changed")]}} | UPHELD_Q1,
                             ["issue #2 comment 15 | regression: no | upheld change-review-1-1: no `fixed` reply"]),
  "recorded-upheld-contradicted": ({"prior": True, "comments": {2: [c(15, "owner", "**Ruling:** change-review-1-1 finding upheld (fix it)"),
                                                                    c(17, "owner", "**Ruling:** change-review-1-1 finding overruled — again")]}} | UPHELD_Q1,
                                   ["issue #2 comment 15 | regression: no | upheld change-review-1-1: no `fixed` reply"]),
  "tdd-order-allowed-and-contested": ({"prior": True, "prior_foreman": TDD, "commits": [("feat(S1): hook", "src/hooks.py"), ("test(S1): hook", "tests/unit/test_hooks.py")],
                                       "comments": {2: [c(15, "owner", "**Ruling:** foreman-1-2 allowed — an adopted history")],
                                                    70: [c(14, "builder-bot", "**Reply foreman-1-2:** contested — adopted history")]}}, [])}


@pytest.mark.parametrize("name", list(CASES))
def test_collect_records_foreman_findings(world, tmp_path, monkeypatch, name):
  kw, expected = dict(CASES[name][0]), CASES[name][1]
  prior, prior_foreman = kw.pop("prior", False), kw.pop("prior_foreman", "")
  if prior:
    kw.update(rounds=[POSTED_R1], launches=TWO_LAUNCHES)
  if prior:  # the last posted round: one change-review high and the CI finding (and `prior_foreman`'s)
    st0, card0, _ = seed(world, **{k: v for k, v in kw.items() if k != "commits"})
    open_head_review(world, st0, card0, "0" * 40, {
        "change-review": "change-review-1-1 | high | src/hooks.py:1 | regression: no | no hook\n",
        "foreman": "foreman-1-1 | high | ci | regression: no | CI not green on this head: ci red (tests)\n" + prior_foreman})
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


def test_collect_takes_a_fixed_reply_under_the_goldfish_id_for_an_upheld_contest(world, tmp_path, monkeypatch):
  """1.1.3 fix (wave-0021, U18 round 6): the judges rule the contest finding (`foreman-1-2`, "contested
  change-review-1-1: …") upheld, and the builder replies `fixed` under the goldfish id it was shown; either id answers."""
  comments = {2: [c(15, "owner", "**Ruling:** foreman-1-2 finding upheld (fix it)")],
              70: [c(16, "builder-bot", "**Reply change-review-1-1:** fixed", at="2026-11-02T14:00:00Z")]}  # after the ruling
  kw = dict(rounds=[POSTED_R1], launches=TWO_LAUNCHES, comments=comments)
  st0, card0, _ = seed(world, **kw)
  open_head_review(world, st0, card0, "0" * 40, {
      "change-review": "change-review-1-1 | high | src/hooks.py:1 | regression: no | no hook\n",
      "foreman": "foreman-1-1 | high | ci | regression: no | CI not green on this head: ci red (tests)\n"
                 "foreman-1-2 | high | pr #70 comment 14 | regression: no | contested change-review-1-1: the test covers it\n"})
  w = prepared(world, tmp_path, monkeypatch, **kw)
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, "collected: 0 foreman findings"), out


def test_collect_carries_an_overruled_scope_finding_forward(world, tmp_path, monkeypatch):
  """1.1.3 fix (wave-0021, U17 round 5): an owner's `**Ruling:** <fid> finding overruled` on an earlier round's
  out-of-Scope finding widens the Scope for that path, so later rounds do not record it again."""
  commits = [("test(S1): hook", "tests/unit/test_hooks.py"), ("feat(S1): hook", "src/hooks.py"), ("feat(S1): more", "src/other.py")]
  comments = {2: [c(13, "owner", "**Ruling:** foreman-1-2 finding overruled — Scope widened to src/other.py")]}
  kw = dict(rounds=[POSTED_R1], launches=TWO_LAUNCHES, comments=comments)
  st0, card0, _ = seed(world, **kw)
  open_head_review(world, st0, card0, "0" * 40, {
      "change-review": "change-review-1-1 | high | src/hooks.py:1 | regression: no | no hook\n",
      "foreman": "foreman-1-1 | high | ci | regression: no | CI not green on this head: ci red (tests)\n"
                 "foreman-1-2 | high | src/other.py | regression: no | changed path outside Scope paths\n"})
  w = prepared(world, tmp_path, monkeypatch, commits=commits, **kw)
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, "collected: 0 foreman findings"), out


EXT = "external:alice-1-1 | high | src/hooks.py:3 at 0000000 | regression: no | the hook never fires\n"
CARRIED = "src/hooks.py:3 at 0000000 | regression: no | unreplied external:alice-1-1: the hook never fires"
R2 = {**POSTED_R1, "round": 2, "launch": 2, "dispatch_id": "d2"}


@pytest.mark.parametrize("rounds, replies, expected", [
  ([POSTED_R1], {}, [CARRIED]), ([POSTED_R1], {70: [c(14, "builder-bot", "**Reply foreman-2-1:** fixed")]}, [CARRIED]),
  ([POSTED_R1], {70: [c(14, "builder-bot", "**Reply external:alice-1-1:** fixed")]}, []), ([POSTED_R1, R2], {}, [CARRIED]),
  ([POSTED_R1], {70: [c(14, "builder-bot", "**Reply external:alice-1-1:** contested — it fires on push")]}, ["pr #70 comment 14 | regression: no | contested external:alice-1-1: it fires on push"])])
def test_collect_carries_an_unreplied_external_high_forward(world, tmp_path, monkeypatch, rounds, replies, expected):
  n = len(rounds) + 1
  kw = dict(rounds=rounds, launches=[{"round": i, "status": "exited 0"} for i in range(1, n + 1)], comments=replies)
  st0, card0, _ = seed(world, **kw)
  rid = open_head_review(world, st0, card0, "0" * 40, {"change-review": "", "external:alice": EXT})
  n == 3 and record(world, st0, rid, 2, "0" * 40, card0, {"change-review": ""})
  w = prepared(world, tmp_path, monkeypatch, **kw)
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, f"collected: {len(expected)} foreman findings"), out
  assert (w.dir / f"r{n}/foreman.findings").read_text(encoding="utf-8").splitlines() == [f"foreman-{n}-{i} | high | {e}" for i, e in enumerate(expected, 1)]


LATE = c(14, "builder-bot", "**Reply external:alice-1-1:** contested — it fires on push")


@pytest.mark.parametrize("earlier, replies, expected", [
  (None, {70: [LATE]}, ["pr #70 comment 14 | regression: no | contested external:alice-1-1: it fires on push"]),
  ("**Reply external:alice-1-1:** fixed", {}, []), ("**Reply external:alice-1-1:** contested — it fires", {70: [LATE]}, []),
  ("**Reply external:alice-1-1:** contested — it fires", {}, [])])
def test_a_reply_a_round_late_or_a_round_early_still_answers_an_external_finding(world, tmp_path, monkeypatch, earlier, replies, expected):
  """Round 3's collect: a contested reply to an external finding round 2 never saw is recorded, never dropped; a
  reply in round 2's window (its `comments.md`) still answers the finding, and a contest is recorded once."""
  kw = dict(rounds=[POSTED_R1, R2], launches=[{"round": i, "status": "exited 0"} for i in (1, 2, 3)], comments=replies)
  st0, card0, _ = seed(world, **kw)
  rid = open_head_review(world, st0, card0, "0" * 40, {"change-review": "", "external:alice": EXT})
  record(world, st0, rid, 2, "0" * 40, card0, {"change-review": ""})
  w = prepared(world, tmp_path, monkeypatch, **kw)
  if earlier:
    atomic_write(w.dir / "r2/comments.md", f"builder: builder-bot\n### pr #70 comment 9 by builder-bot at 2026-11-02T11:00:00Z\n{earlier}\n")
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, f"collected: {len(expected)} foreman findings"), out
  assert (w.dir / "r3/foreman.findings").read_text(encoding="utf-8").splitlines() == [f"foreman-3-{i} | high | {e}" for i, e in enumerate(expected, 1)]


COPY = "foreman-2-1 | high | src/hooks.py:3 at 0000000 | regression: no | unreplied external:alice-1-1: the hook never fires\n"
R3 = {**POSTED_R1, "round": 3, "launch": 3, "dispatch_id": "d3"}


@pytest.mark.parametrize("at, expected", [("2026-11-02T13:00:00Z", [CARRIED]), ("2026-11-02T16:00:00Z", [])])
def test_a_reply_to_a_carried_copy_counts_only_after_the_copy_is_posted(world, tmp_path, monkeypatch, at, expected):
  """`**Reply foreman-2-1:** fixed` written before round 2 (which carries external:alice-1-1 as foreman-2-1) is posted
  answers nothing: the copy did not exist yet, so round 3 carries the original again; the same reply after the post ends the carry."""
  r2 = {**R2, "posted_at": "2026-11-02T15:00:00Z"}
  kw = dict(rounds=[POSTED_R1, r2], launches=[{"round": i, "status": "exited 0"} for i in (1, 2, 3)], comments={})
  st0, card0, _ = seed(world, **kw)
  rid = open_head_review(world, st0, card0, "0" * 40, {"change-review": "", "external:alice": EXT})
  record(world, st0, rid, 2, "0" * 40, card0, {"change-review": "", "foreman": COPY})
  w = prepared(world, tmp_path, monkeypatch, **kw)
  atomic_write(w.dir / "r2/comments.md", f"builder: builder-bot\n### pr #70 comment 9 by builder-bot at {at}\n**Reply foreman-2-1:** fixed\n")
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, f"collected: {len(expected)} foreman findings"), out
  assert (w.dir / "r3/foreman.findings").read_text(encoding="utf-8").splitlines() == [f"foreman-3-{i} | high | {e}" for i, e in enumerate(expected, 1)]


@pytest.mark.parametrize("at, expected", [
  ("2026-11-02T13:00:00Z", [CARRIED]),
  ("2026-11-02T16:00:00Z", ["pr #70 comment 14 | regression: no | contested foreman-2-1: it fires on push"])])
def test_a_contest_of_a_carried_copy_counts_only_after_the_copy_is_posted(world, tmp_path, monkeypatch, at, expected):
  """`**Reply foreman-2-1:** contested` written before round 2 (which carries external:alice-1-1 as foreman-2-1) is
  posted contests nothing: round 3 records no contest and carries the original again; after the post it is a contest."""
  r2 = {**R2, "posted_at": "2026-11-02T15:00:00Z"}
  kw = dict(rounds=[POSTED_R1, r2], launches=[{"round": i, "status": "exited 0"} for i in (1, 2, 3)],
            comments={70: [c(14, "builder-bot", "**Reply foreman-2-1:** contested — it fires on push", at=at)]})
  st0, card0, _ = seed(world, **kw)
  rid = open_head_review(world, st0, card0, "0" * 40, {"change-review": "", "external:alice": EXT})
  record(world, st0, rid, 2, "0" * 40, card0, {"change-review": "", "foreman": COPY})
  w = prepared(world, tmp_path, monkeypatch, **kw)
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, f"collected: {len(expected)} foreman findings"), out
  assert (w.dir / "r3/foreman.findings").read_text(encoding="utf-8").splitlines() == [f"foreman-3-{i} | high | {e}" for i, e in enumerate(expected, 1)]


@pytest.mark.parametrize("case", ["copy-settled", "copy-contested-then-original"])
def test_a_carried_copy_settled_or_contested_ends_the_carry_of_its_original(world, tmp_path, monkeypatch, case):
  """A carried copy settled by `review settle` ends its original's carry; a contest of the copy recorded in one round
  is not recorded again when a later round's reply contests the original (a contest is recorded once)."""
  rounds = [POSTED_R1, R2] if case == "copy-settled" else [POSTED_R1, R2, R3]
  n = len(rounds) + 1
  kw = dict(rounds=rounds, launches=[{"round": i, "status": "exited 0"} for i in range(1, n + 1)],
            comments={70: [LATE]} if n == 4 else {})
  st0, card0, _ = seed(world, **kw)
  rid = open_head_review(world, st0, card0, "0" * 40, {"change-review": "", "external:alice": EXT})
  record(world, st0, rid, 2, "0" * 40, card0, {"change-review": "", "foreman": COPY})
  if n == 3:
    assert world.run("review", "settle", "--review", rid, "--finding", "foreman-2-1", "--disposition", "fixed", "--runcard", card0)[0] == 0
  else:
    record(world, st0, rid, 3, "0" * 40, card0, {"change-review": "", "foreman": "foreman-3-1 | high | pr #70 comment 9 | regression: no | contested foreman-2-1: it fires\n"})
  w = prepared(world, tmp_path, monkeypatch, **kw)
  if n == 4:
    atomic_write(w.dir / "r3/comments.md", "builder: builder-bot\n### pr #70 comment 9 by builder-bot at 2026-11-02T13:00:00Z\n"
                                           "**Reply foreman-2-1:** contested — it fires\n")
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, "collected: 0 foreman findings"), out
  assert (w.dir / f"r{n}/foreman.findings").read_text(encoding="utf-8") == ""


def test_an_upheld_contest_of_a_carried_copy_takes_a_fixed_reply_under_the_original_id(world, tmp_path, monkeypatch):
  """external:alice-1-1 carried as foreman-2-1, contested as foreman-3-1, foreman-3-1 upheld: a `fixed` reply under
  any id of the finding's group (the external id included) answers the ruling."""
  replies = [c(15, "owner", "**Ruling:** foreman-3-1 finding upheld", at="2026-11-02T13:00:00Z"),
             c(16, "builder-bot", "**Reply external:alice-1-1:** fixed — the hook fires on push", at="2026-11-02T14:00:00Z")]
  kw = dict(rounds=[POSTED_R1, R2, R3], launches=[{"round": i, "status": "exited 0"} for i in range(1, 5)], comments={70: replies})
  st0, card0, _ = seed(world, **kw)
  rid = open_head_review(world, st0, card0, "0" * 40, {"change-review": "", "external:alice": EXT})
  record(world, st0, rid, 2, "0" * 40, card0, {"change-review": "", "foreman": COPY})
  record(world, st0, rid, 3, "0" * 40, card0, {"change-review": "", "foreman": "foreman-3-1 | high | pr #70 comment 9 | regression: no | contested foreman-2-1: it fires\n"})
  w = prepared(world, tmp_path, monkeypatch, **kw)
  atomic_write(w.dir / "r3/comments.md", "builder: builder-bot\n### pr #70 comment 9 by builder-bot at 2026-11-02T13:00:00Z\n"
                                         "**Reply foreman-2-1:** contested — it fires\n")
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert (code, out.strip()) == (0, "collected: 0 foreman findings"), out


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


@pytest.mark.parametrize("case", ["header-present", "header-after-mention", "stale-dispatch", "mention", "commit-differs"])
def test_review_post_guards(world, tmp_path, monkeypatch, case):
  w = prepared(world, tmp_path, monkeypatch)
  assert world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)[0] == 0
  claim = "ping @alice" if case == "mention" else "no hook"
  record(world, w.st, w.rid, 1, w.head, w.child, {"change-review": f"change-review-1-1 | high | src/hooks.py:1 | regression: no | {claim}\n"})
  if case == "header-present":
    world.gh.reviews.append({"id": 5, "commit_id": w.head, "submitted_at": "2026-11-03T09:00:00Z",
                             "body": f"**SuperEGM review round 1 (head {w.head[:7]})**\n\nx"})
  if case == "header-after-mention":  # `render_comment` puts `fix_request_mention` on line 1 when set
    world.gh.reviews.append({"id": 5, "commit_id": w.head, "submitted_at": "2026-11-03T09:00:00Z",
                             "body": f"@fixer\n**SuperEGM review round 1 (head {w.head[:7]})**\n\nx"})
  if case == "commit-differs":
    world.gh.reply_commit = "f" * 40
  did = "d9" if case == "stale-dispatch" else w.did
  code, out = world.run("review", "post", "--unit", UNIT, "--round", 1, "--dispatch", did, "--runcard", w.child)
  entry = json.loads(w.st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][0]
  expected = {"header-present": (0, "posted revise (already on the PR)", "posted", 0),
              "header-after-mention": (0, "posted revise (already on the PR)", "posted", 0),
              "stale-dispatch": (1, "dispatch: d9 is not U01's current dispatch (d1)", "collected", 0),
              "mention": (1, "comment:3: bare mention @alice", "collected", 0),
              "commit-differs": (1, f"posted on {'f' * 7}, not {w.head[:7]}: round 1 not counted", "collected", 1)}[case]
  assert (code, entry["phase"], len(w.posted)) == (expected[0], expected[2], expected[3]), out
  assert out.strip().splitlines()[0].startswith(expected[1]), out
  if case in ("header-present", "header-after-mention"):
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


@pytest.mark.parametrize("outcome", ["clean", "revise", None])
def test_review_ingest_records_posts_and_rewrites_clean(world, outcome):
  git = lambda *a: subprocess.run(["git", "-C", str(world.repo), *a], check=True, capture_output=True, text=True).stdout.strip()
  head, later = git("rev-parse", "HEAD"), (git("commit", "-q", "--allow-empty", "-m", "later"), git("rev-parse", "HEAD"))[1]
  t = lambda cid, login, body, commit=head: {"id": cid, "user": {"login": login}, "body": body, "path": "src/hooks.py", "line": 3, "commit_id": commit, "created_at": "t"}
  st, card, posted = seed(world, head=head, rounds=[{**POSTED_R1, "head": head, "outcome": outcome}] if outcome else [], owners=["owner"])
  rid = outcome and open_head_review(world, st, card, head, {"change-review": ""})
  atomic_write(st.path("review", UNIT, f"pr{PR}") / "r1/ci.json", json.dumps({"verdict": "ci green"}))
  world.gh.threads[PR] = [t(i, "devin-ai-integration[bot]", "nit: " + "spacing " * 25) for i in range(1, 201)] + [t(201, "alice", "**Issue**: no hook"), t(202, "bob", "bug: mine"),
    t(203, "alice", "bug: later", later), t(204, "builder-bot", "bug: x"), t(205, "owner", "**Ruling:** foreman-1-1 finding upheld")]
  world.gh.roles.update(alice={"role_name": "write"}, bob={"role_name": "read"})
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  if outcome is None:
    assert (code, out.strip(), posted) == (0, "0 ingested", [])
    return
  assert (code, out.split()) == (0, ["202", "ingested"] + (["outcome:", "revise"] if outcome == "clean" else []))
  body = posted[0]["body"]
  assert len(posted) == 1 and posted[0]["commit_id"] == head and body.startswith(review_mod.header(1, head)) and body.endswith("\nCI: ci green\n")
  assert body.count("external:devin-ai-integration[bot]-1-") == 200 and "external:alice-1-1 | medium | src/hooks.py:3 at " in body and "external:bob" not in body and "external:owner" not in body
  data = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))
  assert sorted(data["ingested"]) == list(range(1, 203)) and (data["rounds"][0]["outcome"], data["rounds"][0].get("rewritten_from")) == ("revise", "clean" if outcome == "clean" else None)
  assert st.path("journal").read_text(encoding="utf-8").count(f"{UNIT} ready again (external:alice)") == (outcome == "clean")
  world.gh.threads[PR][200]["body"] = "nit: no hook, a nit on reflection"
  assert world.run("review", "ingest", "--unit", UNIT, "--runcard", card)[1].strip() == "0 ingested" and len(posted) == 1
  alice = json.loads((st.path("reviews", rid) / "round-1.json").read_text(encoding="utf-8"))["reviewers"]["external:alice"]["findings"][0]
  assert (alice["severity"], alice["claim"]) == ("medium", "nit: no hook, a nit on reflection")
  assert sum(c[1].startswith(f"repos/{REPO}/collaborators/") for c in world.gh.calls) == 2
  world.gh.threads[PR].append(t(206, "carol", "bug: late")); world.gh.roles["carol"] = 500
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert (code, len(posted), json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["ingested"]) == (1, 1, data["ingested"]) and "HTTP 500" in out


def ingest_world(world, threads, roles=(), outcome="clean"):
  """A unit with one posted round on the repository's HEAD, its head review open with a clean `change-review`, and
  `threads` (`(id, login, body)`) on the PR at that head."""
  head = subprocess.run(["git", "-C", str(world.repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()
  st, card, posted = seed(world, head=head, rounds=[{**POSTED_R1, "head": head, "outcome": outcome}], owners=["owner"])
  rid = open_head_review(world, st, card, head, {"change-review": ""})
  atomic_write(st.path("review", UNIT, f"pr{PR}") / "r1/ci.json", json.dumps({"verdict": "ci green"}))
  world.gh.threads[PR] = [{"id": i, "user": {"login": who}, "body": body, "path": "src/hooks.py", "line": 3, "commit_id": head, "created_at": "t"}
                          for i, who, body in threads]
  world.gh.roles.update(roles)
  return st, card, posted, rid, head


def test_review_ingest_at_the_cap_rewrites_clean_to_cap_reached(world, monkeypatch):
  st, card, posted, rid, head = ingest_world(world, [(1, "alice", "bug: the hook never fires")], {"alice": {"role_name": "write"}})
  monkeypatch.setattr(review_mod, "CAP", 1)
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert (code, out.split()) == (0, ["1", "ingested", "outcome:", "cap-reached"]), out
  entry = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][0]
  assert (entry["outcome"], entry["rewritten_from"]) == ("cap-reached", "clean")
  assert st.path("journal").read_text(encoding="utf-8").count(f"{UNIT} ready again (external:alice)") == 1
  # stopped before the routing line was acted on: a retry prints it again until point 2 is opened after the round's post
  assert world.run("review", "ingest", "--unit", UNIT, "--runcard", card)[1].split() == ["0", "ingested", "outcome:", "cap-reached"]
  state = json.loads(st.path("state").read_text(encoding="utf-8"))  # the PR head moved past the reviewed one: `decision open` records it
  state.setdefault("status", {}).setdefault("units", {}).setdefault(UNIT, {})["head"] = "e" * 40
  atomic_write(st.path("state"), state)
  question = world.repo.parent / "q2.md"
  question.write_text("U01 at the cap after an external finding\n", encoding="utf-8")
  world.clock = 1_793_000_000.0  # 2026-10-26: a point 2 asked before the round's `posted_at` routes nothing
  code, out = world.run("decision", "open", "--unit", UNIT, "--point", "2", "--question", str(question), "--source", f"review {rid} cap", "--runcard", card)
  assert code == 0, out
  assert world.run("review", "ingest", "--unit", UNIT, "--runcard", card)[1].split() == ["0", "ingested", "outcome:", "cap-reached"]
  data = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))
  data["rulings"].append({"decision": data["decisions"][-1]["id"], "ruling": "stop", "by": "owner", "reason": "r", "posted": None, "posted_at": "t"})
  atomic_write(st.path("foreman", UNIT), data)
  world.clock = 1_794_000_000.0  # 2026-11-07, after the round's post
  code, out = world.run("decision", "open", "--unit", UNIT, "--point", "2", "--question", str(question), "--source", f"review {rid} cap", "--runcard", card)
  assert code == 0, out
  assert json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["decisions"][-1]["head"] == "e" * 40
  assert world.run("review", "ingest", "--unit", UNIT, "--runcard", card)[1].split() == ["0", "ingested"]
  assert st.path("journal").read_text(encoding="utf-8").count(f"{UNIT} ready again (external:alice)") == 1


def test_review_ingest_posts_when_another_review_merely_carries_its_header_and_ids(world):
  st, card, posted, rid, head = ingest_world(world, [(1, "alice", "bug: the hook never fires")], {"alice": {"role_name": "write"}})
  world.gh.reviews.append({"id": 5, "user": {"login": "mallory"}, "commit_id": head, "submitted_at": "2026-11-03T09:00:00Z",
                           "body": f"{review_mod.header(1, head)}\n\nexternal:alice-1-1 | high | PR at {head[:7]} | regression: no | all fine\n"})
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert (code, out.split()[:2], len(posted)) == (0, ["1", "ingested"], 1), out
  assert "external:alice-1-1 | high | src/hooks.py:3 at " in posted[0]["body"]


def test_review_ingest_posts_past_an_exact_copy_of_its_lines_on_another_commit(world):
  """An exact copy of the planned header and line, bound to another commit by another reviewer, is not the ingest's
  own comment: the ingest posts on the round's head and records, never refusing on the copy."""
  st, card, posted, rid, head = ingest_world(world, [(1, "alice", "bug: the hook never fires")], {"alice": {"role_name": "write"}})
  line = f"external:alice-1-1 | high | src/hooks.py:3 at {head[:7]} | regression: no | bug: the hook never fires"
  world.gh.reviews.append({"id": 5, "user": {"login": "mallory"}, "commit_id": "f" * 40, "submitted_at": "2026-11-03T09:00:00Z",
                           "body": f"{review_mod.header(1, head)}\n\n{line}\n"})
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert (code, out.split()[:2], len(posted)) == (0, ["1", "ingested"], 1), out
  assert line in posted[0]["body"] and posted[0]["commit_id"] == head


def test_review_ingest_refuses_to_finish_a_plan_into_an_earlier_round(world, monkeypatch):
  """Round 1's ingest posts alice's medium, then stops before recording it; round 2 is posted `clean`. The retry never
  finishes round 1's plan into round 1: it refuses, recording nothing, and the re-run it names plans afresh on round 2."""
  bot = "devin-ai-integration[bot]"
  st, card, posted, rid, head = ingest_world(world, [(1, bot, "nit: one"), (2, "alice", "issue: two")], {"alice": {"role_name": "write"}})
  real = review_mod.record_round
  monkeypatch.setattr(review_mod, "record_round", lambda a: 1 if a.reviewer == "external:alice" else real(a))
  assert world.run("review", "ingest", "--unit", UNIT, "--runcard", card)[0] == 1 and len(posted) == 1
  monkeypatch.setattr(review_mod, "record_round", real)
  data = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))
  data["rounds"].append({**POSTED_R1, "round": 2, "launch": 2, "dispatch_id": "d2", "head": head, "outcome": "clean"})
  atomic_write(st.path("foreman", UNIT), data)
  record(world, st, rid, 2, head, card, {"change-review": ""})
  atomic_write(st.path("review", UNIT, f"pr{PR}") / "r2/ci.json", json.dumps({"verdict": "ci green"}))
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert code == 1 and len(posted) == 1, out
  assert ("review ingest: round 1's unfinished ingest is not on the latest posted round (2): nothing recorded; "
          "re-run `review ingest` to plan its threads afresh on round 2") in out
  assert "external:alice" not in json.loads((st.path("reviews", rid) / "round-1.json").read_text(encoding="utf-8"))["reviewers"]
  assert json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][1]["outcome"] == "clean"
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert (code, out.split(), len(posted)) == (0, ["1", "ingested", "outcome:", "revise"], 2), out
  assert posted[1]["body"].startswith(review_mod.header(2, head)) and "external:alice-2-1 | medium | " in posted[1]["body"]
  rnd = json.loads((st.path("reviews", rid) / "round-2.json").read_text(encoding="utf-8"))
  assert [(f["id"], f["thread"]) for f in rnd["reviewers"]["external:alice"]["findings"]] == [("external:alice-2-1", 2)]
  assert sorted(json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["ingested"]) == [1, 2]


def test_review_ingest_marks_its_plan_done_only_after_every_save(world, monkeypatch):
  """Stopped at the save of the rewritten outcome, the plan is not `done`: the retry finishes it and rewrites `clean`."""
  st, card, posted, rid, head = ingest_world(world, [(1, "alice", "issue: the hook never fires")], {"alice": {"role_name": "write"}})
  real = review_mod.core.save_foreman
  def killed(st_, unit, data):
    if any(e.get("rewritten_from") for e in data["rounds"]):
      raise review_mod.core.HandoffError("killed")
    real(st_, unit, data)
  monkeypatch.setattr(review_mod.core, "save_foreman", killed)
  assert world.run("review", "ingest", "--unit", UNIT, "--runcard", card)[0] == 1 and len(posted) == 1
  assert json.loads((st.path("review", UNIT, f"pr{PR}") / "r1/ingest.json").read_text(encoding="utf-8"))["done"] is False
  monkeypatch.setattr(review_mod.core, "save_foreman", real)
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert (code, out.split()[2:], len(posted)) == (0, ["outcome:", "revise"], 1), out
  assert json.loads((st.path("review", UNIT, f"pr{PR}") / "r1/ingest.json").read_text(encoding="utf-8"))["done"] is True


def test_review_ingest_refuses_an_unknown_builder_login(world, monkeypatch):
  """No builder App and no builder token: the login `gh api user` would answer is the owner's, so ingest refuses."""
  st, card, posted, rid, head = ingest_world(world, [(1, "alice", "bug: one")], {"alice": {"role_name": "write"}})
  monkeypatch.delenv("SUPEREGM_BUILDER_TOKEN", raising=False)
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert code == 1 and "review ingest: SUPEREGM_BUILDER_TOKEN is not set: the builder's login is unknown" in out and posted == [], out
  assert json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8")).get("ingested") is None


@pytest.mark.parametrize("case", ["over-limit", "scan"])
def test_review_ingest_refusals_record_nothing(world, case):
  bot = "devin-ai-integration[bot]"
  threads = [(i, bot, "nit: " + "spacing " * 25) for i in range(1, 301)] if case == "over-limit" else [(1, bot, "nit: spacing")]
  st, card, posted, rid, head = ingest_world(world, threads)
  if case == "scan":
    set_config(world, repo=REPO, owners=["owner"], banned_terms=["(?i)ci green"])
  journal = st.path("journal").read_text(encoding="utf-8")
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  reason = "review ingest: comment over 65,536 bytes (300 threads)" if case == "over-limit" else "review ingest: comment:"
  assert code == 1 and reason in out and posted == [], out
  data = json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))
  rnd = json.loads((st.path("reviews", rid) / "round-1.json").read_text(encoding="utf-8"))
  assert data.get("ingested") is None and data["rounds"][0]["outcome"] == "clean" and not any(r.startswith("external:") for r in rnd["reviewers"])
  assert st.path("journal").read_text(encoding="utf-8") == journal


@pytest.mark.parametrize("fault", ["record", "commit"])
def test_review_ingest_resumes_an_interrupted_ingest_without_a_second_post(world, monkeypatch, fault):
  bot = "devin-ai-integration[bot]"
  st, card, posted, rid, head = ingest_world(world, [(1, bot, "bug: one"), (2, "alice", "issue: two")], {"alice": {"role_name": "write"}})
  real = review_mod.record_round
  if fault == "record":  # the comment is posted, the bot recorded, then alice's record refused
    monkeypatch.setattr(review_mod, "record_round", lambda a: 1 if a.reviewer == "external:alice" else real(a))
  else:
    world.gh.reply_commit = "f" * 40
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert code == 1 and len(posted) == 1, out
  if fault == "commit":
    assert "the comment stands on the PR, nothing recorded" in out
    world.gh.reply_commit = None
    code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
    assert code == 1 and f"header present on fffffff, not {head[:7]}: nothing recorded" in out and len(posted) == 1, out
    assert json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8")).get("ingested") is None
    return
  assert json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["ingested"] == [1]
  monkeypatch.setattr(review_mod, "record_round", real)
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert (code, out.split()[:2], len(posted)) == (0, ["1", "ingested"], 1), out
  rnd = json.loads((st.path("reviews", rid) / "round-1.json").read_text(encoding="utf-8"))
  assert [(f["id"], f["thread"]) for r in (f"external:{bot}", "external:alice") for f in rnd["reviewers"][r]["findings"]] == [
    (f"external:{bot}-1-1", 1), ("external:alice-1-1", 2)]
  assert sorted(json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["ingested"]) == [1, 2]


@pytest.mark.parametrize("fault", ["save", "mention", "deleted"])
def test_review_ingest_resumes_its_plan_whatever_window_it_stopped_in(world, monkeypatch, fault):
  """Round 2's windows: a record landed but `ingested[]` not saved; a mention on line 1 of the comment; a posted
  thread deleted before the retry. Each retry posts nothing and records each posted id against its own thread."""
  st, card, posted, rid, head = ingest_world(world, [(1, "alice", "issue: one"), (2, "alice", "issue: two")], {"alice": {"role_name": "write"}})
  if fault == "mention":
    config = json.loads((world.repo / ".superegm/config.json").read_text(encoding="utf-8"))
    set_config(world, **{k: v for k, v in config.items() if k != "artifacts_dir"}, fix_request_mention="@copilot")
  real_save, real_record = review_mod.core.save_foreman, review_mod.record_round
  if fault == "save":  # the round file written, then the ingest killed before anything else lands
    def killed(a):
      real_record(a)
      raise review_mod.core.HandoffError("killed")
    monkeypatch.setattr(review_mod, "record_round", killed)
  else:
    monkeypatch.setattr(review_mod, "record_round", lambda a: 1)
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert code == 1 and len(posted) == 1, out
  assert (fault == "mention") == posted[0]["body"].startswith("@copilot\n")
  monkeypatch.setattr(review_mod.core, "save_foreman", real_save); monkeypatch.setattr(review_mod, "record_round", real_record)
  if fault == "deleted":
    world.gh.threads[PR] = world.gh.threads[PR][1:]
  code, out = world.run("review", "ingest", "--unit", UNIT, "--runcard", card)
  assert code == 0 and len(posted) == 1, out
  rnd = json.loads((st.path("reviews", rid) / "round-1.json").read_text(encoding="utf-8"))
  assert [(f["id"], f["thread"], f["claim"]) for f in rnd["reviewers"]["external:alice"]["findings"]] == [
    ("external:alice-1-1", 1, "issue: one"), ("external:alice-1-2", 2, "issue: two")]
  assert sorted(json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["ingested"]) == [1, 2]
  assert world.run("review", "ingest", "--unit", UNIT, "--runcard", card)[1].strip() == "0 ingested" and len(posted) == 1


def test_review_ingest_numbers_after_the_highest_recorded_id(world):
  st, card, posted, rid, head = ingest_world(world, [(5, "alice", "bug: new")], {"alice": {"role_name": "write"}})
  record(world, st, rid, 1, head, card, {"external:alice": "external:alice-1-2 | low | src/hooks.py:3 at 0000000 | regression: no | old\n"})
  assert world.run("review", "ingest", "--unit", UNIT, "--runcard", card)[1].split()[:2] == ["1", "ingested"]
  rnd = json.loads((st.path("reviews", rid) / "round-1.json").read_text(encoding="utf-8"))
  assert [(f["id"], f["severity"]) for f in rnd["reviewers"]["external:alice"]["findings"]] == [("external:alice-1-2", "low"), ("external:alice-1-3", "high")]


def test_review_ingest_skips_a_landed_unit(world):
  st, card, posted, rid, head = ingest_world(world, [(1, "alice", "bug: after the merge")], {"alice": {"role_name": "write"}})
  state = json.loads(st.path("state").read_text(encoding="utf-8"))
  atomic_write(st.path("state"), {**state, "status": {"units": {UNIT: {"landed": True}}}})
  before = st.path("foreman", UNIT).read_text(encoding="utf-8")
  assert world.run("review", "ingest", "--unit", UNIT, "--runcard", card)[1].strip() == "0 ingested"
  assert posted == [] and st.path("foreman", UNIT).read_text(encoding="utf-8") == before


def test_review_ingest_that_finds_nothing_writes_nothing(world):
  st, card, posted, rid, head = ingest_world(world, [], outcome="revise")
  before = (st.path("foreman", UNIT).read_text(encoding="utf-8"), st.path("journal").read_text(encoding="utf-8"))
  assert world.run("review", "ingest", "--unit", UNIT, "--runcard", card)[1].strip() == "0 ingested"
  assert (st.path("foreman", UNIT).read_text(encoding="utf-8"), st.path("journal").read_text(encoding="utf-8")) == before


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
    "never merges, never approves, never edits the owner's working tree, never removes a worktree, never launches a session (the head's Astra lane excepted: one bounded foreground runner call), never convenes the judges, never infers that a builder died",
])
def test_foreman_brief_carries_the_round(line):
  assert line in (ROOT / "skills/wave/references/foreman_brief.md").read_text(encoding="utf-8"), line


PROSE = [("skills/wave/references/foreman_brief.md", n) for n in ("Step 2b, the Astra lane", "--timeout 540", "600000", "astra_brief.md", "--not-run 'not installed'",
                                                                   "stopped: two incomplete runs", "astra: ok <RUNNER>", "fresh every round", "every panel entry but `astra`", "(the head's Astra lane excepted: one bounded foreground runner call)", "record the lane once per round", "a head's diff is small", "ends `astra: ok` or `astra: not installed`")] + [
         ("resources/astra_lane.md", "## 8. The head lane"), ("resources/astra_lane.md", "--timeout 540"), ("resources/astra_lane.md", "one foreground"), ("resources/astra_lane.md", "head lane excepted"), ("resources/astra_lane.md", "interactive flow only"),
         ("resources/astra_lane.md", "The head review mapping"), ("resources/astra_lane.md", "the bare id `astra-<round>-<n>`"), ("resources/review_panels.md", "inspect launch is the interactive flow only"),
         ("resources/review_panels.md", "change-review, astra"), ("docs/claude.md", "one bounded foreground"), ("docs/claude.md", "astra.heads"),
         ("docs/privacy.md", "every head review of a SuperEGM wave"), ("docs/privacy.md", "the diff, the CI file, the PR body and the comments"),
         (".claude-plugin/agents/foreman.md", "the head's Astra lane excepted: one bounded foreground runner call"),
         ("resources/astra_lane.md", "Modified by SuperEGM (gsVAM), 2026: "), ("resources/astra_lane.md", "**Data notice (head lane).**"),
         ("skills/wave/SKILL.md", "Astra review lane"),
         ("skills/wave/references/foreman_brief.md", "`gpt-6-astra`"), ("skills/wave/references/foreman_brief.md", "`xhigh`"),
         ("skills/wave/references/foreman_brief.md", "never the review worktree's copy"), ("skills/wave/references/foreman_brief.md", "replace that separator in Astra's text"),
         ("resources/astra_lane.md", "the `# Prior round` section"), ("docs/privacy.md", "the `# Prior round` section"),
         ("docs/privacy.md", "outside a head review"), ("resources/review_panels.md", "(interactive flow only)"),
         ("skills/using-superegm/references/claude-code-tools.md", "the head's Astra lane excepted")]


@pytest.mark.parametrize("path, needle", PROSE)
def test_the_head_lane_prose(path, needle):
  assert needle in (ROOT / path).read_text(encoding="utf-8"), (path, needle)


ABSENT = [("docs/privacy.md", "never runs on a pull request head"), ("docs/privacy.md", "one reviewer of a spec, plan or integrate review"),
          ("skills/wave/SKILL.md", "Astra inspect lane"), ("resources/astra_lane.md", "through the inspect launch of section 3b."),
          ("resources/astra_lane.md", "A wave's pull request review uses the runner's `inspect` subcommand"),
          ("resources/astra_lane.md", "writes the exact line and that Bash timeout into")]


@pytest.mark.parametrize("path, text", ABSENT)
def test_the_head_lane_prose_drops_the_stale_claims(path, text):
  assert text not in " ".join((ROOT / path).read_text(encoding="utf-8").split()), (path, text)


FILES = [".claude-plugin/agents/foreman.md", "skills/wave/references/foreman_brief.md",
         "skills/plan/scripts/superegm/foreman.py", "skills/plan/scripts/superegm/prepare.py",
         "skills/plan/scripts/superegm/collect.py"]
TERMS = ["head-moved", "run folder", "run_folder", "`launched`", "inspect", "Blocker", "Major",
         "wave_round_", "pr_comment_", "wave_dispositions", "egm-change-review", "refs/egm/", "foreman_<unit-id>_state.json",
         "--verdict", ".egm/handoff.json", "handoff_state.json", "new triple", "require_reviewed_pair", "unit_file_text",
         "record-launch", "SendMessage"]


@pytest.mark.parametrize("term", TERMS)
@pytest.mark.parametrize("file", FILES)
def test_removed_mechanisms_are_not_named(file, term):
  assert term not in (ROOT / file).read_text(encoding="utf-8"), (file, term)
