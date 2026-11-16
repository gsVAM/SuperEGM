# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the builder-setup subcommand (spec section 3.3, U59).

"""superegm builder-setup: create the builder profile with its two settings, copy the owner's named MCP servers into
`builder.mcp`, add the rules they and `--allow` need to `builder.allowed_tools`. It writes the profile and the working
tree's config, never the store, and takes no run card."""

import json
import os
import re
from pathlib import Path

import superegm as core
from superegm import launch_builder
from superegm.launch_builder import profile_problem

WRITES = frozenset()  # the profile and the config are outside the store
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
WHOLE_REFERENCE = re.compile(r"\$\{[A-Za-z_][A-Za-z0-9_]*\}")  # `${VAR}` and nothing else
SETTINGS = {"syncClaudeAiPlugins": False, "disableClaudeAiConnectors": True}


def register(subparsers):
  p = core.add_parser(subparsers, "builder-setup", "create the builder profile; copy MCP servers and Bash prefixes into the config",
                      runcard=False)
  p.add_argument("--mcp", action="append", default=[], metavar="NAME",
                 help="copy the owner's MCP server NAME into builder.mcp and allow mcp__NAME__*")
  p.add_argument("--allow", action="append", default=[], metavar="PREFIX",
                 help="allow the Bash command prefix PREFIX to a builder (Bash(PREFIX:*))")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  root = core.git_toplevel(Path.cwd())
  config = core.load_config(root)
  builder = config["builder"]
  profile_dir = Path(builder["profile_dir"])
  settings = profile_settings(profile_dir)  # every refusal is raised before the first write
  servers, allowed, lines = dict(builder["mcp"]), list(builder["allowed_tools"]), []
  for name in dict.fromkeys(args.mcp):
    if name not in servers:
      servers[name] = owner_server(root, name)
      lines.append(f"builder.mcp: added {name}")
    rule = f"mcp__{name}__*"
    if rule not in allowed:
      allowed.append(rule)
      lines.append(f"builder.allowed_tools: added {rule}")
  for prefix in dict.fromkeys(args.allow):
    if not prefix.strip() or prefix.strip() == "*":
      raise core.HandoffError(f"--allow {prefix!r} names no command prefix")
    rule = f"Bash({prefix}:*)"
    if rule not in allowed:
      allowed.append(rule)
      lines.append(f"builder.allowed_tools: added {rule}")
  launch_builder.allowed_tools(allowed, "unit", "", "gh")  # the launch's own check of the list, raised before the first write
  config_path = root / ".superegm" / "config.json"
  if lines and not config_path.is_file():
    raise core.HandoffError(f"{config_path} is absent: run superegm init first")
  if any(settings.get(key) is not value for key, value in SETTINGS.items()):
    core.atomic_write(profile_dir / "settings.json", {**settings, **SETTINGS})
    lines.insert(0, f"wrote {profile_dir / 'settings.json'}: syncClaudeAiPlugins false, disableClaudeAiConnectors true")
  if servers != builder["mcp"] or allowed != builder["allowed_tools"]:
    held = json.loads(core.read_text(config_path))
    held["builder"] = {**held.get("builder", {}), "mcp": servers, "allowed_tools": allowed}
    core.atomic_write(config_path, held)
  for line in lines:
    print(line)
  print("then run superegm doctor --probe")
  return 0


def read_servers(path: Path, *scopes) -> dict:
  """The `mcpServers` object under `scopes` (keys to descend through) in the JSON file `path`; an absent or malformed file,
  or anything not an object on the way, is no servers."""
  try:
    data = json.loads(core.read_text(path))
  except (OSError, ValueError):
    return {}
  for key in scopes:
    data = data.get(key) if isinstance(data, dict) else None
  servers = data.get("mcpServers") if isinstance(data, dict) else None
  return servers if isinstance(servers, dict) else {}


def owner_server(root: Path, name: str) -> dict:
  """The owner's entry for MCP server `name`: `.claude.json` under CLAUDE_CONFIG_DIR, else `~/.claude.json` (the repository's
  local scope, then the user scope), else the repository's `.mcp.json`; a name in none is refused."""
  folder = os.environ.get("CLAUDE_CONFIG_DIR")
  owner = Path(folder) / ".claude.json" if folder else Path.home() / ".claude.json"
  for servers in (read_servers(owner, "projects", str(root)), read_servers(owner), read_servers(root / ".mcp.json")):
    if isinstance(servers.get(name), dict):
      return checked_entry(name, servers[name])
  raise core.HandoffError(f"MCP server {name} is in no local or user scope of {owner} and not in {root / '.mcp.json'}")


def profile_settings(profile_dir: Path) -> dict:
  """The profile's `settings.json` object (empty when the profile or the file is absent); a profile `profile_problem`
  refuses for anything but the two settings, or a `settings.json` that is not a JSON object, is refused."""
  problem = profile_problem(profile_dir)
  if problem and problem not in (f"builder profile {profile_dir} does not exist",
                                 f"builder profile {profile_dir} lacks disableClaudeAiConnectors"):
    raise core.HandoffError(problem)
  path = profile_dir / "settings.json"
  if not path.is_file():
    return {}
  try:
    data = json.loads(core.read_text(path))
  except (OSError, ValueError):
    data = None
  if not isinstance(data, dict):
    raise core.HandoffError(f"builder profile {profile_dir} settings.json is not a JSON object")
  return data


def checked_entry(name: str, entry: dict) -> dict:
  """`entry` when every value under its `env` and `headers` is a whole `${VAR}` reference; else refused naming the key (a literal
  secret would be committed with the config)."""
  for field in ("env", "headers"):
    values = entry.get(field)
    if values is None:
      continue
    if not isinstance(values, dict):
      raise core.HandoffError(f"MCP server {name} {field} is not an object")
    for key, value in values.items():
      if not (isinstance(value, str) and WHOLE_REFERENCE.fullmatch(value)):
        raise core.HandoffError(f"MCP server {name} {field} {key} is not a whole ${{VAR}} reference; keep secrets out of the config")
  return entry
