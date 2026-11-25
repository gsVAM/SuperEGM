# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U105's tests, spec §3.8 "Respec": a respec reaches every unit it touches.

"""U105: prose under `## Units` touches every unfiled or unmerged unit, Units-table lines are exempt from the quoted-line
and range rules, Interfaces names are read as `scan.names_of` reads them, a respec cycle's ingest reads its scope alone,
and `approve-spec --respec` runs after the approving worktree is removed."""

import json

import pytest

import superegm as core
from test_u85 import BASE, BODIES, HID, SECTIONS, design_range, replace, respec_world

UNITS_AT = BASE.index("## 5. Units\n")
UNITS = BASE[:UNITS_AT] + [
  "## 5. Units\n", "\n", "Every unit logs its retries.\n", "\n",
  "| Unit | Scope | Blocked by | Size |\n", "| --- | --- | --- | --- |\n",
  "| U0 | old | — | S |\n", "| U1 | queue | — | S |\n", "| U2 | deliver | — | S |\n", "| U3 | admin | — | S |\n"]
PROSE, U1_ROW = "Every unit logs its retries.", "| U1 | queue | — | S |"


def ranges(**over):
  """Each unit's Design range, its section's in `UNITS`, or `## 5. Units` for the units named in `over`."""
  return {u: {"id": u, "design_range": design_range(UNITS, "## 5. Units" if over.get(u) else h)} for u, h in SECTIONS.items()}


UNITS_CASES = {
  "a prose line under `## Units`, outside the table": ({}, {}, lambda: replace(UNITS, PROSE, "Every unit logs each retry.")),
  "a prose line under `## Units` that U2's Design range covers and U3's body quotes":
    ({"U2": True}, {"U3": PROSE}, lambda: replace(UNITS, PROSE, "Every unit logs each retry.")),
  "a prose line under `## Units` that merged U0's Design range covers":
    ({"U0": True}, {}, lambda: replace(UNITS, PROSE, "Every unit logs each retry.")),
  "U1's row of the Units table, which U2's body quotes word for word":
    ({}, {"U2": U1_ROW}, lambda: replace(UNITS, U1_ROW, "| U1 | queue, fifo | — | S |")),
  "U1's row of the Units table, with U3's Design range covering the spec's Units table":
    ({"U3": True}, {}, lambda: replace(UNITS, U1_ROW, "| U1 | queue, fifo | — | S |")),
}


@pytest.mark.parametrize("change, touched, merged_review", [
  ("a prose line under `## Units`, outside the table", ["U1", "U2", "U3"], ["U0"]),
  ("a prose line under `## Units` that U2's Design range covers and U3's body quotes", ["U1", "U2", "U3"], ["U0"]),
  ("a prose line under `## Units` that merged U0's Design range covers", ["U0", "U1", "U2", "U3"], []),
  ("U1's row of the Units table, which U2's body quotes word for word", ["U1"], []),
  ("U1's row of the Units table, with U3's Design range covering the spec's Units table", ["U1"], []),
])
def test_units_section_changes_touch_by_their_rules(world, change, touched, merged_review):
  # prose under ## Units is a build rule: every unfiled or unmerged unit, covered or quoted or not, and the range
  # rule still applies; a table row touches its own unit, whoever quotes it or ranges over the table; U0 is merged
  from superegm import respec
  over, quotes, draft = UNITS_CASES[change]
  spec, st = respec_world(world, [(UNITS, None)], units=ranges(**over))
  for uid, line in quotes.items():
    core.atomic_write(st.path("unit", uid), BODIES[uid] + f"\n{line}\n")
  result = respec.touched(st, HID, "".join(draft()))
  assert (result["touched"], result["merged_review"]) == (touched, merged_review)


RULE = "Each unit commits its tests first."
UNITS_H3 = BASE[:UNITS_AT] + ["## 5. Units\n", "\n", "Every unit logs its retries.\n", "\n", "### Rows\n", "\n"] \
  + UNITS[UNITS_AT + 4:] + ["\n", "### Build rules\n", "\n", RULE + "\n"]


