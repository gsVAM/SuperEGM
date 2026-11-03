# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's helper split into this package; the shared names live here, one module per subcommand.

"""EGM handoff helper: units -> graph, waves, issue bodies, dry run, GitHub.

Standard library only. Run as `python3 '<absolute path>' <subcommand> ...`
from the `egm-handoff` and `egm-wave` skills. Every subcommand is read-only
except `apply --yes` (GitHub writes), `defer --yes` (one label edit) and
`prepare` (refs under `refs/egm/` and worktrees under `${TMPDIR:-/tmp}/egm-wave`).
Every `gh` call goes through `gh()`; tests replace `GH`, `SLEEP` and `NOW`.
"""
import argparse
import importlib
import calendar
import difflib
import hashlib
import json
import os
import re
import subprocess
import urllib.parse
import sys
import tempfile
import time
from graphlib import CycleError, TopologicalSorter
from pathlib import Path
LABEL_RE = re.compile(r"^[^,\s]{1,50}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MENTION_CONFIG_RE = re.compile(r"^@[A-Za-z0-9][A-Za-z0-9-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?(?:\[bot\])?$")
# The whole token GitHub would resolve: `@user`, `@user[bot]`, or `@org/team` -
# a team mention subscribes every member, so the slash segment is part of the
# mention and must be matched and allow-listed as one literal (R8-01).
MENTION_RE = re.compile(r"(?<![\w./-])@[A-Za-z0-9][A-Za-z0-9-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?(?:\[bot\])?")
REMOTE_URL_RE = re.compile(
    r"^(?:https://github\.com/|git@github\.com:|ssh://git@github\.com/)"
    r"([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+?)(?:\.git)?/?$")
UNIT_RE = re.compile(r"^### (U\d{2,}): (.+?)\s*$")
UNIT_ID_RE = re.compile(r"^U\d{2,}$")
DESIGN_RANGE_RE = re.compile(r"^`([^`:]+):(\d+)-(\d+) \((.+)\)`$")
SCOPE_RE = re.compile(r"`([^`]+)` \((create|modify|delete)\)")
SHARED_RE = re.compile(r"^`([^`]+)`: (.+)$")
RISK_RE = re.compile(r"^(low|medium|high): (.+)$")
DOD_RE = re.compile(r"^(\d+)\. (.+)$")
DECIDE_RE = re.compile(
    r"^- (D\d+) (.+?) owner: (.+?); default: (.+?); blocking: (yes|no)$")
MARKER_RE = re.compile(r"^<!-- egm:handoff=(\S+) unit=(\S+) -->")
GEN_START, GEN_END = "<!-- egm:generated start -->", "<!-- egm:generated end -->"
FIELDS = ("Objective", "Scope paths", "Design range", "Blocked by",
          "Shared files", "Risk", "Size")
SIZE_LIMIT = {"S": 3, "M": 8, "L": 10**6}
BODY_LIMIT = 65_000
MAX_UNITS = 100
WRITE_WARN = 450
LABEL_COLOR = "1b6ef3"
BRANCH_PREFIX = "superegm"
WAITING_STATES = {"queued", "in_progress", "waiting", "requested", "pending"}
GREEN_CONCLUSIONS = {"success", "neutral", "skipped"}
NO_CI_SECONDS = 30 * 60
WAIT_INTERVAL = 90
EFFORTS = ("low", "medium", "high", "xhigh")
MODEL_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,63}$")

DEFAULT_CONFIG = {
    "repo": None,
    "artifacts_dir": None,
    "labels": {"unit": "superegm:unit", "wave_prefix": "superegm:wave-",
               "handoff_prefix": "superegm:handoff-", "tracking": "superegm:tracking",
               "stopped": "superegm:stopped", "extra": []},
    "issue_template": None,
    "tracking_issue_title": "Build: <design title>",
    "banned_terms": [],
    "fix_request_mention": None,
    "allowed_mentions": [],
}

DEFAULT_TEMPLATE = """<!-- egm:handoff={{handoff_id}} unit={{unit_id}} -->
**Objective.** {{objective}}

**Scope.**
{{scope}}

**Definition of done.**
{{dod}}

**Blocked by.** {{blocked_by}}

**Shared files and order.**
{{shared}}

**Decide before build.**
{{decisions}}

**Risk and size.** {{risk}}; size {{size}}.

**Design.** `{{design}}`

Part of #{{tracking}}. Wave {{wave}}. Branch: `{{branch}}`
"""

TRACKING_TEMPLATE = """<!-- egm:handoff={{handoff_id}} unit=tracking -->
Tracking issue for the build of `{{design}}`. Each unit below is one issue and one PR on a branch `{{branch_prefix}}/<unit>`; a unit starts when every unit it is blocked by has landed.

**Units by wave.**
{{waves}}

**Critical path.** {{critical_path}}

**Shared files.**
{{shared_files}}
"""


class HandoffError(Exception):
  """A stop with a message for the user; exit code 1."""


# ---------------------------------------------------------------- utilities


def sha256_text(text: str) -> str:
  return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
  return hashlib.sha256(path.read_bytes()).hexdigest()


def read_text(path: Path) -> str:
  return path.read_text(encoding="utf-8")


def atomic_write(path: Path, obj) -> None:
  """Write `obj` (text, bytes, or anything else as JSON) through a temp file
  and `os.replace`, creating parents. Inside the store, only a kind the
  running subcommand declared in its `WRITES` may be written."""
  path = Path(path)
  if CURRENT_WRITES is not None and STORE is not None and STORE.holds(path):
    kind = STORE.kind_of(path)
    if kind not in CURRENT_WRITES:
      raise HandoffError(f"{CURRENT_SUBCOMMAND} may not write {kind} ({path})")
  path.parent.mkdir(parents=True, exist_ok=True)
  tmp = path.with_name(path.name + f".tmp{os.getpid()}")
  if isinstance(obj, bytes):
    tmp.write_bytes(obj)
  elif isinstance(obj, str):
    tmp.write_text(obj, encoding="utf-8")
  else:
    tmp.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")
  os.replace(tmp, path)


def spec_slug(path) -> str:
  return Path(path).stem


class Store:
  """The files under `artifacts_dir`; every unit-keyed kind lives under the
  handoff's 6-hex prefix so two handoffs share one store."""

  FILES = {"state": "state.json", "journal": "journal.md", "plan": "handoff_plan.md",
           "units": "handoff_units.json", "bodies": "handoff_bodies.md"}
  KEYED = ("unit", "foreman", "launches", "worktrees", "review")

  def __init__(self, root: Path, handoff_id: str | None = None):
    self.root = Path(root)
    self.handoff_id = handoff_id

  def path(self, kind, *parts) -> Path:
    parts = [str(p) for p in parts]
    if kind in self.FILES:
      return self.root / self.FILES[kind]
    if kind == "report":
      return self.root / f"wave_{parts[0]}_report.md"
    if kind in ("approvals", "runcards"):
      return self.root / kind / f"{parts[0]}.json"
    if kind in ("reviews", "judges", "file"):
      return self.root.joinpath(*([kind] if kind != "file" else []), *parts)
    if kind not in self.KEYED:
      raise HandoffError(f"unknown store kind {kind}")
    if not self.handoff_id:
      raise HandoffError("no handoff in this store: run approve-spec and graph first")
    base = self.root / self.handoff_id[-6:]
    if kind == "unit":
      return base / f"unit_{parts[0]}.md"
    if kind == "foreman":
      return base / "foreman" / f"{parts[0]}.json"
    if kind == "launches":
      name = parts[0] if "." in parts[0] else f"{parts[0]}.json"
      return base.joinpath("launches", name, *parts[1:])
    if kind == "review":
      number = parts[1] if parts[1].startswith("pr") else f"pr{parts[1]}"
      return base.joinpath("review", parts[0], number, *parts[2:])
    return base.joinpath(kind, *parts)

  def holds(self, path: Path) -> bool:
    return Path(path).resolve().is_relative_to(self.root.resolve())

  def kind_of(self, path: Path) -> str:
    parts = Path(path).resolve().relative_to(self.root.resolve()).parts
    names = {v: k for k, v in self.FILES.items()}
    if len(parts) == 1:
      if parts[0] in names:
        return names[parts[0]]
      return "report" if re.fullmatch(r"wave_\d+_report\.md", parts[0]) else "file"
    if parts[0] in ("approvals", "runcards", "reviews", "judges"):
      return parts[0]
    if re.fullmatch(r"[0-9a-f]{6}", parts[0]):
      if len(parts) == 2 and re.fullmatch(r"unit_.+\.md", parts[1]):
        return "unit"
      if parts[1] in self.KEYED:
        return parts[1]
    return "file"


STORE = None


def store(repo_root: Path) -> Store:
  """The store `.superegm/config.json` names, with the handoff `state.json` records."""
  global STORE
  root = Path(load_config(repo_root)["artifacts_dir"])
  STORE = Store(root, handoff_id=load_state(root).get("handoff_id"))
  return STORE


def journal(store: Store, line: str) -> None:
  """Append one fact; `O_APPEND` keeps concurrent lines whole."""
  path = store.path("journal")
  path.parent.mkdir(parents=True, exist_ok=True)
  fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
  try:
    os.write(fd, f"{now_iso()} {line}\n".encode("utf-8"))
  finally:
    os.close(fd)


def now_iso() -> str:
  return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW()))


