# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's helper split into this package; the shared names live here, one module per subcommand; the orient and orient_unit store kinds (spec section 9.3); builder.app and the launches `_bin` form (U15); astra.heads and the head panel's informational `astra` entry (U17); the ingest key and the comment scan's size limit (U21); the notify_timeout_seconds key and the inbox module (U23); the foreman key, kill_group, hook-free git calls and the forced worktree removal (U25); the registry, the boot id, the driver store kind and runcard open's refusal while a tick's launch may be live (U24); builder.plugins, builder.mcp and builder.max_subagent_calls (U27); the default models and efforts per role and the builder and reviewers merge (U28); builder.stall_minutes and the one stamp formatter and parser (U31); `discover()`, CORE_CONFIG and SUBCOMMANDS and DEFAULT_CONFIG derived from the modules (U32).

"""SuperEGM helper: the store, run cards, units -> graph, waves, issue bodies, dry run, GitHub.

Standard library only. Run as `python3 '<absolute path>' <subcommand> ...` from
the `plan`, `file`, `wave`, `integrate` and `judges` skills; this package holds
the shared names and one module per subcommand (found by `discover()`; `SUBCOMMANDS`
is its import-time snapshot). Store writes go under the config's `artifacts_dir`,
through `atomic_write` and under an open run card; what a subcommand writes beyond
the store (GitHub, git refs, worktrees, files outside the store) its own module
docstring and `--help` name, `apply --yes`, `close`, `decision`, `status` under a
wave card, `init` and `prepare` among them.
Every `gh` call goes through `gh()`; tests inject `GH`, `SLEEP` and `NOW` here.
"""
import argparse
import importlib
import calendar
import contextlib
import difflib
import hashlib
import json
import os
import pkgutil
import re
import shutil
import signal
import subprocess
import urllib.parse
import sys
import tempfile
import time
from graphlib import CycleError, TopologicalSorter
from pathlib import Path

from . import body
LABEL_RE = re.compile(r"^[^,\s]{1,50}$")
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
MENTION_CONFIG_RE = re.compile(r"^@[A-Za-z0-9][A-Za-z0-9-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?(?:\[bot\])?$")
# The whole token GitHub would resolve: `@user`, `@user[bot]`, or `@org/team` -
# a team mention subscribes every member, so the slash segment is part of the
# mention and must be matched and allow-listed as one literal (R8-01).
MENTION_RE = re.compile(r"(?<![\w./-])@[A-Za-z0-9][A-Za-z0-9-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?(?:\[bot\])?")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")  # a fence line: the run, then the info string
SPAN_RE = re.compile(r"(?<!`)(`+)(?!`)(.+?)(?<!`)\1(?!`)")  # an inline code span: equal backtick runs
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
GEN_START, GEN_END = "<!-- egm:generated start -->", "<!-- egm:generated end -->"
FIELDS = ("Objective", "Scope paths", "Design range", "Blocked by",
          "Shared files", "Risk", "Size")
OPTIONAL_FIELDS = ("Issue",)  # `#<n>`: an open issue `file` adopts instead of creating one (spec section 10)
SIZE_LIMIT = {"S": 3, "M": 8, "L": 10**6}
BODY_LIMIT = 49_152
MAX_UNITS = 100
WRITE_WARN = 450
LABEL_COLOR = "1b6ef3"
BRANCH_PREFIX = "superegm"
WAITING_STATES = {"queued", "in_progress", "waiting", "requested", "pending"}
GREEN_CONCLUSIONS = {"success", "neutral", "skipped"}
WAIT_INTERVAL = 90
EFFORTS = ("low", "medium", "high", "xhigh")
MODEL_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{1,63}$")

CORE_CONFIG = {  # the keys no subcommand owns; each module's CONFIG_DEFAULTS follow, in discovery order (U32)
    "repo": None,
    "base": "main",
    "artifacts_dir": None,
    "mode": "normal",
    "max_in_flight": 5,
    "labels": {"unit": "superegm:unit", "wave_prefix": "superegm:wave-",
               "handoff_prefix": "superegm:handoff-", "tracking": "superegm:tracking",
               "stopped": "superegm:stopped", "extra": []},
    "issue_template": None,
    "tracking_issue_title": "Build: <design title>",
    "banned_terms": [],
    "fix_request_mention": None,
    "allowed_mentions": [],
    "reviewers": None,  # the spec's panels, from review.PANEL_OF at the end of this module
    "commit_trailer": "",  # appended, after a blank line, to every commit the helper makes
    "owners": [],  # the GitHub logins that may update <base> (spec section 11); init writes `gh api user`'s
    "owner_team": None,  # `<org>/<slug>`: the one team a ruleset's bypass actors may name
    "pr_block_file": None,  # a path relative to the repository root whose text every builder PR body carries
}

