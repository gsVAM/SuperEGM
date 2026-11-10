# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the launch-builder subcommand (spec section 11); the prompt's # Orient section from orient (spec section 9.3); the PR block read from the launch's ref and the profile's hooks check (U14); the per-launch bin directory and the launched environment (U15); the prompt keeps rulings and decisions from `config.owners` alone (U22); every `&&`/`;` segment's first word in the allow-list and hook-free git calls (U25); the launch started detached and recorded `running`, the boot-id proof in the terminal check (U24); the builder's plugins and MCP servers passed per launch, the amendment-7 profile refusals and the session id (U27); `--effort` with the session effort level unset, and the requested pair recorded (U28); the watchdog's TERM trap (U31); the idempotent re-run, the builder key as its CONFIG_DEFAULTS and the spec range through `spec_blob` (U32); `builder.tiers` and the launch's model and effort by the unit's tier (U33).

"""superegm launch-builder: a fresh worktree, the prompt file and the command line of one builder launch, started
detached and recorded `running`."""

import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
import uuid
from pathlib import Path

import superegm as core
from superegm import body, orient
from superegm.builder_token import key_path, tool
from superegm.decision import deleted_rulings, overridden_comments, parse_form
from superegm.launch import builder_email, builder_login, load_launches, terminal
from superegm.review_plan import SPEC_LINE_RE

WRITES = frozenset(["launches", "orient_unit"])  # the store kinds this subcommand writes
CONFIG_DEFAULTS = {  # its own config key (U32)
    "builder": {"profile_dir": "~/.superegm/builder-profile", "model": "claude-opus-5-5", "effort": "medium",
                "permission_mode": "acceptEdits", "gh_token_env": "SUPEREGM_BUILDER_TOKEN",
                "allowed_tools": ["Read", "Edit", "Write", "Glob", "Grep", "Bash(git add:*)", "Bash(git commit:*)",
                                  "Bash(git status:*)", "Bash(git diff:*)", "Bash(git log:*)", "Bash(git mv:*)",
                                  "Bash(git rm:*)", "Bash(gh pr create:*)", "Bash(gh pr edit:*)",
                                  "Bash(gh pr comment:*)", "Bash(gh issue comment:*)", "Bash(gh pr view:*)",
                                  "Bash(pytest:*)"],
                "plugins": [],  # <name>@<marketplace> ids, each passed by --plugin-dir (U27)
                "mcp": {},  # mcpServers form, written to launches/<unit>_r<n>_mcp.json (U27)
                "max_subagent_calls": 12,  # the orders' budget when allowed_tools carries Agent (U27)
                "stall_minutes": 30,  # a running launch with no newer commit of its own this long is stalled (U31)
                # the model and effort per tier; doable is `model` and `effort` above (U33)
                "tiers": {"difficult": {"model": "claude-opus-5-5", "effort": "high"},
                          "easy": {"model": "claude-sonnet-5-5", "effort": "medium"}},
                "app": None},  # or {app_id, slug, private_key_env}: the builder as a GitHub App (spec section 11)
}
INIT_STEP, DOCTOR_CHECKS = "", None  # its init lines stay numbered in init's own text (U32)
SKILLS = frozenset(["wave"])  # the skills whose card this subcommand accepts
PROMPT_COMMENT_RE = re.compile(r"^\*\*(Deviation \([a-z]+\)|Decision D\d+|Ruling):\*\*")
# The PR body's DoD-results form (the orders): `### DoD <n>` then one fenced block per item.
DOD_RESULT_RE = re.compile(r"^### DoD (\d+)\n```[^\n]*\n(.*?)\n```", re.M | re.S)
ORDERS = Path(__file__).resolve().parents[4] / "skills/wave/references/builder_orders.md"
HELPER = Path(__file__).resolve().parents[1] / "superegm.py"  # the plugin's own helper, run by `superegm-token`
SENTINEL = "superegm-no-token"  # the launched `GH_TOKEN` on the App path: no token; the shim overrides it with the mint
# the owner's prompts and token, and the session effort level that would beat `--effort` (U28), unset in the launched environment
UNSET = ("GIT_ASKPASS", "SSH_ASKPASS", "GITHUB_TOKEN", "CLAUDE_CODE_EFFORT_LEVEL")
# The PR body's line 2 (owner ruling 2026-11-04): the login of the session that ran `launch`, no `@`, so it mentions nobody.
AUDIT_LINE = "Launched by {owner} · run card {runcard} · unit {unit} · handoff {handoff}"


