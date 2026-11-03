# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's tests moved here from test_helper.py (U03).

"""EGM's tests of the subcommands U05 (plan) changes, moved from test_helper.py by U03;
that unit rewrites the ones whose form it changes."""

import json
import re

import pytest

from conftest import REPO, set_config, applied, unit_path


def test_graph_unknown_reference_cycle_and_contradiction(world):
  text = world.plan.read_text(encoding="utf-8")
  world.plan.write_text(text.replace("| Blocked by | U02 |", "| Blocked by | U09 |"), encoding="utf-8")
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 1 and "unknown unit U09" in out
  world.plan.write_text(text.replace("| Blocked by | none |", "| Blocked by | U03 |"), encoding="utf-8")
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 1 and "blocked-by cycle" in out and "U01" in out and "U03" in out
  contradiction = text.replace("| Shared files | `src/webhooks/queue.ts`: before U02 |",
                               "| Shared files | `src/webhooks/queue.ts`: after U02 |")
  world.plan.write_text(contradiction, encoding="utf-8")
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 1 and "shared-file chain contradicts the blockers" in out


def test_graph_writes_waves_critical_path_placeholders_and_id(world):
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 0, out
  units = json.loads((world.artifacts / "handoff_units.json").read_text(encoding="utf-8"))
  assert units["waves"] == {"1": ["U01"], "2": ["U02"], "3": ["U03"]}
  assert units["critical_path"] == ["U01", "U02", "U03"]
  assert re.fullmatch(r"sample-[0-9a-f]{6}", units["handoff_id"])
  bodies = (world.artifacts / "handoff_bodies.md").read_text(encoding="utf-8")
  assert "**Blocked by.** #<U01>" in bodies and "after #<U01>, before U03 (Admin endpoint)" in bodies
  assert "Part of #<tracking>. Wave 2." in bodies
  unit = unit_path(world, "U02").read_text(encoding="utf-8")
  assert unit.startswith("### U02: Delivery worker") and "#<U01>" in unit
  plan = world.plan.read_text(encoding="utf-8")
  assert "<!-- egm:generated start -->" in plan and "| U01 | U02 | shared file `src/webhooks/queue.ts`; blocked by |" in plan
  assert "- U03/D2 Page size for the listing?" in plan
  # Regenerating is idempotent: the plan text does not change.
  assert world.run("graph", "--plan", world.plan)[0] == 0
  assert world.plan.read_text(encoding="utf-8") == plan


def test_scan_banned_terms_mentions_and_size(world):
  ns = world.ns
  config = {"banned_terms": ["(?i)secret-codename"], "fix_request_mention": "@copilot"}
  # The scan is not code-aware (0.2.1): a banned term inside a code span is
  # still refused, and the author rewords.
  assert any("banned term" in p for p in ns["scan_text"]("plain `secret-codename` in code", config, "body"))
  assert any("banned term" in p for p in ns["scan_text"]("the secret-codename leaks", config, "body"))
  assert any("bare mention" in p for p in ns["scan_text"]("ask @alice please", config, "body"))
  assert ns["scan_text"]("email a@b.example only", config, "body") == []
  assert any("bare mention" in p for p in ns["scan_text"]("email a@b.example and `@alice`", config, "body"))
  assert ns["scan_text"]("@copilot\n**EGM review round 1**", config, "comment") == []
  assert any("bare mention" in p for p in ns["scan_text"]("hello\n@copilot", config, "comment"))
  assert any("bare mention" in p for p in ns["scan_text"]("@copilot first", config, "body"))
  big = "é" * 40_000
  assert any("exceeds 65000" in p for p in ns["scan_text"](big, config, "body"))
  assert any("merge marker" in p for p in ns["scan_text"]("a\n<<<<<<< HEAD\nb", config, "body"))
  assert any("missing from the body" in p for p in ns["scan_text"]("x", config, "body", dod=["`npm test`"]))


def test_scan_command_over_rendered_bodies(world):
  text = world.plan.read_text(encoding="utf-8").replace("retries failed jobs.", "retries jobs; see secret-codename.")
  world.plan.write_text(text, encoding="utf-8")
  code, out = world.run("scan", "--plan", world.plan)
  assert code == 1 and "banned term" in out and "U02" in out
  world.plan.write_text(world.plan.read_text(encoding="utf-8").replace("; see secret-codename.", "."), encoding="utf-8")
  code, out = world.run("scan", "--plan", world.plan)
  assert code == 0 and "scan: clean" in out


