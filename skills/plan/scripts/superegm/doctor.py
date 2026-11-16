# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the doctor subcommand (spec section 11); the App lines and the launched environment (U15); the informational `astra:` line (U17); the informational `merge:` line (U19); the informational `python3.12`, `hooks` and `core.hooksPath` lines (U25); the five informational driver lines (U24); the informational `plugins` and `mcp` lines and the profile line's plugin refusals (U27); the informational `model:` role table (U28); the informational `stall:` line (U31); the modules' DOCTOR_CHECKS lines after its own (U32); the three `model: builder <tier>` lines (U33); `chain` in INFORMATIONAL (U54); `--probe`, one headless builder session on the launch's own flags (U60).

"""superegm doctor: one line per wave prerequisite, `ok` or the refusal `launch` or `launch-builder`
would give; read-only, no run card."""

import json
import os
import re
import shlex
import shutil
import subprocess
import tempfile
from pathlib import Path

import superegm as core
from superegm import instructions
from superegm.builder_token import app_lines, key_path, tool
from superegm.judges import judge_members
from superegm.launch import app_login, builder_login, origin_problems, protection_problems
from superegm.launch_builder import (SENTINEL, UNSET, allowed_tools, builder_flags, elephant_profile, launched_pairs, plugin_dirs,
                                     profile_problem)

WRITES = frozenset()  # doctor writes nothing
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # its own lines are `checks`' (U32)
INFORMATIONAL = ("graphify", "scanning", "astra", "merge", "python3.12", "hooks", "core.hooksPath", "driver", "sleep", "root", "env",
                 "notify", "plugins", "mcp", "model", "stall", "chain")  # lines that never fail the exit
MERGE = ("gh pr merge --admin (informational: the owner merges with the admin bypass where the base ruleset "
         "restricts updates to config.owners)")


def register(subparsers):
  p = core.add_parser(subparsers, "doctor", "print every wave prerequisite as ok or the refusal launch would give",
                      runcard=False)
  p.add_argument("--probe", action="store_true", help="then run one headless builder session on the launch's own flags")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  repo_root = core.git_toplevel(Path.cwd())
  try:
    config = core.load_config(repo_root)
  except core.HandoffError as error:
    print(f"config: {error}")
    return 1
  lines = [("config", "ok"), *checks(config, repo_root, os.environ.get(config["builder"]["gh_token_env"]))]
  for name, text in lines:
    print(f"{name}: {text}")
  passed = all(text.startswith("ok") for name, text in lines if name not in INFORMATIONAL)
  if getattr(args, "probe", False):
    passed = probe(config, repo_root) and passed
  return 0 if passed else 1


PROBE_TAIL = ["--output-format", "stream-json", "--verbose", "--max-turns", "5"]
PROBE_CLOSING = "Do only what these instructions ask at the start of a session, then reply ok."


def probe(config, repo_root: Path) -> bool:
  """Spec 1.2.1 section 3.3: one headless builder session in a fresh temporary directory, on `builder_flags` (the
  launch's own: profile, setting sources, plugin directories, the MCP file from `builder.mcp`, the unset names, the
  allow-list, permission mode, `builder.model` and `builder.effort`) plus `PROBE_TAIL`; no token, issue or worktree.
  Prints the `probe:` lines and returns True when none fails. Writes nothing to the store; the directory is removed."""
  b = config["builder"]
  temp = Path(tempfile.mkdtemp(prefix="superegm-probe-"))
  try:
    try:
      dirs = [d["dir"] for d in plugin_dirs(b["plugins"], elephant_profile())]
      # HEAD's builder-addressed instruction text (U37's renderer); a throwaway store in the temp dir takes any copy it writes
      text = instructions.render(core.Store(temp / "store"), "builder", None, repo_root)[1].strip()
      gh = shutil.which("gh") or "gh"
      tools = [t for t in allowed_tools(b["allowed_tools"], "superegm/probe", "", gh) if not t.startswith("Bash(git push ")]
    except core.HandoffError as error:
      print(f"probe: session {error}")
      return False
    prompt = f"{text}\n\n{PROBE_CLOSING}" if text else "Reply ok."
    mcp_file = temp / "probe-mcp.json"
    mcp_file.write_text(json.dumps({"mcpServers": b["mcp"]}, indent=2) + "\n", encoding="utf-8")
    env_words, args = builder_flags(config, tools, dirs, mcp_file, (b["model"], b["effort"]))
    # no token (spec 1.2.1 section 3.3): the launch's no-token sentinel, never the owner's GH_TOKEN or gh login
    done = subprocess.run(["env", *env_words, "claude", "-p", prompt, *args, *PROBE_TAIL], cwd=temp,
                          env={**os.environ, "GH_TOKEN": SENTINEL}, stdin=subprocess.DEVNULL, capture_output=True, text=True)
    lines = probe_lines(done.stdout, b["profile_dir"])
    for text, _ in lines:
      print(f"probe: {text}")
    if any(text.startswith("mcp ") and text.split()[2] == "needs-auth" for text, _ in lines):
      shutil.copyfile(mcp_file, Path(b["profile_dir"]) / "probe-mcp.json")  # the one-time auth step's file outlives the temp dir
    if done.returncode:
      reason = first_line(done.stderr) or result_text(done.stdout)
      print(f"probe: session exit {done.returncode}" + (f": {reason}" if reason else ""))
    else:
      print("probe: session ok")
    return not done.returncode and all(ok for _, ok in lines)
  finally:
    shutil.rmtree(temp, ignore_errors=True)