def register(subparsers):
  p = core.add_parser(subparsers, "launch-builder", "a fresh worktree, the prompt file and the command line of one builder launch")
  p.add_argument("--unit", required=True)
  p.add_argument("--round", type=int, required=True, help="the launch count")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  card = core.require_runcard(args, SKILLS)
  try:
    return prepare(args, card)
  except core.HandoffError as error:
    raise core.HandoffError(f"launch-builder: {error}") from None


def prepare(args, card):
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  state, config, unit, rnd = handoff.state, handoff.config, args.unit, args.round
  repo, builder_config = config["repo"], config["builder"]
  builder = builder_login(config, os.environ.get(builder_config["gh_token_env"]))
  problem = refusal(st, state, config, unit, rnd, builder)
  if problem:
    raise core.HandoffError(problem)
  dirs = plugin_dirs(builder_config["plugins"], elephant_profile())  # each listed plugin's user-scope directory, version and hooks
  mcp_file = st.path("launches", f"{unit}_r{rnd}_mcp.json")
  for value in (*(d["dir"] for d in dirs), mcp_file, builder_config["model"], builder_config["effort"]):  # command_line's quote check, before any worktree or store write
    if "'" in str(value):
      raise core.HandoffError(f"{value} holds a quote and cannot go on the command line")
  gh, app = tool("gh"), builder_config["app"]
  if app:  # the App path: the scripts bake openssl and the key variable; the bin directory reaches the unquotable allow-list
    openssl = tool("openssl")
    key_path(app["private_key_env"])
    if re.search(r"\s", config["artifacts_dir"]):
      raise core.HandoffError(f"artifacts_dir {config['artifacts_dir']} holds whitespace")
  record = state["units"][unit]
  branch, number = handoff.branch(unit), record["number"]
  issue_body = filed_body(state, unit)
  launched_gh = str(st.path("launches", f"{unit}_r{rnd}_bin", "gh")) if app else gh  # the shim, or the real gh by absolute path
  tools = allowed_tools(builder_config["allowed_tools"], branch, issue_body, launched_gh)
  identity = (card.get("builder") or [None])[-1]
  if not identity and app:  # a re-typed wave relaunching while launch is held off: every reader derives the App login (spec section 11)
    identity = {"login": builder, "email": builder_email(builder)}  # `builder` is `app_login(config)`, `<slug>[bot]`, on this path
  if not identity:
    raise core.HandoffError("the wave card records no builder: run launch first")
  pr = (record.get("pr") or {}).get("number") if rnd >= 2 else None
  ref = "refs/superegm/base"  # the launch's ref: origin/<base> as `launch` fetched it, the PR tip from round 2
  if pr:
    ref = f"refs/superegm/pr/{pr}"
    core.run_git(["fetch", "--no-write-fetch-head", st.config["remote"], f"+refs/pull/{pr}/head:{ref}"], handoff.repo_root)
  elif rnd >= 2:  # no PR yet (decision point 3's `relaunch`): the retained local branch is the tree the builder gets
    ref = f"refs/heads/{branch}"
  pr_block = pr_block_text(handoff.repo_root, ref, config["pr_block_file"]) if config["pr_block_file"] else None
  # The launch's tree, before any worktree: an orient or spec-range refusal is an ordinary precondition.
  orient_text = core.read_text(orient.orient_unit(st, handoff.repo_root, ref, unit))
  range_text = spec_range_text(handoff.repo_root, st, issue_body, "refs/superegm/base")
  comments = core.gh_pages(f"repos/{repo}/issues/{number}/comments")
  reviews = core.gh_pages(f"repos/{repo}/pulls/{pr}/reviews") if pr else []
  audit = AUDIT_LINE.format(owner=record["launched"].get("by", "unknown"),  # a pre-upgrade mark records no login
                            runcard=args.runcard, unit=unit, handoff=st.handoff_id)
  text = prompt_text(number, unit, issue_body, orders_text(tools, launched_gh, builder_config["max_subagent_calls"]), orient_text, comments, reviews, pr, builder, audit, pr_block,
                     spec_range=range_text, owners=config.get("owners") or [], foreman=core.load_foreman(st, unit))
  worktree = add_worktree(handoff.repo_root, st, unit, rnd, branch, pr)
  prompt = st.path("launches", f"{unit}_r{rnd}_prompt.md")
  core.atomic_write(prompt, text)
  if app:
    write_bin(st, unit, rnd, config, openssl, gh)
  managed = managed_plugins(Path(config["builder"]["profile_dir"]).expanduser() / "plugins")
  core.atomic_write(mcp_file, json.dumps({"mcpServers": builder_config["mcp"]}, indent=2) + "\n")
  core.atomic_write(st.path("launches", f"{unit}_r{rnd}_plugins.json"),
                    json.dumps({"plugins": dirs, "managed": managed, "mcp": sorted(builder_config["mcp"])}, indent=2) + "\n")
  core.journal(st, f"{unit} launch {rnd} prepared" + (f" (managed plugins: {', '.join(managed)})" if managed else ""))
  result = st.path("launches", f"{unit}_r{rnd}_result.json")
  session_id = str(uuid.uuid4())  # the session's transcript `projects/<slug>/<id>.jsonl`, read at the exit (U27)
  line = command_line(config, worktree, prompt, result, args.runcard, tools, launched_gh, identity["login"], identity["email"],
                      [d["dir"] for d in dirs], mcp_file, session_id=session_id)
  # the one behaviour (amendment 10): the wrapper started detached, then the launch recorded `running`
  pid = start_detached(["/bin/sh", "-c", line], st.path("launches", f"{unit}_r{rnd}.log"), dict(os.environ))
  launches = load_launches(st, unit)
  launches.append({"round": rnd, "worktree": str(worktree), "branch": branch, "started_at": core.now_iso(), "status": "running",
                   "model": builder_config["model"], "effort": builder_config["effort"],  # the requested pair (U28)
                   "result_file": str(result), "prompt_sha256": core.sha256_file(prompt), "boot_id": core.boot_id(), "pid": pid, "command": line, "session_id": session_id})
  core.atomic_write(st.path("launches", unit), {"launches": launches})
  done = f"{unit} launch {rnd} running (pid {pid})"
  core.journal(st, done)
  print(done)
  return 0


