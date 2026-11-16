# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the builder-setup subcommand (spec section 3.3, U59).

"""superegm builder-setup: create the builder profile with its two settings, copy the owner's named MCP servers into
`builder.mcp`, add the rules they and `--allow` need to `builder.allowed_tools`. It writes the profile and the working
tree's config, never the store, and takes no run card."""

import json
from pathlib import Path

import superegm as core
from superegm.launch_builder import profile_problem

WRITES = frozenset()  # the profile and the config are outside the store
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no config key, init line or doctor line of its own (U32)
SETTINGS = {"syncClaudeAiPlugins": False, "disableClaudeAiConnectors": True}


def register(subparsers):
  p = core.add_parser(subparsers, "builder-setup", "create the builder profile; copy MCP servers and Bash prefixes into the config",
                      runcard=False)
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  root = core.git_toplevel(Path.cwd())
  config = core.load_config(root)
  profile_dir = Path(config["builder"]["profile_dir"])
  settings = profile_settings(profile_dir)  # every refusal is raised before the first write
  lines = []
  if any(settings.get(key) is not value for key, value in SETTINGS.items()):
    core.atomic_write(profile_dir / "settings.json", {**settings, **SETTINGS})
    lines.append(f"wrote {profile_dir / 'settings.json'}: syncClaudeAiPlugins false, disableClaudeAiConnectors true")
  for line in lines:
    print(line)
  return 0


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
