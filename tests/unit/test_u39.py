# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U39's tests: the triage section's parse, its refusals, the frozen `triage` field and the skills that offer and check the section.

"""U39: the triage section of a spec (spec section 5.1)."""

import json
import pytest
from test_review import SPEC, SLUG, converged_spec, approve, git, hstore
from superegm import approve_spec


def with_section(section):
  """SPEC with `## Triage`, a blank line and `section` before its first H2."""
  return SPEC.replace("## 1. Intent", "## Triage\n\n" + section + "\n## 1. Intent", 1)


def entries_of(world):
  """The approval entries written so far: none before the first approval."""
  path = hstore(world).path("approvals", SLUG)
  return json.loads(path.read_text(encoding="utf-8"))["entries"] if path.is_file() else []


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


@pytest.mark.parametrize("section, line", [
  ("Unblock:\n- reach: remote\n", "- reach: remote"),
  ("Unblock:\n- speed: easy\n", "- speed: easy"),
  ("Unblock:\n- reach: agent, reach: config\n", "- reach: agent, reach: config"),
  ("Unblock:\n- \n", "- "),
  ("Unblock:\n- verified: confirmed src/x.py:3\n", "- verified: confirmed src/x.py:3"),
  ("Unblock:\n- later: easy\nUnblock:\n- critical: no\n", "Unblock:"),
  ("prose only\n", "## Triage"),
  ("Unblock:\n\nprose\n", "Unblock:"),
])
def test_malformed_triage_section_is_refused_with_its_line(world, section, line):
  """One refusal names the line at fault; nothing is committed and no entry is written."""
  spec, cid, rid = converged_spec(world, text=with_section(section))
  commits_before, entries_before = git(world, "rev-list", "--count", "HEAD"), entries_of(world)
  code, err = approve(world, spec, cid, "--yes")
  assert code == 1 and err.removeprefix("superegm: ").startswith(f"approve-spec: {line}: "), err
  assert git(world, "rev-list", "--count", "HEAD") == commits_before and entries_of(world) == entries_before