SKILL_RULE_RE = re.compile(r"^Skill\(([^\s()]+)(?: \*)?\)$")  # `Skill(<name>)` or `Skill(<name> *)` (amendment 7)


def skill_names(tools: list) -> list[str]:
  """The skills an allow-list's `Skill(...)` rules name, once each, in the list's order."""
  names = []
  for entry in tools:
    match = SKILL_RULE_RE.match(entry)
    if match and match.group(1) not in names:
      names.append(match.group(1))
  return names


SUBAGENTS_RE = re.compile(r"(?:\n<!-- subagents(?: Agent)?: [^\n]* -->)+\n")  # the two delegation lines (amendment 15)


def orders_text(tools: list, gh: str, cap: int) -> str:
  """`references/builder_orders.md` as one launch reads it: `{{gh}}` the launched `gh`, `{{skills}}` the skills
  the allow-list names, `none` when it names none, and `{{subagents}}` the sentence of the `<!-- subagents Agent: -->`
  line, `{{cap}}` filled, when the list carries `Agent`, else that of the `<!-- subagents: -->` line; both lines removed."""
  text = core.read_text(ORDERS)
  marker = "<!-- subagents Agent: " if "Agent" in tools else "<!-- subagents: "
  line = next(l for l in text.splitlines() if l.startswith(marker))
  sentence = line[len(marker):].removesuffix(" -->").replace("{{cap}}", str(cap))
  text = SUBAGENTS_RE.sub("", text, count=1).replace("{{subagents}}", sentence)
  return text.replace("{{gh}}", gh).replace("{{skills}}", ", ".join(skill_names(tools)) or "none")


def start_detached(command: list, log: Path, env: dict) -> int:
  """Start `command` in its own session and process group (`start_new_session=True`, never `setsid(1)`, which macOS
  lacks), stdin from /dev/null, stdout and stderr into `log`, and return its pid at once: the caller's pipe is not
  held for the launch's hours, and the session that called it may end while the launch runs (spec section 11.2)."""
  log = Path(log)
  log.parent.mkdir(parents=True, exist_ok=True)
  with open(os.devnull, "rb") as stdin, open(log, "ab") as out:
    process = subprocess.Popen(command, stdin=stdin, stdout=out, stderr=subprocess.STDOUT, env=env, start_new_session=True, close_fds=True)
  process.returncode = 0  # never waited here: the detached wrapper outlives this helper and writes its own exit file
  return process.pid