def canonical(obj) -> str:
  return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def run_git(args, cwd: Path, check=True) -> str:
  result = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8")
  if not check:
    return result.stdout if result.returncode == 0 else ""
  if result.returncode != 0:
    raise HandoffError(f"git {' '.join(args)} failed in {cwd}: "
                       f"{result.stderr.strip() or result.stdout.strip()}")
  return result.stdout


def git_toplevel(path: Path) -> Path:
  folder = path if path.is_dir() else path.parent
  return Path(run_git(["rev-parse", "--show-toplevel"], folder).strip())


class GhError(Exception):

  def __init__(self, args, code, stdout, stderr):
    super().__init__(f"gh {' '.join(args)}: exit {code}: {stderr.strip() or stdout.strip()}")
    self.args_list, self.code, self.stdout, self.stderr = args, code, stdout, stderr

  @property
  def http_status(self):
    for text in (self.stdout, self.stderr):
      match = re.search(r"HTTP(?:/[\d.]+)? (\d{3})", text)
      if match:
        return int(match.group(1))
    return None

  @property
  def rate_limited(self) -> bool:
    text = (self.stdout + self.stderr).lower()
    return self.http_status in (403, 429) and (
        "rate limit" in text or "secondary" in text or "abuse" in text)

  @property
  def retry_after(self):
    match = re.search(r"(?im)^retry-after:\s*(\d+)", self.stdout)
    return int(match.group(1)) if match else None


GH_HOSTNAME = "github.com"


def gh_env():
  """Pin gh to github.com: GH_HOST in the environment would otherwise send
  every write to an enterprise server, which no approval or remote check in
  this helper looks at."""
  env = dict(os.environ)
  env["GH_HOST"] = GH_HOSTNAME
  env.pop("GH_ENTERPRISE_TOKEN", None)
  env.pop("GITHUB_ENTERPRISE_TOKEN", None)
  return env


