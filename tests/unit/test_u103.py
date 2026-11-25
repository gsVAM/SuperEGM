# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U103's tests: rulings (1.3 design sections 3.6, 3.7 and 3.10): the missing-fid refusal of a point-1 ruling, the settle a point-1 ruling makes, the refusal of an edited ruling comment, the wave references' forms and refused paths.

"""U103: `decision rule` refuses a point-1 ruling with no fid, settles the finding a point-1 ruling rules, and refuses an
edited ruling comment."""

import json
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import superegm as core
from conftest import REPO, set_config
from superegm import decision, review
from test_wave import foreman_of, open_wave_card, question, wave_store

FINDING = "foreman-1-1 | high | src/x.py:3 | regression: no | the retry loop never backs off\n"


@pytest.mark.parametrize("ruling", ["finding overruled — the test moved", "finding overruled", "finding upheld",
                                    "finding upheld (fix it)", "finding overruled (moved)", "allowed — kept"])
def test_a_ruling_without_a_fid_says_so(world, ruling):
  """A point-1 ruling that opens with the verdict is refused, `<fid>` written as the spec writes it, nothing recorded."""
  card = open_wave_card(world)
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green"})
  qid = world.run("decision", "open", "--unit", "U01", "--point", 1, "--question", question(world, FINDING),
                  "--source", "review head-U01-c1 round 1", "--runcard", card)[1].splitlines()[0]
  rulings_before = foreman_of(s, "U01")["rulings"]
  code, err = world.run("decision", "rule", "--unit", "U01", "--decision", qid, "--ruling", ruling, "--by", "owner",
                        "--runcard", card)
  rulings_after = foreman_of(s, "U01")["rulings"]
  assert code == 1 and 'missing <fid>: write "<fid> finding overruled"' in err
  assert rulings_after == rulings_before
  assert not world.gh.comments, "a refused ruling posts nothing"


# ---------------------------------------------------------------- S2: a point-1 ruling settles the finding it rules


TD_CLAIM = "test-delta: tests/unit/test_q.py:3 removed"
OWNER_COMMENTS = {"U01": 501, "U02": 502}  # the by-hand ruling comment of each unit, on its own issue (#2, #3)
ISSUES = {"U01": 2, "U02": 3, "U03": 4}


def finding(fid, severity="high", location="src/x.py:3", claim="the retry loop never backs off"):
  return {"id": fid, "severity": severity, "location": location, "regression": "no", "claim": claim,
          "disposition": None, "ruling": None}


def round_two(decision, settled):
  """Round 2's findings, the fids the builder contested and the round's word: the blockers are the findings in `settled`;
  `contest+delta` adds foreman-2-2, an unsettled test-delta high; foreman-2-3 is a contest copy of round 1's test-delta finding."""
  kinds = {"foreman-2-1": finding("foreman-2-1", location="tests/unit/test_q.py:3", claim=TD_CLAIM) if decision == "owner"
           else finding("foreman-2-1"),
           "foreman-2-2": finding("foreman-2-2", location="tests/unit/test_q.py:9", claim=TD_CLAIM),
           "foreman-2-3": finding("foreman-2-3", claim=f"contested foreman-1-1: {TD_CLAIM}")}
  found = [kinds[fid] for fid in settled] + ([kinds["foreman-2-2"]] if decision == "contest+delta" else [])
  if decision == "owner":
    return found, [], "owner: " + ", ".join(f["id"] for f in found)
  return found, list(settled), "contested: " + ", ".join(settled)


def question_of(found, contested):
  """The decision's question file: one full finding line per finding it asks about (all of them on an owner decision)."""
  return "".join(f"{f['id']} | {f['severity']} | {f['location']} | regression: no | {f['claim']}\n"
                 for f in found if not contested or f["id"] in contested)


class Gh:
  """The by-hand ruling comments the fake GitHub serves; their reads fail from the `fail_from`-th on."""

  def __init__(self, world, comments):
    self.reads, self.fail_from = 0, None

    def api(args, cwd, token=None):
      match = re.fullmatch(rf"repos/{REPO}/issues/comments/(\d+)", world.gh.endpoint_of(args))
      if not match or int(match.group(1)) not in comments:
        return world.gh.do_api(args)
      self.reads += 1
      if self.fail_from is not None and self.reads >= self.fail_from:
        return 1, "", "gh: Server Error (HTTP 500)"
      return world.gh.ok(comments[int(match.group(1))])
    world.gh.extend("api", api)