def test_the_posted_body_never_changes_when_a_decision_is_answered(world):
  """R09: decide re-rendered the body verify compares against, so answering a
  question reported a mismatch and blocked the wave."""
  applied(world)
  assert world.run("verify", "--plan", world.plan)[0] == 0
  assert world.run("decide", "--plan", world.plan, "--unit", "U03",
                   "--decision", "D2", "--answer", "50")[0] == 0
  code, out = world.run("verify", "--plan", world.plan)
  assert code == 0 and "MISMATCH" not in out, out
  unit_file = unit_path(world, "U03").read_text(encoding="utf-8")
  assert "Decisions answered since the issue was posted" in unit_file
  assert "Decision: 50" in unit_file


def test_scan_is_not_code_aware(world):
  """Seven review rounds each found a defect in a Markdown-aware scanner; it
  could both hide a mention behind a fence shape it misread and refuse an
  ordinary comment. The code-awareness was deleted. Every line is scanned as
  written, fences and spans included."""
  scan = world.ns["scan_text"]
  config = {"banned_terms": ["(?i)secret-codename"], "fix_request_mention": None,
            "allowed_mentions": []}
  for body in ("```\n@alice secret-codename\n```\n",
               "`@alice` and `secret-codename`\n",
               "- ```\n  safe\n  ```\n\n@alice secret-codename\n```\n",
               "<div></div>\n```\n\n@alice secret-codename\n\n```\n",
               "    ```\n\n@alice secret-codename\n\n    ```\n"):
    problems = scan(body, config, "comment")
    assert any("bare mention @alice" in p for p in problems), (body, problems)
    assert any("banned term" in p for p in problems), (body, problems)
  assert "strip_code" not in world.ns and "FENCE_RE" not in world.ns


def test_an_ordinary_body_with_a_fence_and_no_mention_passes(world):
  scan = world.ns["scan_text"]
  config = {"banned_terms": ["(?i)secret-codename"], "fix_request_mention": None,
            "allowed_mentions": []}
  assert scan("Do this:\n\n```sh\nnpm test\n```\n\nThen ship.\n", config, "body") == []
  assert scan("```diff\n- ```sh\n+ ```bash\n```\n", config, "comment") == []


def test_allowed_mentions_are_explicit_and_validated(world):
  scan = world.ns["scan_text"]
  config = {"banned_terms": [], "fix_request_mention": None,
            "allowed_mentions": ["@types/node"]}
  assert scan("import from @types/node\n", config, "body") == []
  problems = scan("ping @alice and @types/node\n", config, "body")
  assert [p for p in problems if "@alice" in p] and not [p for p in problems if "@types" in p]
  assert any("allowed_mentions" in p for p in problems), problems
  # R8-01: the allowlist is exact-literal over the whole token GitHub resolves.
  # `@acme` must not cover the team `@acme/release`, and `@types` must not
  # cover `@types/node`.
  team = {"banned_terms": [], "fix_request_mention": None, "allowed_mentions": ["@acme"]}
  assert any("@acme/release" in p for p in scan("@acme/release please look\n", team, "body"))
  bare = {"banned_terms": [], "fix_request_mention": None, "allowed_mentions": ["@types"]}
  assert any("@types/node" in p for p in scan("uses @types/node\n", bare, "body"))
  # the config refuses anything that is not an @name (the card is opened while it still loads)
  world.card("plan")
  set_config(world, repo=REPO, allowed_mentions=["types"])
  code, out = world.run("graph", "--plan", world.plan)
  assert code == 1 and "allowed_mentions must be a list of `@name` strings" in out


def test_fix_request_mention_still_passes_only_on_a_comment_first_line(world):
  scan = world.ns["scan_text"]
  config = {"banned_terms": [], "fix_request_mention": "@devin", "allowed_mentions": []}
  assert scan("@devin please fix\n", config, "comment") == []
  assert scan("note\n@devin please fix\n", config, "comment") != []
  assert scan("@devin please fix\n", config, "body") != []
