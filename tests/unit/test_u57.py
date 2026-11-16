# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U57

"""U57: proceed, the owner's go-ahead (`review rule --ruling proceed --owner`, spec section 4.2): its refusals, its
records, the convergence it gives ahead of every other test, and its readers downstream."""

import json
import pytest

from conftest import ROOT, set_config
from superegm import atomic_write
from test_wave import open_wave_card, wave_store, fake_gh, foreman_of, head_review

REPO, OWNER = "example-org/webhooks", "owner"
UPDATED = "2026-11-10T09:00:00Z"


def issue_of(s, uid):
  return json.loads(s.path("state").read_text(encoding="utf-8"))["units"][uid]["number"]


def comment(s, n, body, uid="U01", author=OWNER, updated=UPDATED):
  """Comment `n` as `gh api repos/<repo>/issues/comments/<n>` serves it, on `uid`'s issue."""
  return {"id": n, "user": {"login": author}, "body": body + "\n", "updated_at": updated,
          "issue_url": f"https://api.github.com/repos/{REPO}/issues/{issue_of(s, uid)}"}


def head_world(world):
  """U01 and U02 filed, each with a pull request; U01's head review opened and its round 1 posted with one medium;
  `config.owners` names `owner`. The store, the wave card and the review id."""
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "launches": [{"round": 1, "status": "exited 0"}]},
                 U02={"pr": 71, "head": "b" * 40, "ci": "green", "launches": [{"round": 1, "status": "exited 0"}]})
  rid = head_review(world, s, card)
  set_config(world, repo=REPO, owners=[OWNER])
  return s, card, rid


def serve(world, *comments):
  fake_gh(world, {f"repos/{REPO}/issues/comments/{c['id']}": c for c in comments})


def proceed(world, rid, card, *extra):
  return world.run("review", "rule", "--review", rid, "--ruling", "proceed", *extra, "--runcard", card)


def snapshot(s, rid, *units):
  paths = [s.path("reviews", rid, "review.json"), s.path("journal")] + [s.path("foreman", u) for u in units]
  return [p.read_bytes() if p.exists() else None for p in paths]


# ---------------------------------------------------------------- S1: the refusals


@pytest.mark.parametrize("case, message", [
  ("--judges", "review rule: proceed is the owner's"),
  ("posted by a non-owner", "review rule: comment 901 is by passer-by, not a login in config.owners"),
  ("posted comment not of the proceed form", "review rule: comment 901 does not rule proceed"),
  ("posted on another unit's issue", "review rule: comment 901 is not on issue #"),
  ("head of a stopped unit", "review rule: U01 is stopped"),
  ("comment another entry names", "review rule: comment 901 already ruled"),
  ("same comment and review, the unit's moved head", "review rule: comment 901 already ruled"),
])
def test_proceed_refusals(world, case, message):
  s, card, rid = head_world(world)
  body = "**Ruling:** proceed — ship it"
  served = {"posted by a non-owner": comment(s, 901, body, author="passer-by"),
            "posted comment not of the proceed form": comment(s, 901, "**Ruling:** stop"),
            "posted on another unit's issue": comment(s, 901, body, uid="U02")}.get(case, comment(s, 901, body))
  serve(world, served)
  by = ("--owner", "--posted", "901")
  if case == "--judges":
    by = ("--judges", "j1", "--reason", "ship it")
  elif case == "head of a stopped unit":
    f = foreman_of(s, "U01")
    f["stopped"] = {"by": OWNER, "reason": "stop the unit", "at": UPDATED}
    atomic_write(s.path("foreman", "U01"), f)
  elif case == "comment another entry names":
    f = foreman_of(s, "U02")
    f["proceeds"] = [{"ruling": "R1", "review": "other-head-U02-c1", "posted": "comment 901", "posted_at": UPDATED,
                      "issue": issue_of(s, "U02"), "head": "b" * 40, "launch": 1, "by": OWNER, "reason": "ship it"}]
    atomic_write(s.path("foreman", "U02"), f)
  elif case == "same comment and review, the unit's moved head":
    f = foreman_of(s, "U01")
    f["proceeds"] = [{"ruling": "R1", "review": rid, "posted": "comment 901", "posted_at": UPDATED,
                      "issue": issue_of(s, "U01"), "head": "c" * 40, "launch": 1, "by": OWNER, "reason": "ship it"}]
    atomic_write(s.path("foreman", "U01"), f)
  before = snapshot(s, rid, "U01", "U02")
  code, out = proceed(world, rid, card, *by)
  assert code == 1 and message in out, out
  assert snapshot(s, rid, "U01", "U02") == before