def seed_review(s, unit, rid, card, found, contested):
  """An opened head review of `unit`: round 1 holding the test-delta finding foreman-1-1, round 2 holding `found`."""
  core.atomic_write(s.path("reviews", rid, "review.json"),
                    {"kind": "head", "artifact": unit, "cycle": 1, "handoff_id": s.handoff_id, "scope": None,
                     "reviewers": ["change-review"], "cap": 5, "runcard": card, "artifact_sha256": "a" * 64,
                     "astra_incomplete": 0, "converged": "no", "converged_round": None, "rulings": []})
  first = [finding("foreman-1-1", location="tests/unit/test_q.py:3", claim=TD_CLAIM)]
  for n, findings, owed in ((1, first, []), (2, found, contested)):
    core.atomic_write(s.path("reviews", rid, f"round-{n}.json"),
                      {"round": n, "runcard": card, "artifact_sha256": "a" * 64, "what_ran": "completed",
                       "builder_contested": [{"fid": fid, "reason": "r"} for fid in owed],
                       "reviewers": {"change-review": {"findings": []}, "foreman": {"findings": findings}}})


def world_of(world, mode, decision, settled, ruling):
  """A card in `mode`, U01 with an opened head review whose round 2 holds the blockers of `settled`, U02 the same with a review
  nobody opened, U03 a round whose only finding is the CI finding foreman-2-4; each with its point-1 decision q1 open on round 2."""
  extra = ["--mode", "leavemealone"] if mode == "leavemealone" else []
  card = world.run("runcard", "open", "--skill", "wave", "--artifact", world.spec, *extra, card=None)[1].strip()
  found, contested, word = round_two(decision, settled)
  ci = [finding("foreman-2-4", location="ci", claim="CI not green on this head")]
  rounds = lambda outcome: [{"round": n, "phase": "posted", "outcome": "revise" if n == 1 else outcome, "launch": 1, "runcard": card,
                             "head": "a" * 40, "dispatch_id": f"d{n}", "posted_at": None} for n in (1, 2)]
  units = {u: {"pr": 70 + i, "head": "a" * 40, "ci": "green", "rounds": rounds(o)}
           for i, (u, o) in enumerate((("U01", word), ("U02", word), ("U03", "contested: foreman-2-4")))}
  s = wave_store(world, **units)
  set_config(world, repo=REPO, owners=["owner"])
  stamp = "2026-11-24T10:00:00Z"
  comments = {OWNER_COMMENTS[u]: {"id": OWNER_COMMENTS[u], "user": {"login": "owner"}, "body": f"**Ruling:** {ruling}" + ("" if " — " in ruling else " — fine by me"),
                                  "issue_url": f"https://api.github.com/repos/{REPO}/issues/{ISSUES[u]}",
                                  "created_at": stamp, "updated_at": stamp} for u in OWNER_COMMENTS}
  gh = Gh(world, comments)
  rids = {u: review.review_id(s, "head", u, 1) for u in ("U01", "U02", "U03")}
  seed_review(s, "U01", rids["U01"], card, found, contested)  # U02's review is never opened
  seed_review(s, "U03", rids["U03"], card, ci, ["foreman-2-4"])
  for u, f, c in (("U01", found, contested), ("U02", found, contested), ("U03", ci, ["foreman-2-4"])):
    code, out = world.run("decision", "open", "--unit", u, "--point", 1, "--question", question(world, question_of(f, c)),
                          "--source", f"review {rids[u]} round 2", "--runcard", card)
    assert code == 0, out
  return SimpleNamespace(card=card, s=s, rids=rids, gh=gh)


def rule_by(world, w, unit, ruling, by, posted):
  """`decision rule`: the typed ruling on the unit's decision q1, or the by-hand comment of `unit` (`--posted`, no `--decision`)."""
  argv = ["decision", "rule", "--unit", unit, "--ruling", ruling, "--by", by, "--runcard", w.card]
  return world.run(*argv, *(["--posted", OWNER_COMMENTS[unit]] if posted else ["--decision", "q1"]))