def probe_lines(stdout: str, profile: str) -> list[tuple[str, bool]]:
  """The probe's lines from the session's stream-json events, each with whether it passes: `mcp <name> <status>`
  per server of the init event (`connected` passes; `needs-auth` names the one-time auth step), `tool <name> ok` or
  `tool <name> error: <first line>` per tool result, `denied <tool> <input> (--allow <prefix>)` per entry of the
  result's `permission_denials` (each fails)."""
  lines, names = [], {}
  for raw in stdout.splitlines():
    try:
      event = json.loads(raw)
    except ValueError:
      continue
    if not isinstance(event, dict):
      continue
    kind = event.get("type")
    if kind == "system" and event.get("subtype") == "init":
      for server in event.get("mcp_servers") or []:
        name, status = server.get("name"), server.get("status")
        text = f"mcp {name} {status}"
        if status == "needs-auth":
          text += (f" (once: CLAUDE_CONFIG_DIR={profile} claude --mcp-config {profile}/probe-mcp.json --strict-mcp-config, "
                   "then /mcp and Authenticate)")
        lines.append((text, status == "connected"))
    elif kind in ("assistant", "user"):
      content = (event.get("message") or {}).get("content")
      for block in content if isinstance(content, list) else []:
        if not isinstance(block, dict):
          continue
        if block.get("type") == "tool_use":
          names[block.get("id")] = block.get("name")
        elif block.get("type") == "tool_result":
          name = names.get(block.get("tool_use_id"), block.get("tool_use_id"))
          if block.get("is_error"):
            lines.append((f"tool {name} error: {first_line(block.get('content'))}", False))
          else:
            lines.append((f"tool {name} ok", True))
    elif kind == "result":
      for denial in event.get("permission_denials") or []:
        tool_name, tool_input = denial.get("tool_name"), denial.get("tool_input") or {}
        if tool_name == "Bash" and isinstance(tool_input.get("command"), str):
          command = first_line(tool_input["command"])
          allow = " ".join(f"--allow {shlex.quote(p)}" for p in dict.fromkeys(allow_prefixes(tool_input["command"])))
          lines.append((f"denied Bash {command} ({allow})", False))
        else:
          lines.append((f"denied {tool_name} {json.dumps(tool_input, sort_keys=True)}", False))
  return lines


SEPARATORS = (";", "&&", "||", "|", "&")


