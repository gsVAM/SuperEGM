# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's test world (the fake gh, the harness, the sample repository and plan) moved out of test_helper.py so every unit's tests share it; the sample plan in the section 9.1 grammar under an approval record (U05); the PR review threads and collaborator roles of the fake gh (U21); the one-comment route `issues/comments/<id>` (U22).

"""The test world: a temporary repository, a store, the fake `gh` and the harness.

The fake `gh` is extensible: `world.gh.extend(word, handler)` serves `gh <word> ...`
from `handler(args, cwd, token=None) -> (code, stdout, stderr)` before the built-in
`do_<word>` methods, so a later unit adds the calls its subcommand makes without
editing this file.
"""

import hashlib
import importlib
import json
from pathlib import Path
import re
import runpy
import subprocess
import sys
import traceback
import urllib.parse

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills/plan/scripts"
HELPER = SCRIPTS / "superegm.py"
REPO = "example-org/webhooks"
CONFIG = ".superegm/config.json"

for folder in (SCRIPTS, Path(__file__).resolve().parent):
  if str(folder) not in sys.path:
    sys.path.insert(0, str(folder))

DESIGN = """# Webhook delivery

*   **Status:** Approved

## Open Questions

*   Retry ceiling: 5 or 10 attempts?

## Detailed Implementation Plan

### Target Files to Create/Modify

#### 1. `src/webhooks/queue.ts` (Create)

*   **Proposed Changes**: `enqueue(event)` and `dequeue()`.

#### 2. `src/webhooks/deliver.ts` (Create)

*   **Proposed Changes**: `deliver(job)`; `queue.ts` gains `requeue(job, delay)`.

#### 3. `src/webhooks/admin.ts` (Create)

*   **Proposed Changes**: `GET /admin/webhooks` lists jobs.

### Verification Plan

*   `npm test -- src/webhooks/queue.test.ts`
*   `npm test -- src/webhooks/deliver.test.ts`
*   `npm test -- src/webhooks/admin.test.ts`
"""

UNITS = """### U01: Webhook queue
| Field | Value |
| --- | --- |
| Objective | An in-memory queue with enqueue and dequeue exists. |
| Scope paths | `src/webhooks/queue.ts` (create), `src/webhooks/queue.test.ts` (create) |
| Design range | `docs/designs/sample.md:13-15 (#### 1. src/webhooks/queue.ts)` |
| Blocked by | none |
| Shared files | `src/webhooks/queue.ts`: before U02 |
| Risk | low: new module |
| Size | S |

Interfaces
- Produces: enqueue(event) -> void
- Produces: dequeue() -> Job | undefined

Definition of done
1. The test for each Step was committed before its implementation (checked by superegm tdd-order)
2. Run `npm test -- src/webhooks/queue.test.ts` — the enqueue and dequeue order cases pass
3. CI green on the head

Review focus (this unit)
- U01: an empty queue — dequeue returns undefined; pinned by `dequeue_empty`

Steps
1. Write the failing test `dequeue_empty` in `src/webhooks/queue.test.ts`:
   ```ts
   test("dequeue_empty", () => expect(dequeue()).toBeUndefined());
   ```
   Implement `enqueue(event)` and `dequeue()` in `src/webhooks/queue.ts`.

Decide before build
- none

### U02: Delivery worker
| Field | Value |
| --- | --- |
| Objective | A delivery worker posts payloads and retries failed jobs. |
| Scope paths | `src/webhooks/deliver.ts` (create), `src/webhooks/deliver.test.ts` (create), `src/webhooks/queue.ts` (modify) |
| Design range | `docs/designs/sample.md:17-19 (#### 2. src/webhooks/deliver.ts)` |
| Blocked by | U01 |
| Shared files | `src/webhooks/queue.ts`: after U01, before U03; `src/webhooks/types.ts`: before U03 |
| Risk | medium: touches the request path |
| Size | S |

Interfaces
- Consumes: dequeue() (U01)
- Produces: deliver(job) -> Promise<void>

Definition of done
1. The test for each Step was committed before its implementation (checked by superegm tdd-order)
2. Run `npm test -- src/webhooks/deliver.test.ts` — cases A, B, C pass
3. CI green on the head

Review focus (this unit)
- U02: a failed post — the job is requeued with a delay; pinned by `deliver_requeues`

Steps
1. Write the failing test `deliver_requeues` in `src/webhooks/deliver.test.ts`:
   ```ts
   test("deliver_requeues", async () => expect(await deliver(failing)).toBe("requeued"));
   ```
   Implement `deliver(job)` and `requeue(job, delay)` in `src/webhooks/deliver.ts`.

Decide before build
- D1 Retry ceiling (5 or 10 attempts)? options: (a) 5 attempts; (b) 10 attempts; owner: the design author; default: (a); blocking: no

### U03: Admin endpoint
| Field | Value |
| --- | --- |
| Objective | An admin endpoint lists queued and failed jobs. |
| Scope paths | `src/webhooks/admin.ts` (create), `src/webhooks/admin.test.ts` (create), `src/webhooks/queue.ts` (modify) |
| Design range | `docs/designs/sample.md:21-23 (#### 3. src/webhooks/admin.ts)` |
| Blocked by | U02 |
| Shared files | `src/webhooks/queue.ts`: after U02; `src/webhooks/types.ts`: after U02 |
| Risk | low: read-only endpoint |
| Size | S |

Interfaces
- Consumes: dequeue() (U01)
- Produces: listJobs() -> Job[]

Definition of done
1. The test for each Step was committed before its implementation (checked by superegm tdd-order)
2. Run `npm test -- src/webhooks/admin.test.ts` — the listing case passes
3. CI green on the head

Review focus (this unit)
- U03: an empty queue — the listing is empty; pinned by `admin_lists_empty`

Steps
1. Write the failing test `admin_lists_empty` in `src/webhooks/admin.test.ts`:
   ```ts
   test("admin_lists_empty", async () => expect(await listJobs()).toEqual([]));
   ```
   Implement `listJobs()` in `src/webhooks/admin.ts`.

Decide before build
- D2 Page size for the listing? options: (a) 50; (b) 25; owner: the user; default: (a); blocking: yes
"""