def _subprocess_gh(args, cwd, token=None):
  env = gh_env()
  if token:
    env["GH_TOKEN"] = token
  result = subprocess.run(["gh", *args], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", env=env)
  return result.returncode, result.stdout, result.stderr


GH = _subprocess_gh
SLEEP = time.sleep
NOW = time.time


def gh(args, *, token=None) -> str:
  """Run `gh <args>` with cwd = the store; raise GhError on failure.

  `token`, when given, is the account the call runs as (GH_TOKEN)."""
  args = [str(a) for a in args]
  code, out, err = GH(args, STORE.root if STORE else Path.cwd(), token=token)
  if code != 0:
    raise GhError(args, code, out, err)
  return out


def gh_retry(args) -> str:
  """`gh` with the same bounded rate-limit retries the issue and link writes
  get: a secondary limit on a label must not end the run at the first refusal."""
  for attempt in range(4):
    try:
      return gh(args)
    except GhError as error:
      if error.rate_limited and attempt < 3:
        SLEEP(error.retry_after or 60)
        continue
      raise


def gh_json(args):
  out = gh(args)
  return json.loads(out) if out.strip() else None


def gh_pages(endpoint):
  """A paginated read with `--slurp`: pages are returned as one list, flattened."""
  pages = gh_json(["api", endpoint, "--paginate", "--slurp"]) or []
  items = []
  for page in pages:
    items.extend(page if isinstance(page, list) else [page])
  return items


def gh_post(endpoint, fields):
  """A content-creating `gh api -i -X POST` with secondary-limit retries.

  Returns (status, body_text). Raises GhError when the retries are exhausted.
  """
  args = ["api", "-i", "-X", "POST", endpoint]
  for key, value in fields.items():
    args += ["-F", f"{key}={value}"]
  for attempt in range(4):
    try:
      out = gh(args)
      head, _, body = out.partition("\n\n")
      status = int(re.search(r"HTTP(?:/[\d.]+)? (\d{3})", head).group(1)) if "HTTP" in head else 201
      return status, body
    except GhError as error:
      if error.rate_limited and attempt < 3:
        SLEEP(error.retry_after or 60)
        continue
      raise


# ------------------------------------------------------------- configuration


def parse_remote_url(url: str):
  match = REMOTE_URL_RE.match(url.strip())
  return f"{match.group(1)}/{match.group(2)}" if match else None


def load_config(repo_root: Path) -> dict:
  """Read `.superegm/config.json`; defaults when missing; unknown keys stop."""
  config = json.loads(json.dumps(DEFAULT_CONFIG))
  path = repo_root / ".superegm" / "config.json"
  config["_source"] = str(path) if path.is_file() else "defaults (no .superegm/config.json)"
  if path.is_file():
    data = json.loads(read_text(path))
    unknown = set(data) - set(DEFAULT_CONFIG)
    if unknown:
      raise HandoffError(f"{path}: unknown keys {sorted(unknown)}")
    for key, value in data.items():
      if key == "labels":
        unknown = set(value) - set(DEFAULT_CONFIG["labels"])
        if unknown:
          raise HandoffError(f"{path}: unknown label keys {sorted(unknown)}")
        config["labels"].update(value)
      else:
        config[key] = value
  if not config["repo"]:
    origin = run_git(["remote", "get-url", "origin"], repo_root)
    config["repo"] = parse_remote_url(origin)
    if not config["repo"]:
      raise HandoffError(f"cannot parse OWNER/NAME from origin `{origin.strip()}`: "
                         "set `repo` in .superegm/config.json")
  if not REPO_RE.match(config["repo"]):
    raise HandoffError(f"invalid repo `{config['repo']}` in {path}")
  artifacts = config["artifacts_dir"]
  if not artifacts or not Path(artifacts).is_absolute() \
      or Path(artifacts).resolve().is_relative_to(repo_root.resolve()):
    raise HandoffError(f"{path}: artifacts_dir must be an absolute path outside the working tree "
                       f"(run `superegm init`)")
  labels = config["labels"]
  for name in (labels["unit"], labels["tracking"], labels["stopped"], *labels["extra"]):
    if not LABEL_RE.match(name):
      raise HandoffError(f"invalid label `{name}` (must match {LABEL_RE.pattern})")
  for prefix in (labels["wave_prefix"], labels["handoff_prefix"]):
    if not prefix or not LABEL_RE.match(prefix):
      raise HandoffError(f"invalid label prefix `{prefix}`")
  mention = config["fix_request_mention"]
  if mention is not None and not MENTION_CONFIG_RE.match(mention):
    raise HandoffError(f"invalid fix_request_mention `{mention}`")
  allowed = config["allowed_mentions"]
  if not isinstance(allowed, list) or not all(
      isinstance(a, str) and MENTION_CONFIG_RE.match(a) for a in allowed):
    raise HandoffError("allowed_mentions must be a list of `@name` strings (the scan is not "
                       "code-aware, so list the mentions that legitimately appear in text)")
  if not isinstance(config["banned_terms"], list):
    raise HandoffError("banned_terms must be a list of regular expressions")
  for term in config["banned_terms"]:
    re.compile(term)
  config["remote"] = find_remote(repo_root, config["repo"])
  if config["issue_template"]:
    template_path = repo_root / config["issue_template"]
    if not template_path.is_file():
      raise HandoffError(f"issue_template {template_path} does not exist")
    config["_template"] = read_text(template_path)
    check_template(config["_template"])
  else:
    config["_template"] = DEFAULT_TEMPLATE
  return config


def check_template(template: str) -> None:
  first = template.splitlines()[0] if template else ""
  if first != "<!-- egm:handoff={{handoff_id}} unit={{unit_id}} -->":
    raise HandoffError("issue template must start with the marker line "
                       "`<!-- egm:handoff={{handoff_id}} unit={{unit_id}} -->`")
  for name in ("{{objective}}", "{{scope}}", "{{dod}}"):
    if name not in template:
      raise HandoffError(f"issue template lacks {name}")


def find_remote(repo_root: Path, repo: str) -> str:
  for line in run_git(["remote", "-v"], repo_root).splitlines():
    parts = line.split()
    # GitHub owner and name are case-insensitive: a remote at
    # Example-Org/WebHooks serves a config that says example-org/webhooks.
    if len(parts) >= 2 and (parse_remote_url(parts[1]) or "").lower() == repo.lower():
      return parts[0]
  raise HandoffError(f"no remote for {repo} in {repo_root}: add one or fix "
                     "`repo` in `.superegm/config.json`")


# ---------------------------------------------------------------- plan parse


class Unit:

  def __init__(self, uid, title, line):
    self.id, self.title, self.line = uid, title, line
    self.objective = ""
    self.scope = []        # [(path, action)]
    self.design_range = None  # (path, start, end, heading)
    self.blockers = []
    self.shared = []       # [(path, [(after|before, uid)])]
    self.risk = None       # (level, reason)
    self.size = None
    self.dod = []
    self.decisions = []    # [{id, question, owner, default, blocking}]

  def to_json(self, wave, preds):
    return {
        "id": self.id, "title": self.title, "objective": self.objective,
        "scope": [{"path": p, "action": a} for p, a in self.scope],
        "design_range": {"path": self.design_range[0], "start": self.design_range[1],
                         "end": self.design_range[2], "heading": self.design_range[3]},
        "blockers": self.blockers,
        "shared": [{"path": p, "order": [{"kind": k, "unit": u} for k, u in o]}
                   for p, o in self.shared],
        "risk": {"level": self.risk[0], "reason": self.risk[1]},
        "size": self.size, "dod": self.dod,
        "decisions": [{k: v for k, v in d.items() if k != "line"} for d in self.decisions],
        "wave": wave, "predecessors": sorted(preds),
    }


class Plan:

  def __init__(self, path: Path):
    self.path = path
    self.text = read_text(path)
    self.title = None
    self.design = None
    self.units = {}
    self.order = []
    self._parse()

  def _parse(self):
    lines = self.text.splitlines()
    inside_generated = False
    i = 0
    while i < len(lines):
      line = lines[i]
      if line.strip() == GEN_START:
        inside_generated = True
      elif line.strip() == GEN_END:
        inside_generated = False
      elif not inside_generated:
        if self.title is None and line.startswith("# "):
          self.title = line[2:].strip()
        elif line.startswith("Design: `") and self.design is None:
          match = re.match(r"^Design: `([^`]+)`", line)
          self.design = match.group(1)
        elif UNIT_RE.match(line):
          i = self._parse_unit(lines, i)
          continue
      i += 1
    if self.design is None:
      raise HandoffError(f"{self.path}:1: no `Design: \\`<path>\\`` line")
    if not self.units:
      raise HandoffError(f"{self.path}: no `### U<nn>: <title>` unit sections")
    self._check_references()

  def _fail(self, index, message):
    raise HandoffError(f"{self.path}:{index + 1}: {message}")

  def _parse_unit(self, lines, i):
    match = UNIT_RE.match(lines[i])
    uid, title = match.group(1), match.group(2)
    if uid in self.units:
      self._fail(i, f"duplicate unit {uid}")
    unit = Unit(uid, title, i + 1)
    i += 1
    if i + 1 >= len(lines) or lines[i].strip() != "| Field | Value |" \
        or lines[i + 1].strip() != "| --- | --- |":
      self._fail(i, f"{uid}: expected the `| Field | Value |` table")
    i += 2
    fields = {}
    while i < len(lines) and lines[i].startswith("|"):
      row = re.match(r"^\| ([^|]+?) \| (.*?) \|$", lines[i])
      if not row:
        self._fail(i, f"{uid}: malformed table row")
      fields[row.group(1)] = (row.group(2).strip(), i)
      i += 1
    for name in FIELDS:
      if name not in fields:
        self._fail(unit.line - 1, f"{uid}: missing field `{name}`")
    unknown = set(fields) - set(FIELDS)
    if unknown:
      self._fail(unit.line - 1, f"{uid}: unknown fields {sorted(unknown)}")
    self._parse_fields(unit, fields)
    while i < len(lines) and not lines[i].strip():
      i += 1
    if i >= len(lines) or lines[i].strip() != "Definition of done":
      self._fail(i if i < len(lines) else len(lines) - 1,
                 f"{uid}: expected `Definition of done`")
    i += 1
    while i < len(lines) and DOD_RE.match(lines[i]):
      item = DOD_RE.match(lines[i]).group(2).strip()
      if not ("`" in item or re.search(r"\bCI\b", item)):
        self._fail(i, f"{uid}: definition-of-done item names no command, path or CI check")
      unit.dod.append(item)
      i += 1
    if not unit.dod:
      self._fail(i, f"{uid}: empty definition of done")
    while i < len(lines) and not lines[i].strip():
      i += 1
    if i >= len(lines) or lines[i].strip() != "Decide before build":
      self._fail(i if i < len(lines) else len(lines) - 1,
                 f"{uid}: expected `Decide before build`")
    i += 1
    while i < len(lines) and lines[i].startswith("- "):
      if lines[i].strip() == "- none":
        i += 1
        continue
      decide = DECIDE_RE.match(lines[i])
      if not decide:
        self._fail(i, f"{uid}: decide-before-build item must read `- D<n> <question> "
                      "owner: <owner>; default: <default>; blocking: yes|no`")
      unit.decisions.append({"id": decide.group(1), "question": decide.group(2),
                             "owner": decide.group(3), "default": decide.group(4),
                             "blocking": decide.group(5) == "yes", "line": i + 1})
      i += 1
    self._check_decision_ids(unit)
    self.units[uid] = unit
    self.order.append(uid)
    return i

  def _parse_fields(self, unit, fields):
    value, line = fields["Objective"]
    if not value:
      self._fail(line, f"{unit.id}: empty objective")
    unit.objective = value
    value, line = fields["Scope paths"]
    unit.scope = SCOPE_RE.findall(value)
    if not unit.scope or ", ".join(f"`{p}` ({a})" for p, a in unit.scope) != value:
      self._fail(line, f"{unit.id}: scope paths must read `path` (create|modify|delete), comma separated")
    value, line = fields["Design range"]
    match = DESIGN_RANGE_RE.match(value)
    if not match or int(match.group(2)) > int(match.group(3)):
      self._fail(line, f"{unit.id}: design range must read `path:start-end (heading)`")
    unit.design_range = (match.group(1), int(match.group(2)), int(match.group(3)), match.group(4))
    value, line = fields["Blocked by"]
    if value != "none":
      unit.blockers = [v.strip() for v in value.split(",")]
      if not all(UNIT_ID_RE.match(b) for b in unit.blockers):
        self._fail(line, f"{unit.id}: blocked by must list unit ids or `none`")
    value, line = fields["Shared files"]
    if value != "none":
      for item in value.split("; "):
        match = SHARED_RE.match(item)
        if not match:
          self._fail(line, f"{unit.id}: shared files must read `path`: after U01, before U05")
        orders = []
        for token in match.group(2).split(", "):
          kind, _, other = token.partition(" ")
          if kind not in ("after", "before") or not UNIT_ID_RE.match(other):
            self._fail(line, f"{unit.id}: shared file order `{token}` is not `after U<nn>` or `before U<nn>`")
          orders.append((kind, other))
        unit.shared.append((match.group(1), orders))
    value, line = fields["Risk"]
    match = RISK_RE.match(value)
    if not match:
      self._fail(line, f"{unit.id}: risk must read `low|medium|high: reason`")
    unit.risk = (match.group(1), match.group(2))
    value, line = fields["Size"]
    if value not in SIZE_LIMIT:
      self._fail(line, f"{unit.id}: size must be S, M or L")
    if len(unit.scope) > SIZE_LIMIT[value]:
      self._fail(line, f"{unit.id}: size {value} allows at most {SIZE_LIMIT[value]} scope paths")
    unit.size = value

  def _check_decision_ids(self, unit):
    seen = {}
    for d in unit.decisions:
      if d["id"] in seen:
        raise HandoffError(
            f"{self.path}:{d.get('line', unit.line)}: unit {unit.id} has two "
            f"decisions with the id {d['id']} (the first is at line "
            f"{seen[d['id']]}): answering one would release the unit while the "
            f"other is still open. Give each decision its own id.")
      seen[d["id"]] = d.get("line", unit.line)

  def _check_references(self):
    for unit in self.units.values():
      for ref in unit.blockers + [u for _, o in unit.shared for _, u in o]:
        if ref not in self.units:
          raise HandoffError(f"{self.path}:{unit.line}: {unit.id} references unknown unit {ref}")
        if ref == unit.id:
          raise HandoffError(f"{self.path}:{unit.line}: {unit.id} references itself")


# ---------------------------------------------------------------- graph


class Graph:

  def __init__(self, plan: Plan):
    self.plan = plan
    units = plan.units
    self.preds = {u: set() for u in units}
    kinds = {}  # (from, to) -> [kind]
    blockers_only = {u: set() for u in units}
    for unit in units.values():
      for b in unit.blockers:
        self.preds[unit.id].add(b)
        blockers_only[unit.id].add(b)
        kinds.setdefault((b, unit.id), []).append("blocked by")
      for path, orders in unit.shared:
        for kind, other in orders:
          if kind == "after":
            self.preds[unit.id].add(other)
            kinds.setdefault((other, unit.id), []).append(f"shared file `{path}`")
          else:
            self.preds[other].add(unit.id)
            kinds.setdefault((unit.id, other), []).append(f"shared file `{path}`")
    self.edges = [(a, b, "; ".join(dict.fromkeys(k))) for (a, b), k in sorted(kinds.items())]
    cycle = find_cycle(blockers_only)
    if cycle:
      raise HandoffError("blocked-by cycle: " + " -> ".join(cycle))
    cycle = find_cycle(self.preds)
    if cycle:
      raise HandoffError("shared-file chain contradicts the blockers: "
                         + " -> ".join(cycle) + " (fix the chain or the blockers)")
    self.order = topo_order(self.preds)
    self.wave = {}
    for u in self.order:
      self.wave[u] = 1 + max((self.wave[p] for p in self.preds[u]), default=0)
    self.waves = {}
    for u in self.order:
      self.waves.setdefault(self.wave[u], []).append(u)
    end = max(self.order, key=lambda u: (self.wave[u], u))
    path = [end]
    while self.preds[path[-1]]:
      path.append(max(self.preds[path[-1]], key=lambda d: (self.wave[d], d)))
    self.critical_path = path[::-1]
    self.dependents = {u: sorted(v for v in units if u in self.preds[v]) for u in units}


def find_cycle(preds):
  try:
    list(TopologicalSorter(preds).static_order())
  except CycleError as error:
    return error.args[1]
  return None


def topo_order(preds):
  placed, order = set(), []
  remaining = dict(preds)
  while remaining:
    ready = sorted(u for u, ps in remaining.items() if ps <= placed)
    if not ready:
      raise HandoffError("cycle: " + ", ".join(sorted(remaining)))
    order.append(ready[0])
    placed.add(ready[0])
    del remaining[ready[0]]
  return order


# ---------------------------------------------------------------- rendering


class Handoff:
  """A parsed plan, its graph, config, design facts and rendered bodies."""

  def __init__(self, plan_path: Path, store: Store, state=None):
    self.plan_path = plan_path.resolve()
    self.store = store
    self.artifact_dir = store.root
    self.plan = Plan(self.plan_path)
    design = Path(self.plan.design).expanduser()
    if not design.is_absolute():
      design = (self.plan_path.parent / design).resolve()
    if not design.is_file():
      raise HandoffError(f"design file {design} does not exist")
    design = design.resolve()
    self.design_path = design
    self.design_sha = sha256_file(design)
    self.repo_root = git_toplevel(design)
    # An unrelated commit after approval must not change a single rendered
    # body: the gate hashes, a bounded resume and verify all depend on them.
    recorded = ((state if state is not None else load_state(self.artifact_dir))
                .get("approval") or {}).get("commit")
    self.design_commit = recorded or run_git(
        ["rev-parse", "--short", "HEAD"], self.repo_root).strip()
    self.design_title = next((l[2:].strip() for l in read_text(design).splitlines()
                              if l.startswith("# ")), design.stem)
    self.config = load_config(self.repo_root)
    self.graph = Graph(self.plan)
    slug = re.sub(r"[^a-z0-9]+", "-", design.stem.lower()).strip("-")[:20].rstrip("-")
    self.handoff_id = f"{slug}-{self.design_sha[:6]}"
    store.handoff_id = self.handoff_id
    require_binding(self.artifact_dir, self.handoff_id, self.config["repo"])
    self.state = state if state is not None else load_state(self.artifact_dir)
    # Repository identity folds case (GitHub does), but the canonical write
    # list carries the repo as TEXT and its hash is what the owner confirmed.
    # Once a spelling is confirmed, keep using it everywhere so a case-only
    # change in the config or remote is the same destination, not a drift.
    confirmed_repo = ((self.state.get("confirmed") or {}).get("repo")
                      or self.state.get("repo"))
    if confirmed_repo and confirmed_repo.lower() == self.config["repo"].lower():
      self.config["repo"] = confirmed_repo
    if self.state.get("approval") and self.state["approval"].get("design_sha256") != self.design_sha:
      raise HandoffError("design changed since the handoff started: re-run the gate")
    self.check_labels()

  # labels
  @property
  def labels(self):
    return self.config["labels"]

  def handoff_label(self):
    return self.labels["handoff_prefix"] + self.handoff_id

  def wave_label(self, wave):
    return f"{self.labels['wave_prefix']}{wave}"

  def unit_labels(self, uid):
    return sorted({self.labels["unit"], self.wave_label(self.graph.wave[uid]),
                   self.handoff_label(), *self.labels["extra"]})

  def tracking_labels(self):
    return sorted({self.labels["tracking"], self.handoff_label()})

  def derived_labels(self):
    names = [self.labels["unit"], self.labels["tracking"], self.handoff_label()]
    names += [self.wave_label(w) for w in sorted(self.graph.waves)]
    return names

  def check_labels(self):
    for name in self.derived_labels():
      if not LABEL_RE.match(name):
        raise HandoffError(f"derived label `{name}` is longer than 50 characters "
                           "or holds a comma or whitespace")

  # titles and bodies
  def tracking_title(self):
    return self.config["tracking_issue_title"].replace("<design title>", self.design_title)

  def unit_title(self, uid):
    return f"{uid}: {self.plan.units[uid].title}"

  def design_ref(self, unit=None):
    rel = self.design_path.relative_to(self.repo_root).as_posix()
    if unit is None:
      return f"{rel}@{self.design_commit}"
    _, start, end, heading = unit.design_range
    return f"{unit.design_range[0]}@{self.design_commit} lines {start}-{end} ({heading})"

  def branch(self, uid):
    return f"{BRANCH_PREFIX}/{self.handoff_id}/{uid}"

  def ref(self, uid):
    """A blocker or `after` reference: a placeholder until apply fills numbers."""
    return f"#<{uid}>"

  def forward_ref(self, uid):
    return f"{uid} ({self.plan.units[uid].title})"

  def decision_lines(self, unit, answers=False):
    """Render the unit's decisions.

    `answers` is False for anything that becomes a GitHub issue body: the
    posted body must stay byte-identical to what the user confirmed, or verify
    reports a mismatch and the wave cannot start. Answers reach the issue as a
    comment (`decision_comment_*.md`) and the foreman through the unit file."""
    if not unit.decisions:
      return "- none"
    lines = []
    for d in unit.decisions:
      line = (f"- {d['id']} {d['question']} Owner: {d['owner']}. Default: {d['default']}. "
              f"Blocking: {'yes' if d['blocking'] else 'no'}.")
      answer = self.state.get("decisions", {}).get(f"{unit.id}/{d['id']}")
      if answer and answer.get("fingerprint") not in (
          None, sha256_text(canonical([d["question"], d["owner"], d["default"],
                                       d["blocking"]]))[:16]):
        answer = None
      if answers and answer:
        line += f"\n  - Decision: {answer['answer']}"
      lines.append(line)
    return "\n".join(lines)

  def render_unit(self, uid):
    unit = self.plan.units[uid]
    shared = []
    for path, orders in unit.shared:
      parts = [f"after {self.ref(o)}" if k == "after" else f"before {self.forward_ref(o)}"
               for k, o in orders]
      shared.append(f"- `{path}`: " + ", ".join(parts))
    values = {
        "handoff_id": self.handoff_id, "unit_id": uid, "title": unit.title,
        "objective": unit.objective,
        "scope": "\n".join(f"- `{p}` ({a})" for p, a in unit.scope),
        "dod": "\n".join(f"- [ ] {item}" for item in unit.dod),
        "blocked_by": ", ".join(self.ref(b) for b in unit.blockers) or "none",
        "shared": "\n".join(shared) or "- none",
        "decisions": self.decision_lines(unit),
        "risk": f"{unit.risk[0]} ({unit.risk[1]})", "size": unit.size,
        "design": self.design_ref(unit), "tracking": "<tracking>",
        "wave": str(self.graph.wave[uid]), "branch": self.branch(uid),
    }
    return substitute(self.config["_template"], values)

  def render_tracking(self):
    g = self.graph
    rows = ["| Wave | Unit | Title | Blocked by |", "| --- | --- | --- | --- |"]
    for wave in sorted(g.waves):
      for uid in g.waves[wave]:
        blockers = ", ".join(self.plan.units[uid].blockers) or "none"
        rows.append(f"| {wave} | {uid} | {self.plan.units[uid].title} | {blockers} |")
    shared = {}
    for unit in self.plan.units.values():
      for path, _ in unit.shared:
        shared.setdefault(path, []).append(unit.id)
    shared_lines = [f"- `{p}`: " + ", ".join(sorted(set(us))) for p, us in sorted(shared.items())]
    values = {"handoff_id": self.handoff_id, "design": self.design_ref(),
              "branch_prefix": f"{BRANCH_PREFIX}/{self.handoff_id}",
              "waves": "\n".join(rows),
              "critical_path": " -> ".join(g.critical_path),
              "shared_files": "\n".join(shared_lines) or "- none"}
    return substitute(TRACKING_TEMPLATE, values)

  def writes(self):
    """The canonical write list: destination, gate hashes, then every write."""
    items = [["repo", self.config["repo"]],
             ["gate", self.state.get("gate_plan_sha256"), self.state.get("gate_bodies_sha256")]]
    items += [["label", name] for name in self.derived_labels()]
    items.append(["issue", "tracking", self.tracking_title(), self.tracking_labels(),
                  self.render_tracking()])
    for uid in self.graph.order:
      items.append(["issue", uid, self.unit_title(uid), self.unit_labels(uid),
                    self.render_unit(uid)])
    for uid in self.graph.order:
      items.append(["sub_issue", uid])
    for uid in self.graph.order:
      for b in sorted(self.plan.units[uid].blockers):
        items.append(["blocked_by", uid, b])
    return items

  def bodies_text(self):
    parts = []
    for item in self.writes():
      if item[0] == "issue":
        parts.append(f"## {item[1]}\n\nTitle: {item[2]}\nLabels: {', '.join(item[3])}\n\n"
                     f"```markdown\n{item[4]}```\n")
    return "# Rendered issue bodies (creation order)\n\n" + "\n".join(parts)

  def unit_file(self, uid):
    return self.store.path("unit", uid)

  def unit_file_text(self, uid):
    unit = self.plan.units[uid]
    section = unit_section_text(self.plan, uid)
    text = (f"{section}\n\n## Issue body as posted\n\n"
            f"```markdown\n{self.render_unit(uid)}```\n")
    answered = [d for d in unit.decisions
                if self.state.get("decisions", {}).get(f"{uid}/{d['id']}")]
    if answered:
      # Kept out of the issue body on purpose (the posted body must stay
      # byte-identical for verify); the answer reaches the issue as a comment.
      text += "\n## Decisions answered since the issue was posted\n\n"
      text += self.decision_lines(unit, answers=True) + "\n"
    return text

  def generated_section(self):
    g = self.graph
    lines = [GEN_START, "## Generated by `egm_handoff.py graph` (do not edit)", "",
             f"Handoff id: `{self.handoff_id}`. Units: {len(self.plan.units)}. "
             f"Waves: {len(g.waves)}. Design: `{self.design_ref()}`.", "",
             "### Edges", "", "| From | To | Kind |", "| --- | --- | --- |"]
    lines += [f"| {a} | {b} | {k} |" for a, b, k in g.edges] or ["| - | - | no edges |"]
    lines += ["", "### Waves", "", "| Wave | Units |", "| --- | --- |"]
    lines += [f"| {w} | " + ", ".join(f"{u} ({self.plan.units[u].title})" for u in g.waves[w]) + " |"
              for w in sorted(g.waves)]
    lines += ["", "### Critical path", "", " -> ".join(g.critical_path), "",
              "### Blocking decisions", ""]
    blocking = [f"- {u.id}/{d['id']} {d['question']} (owner: {d['owner']}; default: {d['default']})"
                for u in self.plan.units.values() for d in u.decisions if d["blocking"]]
    lines += blocking or ["- none"]
    lines += [GEN_END]
    return "\n".join(lines) + "\n"

  def write_graph_files(self):
    text = self.plan.text
    section = self.generated_section()
    if GEN_START in text and GEN_END in text:
      start, end = text.index(GEN_START), text.index(GEN_END) + len(GEN_END)
      new_text = text[:start] + section.rstrip("\n") + text[end:]
    else:
      new_text = text.rstrip("\n") + "\n\n" + section
    if new_text != text:
      atomic_write(self.plan_path, new_text)
      self.plan = Plan(self.plan_path)
    units = {u: self.plan.units[u].to_json(self.graph.wave[u], self.graph.preds[u])
             for u in self.graph.order}
    data = {"handoff_id": self.handoff_id, "repo": self.config["repo"],
            "design": {"path": str(self.design_path), "sha256": self.design_sha,
                       "commit": self.design_commit, "title": self.design_title},
            "order": self.graph.order, "waves": {str(w): us for w, us in sorted(self.graph.waves.items())},
            "critical_path": self.graph.critical_path,
            "edges": [{"from": a, "to": b, "kind": k} for a, b, k in self.graph.edges],
            "units": units}
    atomic_write(self.store.path("units"), data)
    for uid in self.graph.order:
      atomic_write(self.unit_file(uid), self.unit_file_text(uid))
    atomic_write(self.store.path("bodies"), self.bodies_text())
    previous = self.state.get("handoff_id")
    if previous and previous != self.handoff_id:
      # Nothing was created (require_binding would have refused otherwise), so
      # the records of the superseded handoff are stale, not valuable.
      for key in ("confirmed", "confirmed_sha256", "confirmed_at", "labels",
                  "dry_run", "verify", "gate", "readiness", "units", "tracking",
                  "decisions"):
        self.state.pop(key, None)
    self.state.update({"handoff_id": self.handoff_id, "repo": self.config["repo"],
                       "remote": self.config["remote"], "repo_root": str(self.repo_root),
                       "plan": str(self.plan_path),
                       "design": {"path": str(self.design_path), "sha256": self.design_sha,
                                  "commit": self.design_commit}})
    save_state(self.artifact_dir, self.state)


def unit_section_text(plan: Plan, uid: str) -> str:
  lines = plan.text.splitlines()
  start = plan.units[uid].line - 1
  end = start + 1
  while end < len(lines) and not UNIT_RE.match(lines[end]) and lines[end].strip() != GEN_START \
      and not lines[end].startswith("## "):
    end += 1
  return "\n".join(lines[start:end]).rstrip()


def substitute(template: str, values: dict) -> str:
  def replace(match):
    key = match.group(1)
    if key not in values:
      raise HandoffError(f"issue template uses unknown placeholder {{{{{key}}}}}")
    return values[key]
  return re.sub(r"\{\{(\w+)\}\}", replace, template)


def fill_numbers(body: str, numbers: dict, tracking=None) -> str:
  def replace(match):
    key = match.group(1)
    if key == "tracking":
      return f"#{tracking}" if tracking else match.group(0)
    return f"#{numbers[key]}" if key in numbers else match.group(0)
  return re.sub(r"#<([A-Za-z0-9]+)>", replace, body)


# ---------------------------------------------------------------- state


def state_path(artifact_dir: Path) -> Path:
  return Path(artifact_dir) / "state.json"


def load_state(artifact_dir: Path) -> dict:
  path = state_path(artifact_dir)
  return json.loads(read_text(path)) if path.is_file() else {}


def save_state(artifact_dir: Path, state: dict) -> None:
  """Replace the state file atomically: a truncating write interrupted here
  leaves invalid JSON and no handoff can be resumed from it."""
  atomic_write(state_path(artifact_dir), state)


def normalise(body: str) -> str:
  return "\n".join(line.rstrip() for line in body.replace("\r\n", "\n").split("\n")).strip("\n")


# ---------------------------------------------------------------- scan


def scan_text(text: str, config: dict, kind: str, dod=None, label="body"):
  """Refuse text that must not reach GitHub.

  Deliberately NOT code-aware. Seven adversarial rounds each found a defect in
  a Markdown-aware version (R12, R2-10, R3-08, R4-07, R5-02, R6-01, R7-01/02):
  it could both hide a bare mention behind a fence shape it misread and refuse
  an ordinary comment. GitHub does not notify for a mention inside code, so
  code-awareness bought only false-positive avoidance - at the price of a
  parser that was never right. Raw scan instead: every line, as written. A
  legitimate `@scope/pkg` or `@decorator` goes in the repository's
  `allowed_mentions`, which is explicit and reviewable; a refusal names the
  line and the author rewords. That is the only safe direction to fail.
  """
  problems = []
  size = len(text.encode("utf-8"))
  if size > BODY_LIMIT:
    problems.append(f"{label}: {size} bytes exceeds {BODY_LIMIT}: shorten or split the unit")
  terms = [re.compile(t) for t in config["banned_terms"]]
  mention = config.get("fix_request_mention")
  allowed = set(config.get("allowed_mentions") or [])
  for number, line in enumerate(text.splitlines(), start=1):
    for term in terms:
      if term.search(line):
        problems.append(f"{label}:{number}: banned term /{term.pattern}/")
    for found in MENTION_RE.findall(line):
      # Exact literal only: `@types` in the allowlist does not cover
      # `@types/node`, and `@acme` never covers the team `@acme/release`.
      if found in allowed:
        continue
      if kind == "comment" and number == 1 and mention and found == mention:
        continue
      problems.append(f"{label}:{number}: bare mention {found} (it would notify that user; "
                      f"reword it, or list it in `allowed_mentions` in .superegm/config.json)")
    if re.match(r"^(<<<<<<<|=======|>>>>>>>)( |$)", line):
      problems.append(f"{label}:{number}: merge marker")
  for item in dod or []:
    if item not in text:
      problems.append(f"{label}: definition-of-done item missing from the body: {item}")
  return problems


def scan_handoff(handoff: Handoff):
  problems = []
  for item in handoff.writes():
    if item[0] == "issue":
      dod = handoff.plan.units[item[1]].dod if item[1] != "tracking" else []
      problems += scan_text(item[4], handoff.config, "body", dod, label=item[1])
      problems += scan_text(item[2], handoff.config, "body", label=f"{item[1]} title")
  return problems


# ---------------------------------------------------------------- commands


# ---------------------------------------------------------------- commands


CURRENT_WRITES = None
CURRENT_SUBCOMMAND = None


def locate(args):
  """The store of the repository the working directory is in, and the plan."""
  st = store(git_toplevel(Path.cwd()))
  if not getattr(args, "plan", None):
    raise HandoffError("state holds no plan path: run `graph --plan <file>` first")
  plan = Path(args.plan).expanduser().resolve()
  if not plan.is_file():
    raise HandoffError(f"plan {plan} does not exist")
  return plan, st


def gate_hashes(handoff: Handoff):
  return sha256_file(handoff.plan_path), sha256_text(handoff.bodies_text())


def preflight(handoff: Handoff):
  repo = handoff.config["repo"]
  results = {}
  try:
    gh(["auth", "status", "--hostname", "github.com"])
    results["auth"] = "ok"
  except GhError as error:
    raise HandoffError(f"gh is not logged in to github.com: {error}") from error
  permissions = gh_json(["api", f"repos/{repo}", "-q", ".permissions"]) or {}
  results["push"] = bool(permissions.get("push"))
  if not results["push"]:
    raise HandoffError(f"no push access to {repo}: labels would be dropped silently")
  results["labels"] = {label["name"] for label in gh_pages(f"repos/{repo}/labels")}
  return results


# ---------------------------------------------------------------- status


def require_repo(handoff) -> str:
  """Refuse any operation that uses a stored issue or PR number when the
  configured repository is no longer the one those numbers were created on."""
  repo = handoff.config["repo"]
  frozen = (handoff.state.get("confirmed") or {}).get("repo") or handoff.state.get("repo")
  if frozen and frozen.lower() != repo.lower():
    raise HandoffError(
        f"this handoff was created on {frozen} but the configuration now names "
        f"{repo}: issue and PR numbers are not portable between repositories. "
        f"Restore `repo` in .superegm/config.json or start a handoff in a new "
        f"artifact directory.")
  host = (handoff.state.get("confirmed") or {}).get("host")
  if host and host != GH_HOSTNAME:
    raise HandoffError(f"this handoff was created on {host}, not {GH_HOSTNAME}")
  return repo


def created_anything(state) -> bool:
  """Any successful write to GitHub binds the destination, labels included:
  their `done` flags are destination-scoped bookkeeping."""
  if (state.get("tracking") or {}).get("number"):
    return True
  if any(d.get("number") for d in (state.get("units") or {}).values()):
    return True
  return any(v == "done" for v in (state.get("labels") or {}).values())


def require_binding(artifact_dir: Path, handoff_id=None, repo=None) -> None:
  """Once this artifact directory has created anything on GitHub, its handoff
  id, repository and host are frozen.

  Issue numbers, database ids and `done` flags belong to one repository and one
  design. Re-pointing `repo` (or approving a different design) while those
  records are present would let a later apply skip the first repository's
  issues and attach new ones to an unrelated issue of the same number."""
  state = load_state(artifact_dir)
  if not created_anything(state):
    return
  bound_id = state.get("handoff_id")
  bound_repo = (state.get("confirmed") or {}).get("repo") or state.get("repo")
  if handoff_id and bound_id and handoff_id != bound_id:
    raise HandoffError(
        f"{artifact_dir} already holds handoff {bound_id} with issues on "
        f"{bound_repo}; this design is handoff {handoff_id}. Creation, decision "
        f"and verification records are not transferable: use a new artifact "
        f"directory for the new design. Nothing was changed.")
  if repo and bound_repo and repo.lower() != bound_repo.lower():
    raise HandoffError(
        f"{artifact_dir} already created issues on {bound_repo}; the "
        f"configuration now names {repo}. The creation destination is frozen "
        f"once anything exists: restore `repo` in .superegm/config.json, or use a "
        f"new artifact directory. Nothing was changed.")


def require_reviewed_pair(handoff) -> None:
  """The canonical write list carries the gate hashes as values, so an edit the
  renderer ignores (prose after a unit's decision list, say) leaves the list
  unchanged while still reaching the foreman through `unit_<id>.md`. Hash the
  plan and the bodies as they are now and compare with what was reviewed."""
  state = handoff.state
  reviewed_plan = state.get("gate_plan_sha256")
  reviewed_bodies = state.get("gate_bodies_sha256")
  if not reviewed_plan:
    return
  plan_now, bodies_now = gate_hashes(handoff)
  if plan_now != reviewed_plan or bodies_now != reviewed_bodies:
    raise HandoffError(
        f"{handoff.plan_path.name} or the rendered bodies differ from the pair "
        f"the gate reviewed (plan {plan_now[:12]} vs {reviewed_plan[:12]}, "
        f"bodies {bodies_now[:12]} vs {str(reviewed_bodies)[:12]}). "
        f"Even an edit the issue bodies do not show reaches the builder through "
        f"unit_<id>.md: run the gate again and re-confirm.")


def require_confirmed_plan(handoff) -> None:
  """Refuse to read readiness off a plan edited since the confirmation.

  `status` derives landed and ready from the graph it parses now, but the
  receipt describes the issues on GitHub. Deleting a blocker locally would
  otherwise make a unit ready while its issue is still blocked by it."""
  confirmed = handoff.state.get("confirmed") or {}
  if not confirmed.get("sha256"):
    return
  current = sha256_text(canonical(handoff.writes()))
  if current != confirmed["sha256"]:
    raise HandoffError(
        f"{handoff.plan_path.name} no longer matches the confirmed snapshot "
        f"({current[:12]} vs {confirmed['sha256'][:12]}): the issues on "
        f"{confirmed.get('repo')} were created from the confirmed plan. Restore "
        f"it, or run the gate and dry-run again and re-confirm.")


def receipt_ok(state) -> bool:
  receipt = state.get("verify") or {}
  return bool(receipt.get("complete")) and receipt.get("sha256") == state.get("confirmed_sha256") \
      and not receipt.get("problems")


def require_receipt(state):
  if not receipt_ok(state):
    raise HandoffError("the handoff is not fully created and verified: run `apply --yes`, then `verify`")


def read_pr(repo, number):
  data = gh_json(["pr", "view", str(number), "-R", repo, "--json",
                  "number,state,headRefName,headRefOid,baseRefName,baseRefOid,mergedAt,isDraft"])
  return pr_record(data)


def pr_record(data):
  return {"number": data["number"], "state": data.get("state"), "head_ref": data.get("headRefName"),
          "head": data.get("headRefOid"), "base_ref": data.get("baseRefName"),
          "base_sha": data.get("baseRefOid"), "merged_at": data.get("mergedAt"),
          "draft": bool(data.get("isDraft"))}


GRAPHQL_QUERY = (
    "query($owner: String!, $name: String!, $number: Int!, $endCursor: String) { "
    "repository(owner: $owner, name: $name) { issue(number: $number) { "
    "closedByPullRequestsReferences(first: 100, includeClosedPrs: true, after: $endCursor) { "
    "nodes { number state headRefName headRefOid baseRefName baseRefOid mergedAt isDraft "
    "repository { nameWithOwner } } pageInfo { hasNextPage endCursor } } } } }")


def discover_pr(handoff: Handoff, uid, number):
  repo = handoff.config["repo"]
  owner, name = repo.split("/")
  # `-f` keeps owner and name as strings: with `-F`, gh would turn a repository
  # named `2048`, `true` or `null` into a number/boolean and GraphQL rejects
  # the String! variable. Only the issue number is an Int.
  pages = gh_json(["api", "graphql", "--paginate", "--slurp", "-f", f"owner={owner}",
                   "-f", f"name={name}", "-F", f"number={number}", "-f", f"query={GRAPHQL_QUERY}"]) or []
  nodes = []
  for page in pages:
    issue = ((page.get("data") or {}).get("repository") or {}).get("issue") or {}
    nodes += (issue.get("closedByPullRequestsReferences") or {}).get("nodes") or []
  # GitHub treats owner and name case-insensitively and may echo `Acme/WebHooks`
  # for a config that says `acme/webhooks`; the confirmed destination text is
  # kept as written, only the comparison folds case.
  matches = [pr_record(n) for n in nodes
             if ((n.get("repository") or {}).get("nameWithOwner") or "").lower() == repo.lower()]
  if matches:
    return matches, []
  prs = gh_json(["pr", "list", "-R", repo, "--state", "all", "--limit", "1000", "--json",
                 "number,state,headRefName,headRefOid,baseRefName,baseRefOid,closingIssuesReferences,isDraft,mergedAt"]) or []
  branch = handoff.branch(uid)
  candidates = []
  for pr in prs:
    refs = pr.get("closingIssuesReferences") or []
    for ref in refs:
      repository = ref.get("repository") or {}
      full = f"{(repository.get('owner') or {}).get('login')}/{repository.get('name')}"
      if full.lower() == repo.lower() and ref.get("number") == number:
        matches.append(pr_record(pr))
        break
    else:
      head = pr.get("headRefName") or ""
      if not refs and (head == branch or head.startswith(branch + "/")):
        candidates.append(pr_record(pr))
  return matches, candidates


def read_ci(repo, sha):
  pages = gh_json(["api", f"repos/{repo}/commits/{sha}/check-runs?per_page=100", "--paginate", "--slurp"]) or []
  runs = []
  for page in pages:
    runs += page.get("check_runs") or [] if isinstance(page, dict) else []
  combined = gh_json(["api", f"repos/{repo}/commits/{sha}/status"]) or {}
  # That endpoint returns only the first 30 contexts. Page it, or a failing
  # context beyond the first page is invisible while the aggregate says failure.
  pages = gh_json(["api", f"repos/{repo}/commits/{sha}/status?per_page=100",
                   "--paginate", "--slurp"]) or []
  statuses = []
  for page in pages:
    statuses += (page.get("statuses") or []) if isinstance(page, dict) else []
  if not statuses:
    statuses = combined.get("statuses") or []
  return {"check_runs": [{"name": r.get("name"), "status": r.get("status"), "conclusion": r.get("conclusion")}
                         for r in runs],
          "combined_state": combined.get("state"),
          # Keep each context, not just how many: GitHub's combined state is
          # `failure` as soon as one context fails, even while another is still
          # pending, and a review must not start on a CI run still in flight.
          "contexts": [{"context": s.get("context"), "state": s.get("state")} for s in statuses],
          "statuses": len(statuses)}


def ci_verdict(ci):
  runs = ci["check_runs"]
  if not runs and not ci["statuses"]:
    return "waiting-for-ci"
  contexts = ci.get("contexts") or []
  pending = [c["context"] for c in contexts if c.get("state") == "pending"]
  if any(r["status"] != "completed" for r in runs) or pending \
      or (ci["statuses"] and ci["combined_state"] == "pending"):
    # Any context still pending means CI has not concluded, whatever the
    # combined state says.
    return "waiting-for-ci"
  red = [r["name"] for r in runs if r["conclusion"] not in GREEN_CONCLUSIONS]
  red += [c["context"] for c in contexts
          if c.get("state") not in ("success",) and c.get("state") != "pending"]
  if ci["statuses"] and ci["combined_state"] not in ("success", None) \
      and not any(c["context"] in red for c in contexts):
    # Conservative: an aggregate failure we cannot attribute to a context we
    # read is still a failure.
    red.append(f"status:{ci['combined_state']}")
  return "ci green" if not red else "ci red (" + ", ".join(str(n) for n in red) + ")"


def unit_view(handoff: Handoff, uid):
  repo, state = handoff.config["repo"], handoff.state
  record = state["units"].get(uid, {})
  number = record.get("number")
  issue = gh_json(["api", f"repos/{repo}/issues/{number}"]) or {}
  view = {"unit": uid, "number": number, "issue_state": issue.get("state"),
          "state_reason": issue.get("state_reason"), "launched": record.get("launched"),
          "pr": None, "head": None, "ci": None, "status": "waiting-for-pr", "landed": False,
          "candidates": []}
  chosen = (record.get("watch") or {}).get("number") or (record.get("pr") or {}).get("number")
  if chosen:
    pr = read_pr(repo, chosen)
  else:
    matches, candidates = discover_pr(handoff, uid, number)
    pr = None
    if len(matches) == 1:
      pr = matches[0]
    elif len(matches) > 1:
      view["status"] = "ambiguous: PRs " + ", ".join(f"#{m['number']}" for m in matches) + " (choose with --watch)"
    view["candidates"] = [c["number"] for c in candidates]
  if pr:
    if record.get("pr", {}).get("head") != pr["head"]:
      pr["head_seen_at"] = NOW()
    else:
      pr["head_seen_at"] = record["pr"].get("head_seen_at", NOW())
    record["pr"] = pr
    view["pr"], view["head"] = pr["number"], pr["head"]
    view["pr_state"] = "MERGED" if pr.get("merged_at") else (pr.get("state") or "OPEN").upper()
    # A retarget (main -> an older release branch) changes the merge base and
    # the diff while head and CI stay the same: it is a new review target.
    view["base_ref"], view["base_sha"] = pr.get("base_ref"), pr.get("base_sha")
    if pr["merged_at"]:
      view["status"] = "merged"
    else:
      ci = read_ci(repo, pr["head"])
      view["ci"] = ci
      verdict = ci_verdict(ci)
      if verdict == "waiting-for-ci" and not ci["check_runs"] and not ci["statuses"] \
          and NOW() - pr["head_seen_at"] >= NO_CI_SECONDS:
        verdict = "no-ci"
      view["status"] = verdict
  closed_done = issue.get("state") == "closed" and issue.get("state_reason") == "completed"
  if pr and not pr.get("merged_at") and (pr.get("state") or "").upper() == "CLOSED":
    # Terminal: the builder abandoned this PR. Never rediscover silently; the
    # user picks the replacement with --watch.
    view["status"] = f"pr #{pr['number']} closed unmerged (choose a replacement with --watch)"
  override = record.get("landed_confirmed")
  if override and record.get("landed_confirmation_void"):
    override = None
  if override and not closed_done:
    # The exception is for an issue closed as completed with no watched PR; it
    # lapses the moment either of those stops being true.
    view["status"] = (f"landed confirmation no longer applies (issue is "
                      f"{issue.get('state')}/{issue.get('state_reason')}): "
                      f"re-confirm or watch a PR")
    # Persist it: closing the issue as completed again must not silently
    # revive a confirmation the user gave for an earlier state.
    record["landed_confirmation_void"] = now_iso()
    override = None
  if override and pr:
    view["status"] = (f"landed confirmation no longer applies (pr #{pr['number']} "
                      f"is now visible): re-confirm or let it merge")
    record["landed_confirmation_void"] = now_iso()
    override = None
  if override or (closed_done and pr and pr.get("merged_at")):
    view["landed"], view["status"] = True, "landed"
  elif closed_done and not pr:
    view["status"] = "closed (no watched PR)"
  elif view["candidates"] and view["status"] == "waiting-for-pr":
    view["status"] = "candidate: PRs " + ", ".join(f"#{c}" for c in view["candidates"]) + " (confirm with --watch)"
  record["status"] = view["status"]
  state["units"][uid] = record
  return view


def issue_closed_completed(handoff: Handoff, uid) -> bool:
  record = handoff.state.get("units", {}).get(uid, {})
  issue = gh_json(["api", f"repos/{handoff.config['repo']}/issues/{record.get('number')}"]) or {}
  return issue.get("state") == "closed" and issue.get("state_reason") == "completed"


def status_pass(handoff: Handoff, save=True):
  state = handoff.state
  state.setdefault("units", {})
  views = {uid: unit_view(handoff, uid) for uid in handoff.graph.order}
  landed = {u for u, v in views.items() if v["landed"]}
  decisions = state.get("decisions", {})
  open_blocking = {}
  for unit in handoff.plan.units.values():
    for d in unit.decisions:
      answer = decisions.get(f"{unit.id}/{d['id']}")
      if answer and answer.get("fingerprint") not in (
          None, sha256_text(canonical([d["question"], d["owner"], d["default"],
                                       d["blocking"]]))[:16]):
        # The question changed under the answer: ids are reused, answers are not.
        answer = None
      # An answer the builder cannot see is not an answer: the comment may have
      # failed the scan, failed to post, or the session may have ended first.
      if d["blocking"] and not (answer and answer.get("published")):
        open_blocking.setdefault(unit.id, []).append(d)
  ready = [u for u in handoff.graph.order if u not in landed and not views[u]["launched"]
           and handoff.graph.preds[u] <= landed and u not in open_blocking]
  in_flight = [u for u in handoff.graph.order if views[u]["launched"] and u not in landed]
  unlaunched_prs = [u for u in handoff.graph.order if not views[u]["launched"] and views[u]["pr"]
                    and u not in landed]
  summary = {"landed": sorted(landed), "ready": ready, "in_flight": in_flight,
             "unlaunched_with_pr": unlaunched_prs, "open_blocking": {u: [d["id"] for d in ds] for u, ds in open_blocking.items()},
             "units": {u: {"pr": v["pr"], "head": v["head"], "status": v["status"],
                           "landed": v["landed"], "issue_state": v.get("issue_state"),
                           "pr_state": v.get("pr_state"), "base_ref": v.get("base_ref"),
                           "base_sha": v.get("base_sha"),
                           "candidates": v["candidates"]} for u, v in views.items()},
             "at": now_iso()}
  state["status"] = summary
  if save:
    save_state(handoff.artifact_dir, state)
  return summary, open_blocking


def print_status(handoff: Handoff, summary, open_blocking):
  state = handoff.state
  print(f"handoff {handoff.handoff_id} on {handoff.config['repo']}: tracking #{state.get('tracking', {}).get('number')}; "
        f"receipt {'complete' if receipt_ok(state) else 'INCOMPLETE'}")
  print("landed: " + (", ".join(summary["landed"]) or "none"))
  print("ready: " + (", ".join(summary["ready"]) or "none"))
  for uid in handoff.graph.order:
    v = summary["units"][uid]
    record = state["units"].get(uid, {})
    launched = f" launched wave {record['launched']['wave']}" if record.get("launched") else ""
    pr = f"pr #{v['pr']} head {v['head'][:7]}" if v["pr"] else "no pr"
    print(f"{uid} #{record.get('number')}{launched}: {pr}; {v['status']}")
  for uid, ds in open_blocking.items():
    for d in ds:
      answered = (handoff.state.get("decisions") or {}).get(f"{uid}/{d['id']}")
      note = " [answered, NOT PUBLISHED]" if answered else ""
      print(f"open blocking decision {uid}/{d['id']}{note}: {d['question']} "
            f"(owner: {d['owner']}; default: {d['default']})")
  if summary["unlaunched_with_pr"]:
    print("open PRs for units not launched: " + ", ".join(f"{u} #{summary['units'][u]['pr']}" for u in summary["unlaunched_with_pr"]))


# ---------------------------------------------------------------- prepare


def load_foreman(store: Store, uid):
  path = store.path("foreman", uid)
  return json.loads(read_text(path)) if path.is_file() else {"unit": uid, "rounds": {}}


def save_foreman(store: Store, uid, data):
  """Atomic, like the handoff state: a partial write here loses the run folder
  that the next session needs to resume collection."""
  atomic_write(store.path("foreman", uid), data)


def worktree_path(handoff_id, uid, pr):
  base = Path(os.environ.get("TMPDIR") or "/tmp").expanduser()
  return base / "egm-wave" / handoff_id / uid / f"pr{pr}"


def registered_worktrees(root: Path):
  paths = []
  for line in run_git(["worktree", "list", "--porcelain"], root).splitlines():
    if line.startswith("worktree "):
      paths.append(Path(line[len("worktree "):]).resolve())
  return paths


def remove_worktree(root: Path, tree: Path) -> None:
  """Remove a review worktree only when it is clean.

  `--force` deletes tracked modifications and untracked files. The foreman
  removes a worktree after every round, so a person editing it during a review
  would lose that work without being asked."""
  if not tree.exists():
    run_git(["worktree", "prune"], root, check=False)
    return
  dirty = run_git(["status", "--porcelain"], tree, check=False).strip()
  if dirty:
    raise HandoffError(
        f"the review worktree {tree} has uncommitted changes:\n  "
        + "\n  ".join(dirty.splitlines()[:10])
        + f"\nNothing was removed. Save or discard them, then remove it with "
          f"`git -C {root} worktree remove {tree}`.")
  run_git(["worktree", "remove", str(tree)], root)
  run_git(["worktree", "prune"], root, check=False)


def run_terminated(folder) -> bool:
  """True only when the run folder holds a result with a terminal status.

  This is the only evidence of termination the helper accepts. File
  inactivity proves nothing (a runner can wait on a live child without
  writing), so nothing is inferred: a launch without a terminal result keeps
  its worktree until a human removes it by hand."""
  result = Path(folder) / "result.json"
  if not result.is_file():
    return False
  try:
    return (json.loads(read_text(result)) or {}).get("status") in ("completed", "failed")
  except (ValueError, OSError):
    return False


# ---------------------------------------------------------------- main


SUBCOMMANDS = ("init", "runcard", "approve_spec", "graph", "scan", "review", "gate", "dry_run", "apply",
               "verify", "status", "launch", "launch_builder", "record_launch", "foreman", "prepare",
               "collect", "tdd_order", "decide", "decision", "interrupt", "clean", "report", "close", "judges")


def add_parser(subparsers, name, help_text, *, runcard=True):
  p = subparsers.add_parser(name, help=help_text)
  p.add_argument("--plan", help="the plan file (default: the one the state names)")
  return p


def build_parser():
  parser = argparse.ArgumentParser(prog="superegm.py", description=__doc__.splitlines()[0])
  sub = parser.add_subparsers(dest="command", required=True)
  for name in SUBCOMMANDS:
    importlib.import_module(f"superegm.{name}").register(sub)
  return parser