DEFAULT_TEMPLATE = """<!-- superegm:handoff={{handoff_id}} unit={{unit_id}} spec={{spec_sha256}} -->
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

TRACKING_TEMPLATE = """<!-- superegm:handoff={{handoff_id}} unit=tracking spec={{spec_sha256}} -->
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
    if kind not in {Store.ALIASES.get(k, k) for k in CURRENT_WRITES}:
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
  """The files under `artifacts_dir` (spec section 7): the store level holds `handoffs/`,
  `approvals/`, the spec reviews, their cards and judges and its own `journal.md`; everything
  of a handoff lives under `<handoff id>/`. A flat 1.0/1.1 store (`legacy`) is read in place:
  its files at the root, every unit-keyed kind under the handoff's 6-hex prefix."""

  FILES = {"state": "state.json", "journal": "journal.md", "plan": "handoff_plan.md",
           "units": "handoff_units.json", "bodies": "handoff_bodies.md"}
  # The Interfaces block's longer names for the same kinds.
  ALIASES = {"handoff_plan": "plan", "handoff_units": "units", "handoff_bodies": "bodies", "wave_report": "report"}
  KEYED = ("unit", "foreman", "launches", "worktrees", "review", "orient_unit", "driver")
  LEVEL = ("approvals", "handoffs")  # always at the store level
  SHARED = ("reviews", "judges", "questions")  # at the store level for a spec review's id, else the handoff's

  def __init__(self, root: Path, handoff_id: str | None = None, config: dict | None = None, legacy: bool = False):
    self.root = Path(root)
    self.handoff_id = handoff_id
    self.config = config
    self.legacy = legacy

  @staticmethod
  def card_segment(card_id: str):
    """The hex segment of a `<skill>-<6 hex>-<n>` card id, or None for a `<skill>-<n>` one (a legacy
    `review-spec-0001` included: its `spec` is the skill's second word, not a segment)."""
    parts = str(card_id).removesuffix(".json").rsplit("-", 2)
    if len(parts) != 3 or not parts[2].isdigit() or f"{parts[0].rsplit('-', 1)[-1]}-{parts[1]}" in ("review-spec", "review-plan"):
      return None
    return parts[1]

  def card_dir(self, card_id: str) -> Path:
    """`runcards/` of the handoff whose id ends with the card's segment, else the store's."""
    seg = None if self.legacy else self.card_segment(card_id)
    if seg:
      if self.handoff_id and self.handoff_id.endswith(seg):
        return self.root / self.handoff_id / "runcards"
      for path in sorted((self.root / "handoffs").glob("*.json")):
        if path.stem.endswith(seg):
          return self.root / path.stem / "runcards"
      for folder in sorted(self.root.glob(f"*{seg}/runcards")):
        return folder
    return self.root / "runcards"

  def base(self, need=True) -> Path:
    """The handoff's directory (`<6 hex>/` in a legacy store); the root when `need` is false and none resolved."""
    if not self.handoff_id:
      if need:
        raise HandoffError("no handoff in this store: run approve-spec and graph first")
      return self.root
    return self.root / self.handoff_id[-6:] if self.legacy else self.root / self.handoff_id

  def path(self, kind, *parts) -> Path:
    kind, parts = self.ALIASES.get(kind, kind), [str(p) for p in parts]
    home = self.root if self.legacy else self.base(need=False)
    if kind in self.FILES:
      return home / self.FILES[kind]
    if kind == "report":
      return home / f"wave_{parts[0]}_report.md"
    if kind == "file":
      return home.joinpath(*parts)
    if kind in self.LEVEL:
      return self.root / kind / (parts[0] if parts[0].endswith(".json") else f"{parts[0]}.json")
    if kind == "runcards":
      return self.card_dir(parts[0]) / (parts[0] if parts[0].endswith(".json") else f"{parts[0]}.json")
    if kind in self.SHARED:
      spec_level = bool(parts) and parts[0].startswith("spec-") and "-integrate-" not in parts[0]
      return (self.root if self.legacy or spec_level else home).joinpath(kind, *parts)
    if kind == "orient":
      return home.joinpath("orient", *parts)
    if kind not in self.KEYED:
      raise HandoffError(f"unknown store kind {kind}")
    base = self.base()
    if kind == "unit":
      return base / f"unit_{parts[0]}.md"
    if kind == "foreman":
      return base / "foreman" / f"{parts[0]}.json"
    if kind == "orient_unit":
      return base.joinpath("orient", *parts)
    if kind == "launches":  # `<unit>.json`, a `<unit>_r<n>_<file>` or the `<unit>_r<n>_bin/` directory
      name = parts[0] if "." in parts[0] or parts[0].endswith("_bin") else f"{parts[0]}.json"
      return base.joinpath("launches", name, *parts[1:])
    if kind == "driver":  # `<handoff>.json`, a tick's launches, or a `<handoff>_r<n>.log` file
      name = parts[0] if "." in parts[0] else f"{parts[0]}.json"
      return base.joinpath("driver", name, *parts[1:])
    if kind == "review":
      number = parts[1] if parts[1].startswith("pr") else f"pr{parts[1]}"
      return base.joinpath("review", parts[0], number, *parts[2:])
    return base.joinpath(kind, *parts)

  def holds(self, path: Path) -> bool:
    return Path(path).resolve().is_relative_to(self.root.resolve())

  def kind_of(self, path: Path) -> str:
    """The kind `path` maps to, `path`'s inverse; a file beside `state.json` is `file`."""
    parts = Path(path).resolve().relative_to(self.root.resolve()).parts
    names = {v: k for k, v in self.FILES.items()}
    level = lambda name: names.get(name) or ("report" if re.fullmatch(r"wave_\d+_report\.md", name) else "file")
    if len(parts) == 1:
      return level(parts[0])
    if parts[0] in self.LEVEL + ("runcards",) + self.SHARED:
      return parts[0]
    if parts[0] == "orient":  # the root's `orient/`: a legacy store's, or no handoff resolved
      return "orient"
    if self.legacy:
      if re.fullmatch(r"[0-9a-f]{6}", parts[0]):
        if len(parts) == 2 and re.fullmatch(r"unit_.+\.md", parts[1]):
          return "unit"
        if parts[1] == "orient":
          return "orient_unit"
        if parts[1] in self.KEYED:
          return parts[1]
      return "file"
    rest = parts[1:]
    if len(rest) == 1:
      return "unit" if re.fullmatch(r"unit_.+\.md", rest[0]) else level(rest[0])
    if rest[0] == "orient":
      return "orient_unit" if re.fullmatch(r"U\d{2,}\b.*", rest[1]) else "orient"
    if rest[0] in self.KEYED + ("runcards",) + self.SHARED:
      return rest[0]
    return "file"


STORE = None
CURRENT_ARGS = None  # the running subcommand's arguments, recorded by `build_parser()`'s `parse_args`


def handoffs(root: Path) -> list:
  """One row per handoff: `handoffs/<id>.json` with `legacy: false`; a flat 1.0/1.1 store
  (`state.json` at the root) is one `legacy: true` row from that file, first, whatever `handoffs/`
  holds for its id, the handoffs opened beside it later following as their files."""
  root = Path(root)
  flat = root / "state.json"
  rows = [json.loads(read_text(p)) | {"legacy": False} for p in sorted((root / "handoffs").glob("*.json"))]
  if flat.is_file():
    state = json.loads(read_text(flat))
    hid = state.get("handoff_id")
    return [{"id": hid, "spec": (state.get("design") or {}).get("path"),
             "opened_at": None, "closed_at": state.get("closed_at"), "legacy": True}] + [r for r in rows if r["id"] != hid]
  return rows


def flat_handoff_id(root: Path):
  """The id of a flat 1.0/1.1 store's handoff (`state.json` at the root), else None."""
  flat = Path(root) / "state.json"
  return json.loads(read_text(flat)).get("handoff_id") if flat.is_file() else None


def handoff_store(st: Store, hid) -> Store:
  """The store as handoff `hid` reads it: flat (`legacy`) when `hid` is the root `state.json`'s handoff,
  else under `<hid>/`, whatever handoff `st` resolved."""
  legacy = bool(hid) and hid == flat_handoff_id(st.root)
  return Store(st.root, handoff_id=hid, config=st.config, legacy=legacy)


def load_approvals(store: Store, spec) -> list:
  """The spec's approval history, `approvals/<spec-slug>.json`'s `entries[]`; a 1.1 record
  (one approval, no `entries`) reads as a one-entry history."""
  path = store.path("approvals", spec_slug(spec))
  if not path.is_file():
    return []
  record = json.loads(read_text(path))
  if "entries" in record:
    return list(record["entries"])
  return [{"kind": "opening", "escalated": [], **{k: v for k, v in record.items() if k != "path"}}]


def require_latest_handoff(store: Store) -> None:
  """An older handoff is frozen: refuse when the store's handoff's latest entry is not the last
  of its spec's history (found by scanning `approvals/*.json` for the id). No handoff passes."""
  hid = store.handoff_id
  if not hid:
    return
  for path in sorted((store.root / "approvals").glob("*.json")):
    entries = load_approvals(store, path)
    if any(e.get("handoff_id") == hid for e in entries) and entries[-1].get("handoff_id") != hid:
      raise HandoffError(f"{hid}: not the latest approval: plan the rows in the latest handoff")


def spec_of_plan(plan) -> str | None:
  """The spec a plan file's `Design:` line names, resolved against the plan's folder."""
  plan = Path(plan).expanduser().resolve()
  match = re.search(r"^Design: `([^`]+)`", read_text(plan), re.M) if plan.is_file() else None
  if not match:
    return None
  design = Path(match.group(1)).expanduser()
  return str(design if design.is_absolute() else (plan.parent / design).resolve())


