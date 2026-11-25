# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U105's tests, spec §3.8 "Respec": a respec reaches every unit it touches.

"""U105: prose under `## Units` touches every unfiled or unmerged unit, Units-table lines are exempt from the quoted-line
and range rules, Interfaces names are read as `scan.names_of` reads them, a respec cycle's ingest reads its scope alone,
and `approve-spec --respec` runs after the approving worktree is removed."""

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