def git(args, cwd):
  return subprocess.run(["git", *args], cwd=str(cwd), check=True, capture_output=True,
                        text=True).stdout


def write_config(repo: Path, config: dict) -> None:
  path = repo / CONFIG
  path.parent.mkdir(exist_ok=True)
  path.write_text(json.dumps(config), encoding="utf-8")


def make_repo(path: Path, origin_url=f"https://github.com/{REPO}.git", config=None) -> Path:
  path.mkdir(parents=True, exist_ok=True)
  git(["init", "-q", "-b", "main"], path)
  git(["config", "user.email", "egm@example.invalid"], path)
  git(["config", "user.name", "EGM"], path)
  (path / "docs/designs").mkdir(parents=True)
  (path / "docs/designs/sample.md").write_text(DESIGN, encoding="utf-8")
  if config is not None:
    write_config(path, {"artifacts_dir": str(path.parent / "artifacts"), **config})
  git(["add", "-A"], path)
  git(["commit", "-qm", "Sample design"], path)
  git(["remote", "add", "origin", origin_url], path)
  if config is not None:
    approve(path, path.parent / "artifacts")
  return path


def make_plan(folder: Path, repo: Path, units=UNITS) -> Path:
  folder.mkdir(parents=True, exist_ok=True)
  plan = folder / "handoff_plan.md"
  plan.write_text(f"# Handoff plan: Webhook delivery\n\nDesign: `{repo / 'docs/designs/sample.md'}`\n\n"
                  f"## 1. Issue template\n\n(the layout of references/issue_template.md)\n\n"
                  f"## Global constraints\n- TypeScript strict mode, no new dependencies\n\n## 2. Units\n\n{units}",
                  encoding="utf-8")
  return plan


def approve(repo: Path, artifacts: Path) -> dict:
  """The record `approve-spec --yes` writes for the sample spec, so `graph` runs under an approval."""
  spec = repo / "docs/designs/sample.md"
  sha = hashlib.sha256(spec.read_bytes()).hexdigest()
  record = {"path": str(spec), "sha256": sha, "commit": git(["rev-parse", "--short", "HEAD"], repo).strip(),
            "runcard": None, "review": None, "approved_at": "2026-11-03T00:00:00Z", "amended": [], "voided_by": None,
            "handoff_id": f"sample-{sha[:6]}"}
  path = artifacts / "approvals" / "sample.json"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(json.dumps(record), encoding="utf-8")
  return record


