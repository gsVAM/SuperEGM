# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U39's tests: the triage section's parse, its refusals, the frozen `triage` field and the skills that offer and check the section.

"""U39: the triage section of a spec (spec section 5.1)."""

import pytest
from superegm import approve_spec


@pytest.mark.parametrize("text, patterns", [
  ("# S\n\n## Triage\n\nUnblock:\n- reach: forged, later: easy\n- critical: no, later: easy, verified: confirmed\n\n## Units\n",
   [{"reach": "forged", "later": "easy"}, {"critical": "no", "later": "easy", "verified": "confirmed"}]),
  ("# S\n\n```markdown\n## Triage\nUnblock:\n- reach: agent\n```\n\n## Triage\n\nUnblock:\n- verified: refuted\nprose\n- reach: config\n\n## Units\n",
   [{"verified": "refuted"}]),
  ("# S\n\n## Other\n\n## Triage\n\nUnblock:\n- reach: agent\n\n## Units\n", None),
  ("# S\n\n## Units\n", None),
])
def test_triage_section_parses_the_unblock_run(text, patterns):
  """The first unfenced H2 exactly `Triage`; one `Unblock:` line and the run of `- ` lines after it."""
  assert approve_spec.triage_patterns(text) == patterns
