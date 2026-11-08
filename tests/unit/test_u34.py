# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U34's tests: the team brainstorm (the brainstorm.team key, the cartographer, the teammates' briefs, the skill's team mode and the platform's agent-teams facts).

"""U34: the team brainstorm."""

import json, re
import pytest
from conftest import ROOT, REPO, set_config
from test_skeleton import frontmatter, FINDINGS_LINE, IDS
import superegm


@pytest.mark.parametrize("brainstorm, team, message", [
  ({"team": True}, True, None), ({}, False, None),
  ({"team": "yes"}, None, "brainstorm.team must be true or false"), ("on", None, "brainstorm must be an object")])
def test_brainstorm_team_key(world, brainstorm, team, message):
  assert superegm.DEFAULT_CONFIG["brainstorm"] == {"team": False}
  set_config(world, repo=REPO, brainstorm=brainstorm)
  if message:
    with pytest.raises(superegm.HandoffError, match=re.escape(message)):
      superegm.load_config(world.repo)
    return
  assert superegm.load_config(world.repo)["brainstorm"] == {"team": team}


def test_cartographer_adapter_and_persona():
  adapter, persona = ROOT / ".claude-plugin/agents/cartographer.md", ROOT / "agents/cartographer.md"
  meta = frontmatter(adapter)
  assert (meta["name"], meta["tools"], meta["model"], meta["omitClaudeMd"]) == ("cartographer", ["Read", "Grep", "Glob"], "inherit", True)
  assert "memory" not in meta
  text = adapter.read_text(encoding="utf-8")
  assert "${CLAUDE_PLUGIN_ROOT}/agents/cartographer.md" in text and "Added by SuperEGM (gsVAM), 2026:" in text and "no isolation" in text
  canonical = frontmatter(persona)
  assert canonical["name"] == "cartographer" and canonical["license"] == "Apache-2.0" and not {"tools", "omitClaudeMd"} & set(canonical)
  body = persona.read_text(encoding="utf-8")
  for needle in ("Added by SuperEGM (gsVAM), 2026:", "`orient/map.md`", "`superegm orient`", "where the topic's concerns live", "what calls what",
                 "what tests pin", "what the repository's own docs say", "surprise a newcomer", "by message", "no file"):
    assert needle in body, needle
  assert FINDINGS_LINE not in body and "regression:" not in body
  manifest = json.loads((ROOT / ".claude-plugin/plugin.json").read_text(encoding="utf-8"))
  assert "./.claude-plugin/agents/cartographer.md" in manifest["agents"] and IDS[-1] == "cartographer"


TEAMMATES = ROOT / "skills/brainstorming/references/teammates.md"
BRIEFS = [("The dispatch", n) for n in ("the topic", "the owner's words so far", "`Mode: BRAINSTORM`", "`superegm:cartographer`", "`superegm:design`",
                                        "`superegm:zoom-out`", "`superegm:comprehension`", "no target file to read", "no incomplete review to report",
                                        "not the findings line", "writes no file", "the cartographer's notes")] + [
         ("The message form", n) for n in ("approach:", "costs:", "questions:", "saw:", "notes:", "ask cartographer:", "its return")] + [
         ("Cartographer", n) for n in ("`orient/map.md`", "no `orient` call", "who calls X", "what covers Y", "the three things that would surprise a newcomer")] + [
         ("Architect", "designs against the notes"), ("Skeptic", "failure modes"), ("Skeptic", "what the owner will regret"),
         ("Skeptic", "the cheapest alternative"), ("Advocate", "what they see, type, wait for"), ("Advocate", "the operator's day")]


def test_teammates_reference_briefs():
  text = TEAMMATES.read_text(encoding="utf-8")
  assert text.startswith("<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.") and "Added by SuperEGM (gsVAM), 2026:" in text
  sections = dict(zip(re.findall(r"^## (.+)$", text, re.M), re.split(r"^## .+$", text, flags=re.M)[1:]))
  assert list(sections) == ["The dispatch", "The message form", "Cartographer", "Architect", "Skeptic", "Advocate"]
  for section, needle in BRIEFS:
    assert needle in sections[section], (section, needle)
  assert not re.search(r"Blocker|Major|Nit", text)