def resolve_handoff(st: Store, args):
  """The handoff, once: `--handoff`; then the card (`--runcard`, `--parent`); then the spec
  (`--spec`, `--plan`'s `Design:` line, a file `--artifact`) through its latest approval; then
  the unit (`--unit`, a unit-id `--artifact`) over the open handoffs whose state files it.
  `review-spec`, or a card recording `handoff: null`, ends the resolution at none."""
  if args is None:
    return None
  get = lambda key: getattr(args, key, None)
  if get("handoff"):
    return get("handoff")
  if get("skill") == "review-spec":
    return None
  for key in ("runcard", "parent", "id"):  # `id`: the card `runcard close` names
    path = st.path("runcards", get(key)) if get(key) and (key != "id" or get("command") == "runcard") else None
    if path and path.is_file():
      card = json.loads(read_text(path))
      if "handoff" in card:
        return card["handoff"]
  artifact = get("artifact")
  spec = get("design") or (spec_of_plan(get("plan")) if get("plan") else None) \
      or (artifact if artifact and Path(str(artifact)).expanduser().is_file() else None)
  if spec:
    entries = load_approvals(st, spec)
    return entries[-1].get("handoff_id") if entries else None
  unit = get("unit") or (artifact if artifact and UNIT_ID_RE.match(str(artifact)) else None)
  if unit:
    filed = []
    for row in handoffs(st.root):
      state = st.root / "state.json" if row["legacy"] else st.root / row["id"] / "state.json"
      units = json.loads(read_text(state)).get("units") or {} if state.is_file() else {}
      if not row.get("closed_at") and (units.get(unit) or {}).get("number"):
        filed.append(row["id"])
    if len(filed) > 1:
      raise HandoffError(f"store: {unit} is filed in {' and '.join(filed)}: pass --handoff")
    return filed[0] if filed else None
  return None


def spec_blob(repo_root: Path, rel: str, sha256: str, ref: str = "HEAD") -> str | None:
  """The text of `rel` at the first commit of `git log <ref> -- <rel>` whose blob hashes to `sha256`, or None
  when no commit holds those bytes (U32: the one spec-blob search). The git calls are hook-free."""
  for commit in run_git(["log", "--format=%H", ref, "--", rel], repo_root, check=False).split():
    with hook_free() as pairs:
      shown = subprocess.run(["git", *pairs, "show", f"{commit}:{rel}"], cwd=str(repo_root), capture_output=True)
    if shown.returncode == 0 and hashlib.sha256(shown.stdout).hexdigest() == sha256:
      return shown.stdout.decode("utf-8")
  return None


def store(repo_root: Path, args=None) -> Store:
  """The store `.superegm/config.json` names and the handoff, resolved once from `args`, else `CURRENT_ARGS`;
  a flat store (`state.json` at the root) is read in place as its one `legacy` handoff, unless the
  resolution names a handoff opened beside it (one with its own `handoffs/<id>.json`)."""
  global STORE
  args = CURRENT_ARGS if args is None else args
  config = load_config(repo_root)
  root = Path(config["artifacts_dir"])
  flat = root / "state.json"
  st = Store(root, config=config)
  hid = resolve_handoff(st, args)
  named = getattr(args, "handoff", None)
  if named and named != flat_handoff_id(root) and not st.path("handoffs", named).is_file():
    raise HandoffError(f"store: {named}: no such handoff")
  if flat.is_file():
    flat_id = json.loads(read_text(flat)).get("handoff_id")
    if not hid or hid == flat_id or not st.path("handoffs", hid).is_file():
      hid, st.legacy = flat_id, True
  st.handoff_id = hid
  STORE = st
  return STORE


# ---------------------------------------------------------------- run cards


RUNCARD_REVIEWERS = {"review-spec": "spec", "review-plan": "plan", "wave": "head", "integrate": "integrate"}


def load_card(store: Store, id: str) -> dict:
  path = store.path("runcards", id)
  if not path.is_file():
    raise HandoffError(f"runcard: {id} not found")
  return json.loads(read_text(path))


def open_runcard(store: Store, skill: str, artifact: str, parent=None, mode=None) -> str:
  """Open `<skill>-<6 hex>-<n>` (spec section 7): the hex is the store's handoff's, else (a card
  preceding any handoff, at the store level) the 6 hex of the spec slug (the parent card's, else
  the artifact's stem), counted per skill and hex; a legacy store keeps `<skill>-<n>`. `artifact` is
  stored resolved when it is a file; the card records the handoff it resolved, and a top-level `wave`
  card also its `boot_id` and `driver_card` (`SUPEREGM_RUNCARD` under `SUPEREGM_ROLE=driver`, else
  None). The card is written first; then a top-level card of the six `GUARDED_SKILLS` (a `wave` under
  `SUPEREGM_ROLE=driver` excepted) is refused with `TICK_LIVE` while `tick_live` holds, its own card
  marked interrupted and no other open card of its skill touched (spec section 11.2, U24); for `wave`,
  `tick_live` first applies the boot-id proof to every open handoff (`reboot_proof`), which may record
  `driver/<handoff>.json` and `launches/<unit>.json` entries `interrupted (reboot)` and mark rebooted top-level
  `wave` cards interrupted, on the refusal path too (`runcard`'s `WRITES`); only after that is
  every open card of the same skill and artifact marked interrupted, the artifacts compared rebased
  onto the working directory's checkout, one spec being one artifact in every worktree."""
  if parent is not None and not store.path("runcards", parent).is_file():
    raise HandoffError(f"runcard: parent {parent} not found")
  path = Path(artifact).expanduser()
  sha = sha256_file(path) if path.is_file() else None
  artifact = str(path.resolve()) if path.is_file() else artifact
  if store.legacy:
    folder = store.root / "runcards"
    folder.mkdir(parents=True, exist_ok=True)
    existing = sorted(folder.glob("*.json"))
    rid = f"{skill}-{len(existing) + 1:04d}"
  else:
    hexa = store.handoff_id[-6:] if store.handoff_id else \
        (Store.card_segment(parent) if parent and Store.card_segment(parent) else sha256_text(spec_slug(artifact))[:6])
    folder = store.root / store.handoff_id / "runcards" if store.handoff_id else store.root / "runcards"
    folder.mkdir(parents=True, exist_ok=True)
    rid = f"{skill}-{hexa}-{len(list(folder.glob(f'{skill}-{hexa}-*.json'))) + 1:04d}"
    existing = sorted(folder.glob("*.json"))
  config = store.config or {}
  card = {"skill": skill, "artifact": artifact, "artifact_sha256": sha,
          "reviewers": list((config.get("reviewers") or {}).get(RUNCARD_REVIEWERS.get(skill, ""), [])),
          "tiering": None, "mode": mode or config.get("mode", "normal"), "parent": parent,
          "opened_at": now_iso(), "closed_at": None, "interrupted_at": None, "produced": [],
          "handoff": store.handoff_id}
  driven = os.environ.get("SUPEREGM_ROLE") == "driver"
  if skill == "wave" and parent is None:
    card["boot_id"] = boot_id()
    card["driver_card"] = os.environ.get("SUPEREGM_RUNCARD") if driven else None
  # the card is written before the read for a tick's launch, so a tick racing this open sees it (spec section 11.2)
  atomic_write(store.path("runcards", rid), card)
  journal(store, f"runcard open {rid} {skill} {artifact}")
  if parent is None and skill in GUARDED_SKILLS and not (skill == "wave" and driven) and tick_live(store, skill):
    card["interrupted_at"] = now_iso()
    atomic_write(store.path("runcards", rid), card)
    journal(store, f"runcard interrupted {rid}: a tick's session may be live")
    raise HandoffError(TICK_LIVE)
  # one spec is one artifact in every worktree of the repository, as `require_runcard` reads it (`here`)
  try:
    top = git_toplevel(Path.cwd())
  except HandoffError:
    top = None
  same = (lambda p: str(rebased(p, top))) if top else str
  mine = same(artifact)
  for other in existing:
    held = json.loads(read_text(other))
    if held["skill"] == skill and same(held["artifact"]) == mine and not held["closed_at"] and not held["interrupted_at"]:
      held["interrupted_at"] = now_iso()
      atomic_write(other, held)
      journal(store, f"runcard interrupted {other.stem} by {rid}")
  return rid


