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
