# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U41's tests: the triage goldfish (spec section 5.2): its adapter, its persona and the foreman brief's Step 3b.

"""U41: the triage goldfish."""

import json
import pytest
from conftest import ROOT
from test_skeleton import frontmatter


def text_of(path):
  return (ROOT / path).read_text(encoding="utf-8")


def test_triage_adapter_is_zero_context_and_read_only():
  # a goldfish: no project context, read-only tools, the persona by plugin path, the docs/specs/ ban
  meta = frontmatter(ROOT / ".claude-plugin/agents/triage.md")
  adapter = text_of(".claude-plugin/agents/triage.md")
  manifest = json.loads(text_of(".claude-plugin/plugin.json"))
  assert (meta["name"], set(meta["tools"]), meta["omitClaudeMd"]) == ("triage", {"Read", "Grep", "Glob"}, True)
  assert "${CLAUDE_PLUGIN_ROOT}/agents/triage.md" in adapter and "docs/specs/" in adapter
  assert "./.claude-plugin/agents/triage.md" in manifest["agents"]


@pytest.mark.parametrize("path, phrase", [
    ("agents/triage.md", "docs/specs/"),
    ("agents/triage.md", "external | agent | config | forged"),
    ("agents/triage.md", "easy | migration | version"),
    ("agents/triage.md", "yes | no"),
    ("agents/triage.md", "<fid> | reach: <v> | later: <v> | critical: <v> | verified: confirmed <file:line>"),
    ("agents/triage.md", "verified: refuted <reason>"),
    ("agents/triage.md", "nothing else"),
    ("agents/triage.md", "at the head"),
    ("skills/wave/references/foreman_brief.md", "Step 3b, triage"),
    ("skills/wave/references/foreman_brief.md", "superegm review triage --review <id> --round <n> --eligible"),
    ("skills/wave/references/foreman_brief.md", "prints nothing"),
    ("skills/wave/references/foreman_brief.md", "superegm:triage"),
    ("skills/wave/references/foreman_brief.md", "never the patterns"),
    ("skills/wave/references/foreman_brief.md", "the head reviewers' model and effort"),
    ("skills/wave/references/foreman_brief.md", "--file <path> --isolation"),
    ("skills/wave/references/foreman_brief.md", "once more"),
    ("skills/wave/references/foreman_brief.md", "those mediums blocking"),
    ("agents/foreman.md", "never write or edit a triage value"),
])
def test_triage_texts_name_the_rules(path, phrase):
  # persona: four fields from the code at the head, one line per fid; brief: Step 3b between collect and post
  assert phrase in text_of(path)


@pytest.mark.parametrize("path, phrase", [
    ("agents/triage.md", "exactly one `<path>:<line>`"),
    ("agents/triage.md", "a single line number, never a range"),
    ("agents/triage.md", "only `refuted` takes free text"),
    ("skills/wave/references/foreman_brief.md", "except the `--file` call of Step 3b"),
])
def test_triage_round_3_rules(path, phrase):
  # round 2: `confirmed` takes a bare path:line (the helper fullmatches it); Step 3b's --file refusals are not Step 5 errors
  assert phrase in text_of(path)