def write_bin(store, unit: str, rnd: int, config: dict, openssl: str, gh: str) -> Path:
  """`launches/<unit>_r<n>_bin/` (spec section 11): `superegm-token` (a fresh App token on stdout, its one
  protocol: `superegm builder-token` through this helper's own python3 and plugin root with the repo, app
  id and key variable baked in) and the `gh` shim (`GH_TOKEN` from the mint, then the real `gh` by the
  absolute path baked in; a failing or empty mint exits 1 and execs nothing; the credential helper's
  `store` and `erase` pass the sentinel through). Each 0o700. Returns the shim's path."""
  app, folder = config["builder"]["app"], store.path("launches", f"{unit}_r{rnd}_bin")
  helper, shim = folder / "superegm-token", folder / "gh"
  for value in (sys.executable, HELPER, config["repo"], app["private_key_env"], openssl, gh, helper):
    if "'" in str(value):
      raise core.HandoffError(f"{value} holds a quote and cannot go in a launched script")
  q = lambda value: f"'{value}'"
  core.atomic_write(helper, "#!/bin/sh\n# written by superegm launch-builder: a fresh token of the builder App on stdout, nothing else\n"
                    f"exec {q(sys.executable)} {q(HELPER)} builder-token --repo {q(config['repo'])} --app-id {app['app_id']} "
                    f"--key-env {q(app['private_key_env'])} --openssl {q(openssl)}\n")
  core.atomic_write(shim, "#!/bin/sh\n# written by superegm launch-builder: gh as the builder App, a fresh token per call; store and erase pass the sentinel\n"
                    f'case "$1 $2 $3" in\n  "auth git-credential store"|"auth git-credential erase") exec {q(gh)} "$@" ;;\nesac\n'
                    f'token=$({q(helper)}) || exit 1\n[ -n "$token" ] || exit 1\nGH_TOKEN="$token" exec {q(gh)} "$@"\n')
  helper.chmod(0o700)
  shim.chmod(0o700)
  return shim


def refusal(store, state, config, unit, rnd, builder):
  """The first precondition of spec section 11 this launch fails, or None; evaluated before any
  git or file write."""
  record = (state.get("units") or {}).get(unit) or {}
  if not record.get("launched"):
    return f"{unit} is not marked by launch"
  core.reboot_launches(store, unit, core.boot_id())  # the boot-id proof: a launch a reboot ended is terminal (spec section 11.2)
  launches = load_launches(store, unit)
  for entry in launches:
    if not terminal(entry):
      return f"{unit} launch {entry['round']} is not terminal"
  if rnd != len(launches) + 1:
    return f"--round {rnd} is not the next launch count ({len(launches) + 1})"
  problem = profile_problem(Path(config["builder"]["profile_dir"]).expanduser(), config["builder"]["plugins"])
  if problem:
    return problem
  issue = core.gh_json(["api", f"repos/{config['repo']}/issues/{record['number']}"]) or {}
  if body.normalise(filed_body(state, unit)) != body.normalise(issue.get("body") or ""):
    return f"issue #{record['number']} body differs from the filed body"
  return None


def installed_entries(plugins):
  """`installed_plugins.json`'s entries as `{name: [scope, ...]}`; `None` when the file is unreadable."""
  installed = plugins / "installed_plugins.json"
  if not installed.is_file():
    return {}
  try:
    data = json.loads(installed.read_text(encoding="utf-8"))
  except ValueError:
    return None
  entries = data.get("plugins") if isinstance(data, dict) else None
  return {name: [e.get("scope") for e in (records or []) if isinstance(e, dict)] for name, records in (entries or {}).items()} if isinstance(entries, dict) else None


def managed_plugins(plugins):
  """The plugins the organization's policy installs into every profile of the account (`scope: managed`): policy,
  not the owner's plugins; each launch records them (owner ruling 2026-11-06)."""
  entries = installed_entries(plugins) or {}
  return sorted(name for name, scopes in entries.items() if scopes and all(s == "managed" for s in scopes))


def plugins_held(plugins):
  """Claude Code writes `installed_plugins.json`, `known_marketplaces.json`, clones of its default marketplaces
  under `marketplaces/` (catalogs, not plugins), its own `store/`, and the organization's managed plugins with
  their copies under `cache/` into a profile on every start, and `syncClaudeAiPlugins: false` leaves `.trash/`:
  none of those is the owner's plugin. One is an `installed_plugins.json` entry of any scope but `managed`, or a
  `synced/<bucket>/<name>` directory (the account's plugins, synced on sign-in unless the profile's settings set
  `syncClaudeAiPlugins` false)."""
  if not plugins.is_dir():
    return False
  entries = installed_entries(plugins)
  if entries is None or any(name not in managed_plugins(plugins) for name in entries):
    return True
  synced = plugins / "synced"
  return synced.is_dir() and any(
      bucket.is_dir() and not bucket.name.startswith(".") and any(p.is_dir() and not p.name.startswith(".") for p in bucket.iterdir())
      for bucket in synced.iterdir())