class FakeGitHub:
  """An in-process `gh` that keeps a small GitHub in memory and records calls."""

  def __init__(self, repo=REPO):
    self.repo = repo
    self.labels = {"bug": {"name": "bug", "color": "d73a4a"}}
    self.issues = {}
    self.next_number, self.next_id = 1, 1000
    self.sub_issues, self.blocked_by = {}, {}
    self.prs, self.graphql = {}, {}
    self.check_runs, self.combined = {}, {}
    self.comments, self.reviews = {}, {}
    self.threads, self.roles = {}, {}  # PR review comments by PR number; collaborator permission by login (an int: that HTTP error)
    self.calls = []
    self.push = True
    self.rate_limit_hits = 0
    self.link_422_once = set()
    self.read_only = False
    self.handlers = {}

  def extend(self, word, handler):
    """Serve `gh <word> ...` from `handler(args, cwd, token=None)`."""
    self.handlers[word] = handler

  def __call__(self, args, cwd, token=None):
    args = list(args)
    self.calls.append(args)
    if args[0] in ("api", "auth") and "-R" in args:
      return 1, "", "unknown shorthand flag: 'R' in -R"
    if any("{owner}" in a or "{repo}" in a for a in args):
      return 1, "", "placeholder would resolve from cwd"
    if args[0] in self.handlers:
      return self.handlers[args[0]](args, cwd, token=token)
    method = getattr(self, "do_" + args[0], None)
    if method is None:
      return 1, "", f"unexpected: {args}"
    try:
      return method(args)
    except KeyError as error:
      return 1, "", f"gh: Not Found (HTTP 404): {error!r}\n{traceback.format_exc()}"

  def ok(self, data=None, text=None):
    return 0, text if text is not None else (json.dumps(data) if data is not None else ""), ""

  def do_auth(self, args):
    assert args[1:] == ["status", "--hostname", "github.com"], args
    return self.ok(text="Logged in to github.com\n")

  def do_label(self, args):
    assert args[1] == "create" and "-R" in args and "--force" not in args, args
    self.assert_write()
    name = args[2]
    if name in self.labels:
      return 1, "", "label already exists (HTTP 422)"
    self.labels[name] = {"name": name, "color": args[args.index("--color") + 1]}
    return self.ok(text=f"https://github.com/{self.repo}/labels/{name}\n")

  def assert_write(self):
    if self.read_only:
      raise AssertionError("write in a read-only run")

  def do_issue(self, args):
    assert "-R" in args and args[args.index("-R") + 1] == self.repo, args
    if args[1] == "create":
      self.assert_write()
      if self.rate_limit_hits:
        self.rate_limit_hits -= 1
        return 1, "", "gh: You have exceeded a secondary rate limit (HTTP 403)"
      body = Path(args[args.index("--body-file") + 1]).read_text(encoding="utf-8")
      labels = [args[i + 1] for i, a in enumerate(args) if a == "--label" and args[i + 1] in self.labels]
      number = self.next_number
      self.next_number += 1
      self.issues[number] = {"number": number, "id": self.next_id, "title": args[args.index("--title") + 1],
                             "body": body, "labels": labels, "state": "open", "state_reason": None}
      self.next_id += 1
      return self.ok(text=f"https://github.com/{self.repo}/issues/{number}\n")
    if args[1] == "view":
      issue = self.issues[int(args[2])]
      return self.ok({"body": issue["body"], "labels": [{"name": l} for l in issue["labels"]]})
    if args[1] == "edit":
      self.assert_write()
      issue = self.issues[int(args[2])]
      added = args[args.index("--add-label") + 1]
      if added not in self.labels:
        # The real gh refuses a label the repository does not have; a fake that
        # appends it hides exactly the bug this guards.
        return 1, "", f"could not add label: '{added}' not found (HTTP 422)"
      issue["labels"] = [l for l in issue["labels"] if l != args[args.index("--remove-label") + 1]]
      issue["labels"].append(added)
      return self.ok(text="")
    raise AssertionError(args)

  def do_pr(self, args):
    assert "-R" in args, args
    if args[1] == "view":
      return self.ok(self.prs[int(args[2])])
    if args[1] == "list":
      assert "--limit" in args and args[args.index("--limit") + 1] == "1000", args
      return self.ok(list(self.prs.values()))
    raise AssertionError(args)

  @staticmethod
  def endpoint_of(args):
    skip = False
    for arg in args[1:]:
      if skip:
        skip = False
      elif arg in ("-X", "-F", "-f", "-q"):
        skip = True
      elif not arg.startswith("-"):
        return arg
    raise AssertionError(args)

  def do_api(self, args):
    endpoint = self.endpoint_of(args)
    paginate = "--paginate" in args
    if endpoint == "graphql":
      query = next(a for a in args if a.startswith("query="))
      assert "includeClosedPrs: true" in query and "$endCursor" in query, query
      # R9-03: String! variables must travel with -f; -F would coerce `2048`
      # or `true` to a non-string and GraphQL would reject them.
      for key in ("owner=", "name="):
        i = next(i for i, a in enumerate(args) if a.startswith(key))
        assert args[i - 1] == "-f", (key, args)
      i = next(i for i, a in enumerate(args) if a.startswith("number="))
      assert args[i - 1] == "-F", args
      assert paginate and "--slurp" in args
      number = int([a for a in args if a.startswith("number=")][0][7:])
      nodes = self.graphql.get(number, [])
      return self.ok([{"data": {"repository": {"issue": {"closedByPullRequestsReferences": {
          "nodes": nodes, "pageInfo": {"hasNextPage": False, "endCursor": None}}}}}}])
    if "-X" in args and args[args.index("-X") + 1] == "POST":
      self.assert_write()
      assert "-i" in args, args
      fields = dict(a.split("=", 1) for a in args[args.index("-F") + 1::2] if "=" in a)
      fields = {k: v for k, v in fields.items() if not k.startswith("-")}
      match = re.fullmatch(r"repos/([^/]+/[^/]+)/issues/(\d+)/sub_issues", endpoint)
      if match:
        assert fields["sub_issue_id"].isdigit(), fields
        if ("sub", int(match.group(2))) in self.link_422_once:
          self.link_422_once.discard(("sub", int(match.group(2))))
          self.sub_issues.setdefault(int(match.group(2)), []).append(int(fields["sub_issue_id"]))
          return 1, "HTTP/2.0 422 Unprocessable Entity\n\n{}", "gh: Validation Failed (HTTP 422)"
        self.sub_issues.setdefault(int(match.group(2)), []).append(int(fields["sub_issue_id"]))
        return self.ok(text="HTTP/2.0 201 Created\ncontent-type: application/json\n\n{}")
      match = re.fullmatch(r"repos/([^/]+/[^/]+)/issues/(\d+)/dependencies/blocked_by", endpoint)
      if match:
        assert fields["issue_id"].isdigit(), fields
        self.blocked_by.setdefault(int(match.group(2)), []).append(int(fields["issue_id"]))
        return self.ok(text="HTTP/2.0 201 Created\n\n{}")
      raise AssertionError(args)
    path, _, query = endpoint.partition("?")
    assert path.startswith(f"repos/{self.repo}") or path.startswith("repos/"), endpoint
    rest = path[len(f"repos/{self.repo}"):]
    if rest == "":
      assert args[2:4] == ["-q", ".permissions"], args
      return self.ok({"push": self.push, "pull": True})
    if rest == "/labels":
      assert paginate and "--slurp" in args, args
      return self.ok([list(self.labels.values())])
    if rest == "/issues":
      assert paginate, args
      label = urllib.parse.parse_qs(query).get("labels", [None])[0]
      items = [i for i in self.issues.values() if label in i["labels"]]
      return self.ok([items])
    match = re.fullmatch(r"/issues/(\d+)", rest)
    if match:
      issue = self.issues[int(match.group(1))]
      return self.ok({**issue, "labels": [{"name": l} for l in issue["labels"]]})
    match = re.fullmatch(r"/issues/comments/(\d+)", rest)
    if match:  # one comment by its id, wherever it was posted (U22's read-back of a session ruling)
      found = [c for cs in self.comments.values() for c in cs if str(c.get("id")) == match.group(1)]
      return self.ok(found[0]) if found else (1, "", "gh: Not Found (HTTP 404)")
    match = re.fullmatch(r"/issues/(\d+)/comments", rest)
    if match:
      assert paginate, args
      return self.ok([self.comments.get(int(match.group(1)), [])])
    match = re.fullmatch(r"/pulls/(\d+)/(comments|reviews)", rest)
    if match:
      assert paginate and "--slurp" in args, args
      store = self.threads if match.group(2) == "comments" else self.reviews
      return self.ok([store.get(int(match.group(1)), [])])
    match = re.fullmatch(r"/collaborators/([^/]+)/permission", rest)
    if match:
      role = self.roles.get(match.group(1), 404)
      if isinstance(role, int):
        return 1, "", f"gh: collaborator permission (HTTP {role})"
      return self.ok(role)
    match = re.fullmatch(r"/issues/(\d+)/sub_issues", rest)
    if match:
      assert paginate, args
      ids = self.sub_issues.get(int(match.group(1)), [])
      return self.ok([[{"id": i, "number": self.number_of(i)} for i in ids]])
    match = re.fullmatch(r"/issues/(\d+)/dependencies/blocked_by", rest)
    if match:
      assert paginate, args
      ids = self.blocked_by.get(int(match.group(1)), [])
      return self.ok([[{"id": i, "number": self.number_of(i)} for i in ids]])
    match = re.fullmatch(r"/commits/([0-9a-f]+)/check-runs", rest)
    if match:
      assert paginate, args
      runs = self.check_runs.get(match.group(1), [])
      return self.ok([{"total_count": len(runs), "check_runs": runs}])
    match = re.fullmatch(r"/commits/([0-9a-f]+)/status", rest)
    if match:
      data = self.combined.get(match.group(1), {"state": "pending", "statuses": []})
      pages = data.get("pages") or [{"state": data["state"], "statuses": data.get("statuses", [])}]
      if paginate:
        # `--paginate --slurp` yields an array of pages. A fake that returned a
        # dict here made read_ci iterate dict keys, collect nothing and fall
        # back silently - so the pagination path was never exercised (R7-05).
        assert "--slurp" in args, args
        return self.ok(pages)
      # The non-paginated endpoint returns the FIRST page only, like GitHub.
      # Returning [] here let the pagination test pass for the wrong reason
      # (empty CI -> waiting-for-ci), R8-05.
      return self.ok({"state": data["state"], "statuses": pages[0]["statuses"]})
    raise AssertionError(args)

  def number_of(self, issue_id):
    return next(i["number"] for i in self.issues.values() if i["id"] == issue_id)