# ---------------------------------------------------------------- S2: a head's proceed is recorded


def launches(s, uid, *rounds):
  atomic_write(s.path("launches", uid), {"launches": [{"round": n, "status": "exited 0"} for n in rounds]})


def test_proceed_records_the_head(world):
  s, card, rid = head_world(world)
  launches(s, "U01", 1, 2)
  serve(world, comment(s, 901, "**Ruling:** proceed — the medium is accepted risk"),
        comment(s, 902, "**Ruling:** proceed — again, after the merge round", updated="2026-11-11T09:00:00Z"))
  rulings_before = foreman_of(s, "U01")["rulings"]
  code, out = proceed(world, rid, card, "--owner", "--posted", "901")
  assert code == 0, out
  entry = {"ruling": "R1", "review": rid, "posted": "comment 901", "posted_at": UPDATED, "issue": issue_of(s, "U01"),
           "head": "a" * 40, "launch": 2, "by": OWNER, "reason": "the medium is accepted risk"}
  assert foreman_of(s, "U01")["proceeds"] == [entry]
  ruling = json.loads(s.path("reviews", rid, "review.json").read_text(encoding="utf-8"))["rulings"][-1]
  assert {k: ruling[k] for k in ("id", "ruling", "by", "reason", "sha256")} == {
    "id": "R1", "ruling": "proceed", "by": "owner", "reason": "the medium is accepted risk", "sha256": "a" * 40}
  # the same comment, review and head again: the recorded entry, nothing written
  before = snapshot(s, rid, "U01")
  code, out = proceed(world, rid, card, "--owner", "--posted", "901")
  assert code == 0 and json.loads(out) == entry, out
  assert snapshot(s, rid, "U01") == before
  # a newer launch, then a second proceed on a new comment
  launches(s, "U01", 1, 2, 3)
  code, out = proceed(world, rid, card, "--owner", "--posted", "902")
  assert code == 0, out
  proceeds = foreman_of(s, "U01")["proceeds"]
  assert len(proceeds) == 2 and proceeds[-1]["launch"] == 3 and proceeds[-1]["ruling"] == "R2", proceeds
  assert proceeds[-1]["posted_at"] == "2026-11-11T09:00:00Z"
  # a typed head proceed on another unit: no comment, by the owner
  code, out = world.run("review", "open", "--kind", "head", "--artifact", "U02", "--reviewers", "change-review",
                        "--runcard", card)
  assert code == 0, out
  rid2 = out.strip()
  u02_rulings = foreman_of(s, "U02")["rulings"]
  code, out = proceed(world, rid2, card, "--owner", "--reason", "typed in session")
  assert code == 0, out
  assert foreman_of(s, "U02")["proceeds"] == [
    {"ruling": "R1", "review": rid2, "posted": None, "posted_at": None, "issue": issue_of(s, "U02"),
     "head": "b" * 40, "launch": 1, "by": "owner", "reason": "typed in session"}]
  assert foreman_of(s, "U01")["rulings"] == rulings_before and foreman_of(s, "U02")["rulings"] == u02_rulings
  rulings_md = (ROOT / "skills" / "wave" / "references" / "rulings.md").read_text(encoding="utf-8")
  assert "review rule --ruling proceed --owner --posted <cid>" in rulings_md
