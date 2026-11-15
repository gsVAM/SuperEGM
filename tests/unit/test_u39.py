# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U39's tests: the triage section's parse, its refusals, the frozen `triage` field and the skills that offer and check the section.

"""U39: the triage section of a spec (spec section 5.1)."""

import json
from pathlib import Path
import pytest
from conftest import make_pr
from test_review import SPEC, SLUG, card, converged_spec, approve, git, hstore, rjson
from test_u26 import THREADS, reader
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


@pytest.mark.parametrize("spec, frozen", [
  ("with the example section", [{"reach": "forged", "later": "easy"}, {"critical": "no", "later": "easy", "verified": "confirmed"}]),
  ("without a section", None),
])
def test_approval_entry_freezes_the_patterns(world, spec, frozen):
  """The entry carries `triage`; `--amend-units` copies it from the entry it extends."""
  section = "Unblock:\n- reach: forged, later: easy\n- critical: no, later: easy, verified: confirmed\n"
  path, cid, rid = converged_spec(world, text=with_section(section) if frozen else SPEC)
  code, out = approve(world, path, cid, "--yes")
  assert code == 0, out
  entry = entries_of(world)[-1]
  icid = card(world, path, "integrate")
  path.write_text(path.read_text(encoding="utf-8") + "| U02 | more | U01 | S |\n", encoding="utf-8")
  code, out = approve(world, path, icid, "--amend-units")
  assert code == 0, out
  amended_entry = entries_of(world)[-1]
  assert amended_entry["kind"] == "amend-units"
  assert entry["triage"] == frozen and amended_entry["triage"] == frozen
  assert "triage" in approve_spec.FROZEN_FIELDS


@pytest.mark.parametrize("path, phrases", [
  ("skills/brainstorming/SKILL.md", ["## Triage", "Unblock:", "reach", "later", "critical", "verified"]),
  ("agents/structural.md", ["## Triage", "Unblock:"]),
  ("agents/design.md", ["## Triage", "safe"]),
])
def test_skills_offer_and_check_the_section(path, phrases):
  """Brainstorming offers and writes the section; structural checks the grammar; design judges the patterns' safety."""
  text = (Path(__file__).resolve().parents[2] / path).read_text(encoding="utf-8")
  assert all(p in text for p in phrases), [p for p in phrases if p not in text]


def test_malformed_triage_section_reads_no_pr_thread(world, monkeypatch):
  """The refusal comes before the spec PR's ingest: no thread is read, no round or journal line is written."""
  seen = reader(monkeypatch, threads=THREADS[1:])
  make_pr(world.gh, 7, "c" * 40, branch="main")
  spec, cid, rid = converged_spec(world, text=with_section("Unblock:\n- reach: remote\n"))
  journal = hstore(world).path("journal")
  rounds_before, journal_before = rjson(world, rid, "round-1.json"), journal.read_text(encoding="utf-8") if journal.is_file() else None
  code, err = approve(world, spec, cid, "--yes")
  assert code == 1 and err.removeprefix("superegm: ").startswith("approve-spec: - reach: remote: "), err
  assert seen == [] and rjson(world, rid, "round-1.json") == rounds_before and rjson(world, rid)["ingested"] == []
  assert (journal.read_text(encoding="utf-8") if journal.is_file() else None) == journal_before


@pytest.mark.parametrize("section, line", [
  ("Unblock:\n- reach\n", "- reach"),
  ("Unblock:\n- reach:forged\n", "- reach:forged"),
  ("Unblock:\n- reach: agent, later\n", "- reach: agent, later"),
])
def test_a_pair_that_is_no_field_value_is_refused_with_its_line(section, line):
  """A pair without `: ` names its line at fault."""
  with pytest.raises(approve_spec.core.HandoffError) as error:
    approve_spec.triage_patterns("# S\n\n## Triage\n\n" + section + "\n## Units\n")
  assert str(error.value).startswith(f"approve-spec: {line}: ")


@pytest.mark.parametrize("section, patterns", [
  ("```\nUnblock:\n- reach: remote\n```\nUnblock:\n- reach: agent\n", [{"reach": "agent"}]),
  ("Unblock:\n- reach: agent\n```\n- reach: remote\n```\n- later: easy\n", [{"reach": "agent"}]),
  ("Unblock:\n- reach: agent\n~~~\n## Other\n~~~\n", [{"reach": "agent"}]),
])
def test_a_fenced_block_inside_the_section_is_prose(section, patterns):
  """A fenced `Unblock:` is ignored, and a fence ends the run; a fenced H2 does not end the section."""
  assert approve_spec.triage_patterns("# S\n\n## Triage\n\n" + section + "\n## Units\n") == patterns