# The skill whose card `Harness.run` opens for each gated subcommand (spec section 6).
SKILL_OF = {"approve-spec": "review-spec", "graph": "plan", "decide": "plan",
            "gate": "file", "dry-run": "file", "apply": "file", "verify": "file",
            "status": "wave", "launch": "wave", "record-launch": "wave", "collect": "wave", "prepare": "wave"}


class Harness:
  """The package with the fake injected; `run` returns (code, stdout + stderr).

  `run(*argv)` appends `--runcard <an open card of the serving skill>` to a
  gated subcommand; `card=None` sends the argv as written."""

  def __init__(self, capsys, now=1_700_000_000.0):
    import superegm
    # One package for the whole process: reload it so a name a test injected
    # (`find_remote`, `save_state`) never reaches the next test. The subcommand
    # modules reach every shared name as `core.<name>`, so an injection into
    # the package's namespace reaches all of them.
    importlib.reload(superegm)
    self.ns = vars(superegm)
    self.main = runpy.run_path(str(HELPER))["main"]
    self.gh = FakeGitHub()
    self.sleeps = []
    self.clock = now
    self.ns["GH"] = self.gh
    self.ns["_subprocess_gh"] = self.never
    self.ns["SLEEP"] = lambda s: (self.sleeps.append(s), self.advance(s))
    self.ns["NOW"] = lambda: self.clock
    self.capsys = capsys
    self.spec = None
    self.cards = {}

  @staticmethod
  def never(args, cwd, token=None):
    raise AssertionError(f"real gh must not run in tests: {args}")

  def advance(self, seconds):
    self.clock += seconds

  def run(self, *argv, card="auto"):
    argv = [str(a) for a in argv]
    if card == "auto" and argv and argv[0] in SKILL_OF and "--runcard" not in argv and "--help" not in argv:
      argv += ["--runcard", self.card(SKILL_OF[argv[0]])]
    try:
      code = self.main(argv)
    except SystemExit as stop:  # `--help` exits 0 after printing; argparse errors propagate
      if stop.code != 0:
        raise
      code = 0
    captured = self.capsys.readouterr()
    return code, captured.out + captured.err

  def open_card(self, skill, artifact):
    code, out = self.run("runcard", "open", "--skill", skill, "--artifact", artifact, card=None)
    assert code == 0, out
    return out.strip()

  def card(self, skill):
    """One open card per skill on the spec, reused across a test's runs."""
    if skill not in self.cards:
      self.cards[skill] = self.open_card(skill, self.spec)
    return self.cards[skill]


