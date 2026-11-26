# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U112's tests (1.3 design section 3.10, doctor): no --allow hint for a command runner.

"""U112 (spec section 3.10, Doctor): a denied call of `git subtree`, `git rebase`, `git submodule`, `git bisect`,
`gh alias set` or `gh extension` (and its aliases) gets the runner reason, never an `--allow` hint."""

import json
import pytest
from superegm.doctor import probe_lines


@pytest.mark.parametrize("command, name", [
    ("git subtree push --prefix docs origin gh-pages", "git subtree"),
    ("git rebase --exec 'make test' main", "git rebase"),
    ("git rebase main", "git rebase"),
    ("git submodule foreach 'git pull'", "git submodule"),
    ("git submodule update --init", "git submodule"),
    ("git bisect run pytest", "git bisect"),
    ("git bisect start", "git bisect"),
    ("gh alias set --shell co 'echo hi'", "gh alias set"),
    ("gh alias set co 'pr checkout'", "gh alias set"),
    ("gh extension install owner/gh-ext", "gh extension"),
    ("gh ext install owner/gh-ext", "gh ext"),
    ("gh extensions list", "gh extensions"),
])
def test_probe_offers_no_allow_for_a_command_runner(command, name):
  assert runner_line(command) == (f"denied Bash {command} ({name}: runs commands or pushes, no --allow)", False)


def test_runner_reason_survives_an_unparseable_quote():
  # astra-1-1: shlex rejects bash's ANSI-C quoting, yet the subcommand comes right after git: still the runner reason
  command = "git rebase --exec $'echo \\'ok\\'' main"
  assert runner_line(command) == (f"denied Bash {command} (git rebase: runs commands or pushes, no --allow)", False)


def runner_line(command):
  result_event = json.dumps({"type": "result", "permission_denials": [
      {"tool_name": "Bash", "tool_input": {"command": command}}]})
  [(line, ok)] = probe_lines(result_event, "/p")
  return line, ok