def elephant_profile() -> Path:
  """The elephant's own Claude Code profile: `CLAUDE_CONFIG_DIR` when set, else `~/.claude`."""
  configured = os.environ.get("CLAUDE_CONFIG_DIR")
  return Path(configured).expanduser() if configured else Path.home() / ".claude"


def hook_events(plugin_dir: Path) -> list:
  """The sorted union of the `hooks` keys of the plugin's `hooks/hooks.json` (Claude Code loads it by default) and of
  the hook files its manifest names besides (a path or a list of paths relative to its directory, or an inline
  object); an absent or non-JSON file is ignored."""
  def load(path):
    try:
      data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
      return None
    return data
  manifest = load(plugin_dir / ".claude-plugin/plugin.json")
  named = manifest.get("hooks") if isinstance(manifest, dict) else None
  named = named if isinstance(named, list) else [named] if named else []
  events = set()
  for item in ["./hooks/hooks.json", *named]:
    data = item if isinstance(item, dict) else load(plugin_dir / item) if isinstance(item, str) else None
    hooks = data.get("hooks") if isinstance(data, dict) else None
    if isinstance(hooks, dict):
      events.update(hooks)
  return sorted(events)


def plugin_dirs(plugins: list, profile_dir: Path) -> list[dict]:
  """One `{id, version, dir, hooks}` per listed plugin id, in order, from the first `scope: user` entry of
  `<profile_dir>/plugins/installed_plugins.json` (enabled there or not; spec section 11.1); `dir` is its
  `installPath`, `hooks` its hook events. A listed id with no `user` entry is refused; `[]` reads no file."""
  if not plugins:
    return []
  try:
    data = json.loads((Path(profile_dir) / "plugins/installed_plugins.json").read_text(encoding="utf-8"))
  except (OSError, ValueError):
    data = {}
  entries = data.get("plugins") if isinstance(data, dict) else None
  entries = entries if isinstance(entries, dict) else {}
  found = []
  for pid in plugins:
    user = next((e for e in entries.get(pid) or [] if isinstance(e, dict) and e.get("scope") == "user" and isinstance(e.get("installPath"), str)), None)
    if user is None:
      raise core.HandoffError(f"plugin {pid} not installed")
    found.append({"id": pid, "version": user.get("version"), "dir": user["installPath"], "hooks": hook_events(Path(user["installPath"]))})
  return found


def profile_problem(profile_dir: Path, plugins=(), elephant: Path | None = None) -> str | None:
  """Spec sections 4 and 11: the builder profile exists, holds no CLAUDE.md, no plugins (`plugins_held`), no
  hooks (a `settings.json` with a `hooks` key), no `skills/` or `commands/` directory, and a `settings.json` with
  `disableClaudeAiConnectors` exactly true (amendment 7); each listed plugin id has a `user` entry in the elephant
  profile (`elephant`, else `elephant_profile()`) and is not among the builder profile's managed plugins."""
  problem = landed_problem(profile_dir)
  if problem:
    return problem
  for folder in ("skills", "commands"):
    if (profile_dir / folder).is_dir():
      return f"builder profile {profile_dir} holds {folder}/"
  try:
    data = json.loads((profile_dir / "settings.json").read_text(encoding="utf-8"))
  except (OSError, ValueError):
    data = None
  if not isinstance(data, dict) or data.get("disableClaudeAiConnectors") is not True:
    return f"builder profile {profile_dir} lacks disableClaudeAiConnectors"
  managed = managed_plugins(profile_dir / "plugins") if plugins else []
  for pid in plugins:
    try:
      plugin_dirs([pid], elephant or elephant_profile())
    except core.HandoffError as error:
      return str(error)
    if pid in managed:
      return f"plugin {pid} managed in the builder profile"
  return None


def landed_problem(profile_dir):
  """The checks before amendment 7: the profile exists and holds no CLAUDE.md, plugins or hooks."""
  plugins, settings = profile_dir / "plugins", profile_dir / "settings.json"
  if not profile_dir.is_dir():
    return f"builder profile {profile_dir} does not exist"
  if (profile_dir / "CLAUDE.md").exists():
    return f"builder profile {profile_dir} holds CLAUDE.md"
  if plugins_held(plugins):
    return f"builder profile {profile_dir} holds plugins"
  if settings.is_file():
    try:
      data = json.loads(settings.read_text(encoding="utf-8"))
    except ValueError:  # not JSON: no hooks key to find
      data = None
    if isinstance(data, dict) and "hooks" in data:
      return f"builder profile {profile_dir} holds hooks"
  return None