def make_world(tmp_path, capsys, monkeypatch, config=None, origin_url=f"https://github.com/{REPO}.git"):
  """What `world` builds, with the config and origin overridable."""
  if config is None:
    config = {"repo": REPO, "banned_terms": ["(?i)secret-codename"]}
  repo = make_repo(tmp_path / "repo", origin_url=origin_url, config=config)
  plan = make_plan(tmp_path / "plans", repo)
  harness = Harness(capsys)
  harness.repo, harness.plan, harness.artifacts = repo, plan, tmp_path / "artifacts"
  harness.spec = repo / "docs/designs/sample.md"
  monkeypatch.chdir(repo)
  return harness


def set_config(world, **keys):
  """Replace the repository's config with `keys`, keeping `artifacts_dir`."""
  current = json.loads((world.repo / CONFIG).read_text(encoding="utf-8"))
  write_config(world.repo, {"artifacts_dir": current["artifacts_dir"], **keys})


@pytest.fixture
def world(tmp_path, capsys, monkeypatch):
  return make_world(tmp_path, capsys, monkeypatch)


def handoff_store(world):
  """The world's store, its handoff resolved as a `--spec <the sample spec>` subcommand resolves it
  (the spec's latest approval; a flat store, `state.json` at the root, is its one legacy handoff)."""
  import argparse
  import superegm
  superegm.CURRENT_ARGS = argparse.Namespace(design=str(world.spec))
  return superegm.store(world.repo)