def allow_prefixes(command: str) -> list:
  """The `--allow` prefix for every `;`, `&&`, `||`, `|` and `&` segment of a denied command: its first word, but for
  git and gh (by bare name or path) as narrow as the allow-list's own entries, `git <subcommand>` and `gh <group>
  <command>` (`gh api`), so the hint never admits every git or gh subcommand; one whose subcommand follows an option
  is named whole. An unsplittable line gives its first word."""
  try:
    lexer = shlex.shlex(command, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    tokens = list(lexer)
  except ValueError:
    return command.split()[:1]
  segments, current = [], []
  for token in tokens:
    if token in SEPARATORS:
      segments.append(current)
      current = []
    else:
      current.append(token)
  prefixes = []
  for words in segments + [current]:
    if not words:
      continue
    name = os.path.basename(words[0])
    depth = {"git": 1, "gh": 1 if words[1:2] == ["api"] else 2}.get(name, 0)
    sub = words[1:1 + depth]
    if not depth:
      prefixes.append(words[0])
    elif len(sub) == depth and not any(w.startswith("-") for w in sub):
      prefixes.append(" ".join([name, *sub]))
    else:
      prefixes.append(" ".join(words))
  return prefixes


def result_text(stdout: str) -> str:
  """The first line of the result event's `result` text, or empty."""
  for raw in stdout.splitlines():
    try:
      event = json.loads(raw)
    except ValueError:
      continue
    if isinstance(event, dict) and event.get("type") == "result":
      return first_line(event.get("result"))
  return ""


def first_line(content) -> str:
  """The first line of a tool result's content: a string, or a list of blocks whose text is joined."""
  if isinstance(content, list):
    content = "\n".join(b.get("text", "") for b in content if isinstance(b, dict))
  return (str(content or "").strip().splitlines() or [""])[0]


def checks(config, repo_root, token):
  """The lines after `config`: `launch`'s and `launch-builder`'s own predicates, each line `ok…` or the
  refusal they would give (a check's HandoffError or GhError text is its line). On the machine-account
  path the order is owner, origin, token, builder, role, scopes, protection, merge, profile, plugins, mcp, gh,
  environment; the builder, role, scopes and protection lines need the token and are absent without it.
  On the App path: owner, origin, credential, key, openssl, artifacts_dir, app, permissions, token,
  installation, scanning, protection, merge, profile, plugins, mcp, gh, environment; the four App lines are
  absent after a failing key or openssl. The environment line is absent after a failing gh line;
  scanning and merge are informational and never fail, as are python3.12, hooks and core.hooksPath (U25)
  and plugins and mcp (U27, the profile line carrying a listed plugin's refusal), and stall, the watchdog's
  `builder.stall_minutes` after environment (U31).
  The five driver lines (driver, sleep, root, env, notify) follow, informational too, then the `model:`
  role table (U28), informational, then each module's DOCTOR_CHECKS lines in discovery order: foreman's
  astra and orient's graphify, informational (U32)."""
  repo, base, owners, team, app = config["repo"], config["base"], config["owners"], config["owner_team"], config["builder"]["app"]
  lines, found = [], {}

  def check(name, fn):
    try:
      text = fn()
    except (core.HandoffError, core.GhError) as error:
      text = str(error)
    lines.append((name, text))

  def owner():
    me = core.gh(["api", "user", "-q", ".login"]).strip()
    return f"ok ({me})" if me in owners else f"{me} is not in config.owners ({', '.join(owners)})"

  def origin():
    core.run_git(["fetch", "--no-write-fetch-head", config["remote"], f"+refs/heads/{base}:refs/superegm/base"], repo_root)
    problems = origin_problems(repo_root, base)
    return problems[0] if problems else "ok"

  def builder():
    found["login"] = builder_login(config, token)
    return f"ok ({found['login']})"

  def token_login():
    if "login" not in found:  # the builder check refused: the token's own login, read once
      found["login"] = core.gh(["api", "user", "-q", ".login"], token=token).strip()
    return found["login"]

  def role():
    name = (core.gh_json(["api", f"repos/{repo}/collaborators/{token_login()}/permission"]) or {}).get("role_name")
    return "ok (write)" if name == "write" else f"{token_login()}'s role on {repo} is {name}, not write"

  def scopes():
    head = re.split(r"\r?\n\r?\n", core.gh(["api", "-i", "user"], token=token), 1)[0]
    match = re.search(r"(?im)^x-oauth-scopes:[ \t]*(.*?)[ \t\r]*$", head)
    if not match:
      return "ok (fine-grained: permissions not probed)"
    names = [s.strip() for s in match.group(1).split(",") if s.strip()]
    listed = ", ".join(names)
    if "repo" not in names:
      return f"classic token lacks repo ({listed})"
    if "workflow" in names:
      return f"classic token carries workflow ({listed})"
    return f"ok (classic: {listed})"

  def protection():
    problems = protection_problems(repo, base, app_login(config) or token_login(), "superegm/x/U01", owners, team,
                                   app_id=app["app_id"] if app else None)
    return problems[0] if problems else "ok"

  def credential():
    builder_login(config, token)  # the both-set refusal
    return f"ok (app {app['slug']})"

  def key():
    found["key"] = key_path(app["private_key_env"])
    return f"ok ({found['key']})"

  def openssl():
    found["openssl"] = tool("openssl")
    return f"ok ({found['openssl']})"

  def artifacts_dir():
    return f"artifacts_dir {config['artifacts_dir']} holds whitespace" if re.search(r"\s", config["artifacts_dir"]) else "ok"

  def scanning():
    data = (core.gh_json(["api", f"repos/{repo}"]) or {}).get("security_and_analysis")
    if not data:
      return "not reported (informational)"
    status = lambda field: (data.get(field) or {}).get("status") or "not reported"
    return f"push protection {status('secret_scanning_push_protection')}, non-provider patterns {status('secret_scanning_non_provider_patterns')}"

  def gh():
    found["gh"] = tool("gh")
    return f"ok ({found['gh']})"

  def plugins():  # what each launch passes by `--plugin-dir` (U27): id, version and hook events, `; `-joined
    dirs = plugin_dirs(config["builder"]["plugins"], elephant_profile())
    return "; ".join(f"{d['id']} {d['version']} [{', '.join(d['hooks'])}]" for d in dirs) or "none"

  check("owner", owner)
  check("origin", origin)
  if app:
    for name, fn in (("credential", credential), ("key", key), ("openssl", openssl), ("artifacts_dir", artifacts_dir)):
      check(name, fn)
    if "key" in found and "openssl" in found:
      lines += app_lines(app, repo, found["key"], found["openssl"])
    check("scanning", scanning)
    check("protection", protection)
  elif not token:
    lines.append(("token", f"{config['builder']['gh_token_env']} is not set"))
  else:
    lines.append(("token", "ok"))
    for name, fn in (("builder", builder), ("role", role), ("scopes", scopes), ("protection", protection)):
      check(name, fn)
  lines.append(("merge", MERGE))
  check("profile", lambda: profile_problem(Path(config["builder"]["profile_dir"]).expanduser(), config["builder"]["plugins"]) or "ok")
  check("plugins", plugins)
  check("mcp", lambda: ", ".join(sorted(config["builder"]["mcp"])) or "none")
  check("gh", gh)
  if "gh" in found:
    check("environment", lambda: environment_problem(repo_root, found["gh"], bool(app)) or "ok")
  lines.append(("stall", f"{config['builder']['stall_minutes']} min"))  # the watchdog's bound (U31)
  python = shutil.which("python3.12")  # this repository's own prerequisite, not the gate's (U25)
  lines.append(("python3.12", f"ok ({python})" if python else "not on PATH (informational)"))
  hooks_path, hooks = hooks_of(repo_root)
  lines.append(("hooks", ", ".join(hooks) or "none"))
  lines.append(("core.hooksPath", hooks_path or "unset"))
  lines.extend(driver_lines(config))
  try:
    lines.extend(role_lines(config))
  except (KeyError, TypeError, AttributeError) as error:  # a malformed role key: informational, the other lines still print
    lines.append(("model", f"unreadable ({type(error).__name__}: {error})"))
  for module in core.discover().values():  # the modules' own lines, after doctor's, in discovery order (U32)
    if module.DOCTOR_CHECKS:
      lines.extend(module.DOCTOR_CHECKS(config, repo_root, token))
  return lines


def role_lines(config):
  """The role table (U28): one informational `model:` line per role, the configured model and effort; the
  builder's one line per tier, through `tier_pair` (U33)."""
  r, a = config["reviewers"], config["astra"]
  rows = [f"builder {tier} {' '.join(core.tier_pair(config, tier))}" for tier in core.TIERS]
  rows += [f"goldfish {r['model']} {r['effort']}",
          f"astra lanes {a['model']} {a['effort']}", f"astra head lane {a['model']} {a['heads_effort']}"]
  rows += [f"judge {jid} {m['model']} {m['effort']}" for jid, m in judge_members(config).items()]
  return [("model", row) for row in rows]


def hooks_of(repo_root: Path):
  """`core.hooksPath` as configured (None when unset) and the sorted hook names of its directory, else of
  `<git-common-dir>/hooks`, `.sample` files skipped. Read by a direct `subprocess.run`, never `run_git`, whose
  `hook_free()` pair would answer its own empty directory (U25)."""
  got = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=str(repo_root), capture_output=True, text=True)
  hooks_path = got.stdout.strip() or None
  if hooks_path:
    folder = repo_root / Path(hooks_path).expanduser()
  else:
    folder = repo_root / core.run_git(["rev-parse", "--git-common-dir"], repo_root).strip() / "hooks"
  names = sorted(p.name for p in folder.iterdir() if p.is_file() and not p.name.endswith(".sample")) if folder.is_dir() else []
  return hooks_path, names