@pytest.mark.parametrize("change, touched, merged_review", [
  ("a prose line under `### Build rules` of `## Units`, U2's Design range over the section", ["U1", "U2", "U3"], ["U0"]),
  ("U1's row of a table under `### Rows` of `## Units`, U3's Design range over the section", ["U1"], []),
])
def test_units_subsections_keep_the_units_rules(world, change, touched, merged_review):
  # astra-1-2: the Units section runs to the next H2 (as `approve_spec.units_section` reads it), its H3s included
  from superegm import respec
  owner = "U2" if "prose" in change else "U3"
  units = {u: {"id": u, "design_range": design_range(UNITS_H3, "## 5. Units" if u == owner else h)} for u, h in SECTIONS.items()}
  spec, st = respec_world(world, [(UNITS_H3, None)], units=units)
  draft = replace(UNITS_H3, RULE, "Each unit commits its tests before its code.") if "prose" in change \
    else replace(UNITS_H3, U1_ROW, "| U1 | queue, fifo | — | S |")
  result = respec.touched(st, HID, "".join(draft))
  assert (result["touched"], result["merged_review"]) == (touched, merged_review)


@pytest.mark.parametrize("u1_line, u2_line, touched", [
  ("- Produces: `load(path) -> dict`", "- Consumes: `load` (U1)", ["U1", "U2"]),
  ("- Produces: `superegm review open --review <id>`", "- Consumes: `superegm review open` (U1)", ["U1", "U2"]),
  ("- Produces: `superegm review open --review <id>`", "- Consumes: `superegm launch --runcard <card>` (U1)", ["U1"]),
  ("- Produces: `state.json` key `x`", "- Consumes: `state.json` key `x` (U1)", ["U1", "U2"]),
  ("- Produces: `state.json` key `x`", "- Consumes: `state.json` key `y` (U1)", ["U1"]),
  ("- Produces: none", "- Consumes: none", ["U1"]),
])
def test_interface_names_match_as_scan_reads_them(world, u1_line, u2_line, touched):
  # U1's Interfaces hold u1_line, U2's u2_line; the draft removes the spec's copy of u1_line, inside U1's Design range alone
  from superegm import respec
  base = replace(BASE, "Queue keeps jobs.", [u1_line])
  spec, st = respec_world(world, [(base, None)])
  core.atomic_write(st.path("unit", "U1"), f"### U1: Queue\n\n## Interfaces\n{u1_line}\n")
  core.atomic_write(st.path("unit", "U2"), f"### U2: Deliver\n\n## Interfaces\n{u2_line}\n")
  draft = replace(base, u1_line, None)
  assert respec.touched(st, HID, "".join(draft))["touched"] == touched


DRAFT = replace(BASE, "Delay is 5s.", "Delay is 6s.")  # the correction changes `## 2. Deliver` alone
THREAD = {"id": 41, "login": "alice", "bot": False, "body": "high: the delay is unstated", "path": None, "line": None,
          "commit_id": "c" * 40, "review_body": False, "created_at": "2026-11-14T00:00:00Z"}
THREADS_AT = {
  "docs/other.md:3": {"path": "docs/other.md", "line": 3},
  "the spec, a line of a section the correction leaves unchanged": {"path": "docs/specs/x.md", "line": BASE.index("Admin lists jobs.\n") + 1},
  "the spec, a line of the section the correction changes": {"path": "docs/specs/x.md", "line": DRAFT.index("Delay is 6s.\n") + 1},
  "no line: a review body": {"review_body": True},
  "no line: a file-level comment on the spec": {"path": "docs/specs/x.md"},
  "no line: a file-level comment on docs/other.md": {"path": "docs/other.md"},
}


def earlier_cycle(st, spec, cid):
  """`spec-x-c1`, the cycle the opening approval names (closed once the bytes moved), its round 1 holding an unsettled
  external high at docs/other.md:3 from thread 31."""
  from superegm import review as review_mod
  ext = "external:alice"
  [finding] = review_mod.parse_findings(f"{ext}-1-1 | high | docs/other.md:3 at ccccccc | regression: no | the delay is unstated", ext, 1)
  core.atomic_write(st.path("reviews", "spec-x-c1", "review.json"), {
    "kind": "spec", "artifact": str(spec), "cycle": 1, "handoff_id": None, "scope": "auto", "reviewers": ["design"],
    "cap": 3, "runcard": cid, "artifact_sha256": None, "astra_incomplete": 0, "converged": "no", "converged_round": None,
    "rulings": [], "ingested": [31]})
  core.atomic_write(st.path("reviews", "spec-x-c1", "round-1.json"), {
    "round": 1, "runcard": cid, "artifact_sha256": None, "builder_contested": [], "reviewers": {ext: {
      "findings": [finding | {"thread": 31, "review_body": False, "pr": 7}], "not_run": None, "isolation": "exposed:ingest",
      "model": "none:none", "effort": "none:none"}}})