def pr_block_text(repo_root, ref, path):
  """`config.pr_block_file`'s bytes at the launch's ref, verbatim (spec section 11); absent, the launch is refused."""
  with core.hook_free() as pairs:
    result = subprocess.run(["git", *pairs, "cat-file", "-p", f"{ref}:{path}"], cwd=str(repo_root), capture_output=True)
  if result.returncode:
    raise core.HandoffError(f"pr_block_file {path} is absent at {ref}")
  return result.stdout.decode("utf-8")


def allowed_tools(configured, branch, body_text, gh):
  """The configured allow-list with its `gh` prefixes rewritten to `gh`'s absolute path (a bare `gh …`
  is refused, so no PATH order is assumed), plus a push prefix for the unit's own branch and
  `Bash(<first word>:*)` for the first word of every `&&`/`;` segment of every command the body runs (U25's D1 (a));
  a bare `Skill` and unrestricted Bash are refused; `Agent` passes, the owner's opt-in (amendment 15, U27)."""
  for entry in ("Skill", "Bash", "Bash(*)"):
    if entry in configured:
      raise core.HandoffError(f"allowed_tools carries {entry}: a builder invokes no skill bare, never runs unrestricted Bash")
  tools = [f"Bash({gh} {t[8:]}" if t.startswith("Bash(gh ") else t for t in configured] + [f"Bash(git push origin {branch}:*)"]
  for command in body.run_commands(body_text):
    for first in segment_heads(command):
      if f"Bash({first}:*)" not in tools:
        tools.append(f"Bash({first}:*)")
  return tools


def segment_heads(command: str) -> list:
  """The first word of every `&&`/`;` segment of `command`, split as the shell splits it (a `;` or `&&` inside
  quotes or after a backslash separates nothing, a quoted `;` argument included); a line the shell grammar cannot
  split (an unclosed quote) gives its first word alone."""
  segments, start, quote, i = [], 0, None, 0
  while i < len(command):
    ch = command[i]
    if quote:
      if ch == quote:
        quote = None
      elif ch == "\\" and quote == '"':
        i += 1
    elif ch == "\\":
      i += 1
    elif ch in "'\"":
      quote = ch
    elif ch == ";" or command.startswith("&&", i):
      segments.append(command[start:i])
      i += 1 if ch == ";" else 2
      start = i
      continue
    i += 1
  if quote:
    return command.split()[:1]
  heads = []
  for segment in segments + [command[start:]]:
    try:
      words = shlex.split(segment)
    except ValueError:
      return command.split()[:1]
    heads += words[:1]
  return heads


def spec_range_text(repo_root: Path, store, body_text: str, ref: str) -> str:
  """The spec range the body cites (spec section 7): its `Spec:` line's `start..end` read at the commit
  holding the bytes the marker's sha256 names, through `core.spec_blob`: first searched from each history
  entry carrying that sha (the first commit of `git log <entry commit> -- <rel>` holding those bytes, which
  may be an earlier commit than the entry's own; the bytes are the same), else from `<ref>`; no such
  commit refuses."""
  marker, match = body.MARKER_RE.match(body_text), SPEC_LINE_RE.search(body_text)
  if not marker or not match:
    raise core.HandoffError("spec range: the body carries no marker or no `Spec:` range")
  sha, rel, start, end = marker.group(3), match.group(1), int(match.group(2)), int(match.group(3))
  text = None
  for entry in core.load_approvals(store, Path(rel)):
    if entry.get("sha256") == sha and entry.get("commit"):
      text = core.spec_blob(repo_root, rel, sha, ref=entry["commit"])
      if text is not None:
        break
  if text is None:
    text = core.spec_blob(repo_root, rel, sha, ref=ref)
  if text is None:
    raise core.HandoffError(f"spec range: no commit holds {sha[:7]}")
  return "\n".join(text.splitlines()[start - 1:end]) + "\n"


def filed_body(state, unit):
  """The body the filing that created the unit's issue stores, with its numbers filled (spec section 7)."""
  filed = next(w[4] for f in state.get("filings") or [] for w in f["writes"] if w[0] == "issue" and w[1] == unit)
  numbers = {uid: r["number"] for uid, r in state["units"].items() if r.get("number")}
  return body.fill_numbers(filed, numbers, (state.get("tracking") or {}).get("number"))


