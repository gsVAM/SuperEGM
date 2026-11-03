# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's test world (the fake gh, the harness, the sample repository and plan) moved out of test_helper.py so every unit's tests share it.

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
CONFIG = ".egm/handoff.json"

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

Definition of done
1. `npm test -- src/webhooks/queue.test.ts` passes with enqueue and dequeue order cases.
2. CI (typecheck, lint, tests) is green on the PR head.

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

Definition of done
1. `npm test -- src/webhooks/deliver.test.ts` passes with cases A, B, C.
2. CI (typecheck, lint, tests) is green on the PR head.

Decide before build
- D1 Retry ceiling (5 or 10 attempts)? owner: the design author; default: 5; blocking: no

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

Definition of done
1. `npm test -- src/webhooks/admin.test.ts` passes with the listing case.
2. CI (typecheck, lint, tests) is green on the PR head.

Decide before build
- D2 Page size for the listing? owner: the user; default: 50; blocking: yes
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
    write_config(path, config)
  git(["add", "-A"], path)
  git(["commit", "-qm", "Sample design"], path)
  git(["remote", "add", "origin", origin_url], path)
  return path


def make_plan(folder: Path, repo: Path, units=UNITS) -> Path:
  folder.mkdir(parents=True, exist_ok=True)
  plan = folder / "handoff_plan.md"
  plan.write_text(f"# Handoff plan: Webhook delivery\n\nDesign: `{repo / 'docs/designs/sample.md'}`\n\n"
                  f"## Units\n\n{units}", encoding="utf-8")
  return plan


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


class Harness:
  """The package with the fake injected; `run` returns (code, stdout + stderr)."""

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

  @staticmethod
  def never(args, cwd, token=None):
    raise AssertionError(f"real gh must not run in tests: {args}")

  def advance(self, seconds):
    self.clock += seconds

  def run(self, *argv, card="auto"):
    code = self.main([str(a) for a in argv])
    captured = self.capsys.readouterr()
    return code, captured.out + captured.err


def make_world(tmp_path, capsys, monkeypatch, config=None, origin_url=f"https://github.com/{REPO}.git"):
  """What `world` builds, with the config and origin overridable."""
  if config is None:
    config = {"repo": REPO, "banned_terms": ["(?i)secret-codename"]}
  repo = make_repo(tmp_path / "repo", origin_url=origin_url, config=config)
  plan = make_plan(tmp_path / "artifacts", repo)
  harness = Harness(capsys)
  harness.repo, harness.plan, harness.artifacts = repo, plan, plan.parent
  harness.spec = repo / "docs/designs/sample.md"
  monkeypatch.chdir(repo)
  return harness


def set_config(world, **keys):
  """Replace the repository's config with `keys`."""
  write_config(world.repo, keys)


@pytest.fixture
def world(tmp_path, capsys, monkeypatch):
  return make_world(tmp_path, capsys, monkeypatch)


def result_for(world, uid, rnd):
  """An inspect result that is attributable to this round: full identity."""
  unit_file = world.artifacts / f"unit_{uid}.md"
  data = json.loads((world.artifacts / f"foreman_{uid}_state.json").read_text(encoding="utf-8")) \
      if (world.artifacts / f"foreman_{uid}_state.json").is_file() else {}
  record = (data.get("rounds") or {}).get(str(rnd)) or {}
  return {"status": "completed", "plan": str(unit_file),
          "plan_sha256": hashlib.sha256(unit_file.read_bytes()).hexdigest(),
          "base": record.get("merge_base"), "repo": record.get("worktree"),
          "started_at": world.clock}


def state_of(world):
  return json.loads((world.artifacts / "handoff_state.json").read_text(encoding="utf-8"))


def pass_gate(world):
  assert world.run("graph", "--plan", world.plan)[0] == 0
  assert world.run("gate", "--plan", world.plan, "--reviewed", "--round", 1)[0] == 0
  code, out = world.run("gate", "--plan", world.plan, "--pass", "--what-ran", "astra: not run (test)")
  assert code == 0, out


def dry_run(world):
  pass_gate(world)
  code, out = world.run("dry-run", "--plan", world.plan)
  assert code == 0, out
  return out


def applied(world):
  dry_run(world)
  assert world.run("apply", "--plan", world.plan, "--yes")[0] == 0
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