def driver_lines(config):
  """The five informational lines of the owner's timer (spec section 11.2): `driver:`, `sleep:`, `root:`, `env:`
  and `notify:`."""
  from superegm import driver
  from superegm.launch_builder import HELPER
  lines, helper, mine = [], driver.plist_helper(), str(HELPER.parents[3])
  if helper is None:
    lines.append(("driver", "not installed"))
  elif helper != str(HELPER):
    lines.append(("driver", f"stale ({driver.helper_root(helper)}; the env profile's root {mine})"))
  else:
    lines.append(("driver", f"installed ({timer_minutes(driver)} min) at {mine}"))
  lines.append(("sleep", sleep_setting()))
  entries = registry_entries()
  entry = None if isinstance(entries, str) else next(
    (e for e in entries if Path(e["artifacts_dir"]).expanduser().resolve()
     == Path(config["artifacts_dir"]).expanduser().resolve()), None)
  if isinstance(entries, str):
    lines.append(("root", entries))
  elif entry is None:
    lines.append(("root", "not registered"))
  else:
    lines.append(("root", "ok" if driver.root_ok(entry["root"], entry["artifacts_dir"])
                  else f"{entry['root']} is not a worktree of {entry['repo']}"))
  lines.append(("env", env_setting(driver.env_file())))
  hook = Path.home() / ".superegm" / "notify"
  lines.append(("notify", f"ok ({core.sha256_file(hook)})" if hook.is_file() else "absent"))
  return lines


