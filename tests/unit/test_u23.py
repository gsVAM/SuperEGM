# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U23, the inbox and the notify hook (spec §11.2).

"""U23: the `notify_timeout_seconds` key, the `inbox` module, the notify step and the bar prose, the inbox skill."""

import re

import pytest

import superegm
from conftest import REPO, ROOT, set_config
from superegm import init


@pytest.mark.parametrize("value, ok", [(30, True), (2.5, True), (0, False), (True, False), ("30", False)])
def test_notify_timeout_seconds_key_and_the_inbox_module(world, value, ok):
  assert superegm.DEFAULT_CONFIG["notify_timeout_seconds"] == 30 and "inbox" in superegm.SUBCOMMANDS and "~/.superegm/notify" in init.STEPS
  assert world.run("inbox", "--help")[0] == 0 and world.run("notify", "--help")[0] == 0
  set_config(world, repo=REPO, notify_timeout_seconds=value)
  if not ok:
    with pytest.raises(superegm.HandoffError, match=re.escape("notify_timeout_seconds must be a positive number")):
      superegm.load_config(world.repo)
    return
  assert superegm.load_config(world.repo)["notify_timeout_seconds"] == value


PROSE = [("skills/wave/SKILL.md", n) for n in ("notify --runcard '<CARD>'", "a failing or slow hook never stops the wave", "a pending decision whose panel answered is the owner's alone")] + [
         ("skills/judges/references/leavemealone.md", n) for n in ("needs a `high` finding behind it", "held until `decision rule` accepts")]


@pytest.mark.parametrize("path, needle", PROSE)
def test_the_notify_step_and_the_bar_prose(path, needle):
  assert needle in (ROOT / path).read_text(encoding="utf-8"), (path, needle)


def test_the_inbox_skill_is_auto_invokable_with_effects_none():
  text = (ROOT / "skills/inbox/SKILL.md").read_text(encoding="utf-8")
  assert "disable-model-invocation" not in text
  for needle in ("superegm inbox", "--all", "--json", "--handoff", "never notifies", "no run card", "Added by SuperEGM"):
    assert needle in text, needle


def test_a_non_finite_notify_timeout_is_refused(world):
  """Round 2 (astra-1-8): JSON's 1e309 loads as infinity, a timeout no hook run can be bounded by."""
  set_config(world, repo=REPO, notify_timeout_seconds=float("inf"))
  with pytest.raises(superegm.HandoffError, match=re.escape("notify_timeout_seconds must be a positive number")):
    superegm.load_config(world.repo)


@pytest.mark.parametrize("needle", ["`python3 '<HELPER>' report --runcard '<CARD>'`, then `python3 '<HELPER>' notify --runcard '<CARD>'`"])
def test_the_notify_call_follows_the_report_before_its_branches(needle):
  """Round 2 (codebase-details-1-2): notify runs right after `report`, before a pause or the end."""
  text = (ROOT / "skills/wave/SKILL.md").read_text(encoding="utf-8")
  assert needle in text and text.index(needle) < text.index("decision was opened this batch, pause")


@pytest.mark.parametrize("needle", ["`**Ruling:** (<comment id>) <option> — <reason>`", "(<a> | <b>)", "`/superegm:plan <spec>`",
                                    "`superegm review rule --review <id>", "`superegm review settle --review <id>",
                                    "`/superegm:wave <spec>`", "not yet listed"])
def test_the_inbox_skill_names_each_kinds_action(needle):
  """Round 2 (codebase-details-1-3, -1-4, -1-5): every action the module prints is named in the skill."""
  assert needle in (ROOT / "skills/inbox/SKILL.md").read_text(encoding="utf-8"), needle
