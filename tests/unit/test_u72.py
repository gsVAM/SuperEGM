# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U72

"""U72 (spec 1.2.1 section 7.3): the inbox is a typed external skill that asks the owner in words and does the
rest; every ruling item's action points to the inbox, with its `**Ruling:**` forms and the URL it is posted on; a
review's cap or escalation points to that review's skill session; the machine steps stay typed commands."""

import runpy
from pathlib import Path

from conftest import ROOT

PACKER = runpy.run_path(str(ROOT / "scripts/pack_plugin.py"))
SKILL = ROOT / "skills/inbox/SKILL.md"


def test_the_inbox_is_a_typed_external_skill():
  # the house reader returns frontmatter values as strings
  fm = PACKER["read_frontmatter"](SKILL)
  assert (fm["effects"], fm["effect_kinds"], fm["disable-model-invocation"]) == ("external", "[github-write, state-store, start-session]", "true")
  assert "inbox" in PACKER["TYPED_SKILLS"]