@pytest.mark.parametrize("mode, by, decision, ruling, posted, settled, word", [
    ("normal", "owner", "contest", "foreman-2-1 finding overruled — the spec allows it", False, {"foreman-2-1": "contested"}, None),
    ("normal", "owner", "contest", "foreman-2-1 finding overruled — the spec allows it", True, {"foreman-2-1": "contested"}, None),
    ("leavemealone", "owner", "contest", "foreman-2-1 finding overruled — the spec allows it", True, {"foreman-2-1": "contested"}, None),
    ("leavemealone", "owner", "contest", "foreman-2-1 finding overruled — the spec allows it", False, {"foreman-2-1": None}, None),
    ("normal", "judges:P", "contest", "foreman-2-1 finding overruled — the panel", False, {"foreman-2-1": "contested"}, None),
    ("normal", "owner", "contest", "foreman-2-1 finding upheld", False, {"foreman-2-1": None}, None),
    ("normal", "owner", "contest", "test-delta tests/unit/test_q.py allowed", True, {"foreman-2-3": "contested"}, None),
    ("normal", "owner", "owner", "foreman-2-1 allowed — kept by design", False, {"foreman-2-1": "declined"}, None),
    ("normal", "owner", "owner", "foreman-2-1 finding overruled — kept by design", False, {"foreman-2-1": "declined"}, None),
    ("normal", "owner", "owner", "test-delta tests/unit/test_q.py allowed", True, {"foreman-2-1": "declined", "foreman-2-2": "declined"}, None),
    ("normal", "owner", "contest+delta", "foreman-2-1 finding overruled — the spec allows it", False, {"foreman-2-1": "contested"},
     "owner: foreman-2-2"),
])
def test_a_point_1_ruling_settles_its_finding(world, mode, by, decision, ruling, posted, settled, word):
  """A point-1 ruling settles the finding it rules through the settle in `review.py`, as the owner or as the panel, every ruler
  check run before anything is recorded; the round's rewritten word is printed as `review settle` prints it."""
  w = world_of(world, mode, decision, settled, ruling)
  s, rid = w.s, w.rids["U01"]
  pid = f"{rid}-r2-a1b2c3"  # the panel `judges open` opened on round 2, converged on `finding overruled`
  by = by.replace("P", pid) if by.startswith("judges:") else by
  folder = s.path("judges", pid, "question.md").parent
  folder.mkdir(parents=True)
  (folder / "question.md").write_text("## Q1 foreman-2-1 (high, src/x.py): claim\n- (a) finding upheld\n- (b) finding overruled — the panel\n",
                                      encoding="utf-8")
  core.atomic_write(folder / "verdict.json", {"panel": pid, "questions": {"Q1": {"converged": True, "option": "b", "round": 1, "positions": {},
                                                                                 "vendors": [], "reason": None}}, "open": [], "converged": True})
  rulings_before = foreman_of(s, "U01")["rulings"]
  if mode == "leavemealone" and posted:  # GitHub answers the ruling's own read and fails the settle's read of the comment
    w.gh.fail_from = 2
    failed_read_code, failed_read_err = rule_by(world, w, "U01", ruling, by, posted)
    failed_read_rulings = foreman_of(s, "U01")["rulings"]
    w.gh.reads, w.gh.fail_from = 0, None  # rerun once it answers
  code, out = rule_by(world, w, "U01", ruling, by, posted)
  unit_rulings = foreman_of(s, "U01")["rulings"]
  round_2 = json.loads(s.path("reviews", rid, "round-2.json").read_text(encoding="utf-8"))
  round_2_findings = {f["id"]: f for f in round_2["reviewers"]["foreman"]["findings"]}
  round_2_word = next(e for e in foreman_of(s, "U01")["rounds"] if e["round"] == 2)["outcome"]
  assert code == 0, out
  assert out.splitlines()[1:] == ([word] if word else [])  # line 1 the post's URL or `recorded (comment <id>)`
  assert any(r["ruling"].startswith(ruling.partition(" — ")[0]) for r in unit_rulings)  # recorded, an uphold too
  assert {fid: f["disposition"] for fid, f in round_2_findings.items() if fid in settled} == settled
  assert all(round_2_findings[fid]["ruling"] == (by if d else None) for fid, d in settled.items())
  assert (round_2_word == "clean") is (all(settled.values()) and word is None)
  # `superegm review settle` run after it on each settled finding, its disposition and provenance (`--owner [--posted]`, `--judges P`)
  provenance = ["--judges", pid] if by.startswith("judges:") \
      else ["--owner"] + (["--posted", OWNER_COMMENTS["U01"]] if mode == "leavemealone" else [])
  replayed_codes = [world.run("review", "settle", "--review", rid, "--finding", fid, "--disposition", d, *provenance,
                              "--runcard", w.card)[0] for fid, d in settled.items() if d]
  assert replayed_codes == [0] * sum(bool(d) for d in settled.values())
  # the same ruling on a decision whose source names an unopened review: recorded as in 1.2.1, nothing settled
  if not (ruling.startswith("test-delta") and decision == "contest"):  # a contest copy's file allowance reads the review's chain
    unopened_before = foreman_of(s, "U02")["rounds"]
    unopened_code, unopened_out = rule_by(world, w, "U02", ruling, by, posted)
    assert unopened_code == 0, unopened_out
    assert not s.path("reviews", w.rids["U02"]).exists() and foreman_of(s, "U02")["rounds"] == unopened_before
  if mode == "leavemealone" and posted:  # the failed read: refused, nothing recorded
    assert failed_read_code == 1 and failed_read_rulings == rulings_before
    assert len(failed_read_err.splitlines()) == 1 and failed_read_err.startswith("gh: ")
  # the owner's overrule of the CI finding foreman-2-4: refused, whether or not it settles, nothing recorded
  ci_before = foreman_of(s, "U03")["rulings"]
  ci_code, ci_err = world.run("decision", "rule", "--unit", "U03", "--decision", "q1", "--ruling", "foreman-2-4 finding overruled — flaky",
                              "--by", "owner", "--runcard", w.card)
  assert ci_code == 1 and "the CI finding is settled by no one" in ci_err and foreman_of(s, "U03")["rulings"] == ci_before


