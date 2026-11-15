# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U38's tests: the records' manifests, the judge panel's render, the Astra brief's section and the skills' placement of the section.

"""U38: instructions to the foreman, reviewers and judges."""

import json

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import REPO, git
from test_review import A, SLUG, F, approve, card, converged_spec, head_round, hstore, opened, record, rounds, seed_handoff
from test_u37 import RULES, blob_sha, commit_file, configure, entries_of

TEXT = "Run the suite.\n"
MANIFEST = [{"file": RULES, "sha": blob_sha(TEXT.encode())}]
ASTRA_ONLY = [{"file": "astra-only.md", "sha": "a" * 12}]


def recorded(world, rid, n, reviewer):
  """The `instructions` key of one reviewer's record in `round-<n>.json`."""
  path = hstore(world).path("reviews", rid, f"round-{n}.json")
  return json.loads(path.read_text(encoding="utf-8"))["reviewers"][reviewer]["instructions"]


def render(world, *argv):
  code, out = world.run("instructions", "--role", "reviewers", *argv, card=None)
  assert code == 0 and out.startswith("# Repository instructions\n"), out


def approved_handoff(world, to):
  """An approved spec whose frozen list names RULES for `to`; the handoff id."""
  commit_file(world, RULES, TEXT)
  configure(world, [{"file": RULES, "to": to}])
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  seed_handoff(world, spec)
  return spec, cid, entries_of(world)[-1]["handoff_id"]


def move_on(world, spec, cid):
  """A HEAD edit and a re-approval after the render."""
  commit_file(world, RULES, "Skip the suite.\n")
  assert approve(world, spec, cid, "--yes")[0] == 0


@pytest.mark.parametrize("dispatch, expected", [
  ("head review, Claude-only, reviewers rendered under the child card with --unit", "card manifest"),
  ("plan review, reviewers rendered on its card", "card manifest"),
  ("spec review round 2, local lane", "instructions-2-reviewers-local.json manifest"),
  ("spec review round 2, astra lane", "instructions-2-reviewers-astra.json manifest"),
  ("no stored render", []),
  ("foreman dispatch from a wave card with a foreman render", "wave card foreman manifest"),
])
def test_records_copy_the_stored_manifest(world, dispatch, expected):
  """Each record copies its own lane's stored manifest, unchanged by a later re-approval or HEAD edit."""
  if dispatch.startswith("foreman"):
    from test_foreman import UNIT, seed
    st, wave, _ = seed(world)

    def dispatch_round():
      code, out = world.run("foreman", "dispatch", "--unit", UNIT, "--runcard", wave)
      assert code == 0, out
      return json.loads(st.path("foreman", UNIT).read_text(encoding="utf-8"))["rounds"][-1]["instructions"]

    assert dispatch_round() == []                       # no render stored on the wave card: no section reached the foreman
    stored = {"foreman": {"local": {"approved_at": None, "manifest": MANIFEST, "text": "# Repository instructions\n"}}}
    path = st.path("runcards", wave)
    superegm.atomic_write(path, {**json.loads(path.read_text(encoding="utf-8")), "instructions": stored})
    assert dispatch_round() == MANIFEST
    return
  if dispatch.startswith("head"):
    spec, cid, hid = approved_handoff(world, ["reviewers"])
    wave = card(world, spec, "wave", handoff=hid)
    child = card(world, "U07", "wave", parent=wave, handoff=hid)
    code, out = world.run("review", "open", "--kind", "head", "--artifact", "U07", "--reviewers", "change-review", "--astra", "off",
                          "--runcard", wave)
    assert code == 0, out
    rid = out.splitlines()[0]
    render(world, "--handoff", hid, "--runcard", child, "--unit", "U07")
    move_on(world, spec, cid)
    head_round(world, 1, "prepared", child)
    assert record(world, rid, 1, "change-review", [], child, sha=A)[0] == 0
    assert recorded(world, rid, 1, "change-review") == MANIFEST
  elif dispatch.startswith("plan"):
    spec, cid, hid = approved_handoff(world, ["reviewers"])
    used = card(world, spec, "review-plan", handoff=hid)
    code, out = world.run("review", "open", "--kind", "plan", "--artifact", "U07", "--reviewers", "readiness", "--astra", "off",
                          "--runcard", used)
    assert code == 0, out
    rid = out.splitlines()[0]
    render(world, "--handoff", hid, "--runcard", used)
    move_on(world, spec, cid)
    assert record(world, rid, 1, "readiness", [], used)[0] == 0
    assert recorded(world, rid, 1, "readiness") == MANIFEST
  else:
    commit_file(world, RULES, TEXT)
    configure(world, [{"file": RULES, "to": ["reviewers"]}])
    git(["commit", "-qam", "config", "--allow-empty"], world.repo)
    spec, cid, rid = opened(world, astra="on")
    rounds(world, rid, cid, [[F("design", 1, 1)]])
    assert record(world, rid, 1, "astra", [], cid)[0] == 0
    assert recorded(world, rid, 1, "design") == [] and recorded(world, rid, 1, "astra") == []   # no render for round 1
    if expected != []:
      render(world, "--spec", spec, "--review", rid, "--round", 2, "--runcard", cid)
      superegm.atomic_write(hstore(world).path("reviews", rid, "instructions-2-reviewers-astra.json"),
                            {"manifest": ASTRA_ONLY, "text": "# Repository instructions\n"})
      commit_file(world, RULES, "Skip the suite.\n")
    assert record(world, rid, 2, "design", [], cid)[0] == 0
    assert record(world, rid, 2, "astra", [], cid)[0] == 0
    local, astra = recorded(world, rid, 2, "design"), recorded(world, rid, 2, "astra")
    if dispatch.endswith("astra lane"):
      assert astra == ASTRA_ONLY and local == MANIFEST
    elif dispatch.endswith("local lane"):
      assert local == MANIFEST and astra == ASTRA_ONLY
    else:
      assert local == [] and astra == []