def timer_minutes(driver):
  """The installed interval: the plist's `StartInterval` or the timer's `OnUnitActiveSec`, in minutes."""
  import plistlib
  try:
    if driver.plist_path().is_file():
      return int(plistlib.loads(driver.plist_path().read_bytes()).get("StartInterval", 0)) // 60
    for line in core.read_text(driver.timer_path()).splitlines():
      if line.startswith("OnUnitActiveSec="):
        return int(line.split("=", 1)[1].strip().removesuffix("min"))
  except (OSError, ValueError, plistlib.InvalidFileException):
    pass
  return "?"


def sleep_setting():
  pmset = shutil.which("pmset")
  if not pmset:
    return "not reported"
  try:
    out = subprocess.run([pmset, "-g"], capture_output=True, text=True, timeout=10).stdout
  except (OSError, subprocess.SubprocessError):
    return "not reported"
  for line in out.splitlines():
    words = line.split(None, 1)
    if words and words[0] == "sleep":
      return words[1].strip() if len(words) > 1 else "not reported"
  return "not reported"


def registry_entries():
  """The registry's entries, or the error that refuses it (shown on the `root:` line, as `tick` would fail)."""
  try:
    return core.load_registry()
  except core.HandoffError as error:
    return str(error)


def env_setting(path: Path) -> str:
  if not path.is_file():
    return "absent"
  if path.stat().st_mode & 0o077:
    return "readable by others"
  keys = {line.split("=", 1)[0].strip() for line in core.read_text(path).splitlines() if "=" in line and not line.lstrip().startswith("#")}
  for key in ("PATH", "CLAUDE_CONFIG_DIR"):
    if key not in keys:
      return f"missing {key}"
  if not keys & {"SUPEREGM_APP_KEY", "SUPEREGM_BUILDER_TOKEN"}:
    return "missing SUPEREGM_APP_KEY or SUPEREGM_BUILDER_TOKEN"
  return "ok"


def environment_problem(repo_root: Path, gh: str, app: bool):
  """What the launched environment (spec section 11: the process environment minus `UNSET` plus
  `launched_pairs`, and the sentinel `GH_TOKEN` on the App path) would let through, or None: on the
  App path `<gh> auth token` prints the sentinel; `git credential fill` with the helper's slot replaced by
  `!false` answers nothing (the owner's askpass, global helper and keyring are shut out); origin's push
  URL is HTTPS (an SSH `pushInsteadOf` of the owner's is shut out)."""
  env = {k: v for k, v in os.environ.items() if k not in UNSET}
  env.update(launched_pairs(gh, "superegm", "superegm"))
  if app:
    env["GH_TOKEN"] = SENTINEL
    printed = subprocess.run([gh, "auth", "token"], capture_output=True, text=True, env=env).stdout.strip()
    if printed != SENTINEL:
      return f"gh auth token under the launched environment prints {printed}, not {SENTINEL}"
  helper = f"!{gh} auth git-credential"
  fill = subprocess.run(["git", "credential", "fill"], input="url=https://github.com\n\n", capture_output=True, text=True,
                        cwd=str(repo_root), env={k: "!false" if v == helper else v for k, v in env.items()})
  if fill.returncode == 0:
    return "git credential fill under the launched environment answered"
  url = subprocess.run(["git", "remote", "get-url", "--push", "origin"], capture_output=True, text=True,
                       cwd=str(repo_root), env=env).stdout.strip()
  if not url.startswith("https://"):
    return f"push URL of origin under the launched environment is {url}, not https://"
  return None