def test_a_ruling_settles_only_its_own_units_review_in_the_round_its_source_names(world):
  """Round 2 (astra-1-1, astra-1-2): finding ids recur across units and carry across rounds, so a decision naming another unit's
  review settles nothing there, and one naming round 1 settles round 1's finding, or is refused when that round lacks it."""
  ruling = "foreman-2-1 finding overruled — the spec allows it"
  w = world_of(world, "normal", "contest", {"foreman-2-1": "contested"}, ruling)
  s, rid = w.s, w.rids["U01"]
  disposition = lambda n: next(f["disposition"] for f in json.loads(s.path("reviews", rid, f"round-{n}.json").read_text(encoding="utf-8"))
                               ["reviewers"]["foreman"]["findings"] if f["id"] == "foreman-2-1")
  source = lambda unit, text: core.atomic_write(s.path("foreman", unit), foreman_of(s, unit) | {
      "decisions": [foreman_of(s, unit)["decisions"][0] | {"source": text}]})
  source("U02", f"review {rid} round 2")  # U02's decision names U01's review: nothing of U01's is settled
  assert rule_by(world, w, "U02", ruling, "owner", False)[0] == 0
  assert disposition(2) is None and next(e for e in foreman_of(s, "U01")["rounds"] if e["round"] == 2)["outcome"] == "contested: foreman-2-1"
  source("U01", f"review {rid} round 1")  # round 1 holds no foreman-2-1: refused, nothing recorded
  before = foreman_of(s, "U01")["rulings"]
  code, err = rule_by(world, w, "U01", ruling, "owner", False)
  assert code == 1 and "no finding foreman-2-1" in err and foreman_of(s, "U01")["rulings"] == before and not world.gh.comments.get(2)
  path = s.path("reviews", rid, "round-1.json")  # round 1 carries a copy of the finding: only that copy is settled
  carried = json.loads(path.read_text(encoding="utf-8"))
  carried["reviewers"]["foreman"]["findings"].append(finding("foreman-2-1"))
  core.atomic_write(path, carried)
  assert rule_by(world, w, "U01", ruling, "owner", False)[0] == 0
  assert (disposition(1), disposition(2)) == ("contested", None)


# ---------------------------------------------------------------- S3: a ruling comment edited before its record is refused