def prompt_text(issue_number, unit, body, orders, orient, comments, reviews, pr, builder, audit, pr_block=None, spec_range=None,
                owners=(), foreman=None):
  """Exactly what spec section 3's anti-goal 3 allows: the issue body, the audit-trail line, the orders, the repository's
  PR block when `pr_block_file` is set, the unit's orient file, the frozen spec range the body cites, every Deviation
  comment, every Decision comment by a `config.owners` login, every Ruling comment by one in a form the one grammar
  reads (`parse_form`; the judges' post under the elephant's token kept, a typo or a stranger's dropped, one the
  unit's record overrides dropped, and a recorded one edited after its record, whatever the edit, shown as its
  record: `overridden_comments` of `foreman`; a recorded one deleted shown as its record in its place:
  `deleted_rulings`), and from round 2 the foreman's reviews on the PR."""
  overridden = overridden_comments(comments, list(owners), foreman or {})

  def keep(c):
    if overridden.get(c["id"]) is not None:  # the record stands in for its comment's edit
      return True
    if not PROMPT_COMMENT_RE.match(c["body"]) or c["id"] in overridden:
      return False
    if c["body"].startswith("**Deviation"):
      return True
    return c["user"]["login"] in owners and (not c["body"].startswith("**Ruling:**") or parse_form(c["body"]) is not None
                                             or overridden.get(c["id"]) is not None)
  # an edited recorded ruling is shown as its record (spec section 13.2: a later comment never changes it)
  kept = [c | {"body": overridden[c["id"]]} if overridden.get(c["id"]) else c for c in comments if keep(c)]
  for gone in deleted_rulings(comments, foreman or {}):  # in its place among the comments, by id
    kept.insert(next((i for i, c in enumerate(kept) if int(c["id"]) > gone["id"]), len(kept)), gone)
  parts = [f"# Issue #{issue_number} — {unit}\n\n{body}", f"# Audit trail\n\n{audit}", f"# Builder orders\n\n{orders}"]
  if pr_block is not None:
    parts.append(f"# PR block\n\n{pr_block}")
  parts.append(f"# Orient\n\n{orient}")
  if spec_range is not None:
    parts.append(f"# Spec range\n\n{spec_range}")
  parts.append(f"# Comments on issue #{issue_number}\n\n" + "\n".join(f"## {c['user']['login']} · comment {c['id']}\n{c['body']}\n" for c in kept))
  if pr:
    kept = [r for r in reviews if r.get("body") and r["user"]["login"] != builder]
    parts.append(f"# Review comments on PR #{pr}\n\n" + "\n".join(
        f"## {r['user']['login']} · review {r['id']} on {r['commit_id'][:7]}\n{r['body']}\n" for r in kept))
  return "\n\n---\n\n".join(parts)


def add_worktree(repo_root, store, unit, rnd, branch, pr):
  """A fresh worktree for the launch on the unit's branch: round 1 from `refs/superegm/base`,
  later rounds at the PR tip (`refs/superegm/pr/<n>`, fetched by `prepare`) or, with no PR yet
  (decision point 3's `relaunch` after an exit without one), at the retained local branch, after
  detaching the earlier launches' worktrees (nothing in them is removed; that is `clean`'s).
  A re-run after a failure before the spawn (U32): an `r<n>` already on the branch refuses before any
  switch (a builder may run there); a detached one is switched to the branch, no `worktree add`, the
  branch moved first to where a fresh launch would start it (round 1 `refs/superegm/base`, later the PR tip)."""
  path = store.path("worktrees", unit, f"r{rnd}")
  path.parent.mkdir(parents=True, exist_ok=True)
  reuse = path.is_dir() and path.resolve() in core.registered_worktrees(repo_root)
  if reuse and core.run_git(["branch", "--show-current"], path).strip() == branch:
    raise core.HandoffError(f"worktree {path} is on {branch}: detach it by hand once no builder runs there")
  if rnd == 1 and not reuse:
    core.run_git(["worktree", "add", "-b", branch, str(path), "refs/superegm/base"], repo_root)
    return path
  for earlier in core.registered_worktrees(repo_root):
    if earlier.is_relative_to(path.parent.resolve()) and earlier.is_dir() and earlier != path.resolve():
      core.run_git(["switch", "--detach"], earlier)
  core.run_git(["worktree", "prune"], repo_root, check=False)
  if rnd == 1:
    core.run_git(["branch", "-f", branch, "refs/superegm/base"], repo_root)
  elif pr:
    core.run_git(["branch", "-f", branch, f"refs/superegm/pr/{pr}"], repo_root)
  if reuse:
    core.run_git(["switch", branch], path)
  else:
    core.run_git(["worktree", "add", str(path), branch], repo_root)
  return path