GUARDED_SKILLS = ("wave", "plan", "file", "integrate", "review-plan", "orient")
TICK_LIVE = "driver: a tick's session may be live; /superegm:driver reset is the owner's interrupt"


def rebooted(entry: dict, current: str | None = None) -> bool:
  """A launch or card whose recorded boot id is neither `unknown` nor the machine's current one: no process
  survives a reboot (spec section 11.2). No proof while the current id cannot be read (`unknown`): a failed lookup
  is never a reboot."""
  recorded, current = entry.get("boot_id"), current or boot_id()
  return bool(recorded) and "unknown" not in (recorded, current) and recorded != current


def tick_terminal(entry: dict) -> bool:
  """A tick's launch that is over: `interrupted` (by reset, a back-off or a reboot) or its exit file written."""
  return str(entry.get("status") or "").startswith("interrupted") or Path(entry["exit_file"]).is_file()


def backed_off(entry: dict) -> bool:
  """A tick's launch recorded and never started: the tick found a card opened since its read and backed off."""
  return entry.get("status") == "interrupted" and "pid" not in entry


def load_driver(hs: Store) -> dict:
  """The handoff's `driver/<handoff>.json`: `launches[]`, `notified`, `refused`, `set_aside` (the round up to which
  `driver reset` set the failures aside)."""
  path = hs.path("driver", hs.handoff_id)
  data = json.loads(read_text(path)) if path.is_file() else {}
  return {"launches": [], "notified": [], "refused": None, **data}


def top_wave_cards(hs: Store) -> list:
  """(path, card) of the handoff's top-level `wave` cards, open or not; a child card counts nowhere."""
  folder = (hs.root if hs.legacy else hs.base()) / "runcards"
  out = []
  for path in sorted(folder.glob("wave-*.json")):
    card = json.loads(read_text(path))
    if card.get("skill") == "wave" and not card.get("parent") and card.get("handoff", hs.handoff_id) == hs.handoff_id:
      out.append((path, card))
  return out


def interrupt_card(hs: Store, path: Path, card: dict, why: str) -> None:
  card["interrupted_at"] = now_iso()
  atomic_write(path, card)
  journal(hs, f"runcard interrupted {path.stem}: {why}")


def reboot_launches(hs: Store, unit: str, current: str) -> None:
  """`launches/<unit>.json`'s running launches with no exit file and a boot id not the current one, recorded
  `interrupted (reboot)` (spec section 11.2: one more proof beside the exit file)."""
  path = hs.path("launches", unit)
  if not path.is_file():
    return
  data = json.loads(read_text(path))
  changed = False
  for entry in data.get("launches") or []:
    if entry.get("status") == "running" and rebooted(entry, current) and not Path(entry["result_file"] + ".exit").is_file():
      entry["status"] = "interrupted (reboot)"
      journal(hs, f"{unit} launch {entry['round']} interrupted (reboot)")
      changed = True
  if changed:
    atomic_write(path, data)


def reboot_proof(hs: Store, current: str) -> None:
  """The boot-id proof over one handoff: its tick launches and builders that a reboot ended recorded
  `interrupted (reboot)`, the open top-level `wave` cards of those launches, or recording a former boot id
  themselves, marked `interrupted`."""
  data, changed = load_driver(hs), False
  ended = set()
  for entry in data["launches"]:
    if not tick_terminal(entry) and rebooted(entry, current):
      entry["status"] = "interrupted (reboot)"
      journal(hs, f"tick: {hs.handoff_id} launch {entry['round']} interrupted (reboot)")
      ended.add(entry.get("card"))
      changed = True
  if changed:
    atomic_write(hs.path("driver", hs.handoff_id), data)
  for path, card in top_wave_cards(hs):
    if not card.get("closed_at") and not card.get("interrupted_at") and (card.get("driver_card") in ended - {None} or rebooted(card, current)):
      interrupt_card(hs, path, card, "interrupted (reboot)")
  folder = hs.base(need=False) / "launches" if not hs.legacy else None
  if folder is not None and folder.is_dir():
    for path in sorted(folder.glob("*.json")):
      if "_" not in path.stem:
        reboot_launches(hs, path.stem, current)


def tick_live(store: Store, skill: str) -> bool:
  """Whether a tick's launch may be live where `skill` would run: any open handoff of the store for `wave` (one
  `.git`), the card's own handoff for the other five. Under `wave` the boot-id proof is written first; the other
  five read it and write nothing."""
  current = boot_id()
  for row in handoffs(store.root):
    if not row.get("id") or row.get("closed_at"):
      continue
    if skill != "wave" and row["id"] != store.handoff_id:
      continue
    hs = handoff_store(store, row["id"])
    if skill == "wave":
      reboot_proof(hs, current)
    if any(not tick_terminal(e) and not rebooted(e, current) for e in load_driver(hs)["launches"]):
      return True
  return False


def rebased(path, root) -> Path:
  """A path the handoff recorded from another worktree of the repository, read under `root`: the longest suffix of it
  that exists there (`register` from a second worktree moves a tick's root, never the state's paths, U24)."""
  path, root = Path(path), Path(root).resolve()
  if not path.is_absolute() or path.resolve().is_relative_to(root):
    return path
  for i in range(1, len(path.parts)):
    candidate = root.joinpath(*path.parts[i:])
    if candidate.exists():
      return candidate
  return path


def here(path) -> Path:
  """`rebased` onto the working directory's checkout (the path unchanged outside a repository)."""
  try:
    return rebased(path, git_toplevel(Path.cwd()))
  except HandoffError:
    return Path(path)


def handoff_spec(args, store: Store) -> str:
  """The handoff's spec: the state's `design.path` (read under this checkout, `here`), else (before the first
  `graph`) the `Design:` line of `--plan`."""
  spec = (load_state(store.root).get("design") or {}).get("path")
  spec = str(here(spec)) if spec else spec
  plan = Path(args.plan).expanduser().resolve() if getattr(args, "plan", None) else None
  if not spec and plan and plan.is_file():
    match = re.search(r"^Design: `([^`]+)`", read_text(plan), re.M)
    if match:
      design = Path(match.group(1)).expanduser()
      spec = str(design if design.is_absolute() else (plan.parent / design).resolve())
  return spec or ""