@pytest.mark.parametrize("cycle, thread_at, ingested", [
  ("respec R1", "docs/other.md:3", 0),
  ("respec R1", "the spec, a line of a section the correction leaves unchanged", 0),
  ("respec R1", "the spec, a line of the section the correction changes", 1),
  ("respec R1", "no line: a review body", 1),
  ("respec R1", "no line: a file-level comment on the spec", 1),
  ("respec R1", "no line: a file-level comment on docs/other.md", 0),
  ("respec R1", "carried: an earlier cycle's unsettled external high at docs/other.md:3", 0),
  ("ordinary", "docs/other.md:3", 1),
])
def test_respec_ingest_reads_its_scope_alone(world, monkeypatch, cycle, thread_at, ingested):
  # `review ingest --pr <n>` on the spec PR: on a respec cycle an external finding, high or medium, outside the correction's scope, new or carried, is
  # never a finding of the round; a thread on another file is skipped with or without a line, and a review body or
  # a thread on the spec naming no line is kept
  from superegm import review as review_mod
  from test_u85 import approved, open_respec
  spec, st = respec_world(world, [(BASE, None)])
  if cycle != "ordinary":
    open_respec(st)
  approved(world, spec, DRAFT, "draft")  # the draft, committed: a respec round records HEAD's spec
  world.spec = spec
  cid = world.card("review-spec")
  carried = thread_at.startswith("carried")
  if carried:
    earlier_cycle(st, spec, cid)
  threads = [] if carried else [THREAD | THREADS_AT[thread_at]]
  monkeypatch.setattr(review_mod, "read_threads", lambda repo, number, skip: [t for t in threads if t["id"] not in skip])
  monkeypatch.setattr(review_mod, "collaborator_role", lambda repo, login: "write")
  code, out = world.run("review", "open", "--kind", "spec", "--artifact", spec, "--reviewers", "design,codebase-details",
                        "--astra", "off", *(["--respec", "R1"] if cycle != "ordinary" else []), "--runcard", cid)
  assert code == 0, out
  rid = out.splitlines()[0]
  for reviewer in ("design", "codebase-details"):
    path = world.repo.parent / f"{rid}-1-{reviewer}.txt"
    path.write_text("", encoding="utf-8")
    code, out = world.run("review", "record", "--review", rid, "--round", "1", "--reviewer", reviewer, "--runcard", cid,
                          "--findings", str(path), "--isolation", "clean", "--model", "inherit:opus", "--effort", "inherit:high")
    assert code == 0, out
  code, out = world.run("review", "ingest", "--pr", "7", "--runcard", cid)
  latest = review_mod.load_round(st, rid, 1)
  external_findings_of_the_latest_round = [f for name, record in latest["reviewers"].items() if name.startswith("external:")
                                           for f in record["findings"]]
  assert code == 0 and f"{ingested} ingested" in out
  assert len(external_findings_of_the_latest_round) == ingested


@pytest.mark.parametrize("flags", [["--dry-run"], ["--yes"]])
def test_respec_approval_after_its_worktree_is_removed(world, flags):
  # handoffs/<id>.json names the spec in a worktree since removed; approve-spec --respec R1 runs from the main checkout
  from test_u85 import MERGED_U1, open_respec, respec_cycle
  state_units = {"U0": MERGED_U1["U0"], "U1": {"number": 11}, "U2": {"number": 12}, "U3": {}}
  spec, st = respec_world(world, [(BASE, None)], state_units=state_units)
  gone = world.repo.parent / "wt-removed" / "docs" / "specs" / "x.md"
  assert not gone.parent.parent.parent.exists()
  core.atomic_write(st.path("handoffs", HID), {"id": HID, "spec": str(gone), "opened_at": "2026-11-12T00:00:00Z", "closed_at": None})
  open_respec(st)
  spec.write_text("".join(DRAFT), encoding="utf-8")
  world.spec = spec
  world.card("review-spec")
  if flags == ["--yes"]:
    respec_cycle(world, spec, st)
  code, out = world.run("approve-spec", "--spec", spec, "--respec", "R1", *flags)
  assert code == 0 and "touched: U2" in out, out
  r1 = st.path("file", "respec", "R1.json")
  respec_r1_json_text = r1.read_text(encoding="utf-8") if r1.exists() else None
  assert flags == ["--dry-run"] or json.loads(respec_r1_json_text)["touched"] == ["U2"]
  assert flags == ["--dry-run"] or "+Delay is 6s." in st.path("file", "respec_comment_U2_R1.md").read_text(encoding="utf-8")