def launched_pairs(gh: str, name: str, email: str) -> list:
  """The launched environment's git pairs (spec section 11): the owner's global and system configuration
  shut out, every SSH transport failing closed, no prompt, and the `GIT_CONFIG_KEY_n` entries: the helper
  reset then `gh` by absolute path as `gh auth setup-git` writes it, the HTTPS `insteadOf` rewrites (which,
  unlike `pushInsteadOf`, reach an explicit `remote.<name>.pushurl`), no askPass, the commit identity.
  No git config file is written."""
  entries = [("credential.https://github.com.helper", ""), ("credential.https://github.com.helper", f"!{gh} auth git-credential"),
             ("url.https://github.com/.insteadOf", "git@github.com:"), ("url.https://github.com/.insteadOf", "ssh://git@github.com/"),
             ("core.askPass", ""), ("user.name", name), ("user.email", email)]
  pairs = [("GIT_CONFIG_GLOBAL", "/dev/null"), ("GIT_CONFIG_SYSTEM", "/dev/null"), ("GIT_SSH_COMMAND", "false"),
           ("GIT_TERMINAL_PROMPT", "0"), ("GIT_CONFIG_COUNT", str(len(entries)))]
  for i, (key, value) in enumerate(entries):
    pairs += [(f"GIT_CONFIG_KEY_{i}", key), (f"GIT_CONFIG_VALUE_{i}", value)]
  return pairs


def command_line(config, worktree, prompt, result, runcard, tools, gh, login, email, plugin_dirs: list, mcp_file: Path,
                 session_id: str | None = None) -> str:
  """The launched command (spec section 11): the owner's prompts and token and `CLAUDE_CODE_EFFORT_LEVEL`
  (which would beat `--effort`, U28) unset, the builder profile,
  `ENABLE_CLAUDEAI_MCP_SERVERS=false` (belt and braces over the profile's `disableClaudeAiConnectors`),
  `GH_TOKEN` as the shell variable expands (never its value) or, on the App path, the sentinel the shim
  overrides, the role and card, the launched git pairs (`gh`, the shim on the App path, as the credential
  helper by absolute path; the identity `login` and `email` from the wave card), `claude -p` on the prompt
  file (with `--session-id` when given), `--model` and `--effort` from `builder` (U28), with `--setting-sources user` (the builder sits in the target repository,
  whose project settings and SessionStart hooks it must not run: the profile's settings alone), one `--plugin-dir`
  per listed plugin's directory, `--mcp-config <mcp_file> --strict-mcp-config` (no other MCP configuration loads),
  the result and exit files; prefixed by the watchdog's trap (U31): TERM writes `stalled` to the exit file and ends
  the wrapper, no code written after it."""
  b = config["builder"]
  pairs = launched_pairs(gh, login, email)
  for value in (worktree, prompt, result, b["profile_dir"], b["model"], b["effort"], b["permission_mode"], runcard, *tools, *(v for _, v in pairs),
                *plugin_dirs, mcp_file, session_id or ""):
    if "'" in str(value):
      raise core.HandoffError(f"{value} holds a quote and cannot go on the command line")
  token = f"GH_TOKEN={SENTINEL}" if b["app"] else f"GH_TOKEN=\"${b['gh_token_env']}\""
  unset, env = " ".join(f"-u {k}" for k in UNSET), " ".join(f"{k}='{v}'" for k, v in pairs)
  session = f" --session-id '{session_id}'" if session_id else ""
  dirs = "".join(f"--plugin-dir '{d}' " for d in plugin_dirs)
  return (f"SUPEREGM_EXIT='{result}.exit'; trap 'echo stalled > \"$SUPEREGM_EXIT\"; exit' TERM; "
          f"cd '{worktree}' && env {unset} CLAUDE_CONFIG_DIR='{b['profile_dir']}' ENABLE_CLAUDEAI_MCP_SERVERS=false {token} "
          f"SUPEREGM_ROLE=builder SUPEREGM_RUNCARD='{runcard}' {env} "
          f"claude -p \"$(cat '{prompt}')\"{session} --model '{b['model']}' --effort '{b['effort']}' --permission-mode '{b['permission_mode']}' --setting-sources user "
          f"{dirs}--mcp-config '{mcp_file}' --strict-mcp-config "
          f"--allowedTools '{','.join(tools)}' --output-format json > '{result}'; echo $? > '{result}.exit'")