def state_of(world):
  return json.loads(handoff_store(world).path("state").read_text(encoding="utf-8"))


def unit_path(world, uid):
  """`unit_<id>.md` in the handoff's directory (after `graph` ran)."""
  return handoff_store(world).path("unit", uid)


def foreman_path(world, uid):
  return handoff_store(world).path("foreman", uid)


def round_of(data, n):
  """The `rounds[]` entry of round `n` in a foreman file, or {}."""
  return next((r for r in data.get("rounds") or [] if r.get("round") == n), {})


def result_for(world, uid, rnd):
  """An inspect result that is attributable to this round: full identity."""
  unit_file = unit_path(world, uid)
  data = json.loads(foreman_path(world, uid).read_text(encoding="utf-8")) \
      if foreman_path(world, uid).is_file() else {}
  record = round_of(data, rnd)
  return {"status": "completed", "plan": str(unit_file),
          "plan_sha256": hashlib.sha256(unit_file.read_bytes()).hexdigest(),
          "base": record.get("merge_base"), "repo": record.get("worktree"),
          "started_at": world.clock}


def converge(artifacts: Path, handoff_id: str, uid: str, sha: str, cycle: int = 1) -> None:
  """What `review-plan` leaves for a converged unit (U04's files, U04's review id): `review.json`
  and its converged round at the body hash, in the handoff's own `reviews/` (`plan-<unit>-c<n>`; a legacy flat store
  keeps U04's `<6 hex>-plan-<unit>-c<n>` at its root)."""
  import superegm
  legacy = (artifacts / "state.json").is_file()
  rid = f"{handoff_id[-6:]}-plan-{uid}-c{cycle}" if legacy else f"plan-{uid}-c{cycle}"
  folder = superegm.Store(artifacts, handoff_id=handoff_id, legacy=legacy).path("reviews", rid)
  folder.mkdir(parents=True, exist_ok=True)
  (folder / "review.json").write_text(json.dumps({"kind": "plan", "artifact": uid, "cycle": cycle, "reviewers": ["readiness"],
                                                  "runcard": "rc-plan", "converged": "yes", "converged_round": 1, "rulings": []}),
                                      encoding="utf-8")
  (folder / "round-1.json").write_text(json.dumps({"runcard": "rc-plan", "artifact_sha256": sha, "findings": {},
                                                   "what_ran": "completed"}), encoding="utf-8")