def subcommand_artifact(args, store: Store) -> str:
  """What the running subcommand acts on: its unit, else its spec, else the
  handoff's spec; a spec read under this checkout (`here`), as the card's side is."""
  if getattr(args, "unit", None):
    return args.unit
  if getattr(args, "design", None):
    return str(here(Path(args.design).expanduser().resolve()))
  return handoff_spec(args, store)


def require_runcard(args, skills) -> dict:
  """The card `--runcard` names, open (or a child of an open or interrupted
  parent), of one of `skills`, on this subcommand's artifact or on the
  handoff's spec (spec section 6). Every refusal starts `runcard: `."""
  rid = getattr(args, "runcard", None)
  if not rid:
    raise HandoffError("runcard: --runcard is required")
  st = STORE or store(git_toplevel(Path.cwd()), args)
  card = load_card(st, rid)
  if card["closed_at"]:
    raise HandoffError(f"runcard: {rid} is closed")
  if card["parent"]:
    if load_card(st, card["parent"])["closed_at"]:
      raise HandoffError(f"runcard: {rid}'s parent {card['parent']} is closed")
  elif card["interrupted_at"]:
    raise HandoffError(f"runcard: {rid} is interrupted")
  if card["skill"] not in skills:
    raise HandoffError(f"runcard: {rid} belongs to {card['skill']}, not {'|'.join(sorted(skills))}")
  ours, theirs = subcommand_artifact(args, st), str(here(card["artifact"]))
  if theirs != ours and not (getattr(args, "unit", None) and theirs == handoff_spec(args, st)):
    raise HandoffError(f"runcard: {rid} is for {card['artifact']}, not {ours}")
  return card


def card_add(store: Store, id: str, key: str, item) -> None:
  card = load_card(store, id)
  card.setdefault(key, []).append(item)
  atomic_write(store.path("runcards", id), card)


def load_approval(store: Store, spec: Path):
  """The latest approval of this spec, its history's last entry, or None."""
  entries = load_approvals(store, spec)
  return entries[-1] if entries else None


def journal(store: Store, line: str) -> None:
  """Append one fact; `O_APPEND` keeps concurrent lines whole."""
  path = store.path("journal")
  path.parent.mkdir(parents=True, exist_ok=True)
  fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o644)
  try:
    os.write(fd, f"{now_iso()} {line}\n".encode("utf-8"))
  finally:
    os.close(fd)


STAMP = "%Y-%m-%dT%H:%M:%SZ"


def iso(seconds):
  """The store's `%Y-%m-%dT%H:%M:%SZ` stamp of these seconds, or None (the one formatter, U31)."""
  return time.strftime(STAMP, time.gmtime(seconds)) if seconds is not None else None


def epoch(stamp: str) -> float:
  """The seconds of a store stamp (the one parser, U31); ValueError or TypeError for any other form."""
  return float(calendar.timegm(time.strptime(stamp, STAMP)))


def now_iso() -> str:
  return iso(NOW())


