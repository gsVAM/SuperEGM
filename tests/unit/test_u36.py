# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U36's tests: the review round cap (`review.rounds`, the cycle's stored `cap`, the `Rounds:` line frozen at approval), the narrowed panel and the hand-written approval.

"""U36: the review round cap and a narrowed panel."""

import json
import pytest
from conftest import REPO, set_config
from test_review import (SPEC, SLUG, PANEL_OF, opened, converged_spec, approve, hstore, rjson, rpath,
                         head_round, record, status, F, A, card)
from superegm import atomic_write

BANNED = ["(?i)secret-codename"]


def live_rounds(world, value):
  """The repository's config with `review.rounds` set to `value` (a bad value stays as written)."""
  set_config(world, repo=REPO, banned_terms=BANNED, review={"rounds": value})


def edit_entry(world, **changes):
  """Rewrite the latest approval entry by hand: a key set, or dropped with `None`."""
  path = hstore(world).path("approvals", SLUG)
  data = json.loads(path.read_text(encoding="utf-8"))
  for key, value in changes.items():
    data["entries"][-1].pop(key, None)
    if value is not None:
      data["entries"][-1][key] = value
  atomic_write(path, data)


def fill_round(world, kind, rid, n, cid):
  """Round `n` with one high finding by the panel's first reviewer, the others empty."""
  if kind == "head":
    head_round(world, n, "posted", cid, "revise")
  for i, reviewer in enumerate(PANEL_OF[kind].split(",")):
    lines = [F(reviewer, n, 1)] if i == 0 else []
    got = record(world, rid, n, reviewer, lines, cid, sha=A if kind == "head" else None)
    assert got[0] == 0, got


def rounds_until_cap(world, kind, rid, cid, limit=12):
  """How many rounds record before `review status` says cap (exit 2)."""
  for n in range(1, limit + 1):
    fill_round(world, kind, rid, n, cid)
    if status(world, rid, cid)[0] == 2:
      return n
  return None


@pytest.mark.parametrize("kind, source, cap", [
  ("spec", "live review.rounds 3", 3),
  ("spec", "live review.rounds 7", 7),
  ("plan", "latest approval entry rounds 4", 4),
  ("head", "latest approval entry rounds 4", 4),
  ("integrate", "latest approval entry rounds 4", 4),
  ("plan", "1.2.0 entry without rounds", 5),
  ("plan", "legacy flat store, no approval entry", 5),
  ("spec", "record opened under 1.2.0 without cap", 5),
])
def test_cap_stored_at_open(world, kind, source, cap):
  """A cycle stores its cap at open and keeps it through a later config edit; no cap reads 5."""
  if source.startswith("live"):
    live_rounds(world, cap)
    spec, cid, rid = opened(world)
  elif source.startswith("latest approval"):
    spec, cid, rid = converged_spec(world)
    assert approve(world, spec, cid, "--yes")[0] == 0
    edit_entry(world, rounds=cap)
    spec, cid, rid = opened(world, kind)
  elif source.startswith("1.2.0 entry"):
    spec, cid, rid = converged_spec(world)
    assert approve(world, spec, cid, "--yes")[0] == 0
    edit_entry(world, rounds=None)
    spec, cid, rid = opened(world, kind)
  elif source.startswith("legacy"):
    spec, cid, rid = opened(world, kind)
  else:
    live_rounds(world, 3)
    spec, cid, rid = opened(world)
    review = rjson(world, rid)
    review.pop("cap")
    atomic_write(rpath(world, rid, "review.json"), review)
  live_rounds(world, 9)                                    # a later config edit does not move the stored cap
  assert rounds_until_cap(world, kind, rid, cid) == cap
  other = spec.with_name("other-design.md")
  other.write_text(SPEC, encoding="utf-8")
  other_card = card(world, other)
  for bad in (0, 11):
    live_rounds(world, bad)
    code, out = world.run("review", "open", "--kind", "spec", "--artifact", str(other), "--reviewers",
                          PANEL_OF["spec"], "--runcard", other_card)
    assert code == 1 and "review.rounds" in out, out