def pass_gate(world):
  """`graph`; every blocking decision answered by its default (a blocking item must be answered before
  the body can pass `scan`, spec section 9.1); every unit's plan review converged at its body hash;
  `gate --pass` on the spec."""
  assert world.run("graph", "--plan", world.plan)[0] == 0
  units = lambda: json.loads(handoff_store(world).path("units").read_text(encoding="utf-8"))["units"]
  for uid, unit in units().items():
    for decision in unit["decisions"]:
      if decision["blocking"] and not decision.get("answer"):
        assert world.run("decide", "--unit", uid, "--decision", decision["id"], "--default")[0] == 0
  handoff_id = state_of(world)["handoff_id"]
  for uid, unit in units().items():
    converge(world.artifacts, handoff_id, uid, unit["body_sha256"])
  code, out = world.run("gate", "--pass", "--spec", world.spec)
  assert code == 0, out


def dry_run(world):
  pass_gate(world)
  code, out = world.run("dry-run", "--spec", world.spec)
  assert code == 0, out
  return out


def applied(world):
  dry_run(world)
  assert world.run("apply", "--spec", world.spec, "--yes")[0] == 0
  world.gh.calls.clear()
  return world.gh


def close_as_completed(gh, number):
  gh.issues[number]["state"], gh.issues[number]["state_reason"] = "closed", "completed"


def make_pr(gh, number, head, base_sha="b" * 40, merged=None, closes=(), branch="feature"):
  gh.prs[number] = {"number": number, "state": "MERGED" if merged else "OPEN", "headRefName": branch,
                    "headRefOid": head, "baseRefName": "main", "baseRefOid": base_sha, "mergedAt": merged,
                    "isDraft": False,
                    "closingIssuesReferences": [{"number": n, "repository": {"name": r.split("/")[1], "owner": {"login": r.split("/")[0]}}}
                                                for r, n in closes]}
  return gh.prs[number]


def mark_launched(world, *units):
  """The mark `launch` leaves on a unit, written as another writer would: `launch`'s own
  preconditions (builder token, origin, protection) are the builders' tests' (test_builders.py)."""
  state = state_of(world)
  for uid in units:
    state["units"][uid]["launched"] = {"at": world.ns["now_iso"](), "runcard": world.card("wave")}
  handoff_store(world).path("state").write_text(json.dumps(state), encoding="utf-8")


def launchable(world):
  """What `launch` checks before the filed units: origin/main (a bare clone the fetch reaches)
  carrying the spec, the config and a pull_request workflow, and the spec's approval record
  (U04's form: the spec ends in `## Units` and a converged spec review precedes `approve-spec --spec`)."""
  (world.repo / ".github/workflows").mkdir(parents=True)
  (world.repo / ".github/workflows/tests.yml").write_text("on: [push, pull_request]\n", encoding="utf-8")
  world.spec.write_text(world.spec.read_text(encoding="utf-8") + "\n## Units\n\n| Unit | Scope | Blocked by | Size |\n"
                        "| --- | --- | --- | --- |\n| U01 | queue | — | S |\n", encoding="utf-8")
  git(["add", "-A"], world.repo); git(["commit", "-qm", "workflow"], world.repo)
  cid = world.card("review-spec")
  code, out = world.run("review", "open", "--kind", "spec", "--artifact", world.spec, "--reviewers", "design", "--runcard", cid, card=None)
  assert code == 0, out
  findings = world.artifacts.parent / "design-1.txt"
  findings.write_text("", encoding="utf-8")
  code, out = world.run("review", "record", "--review", out.strip(), "--round", "1", "--reviewer", "design",
                        "--findings", findings, "--runcard", cid, card=None)
  assert code == 0, out
  code, out = world.run("approve-spec", "--spec", world.spec, "--yes")
  assert code == 0, out
  bare = world.repo.parent / "origin.git"
  git(["clone", "-q", "--bare", str(world.repo), str(bare)], world.repo.parent)
  git(["remote", "set-url", "origin", str(bare)], world.repo)
  world.ns["find_remote"] = lambda root, repo: "origin"  # `remote -v` shows that path, not GitHub