def canonical(obj) -> str:
  return json.dumps(obj, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


@contextlib.contextmanager
def hook_free():
  """The `-c` pairs that keep a git call from running a hook or an fsmonitor the repository names: `core.hooksPath`
  at a fresh empty directory (spec section 4.1), removed on exit (U25)."""
  folder = tempfile.mkdtemp(prefix="superegm-no-hooks-")
  try:
    yield ["-c", f"core.hooksPath={folder}", "-c", "core.fsmonitor=false"]
  finally:
    shutil.rmtree(folder, ignore_errors=True)


def run_git(args, cwd: Path, check=True) -> str:
  with hook_free() as pairs:
    result = subprocess.run(["git", *pairs, *args], cwd=str(cwd), capture_output=True,
                            text=True, encoding="utf-8")
  if not check:
    return result.stdout if result.returncode == 0 else ""
  if result.returncode != 0:
    raise HandoffError(f"git {' '.join(args)} failed in {cwd}: "
                       f"{result.stderr.strip() or result.stdout.strip()}")
  return result.stdout


def kill_group(pgid: int) -> None:
  """SIGTERM to the process group `pgid`, no escalation; a group already gone is no error."""
  try:
    os.killpg(pgid, signal.SIGTERM)
  except (ProcessLookupError, PermissionError):
    pass


def git_toplevel(path: Path) -> Path:
  folder = path if path.is_dir() else path.parent
  return Path(run_git(["rev-parse", "--show-toplevel"], folder).strip())


REGISTRY_KEYS = ("repo", "root", "artifacts_dir")


def registry_path() -> Path:
  return Path.home() / ".superegm" / "registry.json"


def load_registry() -> list:
  """`~/.superegm/registry.json` (spec section 11.2): one `{repo, root, artifacts_dir}` per registered store;
  [] when absent. Unknown keys stop."""
  path = registry_path()
  if not path.is_file():
    return []
  try:
    entries = json.loads(read_text(path))
  except ValueError as error:
    raise HandoffError(f"registry: {path} is not JSON ({error})") from None
  if not isinstance(entries, list) or not all(isinstance(e, dict) for e in entries):
    raise HandoffError(f"registry: {path} is not a list of entries")
  for entry in entries:
    unknown = sorted(set(entry) - set(REGISTRY_KEYS))
    if unknown:
      raise HandoffError(f"registry: unknown key {unknown[0]}")
  return entries


def boot_id() -> str:
  """The machine's boot id (spec section 11.2): `kern.bootsessionuuid`, else Linux's `boot_id`, else `unknown`;
  never the boot time, which a clock step moves."""
  for sysctl in ("/usr/sbin/sysctl", "sysctl"):  # the absolute path first: a timer's PATH is not the shell's
    try:
      done = subprocess.run([sysctl, "-n", "kern.bootsessionuuid"], capture_output=True, text=True, timeout=10)
      if done.returncode == 0 and done.stdout.strip():
        return done.stdout.strip()
    except (OSError, subprocess.SubprocessError):
      pass
  try:
    held = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="utf-8").strip()
    if held:
      return held
  except OSError:
    pass
  return "unknown"


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
      elif key in ("astra", "ingest", "foreman", "builder", "reviewers") and isinstance(value, dict):
        config[key] = {**config[key], **value}
      else:
        config[key] = value
  if not isinstance(config["astra"], dict):
    raise HandoffError("astra must be an object")
  if not isinstance(config["astra"].get("heads"), bool):
    raise HandoffError("astra.heads must be true or false")
  if not isinstance(config["ingest"], dict):
    raise HandoffError("ingest must be an object")
  words = config["ingest"].get("severity_words")
  if not isinstance(words, dict) or any(not isinstance(k, str) or v not in ("high", "medium", "low") for k, v in words.items()):
    raise HandoffError("ingest.severity_words must map words to high|medium|low")
  if config["ingest"].get("human_role") not in ROLES[1:]:
    raise HandoffError(f"ingest.human_role must be one of {', '.join(ROLES[1:])}")
  if not isinstance(config["foreman"], dict):
    raise HandoffError("foreman must be an object")
  if set(config["foreman"]) - {"run_timeout_minutes"}:
    raise HandoffError(f"foreman: unknown keys {sorted(set(config['foreman']) - {'run_timeout_minutes'})}")
  bound = config["foreman"].get("run_timeout_minutes")
  if isinstance(bound, bool) or not isinstance(bound, (int, float)) or not 0 < bound <= 9:
    raise HandoffError("foreman.run_timeout_minutes must be a number above 0 and at most 9")
  if not config["repo"]:
    origin = run_git(["remote", "get-url", "origin"], repo_root)
    config["repo"] = parse_remote_url(origin)
    if not config["repo"]:
      raise HandoffError(f"cannot parse OWNER/NAME from origin `{origin.strip()}`: "
                         "set `repo` in .superegm/config.json")
  if not REPO_RE.match(config["repo"]):
    raise HandoffError(f"invalid repo `{config['repo']}` in {path}")
  if config["artifacts_dir"]:
    config["artifacts_dir"] = str(Path(config["artifacts_dir"]).expanduser())
  builder = config["builder"]
  if isinstance(builder, dict) and isinstance(builder.get("profile_dir"), str):
    builder["profile_dir"] = str(Path(builder["profile_dir"]).expanduser())
  app = builder.setdefault("app", None) if isinstance(builder, dict) else None
  isinstance(builder, dict) and builder.setdefault("stall_minutes", 30)  # a file written before U31 lacks it
  if app is not None:
    app = {"private_key_env": "SUPEREGM_APP_KEY", **app} if isinstance(app, dict) else app
    if not isinstance(app, dict) or set(app) != {"app_id", "slug", "private_key_env"} \
        or isinstance(app["app_id"], bool) or not isinstance(app["app_id"], int) or app["app_id"] < 1 \
        or not isinstance(app["slug"], str) or not re.fullmatch(r"[a-z0-9-]+", app["slug"]) \
        or not isinstance(app["private_key_env"], str):
      raise HandoffError(f"{path}: builder.app must be null or {{app_id: <int>, slug: <slug>, private_key_env: <name>}}")
    builder["app"] = app
  if isinstance(builder, dict):
    for key, default in (("plugins", []), ("mcp", {}), ("max_subagent_calls", 12)):
      builder.setdefault(key, default)  # a file written before U27 lacks them
    tools = builder.get("allowed_tools")
    if not isinstance(tools, list) or not all(isinstance(t, str) for t in tools):
      raise HandoffError(f"{path}: builder.allowed_tools must be a list of strings")
    plugins = builder["plugins"]
    if not isinstance(plugins, list) or not all(isinstance(p, str) and re.fullmatch(r"[^@\s]+@[^@\s]+", p) for p in plugins):
      raise HandoffError(f"{path}: builder.plugins must be a list of <name>@<marketplace> ids")
    mcp = builder["mcp"]  # the server map that goes under `mcpServers`, never a whole `.mcp.json`
    if not isinstance(mcp, dict) or "mcpServers" in mcp or not all(isinstance(v, dict) for v in mcp.values()):
      raise HandoffError(f"{path}: builder.mcp must be an object in mcpServers form: the server map, name to server object")
    cap = builder["max_subagent_calls"]
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
      raise HandoffError("config: builder.max_subagent_calls: a positive integer")
  artifacts = config["artifacts_dir"]
  if not artifacts or not Path(artifacts).is_absolute() \
      or Path(artifacts).resolve().is_relative_to(repo_root.resolve()):
    raise HandoffError(f"{path}: artifacts_dir must be an absolute path outside the working tree "
                       f"(run `superegm init`)")
  if not isinstance(config["base"], str) or not config["base"]:
    raise HandoffError(f"{path}: base must name the default branch")
  if config["mode"] not in ("normal", "leavemealone"):
    raise HandoffError(f"{path}: mode must be `normal` or `leavemealone`")
  for key in ("max_in_flight", "ci_wait_minutes"):
    if isinstance(config[key], bool) or not isinstance(config[key], int) or config[key] < 1:
      raise HandoffError(f"{path}: {key} must be a positive integer")
  stall = config["builder"].get("stall_minutes") if isinstance(config["builder"], dict) else None
  if isinstance(stall, bool) or not isinstance(stall, int) or stall < 1:
    raise HandoffError(f"{path}: builder.stall_minutes must be a positive integer")
  timeout = config["notify_timeout_seconds"]
  if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not 0 < timeout < float("inf"):
    raise HandoffError(f"{path}: notify_timeout_seconds must be a positive number")
  if not isinstance(config["commit_trailer"], str):
    raise HandoffError(f"{path}: commit_trailer must be a string")
  # shortcut: the nested keys of reviewers/judges/builder are not validated here, the unit that
  # reads each validates (astra is checked above as an object, astra.heads as a bool)
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
    raise HandoffError("allowed_mentions must be a list of `@name` strings")
  if not isinstance(config["banned_terms"], list):
    raise HandoffError("banned_terms must be a list of regular expressions")
  for term in config["banned_terms"]:
    re.compile(term)
  owners = config["owners"]
  if not isinstance(owners, list) or not all(isinstance(o, str) for o in owners):
    raise HandoffError(f"{path}: owners must be a list of GitHub logins")
  team = config["owner_team"]
  if team is not None and not (isinstance(team, str) and team.count("/") == 1 and all(team.split("/"))):
    raise HandoffError(f"{path}: owner_team must be `<org>/<slug>` or null")
  if config["pr_block_file"] is not None and not isinstance(config["pr_block_file"], str):
    raise HandoffError(f"{path}: pr_block_file must be a path relative to the repository root or null")
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
  if first != "<!-- superegm:handoff={{handoff_id}} unit={{unit_id}} spec={{spec_sha256}} -->":
    raise HandoffError("issue template must start with the marker line "
                       "`<!-- superegm:handoff={{handoff_id}} unit={{unit_id}} spec={{spec_sha256}} -->`")
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
    self.issue = None      # the adopted issue number, an int once parsed
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
        "size": self.size, "issue": self.issue, "dod": self.dod,
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
    unknown = set(fields) - set(FIELDS) - set(OPTIONAL_FIELDS)
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
    if "Issue" in fields:
      value, line = fields["Issue"]
      match = re.match(r"^#(\d+)$", value)
      if not match:
        self._fail(line, f"{unit.id}: Issue must read `#<n>`")
      unit.issue = int(match.group(1))

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


def parse_plan(path: Path):
  """One plan grammar (spec section 9.1): the parser is `graph.Plan`, for every subcommand."""
  from superegm import graph  # here, not at the top: graph imports this module
  return graph.Plan(path)