@pytest.mark.parametrize("updated_at, refused", [("2026-11-24T10:00:00Z", False), (None, False), ("2026-11-24T10:05:00Z", True)])
def test_an_edited_ruling_comment_is_refused(world, updated_at, refused):
  """A posted ruling comment whose `updated_at` differs from its `created_at` when first recorded is refused, nothing recorded,
  a `review rule --ruling proceed --owner --posted` comment too; one recorded unedited and edited after is still a ruling event."""
  card = open_wave_card(world)
  rounds = [{"round": n, "phase": "posted", "outcome": "revise" if n == 1 else "contested: foreman-1-1", "launch": 1, "runcard": card,
             "head": "a" * 40, "dispatch_id": f"d{n}", "posted_at": None} for n in (1, 2)]
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "rounds": rounds})
  set_config(world, repo=REPO, owners=["owner"])
  rid = review.review_id(s, "head", "U01", 1)
  seed_review(s, "U01", rid, card, [finding("foreman-2-1")], ["foreman-2-1"])
  comment = lambda cid, text: {"id": cid, "user": {"login": "owner"}, "body": f"**Ruling:** {text}",
                               "issue_url": f"https://api.github.com/repos/{REPO}/issues/2",
                               "created_at": "2026-11-24T10:00:00Z"} | ({"updated_at": updated_at} if updated_at else {})
  comments = {13: comment(13, "foreman-1-1 finding overruled — moved"), 14: comment(14, "proceed — go ahead")}
  Gh(world, comments)
  assert world.run("decision", "open", "--unit", "U01", "--point", 1, "--question", question(world, FINDING),
                   "--source", f"review {rid} round 2", "--runcard", card)[0] == 0
  rulings_before = foreman_of(s, "U01")["rulings"]
  proceeds_before = foreman_of(s, "U01").get("proceeds")
  code, err = world.run("decision", "rule", "--unit", "U01", "--posted", 13, "--ruling", "foreman-1-1 finding overruled — moved",
                        "--by", "owner", "--runcard", card)
  rulings_after = foreman_of(s, "U01")["rulings"]
  assert (code, "ruling comment edited: post a new one" in err) == ((1, True) if refused else (0, False)), err
  assert (rulings_after == rulings_before) is refused
  if not refused:  # comment 13 recorded unedited, then edited: still read as the owner's ruling, its rerun refused as before
    edited_13 = comments[13] | {"updated_at": "2026-11-24T10:05:00Z"}
    comments[13] = edited_13
    assert decision.ruling_of(edited_13, ["owner"]) is not None
    rerun_code, rerun_err = world.run("decision", "rule", "--unit", "U01", "--posted", 13, "--ruling",
                                      "foreman-1-1 finding overruled — moved", "--by", "owner", "--runcard", card)
    assert rerun_code == 1 and "already recorded (ruling edited after record, ignored)" in rerun_err
  if refused:  # comment 14: the same refusal before any form or head check, no `proceeds[]` entry
    proceed_code, proceed_err = world.run("review", "rule", "--review", rid, "--ruling", "proceed", "--owner", "--posted", 14,
                                          "--runcard", card)
    assert proceed_code == 1 and "ruling comment edited: post a new one" in proceed_err
    assert foreman_of(s, "U01").get("proceeds") == proceeds_before


# ---------------------------------------------------------------- S4: the wave references


ROOT = Path(__file__).resolve().parents[2]


def test_the_wave_references_state_the_forms_and_the_refused_paths():
  """`decision rule` settles the point-1 finding it rules, so neither reference tells the wave to run `review settle --owner` after
  it, and its second line routes as `review settle`'s word does; Decision point 1's owner paragraph names, besides a panel that
  does not converge, the round `judges question` refuses and the refused `redesign`."""
  collapsed = lambda name: " ".join((ROOT / "skills/wave/references" / name).read_text(encoding="utf-8").split())
  rulings, points = collapsed("rulings.md"), collapsed("decision_points.md")
  section = points.split("### Decision point 1")[1].split("### Decision point 2")[0]
  _, opens, rest = section.partition("Only a panel that does not converge")
  owner_paragraph = (opens + rest).partition("Record each ruling")[0]
  for text in (rulings, points):
    assert "`decision rule` settles the finding it rules" in text and "`decision rule`'s second line" in text
    assert not re.search(r"review settle [^`]*--disposition (contested|declined) --owner", text)
  assert 'missing <fid>: write "<fid> finding overruled"' in rulings and "ruling comment edited: post a new one" in rulings
  assert "the CI finding is settled by no one" in rulings and "on the CI finding, `<fid> finding upheld`" in rulings
  assert all(word in owner_paragraph for word in ("does not converge", "refused round", "refused `redesign`"))