class Handoff:
  """A parsed plan, its graph, config, design facts and rendered bodies."""

  def __init__(self, plan_path: Path, store: Store, state=None):
    self.plan_path = plan_path.resolve()
    self.store = store
    self.artifact_dir = store.root
    self.plan = parse_plan(self.plan_path)
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
    # The handoff's own approval is its latest entry (spec section 7); the spec may stand at a later link.
    entries = load_approvals(store, design)
    own = [i for i, e in enumerate(entries) if store.handoff_id and e.get("handoff_id") == store.handoff_id] \
        or ([len(entries) - 1] if entries else [])
    approval = entries[own[-1]] if own else None
    if approval and self.design_sha not in {approval["sha256"], *(e["sha256"] for e in entries[own[-1] + 1:])}:
      raise HandoffError("spec changed since the approval: run approve-spec again")
    self.design_commit = (approval or {}).get("commit") or run_git(
        ["rev-parse", "--short", "HEAD"], self.repo_root).strip()
    self.design_title = next((l[2:].strip() for l in read_text(design).splitlines()
                              if l.startswith("# ")), design.stem)
    self.config = load_config(self.repo_root)
    self.graph = Graph(self.plan)
    slug = re.sub(r"[^a-z0-9]+", "-", design.stem.lower()).strip("-")[:20].rstrip("-")
    self.handoff_id = (approval or {}).get("handoff_id") or f"{slug}-{self.design_sha[:6]}"
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
        "spec_sha256": self.design_sha,
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
    values = {"handoff_id": self.handoff_id, "spec_sha256": self.design_sha, "design": self.design_ref(),
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
    lines = [GEN_START, "## Generated by `superegm.py graph` (do not edit)", "",
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
      self.plan = parse_plan(self.plan_path)
    # The store's copy: `require_frozen_units` compares a filed unit's section
    # in the plan file with the one stored here.
    atomic_write(self.store.path("plan"), self.plan.text)
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


# ---------------------------------------------------------------- state


def state_path(artifact_dir: Path) -> Path:
  """The handoff's `state.json`: through `STORE` when `artifact_dir` is its root."""
  if STORE is not None and Path(artifact_dir) == STORE.root:
    return STORE.path("state")
  return Path(artifact_dir) / "state.json"


def load_state(artifact_dir: Path) -> dict:
  path = state_path(artifact_dir)
  return json.loads(read_text(path)) if path.is_file() else {}


def save_state(artifact_dir: Path, state: dict) -> None:
  """Replace the state file atomically: a truncating write interrupted here
  leaves invalid JSON and no handoff can be resumed from it."""
  atomic_write(state_path(artifact_dir), state)


# ---------------------------------------------------------------- scan


def scan_text(text: str, config: dict, kind: str, dod=None, label="body", limit=BODY_LIMIT) -> list:
  """The raw text rules, one `<rule>: <label>[:<line>]: <reason>` per problem: `body-size`,
  `banned-term`, `mention`, `merge-marker`, `dod-missing`. The mention rule alone skips a
  fenced code block and an inline code span (GitHub notifies for neither); a banned term is
  refused wherever it stands, and a legitimate `@scope/pkg` goes in `allowed_mentions`.
  `limit=None` skips the body-size rule (`review ingest` bounds its comment by GitHub's own limit)."""
  problems = []
  size = len(text.encode("utf-8"))
  if limit is not None and size > limit:
    problems.append(f"body-size: {label}: {size:,} bytes exceeds {limit:,}: split it")
  terms = [re.compile(t) for t in config["banned_terms"]]
  mention = config.get("fix_request_mention")
  allowed = set(config.get("allowed_mentions") or [])
  fence = None  # the open fence's (character, run length): closed by a run of that character at least as long
  for number, line in enumerate(text.splitlines(), start=1):
    for term in terms:
      if term.search(line):
        problems.append(f"banned-term: {label}:{number}: banned term /{term.pattern}/")
    if fence:
      if re.match(rf"^ {{0,3}}{fence[0]}{{{fence[1]},}}\s*$", line):
        fence = None
    elif (opener := FENCE_RE.match(line)) and not (opener.group(1)[0] == "`" and "`" in opener.group(2)):
      fence = (opener.group(1)[0], len(opener.group(1)))
    else:
      for found in MENTION_RE.findall(SPAN_RE.sub(" ", line)):
        # Exact literal only: `@types` does not cover `@types/node`, `@acme` never the team `@acme/release`.
        if found in allowed or (kind == "comment" and number == 1 and mention and found == mention):
          continue
        problems.append(f"mention: {label}:{number}: bare mention {found} (it would notify that user; "
                        f"reword it, or list it in `allowed_mentions` in .superegm/config.json)")
    if re.match(r"^(<<<<<<<|=======|>>>>>>>)( |$)", line):
      problems.append(f"merge-marker: {label}:{number}: merge marker")
  for item in dod or []:
    if item not in text:
      problems.append(f"dod-missing: {label}: definition-of-done item missing from the body: {item}")
  return problems


# ---------------------------------------------------------------- commands


# ---------------------------------------------------------------- commands


CURRENT_WRITES = None
CURRENT_SUBCOMMAND = None


def locate(args):
  """The store of the repository the working directory is in, and the plan."""
  st = store(git_toplevel(Path.cwd()), args)
  if getattr(args, "plan", None):
    plan = Path(args.plan).expanduser().resolve()
  else:
    recorded = load_state(st.root).get("plan")
    if not recorded:
      raise HandoffError("state holds no plan path: run `graph --plan <file>` first")
    plan = here(recorded)
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


def unit_file_body(path: Path) -> str:
  """The body inside `unit_<id>.md`'s fence after `## Issue body as posted`:
  the first ```markdown (three or more backticks) line after that heading up
  to the line equal to that backtick run; text outside the fence is not the body."""
  lines = read_text(path).splitlines() if path.is_file() else []
  if "## Issue body as posted" not in lines:
    return ""
  start, fence = lines.index("## Issue body as posted") + 1, None
  while start < len(lines) and fence is None:
    match = re.match(r"^(`{3,})markdown$", lines[start])
    fence = match.group(1) if match else None
    start += 1
  if fence is None:
    return ""
  inside = []
  for line in lines[start:]:
    if line == fence:
      break
    inside.append(line)
  return "\n".join(inside)


def require_frozen_units(handoff) -> None:
  """A filed unit (one with an issue number) is frozen (spec section 7): its
  section in the plan file equals the stored `handoff_plan.md`'s, and the body
  its filing's write list in `filings[]` stores is still what `unit_<id>.md`
  carries in its fence. Runs before any read of GitHub."""
  state = handoff.state
  filed = [uid for uid, record in (state.get("units") or {}).items() if record.get("number")]
  if not filed:
    return
  stored_path = handoff.store.path("plan")
  stored = parse_plan(stored_path) if stored_path.is_file() else None
  for uid in filed:
    if stored is None or uid not in stored.units or uid not in handoff.plan.units \
        or unit_section_text(handoff.plan, uid) != unit_section_text(stored, uid):
      raise HandoffError(f"{uid} is filed and frozen: its section in handoff_plan.md differs from the stored one")
  for filing in state.get("filings") or []:
    for item in filing.get("writes") or []:
      if item[0] == "issue" and item[1] in filed \
          and body.normalise(item[4]) != body.normalise(unit_file_body(handoff.unit_file(item[1]))):
        raise HandoffError(f"{item[1]} is filed and frozen: unit_{item[1]}.md no longer carries the filed body")


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


def issue_closed_completed(handoff: Handoff, uid) -> bool:
  record = handoff.state.get("units", {}).get(uid, {})
  issue = gh_json(["api", f"repos/{handoff.config['repo']}/issues/{record.get('number')}"]) or {}
  return issue.get("state") == "closed" and issue.get("state_reason") == "completed"


def status_pass(handoff: Handoff, save=True):
  from superegm import status as events  # the unit view lives with the event lines it feeds (U09b)
  state = handoff.state
  state.setdefault("units", {})
  views = {uid: events.unit_view(handoff, uid) for uid in handoff.graph.order}
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
      if d["blocking"] and not answer:
        open_blocking.setdefault(unit.id, []).append(d)
  ready = [u for u in handoff.graph.order if u not in landed and not views[u]["launched"]
           and handoff.graph.preds[u] <= landed and u not in open_blocking]
  in_flight = [u for u in handoff.graph.order if views[u]["launched"] and u not in landed]
  unlaunched_prs = [u for u in handoff.graph.order if not views[u]["launched"] and views[u]["pr"]
                    and u not in landed]
  summary = {"landed": sorted(landed), "ready": ready, "in_flight": in_flight,
             "unlaunched_with_pr": unlaunched_prs, "open_blocking": {u: [d["id"] for d in ds] for u, ds in open_blocking.items()},
             # `stalled` rides the pass, never the saved fingerprint (U31: the predicate, derived afresh at every pass)
             "units": {u: {**events.fingerprint(v), "status": v["status"], "stalled": v.get("stalled")} for u, v in views.items()},
             "at": now_iso()}
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
    launched = " launched" if record.get("launched") else ""
    pr = f"pr #{v['pr']} head {v['head'][:7]}" if v["pr"] else "no pr"
    print(f"{uid} #{record.get('number')}{launched}: {pr}; {v['status']}")
  for uid, ds in open_blocking.items():
    for d in ds:
      print(f"open blocking decision {uid}/{d['id']}: {d['question']} "
            f"(owner: {d['owner']}; default: {d['default']})")
  if summary["unlaunched_with_pr"]:
    print("open PRs for units not launched: " + ", ".join(f"{u} #{summary['units'][u]['pr']}" for u in summary["unlaunched_with_pr"]))


# ---------------------------------------------------------------- prepare


ROUND_KEYS = ("round", "runcard", "launch", "head", "phase", "dispatch_id", "outcome", "posted_at")


def load_foreman(store: Store, uid):
  """`foreman/<unit>.json` per spec section 7: `dispatch_id`, `rounds[]`, `decisions[]`, `rulings[]`."""
  path = store.path("foreman", uid)
  return json.loads(read_text(path)) if path.is_file() else {"dispatch_id": None, "rounds": [], "decisions": [], "rulings": []}


def round_entry(data: dict, n: int) -> dict:
  """The `rounds[]` entry of round `n`, created with every key None when missing."""
  for entry in data["rounds"]:
    if entry.get("round") == n:
      return entry
  entry = {key: None for key in ROUND_KEYS}
  entry["round"] = n
  data["rounds"].append(entry)
  return entry


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


def remove_worktree(root: Path, tree: Path, force=False) -> None:
  """Remove a review worktree only when it is clean, unless `force`.

  `--force` deletes tracked modifications and untracked files. By default the
  foreman would not take a person's edits without asking; `prepare` passes
  `force` (U25): the review worktree is the store's, and a DoD `Run` line may
  leave it dirty."""
  if not tree.exists():
    run_git(["worktree", "prune"], root, check=False)
    return
  if force:
    run_git(["worktree", "remove", "--force", str(tree)], root)
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


def discover() -> dict:
  """The subcommand modules, `{name: module}` sorted by name: every module of this package that defines
  `register` (U32). `SUBCOMMANDS` and `DEFAULT_CONFIG` are derived from it at import. A module that fails to
  import or exposes no `CONFIG_DEFAULTS` is skipped and kept on `FAULTS` as `(name, message)`, the list
  cleared and refilled by each call in name order; `build_parser()` turns the first, by name, into every
  command's refusal. Two limits: a failure raised through another module's import is recorded under the
  importing module, so the refusal names the first importer by name (a broken `launch` reads
  `superegm.clean: ...`, `clean` importing it and sorting first), and `review`,
  which the package's foot imports directly for `PANEL_OF`, raises at package import when it cannot load."""
  modules = {}
  FAULTS.clear()
  for entry in sorted(pkgutil.iter_modules(__path__), key=lambda e: e.name):
    try:
      module = importlib.import_module(f"superegm.{entry.name}")
    except Exception as error:  # noqa: BLE001  an import failure here is named, not raised (`review`'s aside: docstring)
      FAULTS.append((entry.name, f"superegm.{entry.name}: {error}"))
      continue
    if not hasattr(module, "register"):
      continue
    if not hasattr(module, "CONFIG_DEFAULTS"):
      FAULTS.append((entry.name, f"superegm.{entry.name} exposes no CONFIG_DEFAULTS"))
      continue
    modules[entry.name] = module
  return modules


FAULTS = []  # discover()'s skipped modules, `(name, message)` (U32)


def fault_run(message):
  """A subcommand's `run` while a module is faulty: the fault, before the command's own `run`."""
  def run(args):
    raise HandoffError(message)
  return run


def add_parser(subparsers, name, help_text, *, runcard=True):
  """A subcommand parser with `--plan`; `runcard=True` (a writing subcommand)
  adds `--runcard`, checked first by `require_runcard`."""
  p = subparsers.add_parser(name, help=help_text)
  p.add_argument("--plan", help="the plan file (default: the one the state names)")
  if runcard:
    p.add_argument("--runcard", help="the open run card this effect runs under")
  return p


class Parser(argparse.ArgumentParser):
  """The top-level parser: `parse_args` records the arguments in `CURRENT_ARGS`, which `store()`
  resolves the handoff from."""

  def parse_args(self, args=None, namespace=None):
    global CURRENT_ARGS, STORE
    CURRENT_ARGS = STORE = None  # a new command resolves its own handoff
    CURRENT_ARGS = super().parse_args(args, namespace)
    return CURRENT_ARGS


def add_handoff_flag(parser) -> None:
  """`--handoff <id>` on every leaf subparser (spec section 7)."""
  children = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
  if not children:
    if "--handoff" not in parser._option_string_actions:
      parser.add_argument("--handoff", help="the handoff this command acts on (default: resolved from the card, spec or unit)")
    return
  for action in children:
    for child in dict.fromkeys(action.choices.values()):
      add_handoff_flag(child)


def build_parser():
  parser = Parser(prog="superegm.py", description=__doc__.splitlines()[0])
  sub = parser.add_subparsers(dest="command", required=True)
  for module in discover().values():
    module.register(sub)
  if FAULTS:  # every command exits 1 naming the first faulty module (U32)
    run = fault_run(FAULTS[0][1])
    for child in dict.fromkeys(sub.choices.values()):
      set_run(child, run)
  add_handoff_flag(parser)
  return parser


def set_run(parser, run) -> None:
  """`run` as the default of `parser` and every nested subparser."""
  parser.set_defaults(run=run)
  for action in parser._actions:
    if isinstance(action, argparse._SubParsersAction):
      for child in dict.fromkeys(action.choices.values()):
        set_run(child, run)


_MODULES = discover()  # every subcommand module, imported once the names they use are defined (U32)
SUBCOMMANDS = tuple(_MODULES)
DEFAULT_CONFIG = json.loads(json.dumps({**CORE_CONFIG, **{k: v for m in _MODULES.values() for k, v in m.CONFIG_DEFAULTS.items()}}))
from .review import PANEL_OF, ROLES  # noqa: E402  review.py imports this package, so it loads after the names it uses
DEFAULT_CONFIG["reviewers"] = {kind: panel.split(",") for kind, panel in PANEL_OF.items()}  # one source: the spec's panels
DEFAULT_CONFIG["reviewers"]["head"].append("astra")  # informational: the lane is seated by astra.enabled and astra.heads
DEFAULT_CONFIG["reviewers"].update(model="opus", effort="xhigh")  # every review goldfish dispatch, in the Agent tool's alias and level forms (amendment 8)
