# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U40's tests: review triage on a pull-request head (spec section 5.2): the eligible mediums, the triage file and its refusals, the deferral and its follow-up row, the owner's undo and its refusals.

"""U40: review triage and the blocking rule (spec section 5.2)."""

import json
import pytest
from superegm import atomic_write, load_approvals, sha256_file
from test_foreman import UNIT, prepared, record

PATTERNS = [{"reach": "agent"}, {"reach": "forged", "later": "easy"},
            {"critical": "no", "later": "easy", "verified": "confirmed"}]


def M(reviewer, i=1, sev="medium", reg="no", claim="a claim", n=1, loc="src/hooks.py:1"):
  """One findings line of round `n`."""
  return f"{reviewer}-{n}-{i} | {sev} | {loc} | regression: {reg} | {claim}\n"


def triage_on(world, st, patterns=PATTERNS):
  """The handoff's approval entry at the spec's bytes, with its frozen `triage` (None: triage off)."""
  entries = load_approvals(st, world.spec)  # the fixture's approval (its `commit` read by a later `prepare`) kept
  atomic_write(st.path("approvals", "sample"), {"entries": entries + [
      {"kind": "opening", "handoff_id": st.handoff_id, "escalated": [], "sha256": sha256_file(world.spec.resolve()),
       "rounds": 5, "triage": patterns, **{k: v for k, v in (entries[-1] if entries else {}).items() if k == "commit"}}]})


def foreman(w):
  return json.loads(w.st.path("foreman", UNIT).read_text(encoding="utf-8"))


def save_foreman(w, data):
  atomic_write(w.st.path("foreman", UNIT), data)


def head(world, tmp_path, monkeypatch, findings, patterns=PATTERNS, **kw):
  """Round 1 of the unit's head review, collected, its findings recorded; triage frozen as `patterns`."""
  w = prepared(world, tmp_path, monkeypatch, **kw)
  triage_on(world, w.st, patterns)
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert code == 0, out
  record(world, w.st, w.rid, 1, w.head, w.child, findings)
  return w


def eligible(world, w, n=1):
  code, out = world.run("review", "triage", "--review", w.rid, "--round", n, "--eligible")
  assert code == 0, out
  return out


@pytest.mark.parametrize("case, eligible_", [
    ("panel medium", True), ("panel high", False), ("regression medium", False),
    ("test-delta: medium", False), ("medium named in an owner: line", False),
    ("external:<login> medium", False), ("medium in a unit whose triage was undone", False),
])
def test_eligible_mediums(world, tmp_path, monkeypatch, case, eligible_):
  """--eligible prints exactly the eligible fids: a panel medium, not a regression, not `test-delta:`, not named in an
  `owner:` line, not an external's, in a unit the owner has not turned triage off for by an undo."""
  fid, findings = "change-review-1-1", {"change-review": M("change-review")}
  if case == "panel high":
    findings = {"change-review": M("change-review", sev="high")}
  if case == "regression medium":
    findings = {"change-review": M("change-review", reg="yes")}
  if case == "test-delta: medium":
    fid, findings = "foreman-1-1", {"foreman": M("foreman", loc="tests/unit/test_hooks.py", claim="test-delta: an assertion went")}
  if case == "external:<login> medium":
    fid, findings = "external:alice-1-1", {"external:alice": M("external:alice")}
  w = head(world, tmp_path, monkeypatch, findings)
  if case == "medium named in an owner: line":
    data = foreman(w); data["rounds"][0]["outcome"] = f"owner: {fid}"; save_foreman(w, data)
  if case == "medium in a unit whose triage was undone":
    data = foreman(w)
    data["rulings"].append({"kind": "undo", "decision": None, "fid": "change-review-0-1", "by": "owner", "posted": "comment 77",
                            "ruling": "change-review-0-1 finding upheld", "posted_at": "2026-11-03T11:00:00Z", "at": "2026-11-03T11:00:00Z"})
    save_foreman(w, data)
  out = eligible(world, w)
  assert (fid in out.split()) == eligible_, out
  assert all(line == "change-review-1-1" for line in out.split()), out


F1, F2 = "change-review-1-1", "change-review-1-2"
GOOD = f"{F1} | reach: agent | later: easy | critical: no | verified: confirmed src/hooks.py:1\n"


def round_text(w, n=1):
  return w.st.path("reviews", w.rid, f"round-{n}.json").read_text(encoding="utf-8")


def triage_file(world, w, text, n=1, name="triage"):
  """The triage goldfish's reply written beside the round and recorded through `review triage --file`."""
  path = w.dir / f"r{n}" / f"{name}.txt"
  path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text, encoding="utf-8")
  return world.run("review", "triage", "--review", w.rid, "--round", n, "--file", str(path), "--isolation", "clean",
                   "--model", "m:m", "--effort", "e:e", "--runcard", w.child)


@pytest.mark.parametrize("case", [
    "triage off", "a line for a fid not eligible", "an eligible medium with no line",
    "reach: remote", "no critical field", "confirmed src/missing.py:9 at the round's head",
    "a second triage of the round", "one good line then one bad line",
])
def test_triage_file_refusals(world, tmp_path, monkeypatch, case):
  """One bad line refuses the whole file and records nothing; a good file prints one `<fid> deferred: triage <n>`
  line per deferred fid."""
  findings = M("change-review")
  if case == "a line for a fid not eligible":
    findings += M("change-review", 2, sev="high")
  if case in ("an eligible medium with no line", "one good line then one bad line"):
    findings += M("change-review", 2)
  w = head(world, tmp_path, monkeypatch, {"change-review": findings}, patterns=None if case == "triage off" else PATTERNS)
  bad = {"triage off": GOOD,
         "a line for a fid not eligible": GOOD + f"{F2} | reach: agent | later: easy | critical: no | verified: refuted no caller\n",
         "an eligible medium with no line": GOOD,
         "reach: remote": GOOD.replace("reach: agent", "reach: remote"),
         "no critical field": GOOD.replace(" | critical: no", ""),
         "confirmed src/missing.py:9 at the round's head": GOOD.replace("src/hooks.py:1", "src/missing.py:9"),
         "a second triage of the round": GOOD,
         "one good line then one bad line": GOOD + f"{F2} | reach: agent | later: soon | critical: no | verified: refuted no caller\n"}[case]
  ok_run = None
  if case == "a second triage of the round":
    ok_run = triage_file(world, w, GOOD, name="first")
  round_record_before = round_text(w)
  code, out = triage_file(world, w, bad)
  round_record_after = round_text(w)
  assert code == 1 and round_record_after == round_record_before, out
  assert out.startswith("triage: "), out
  if case == "triage off":
    triage_on(world, w.st)
  if ok_run is None:
    good = GOOD + (f"{F2} | reach: external | later: version | critical: yes | verified: refuted no caller\n"
                   if case in ("an eligible medium with no line", "one good line then one bad line") else "")
    ok_run = triage_file(world, w, good, name="good")
  assert ok_run[0] == 0, ok_run[1]
  assert ok_run[1].splitlines() == [f"{F1} deferred: triage 1"]


A_PY = {"src/a.py": "a\nb\nc\n"}  # in the base commit: present at the head, outside the PR's changed paths


def finding_of(w, fid, n=1):
  rnd = json.loads(round_text(w, n))
  return next(f for r in rnd["reviewers"].values() for f in r["findings"] if f["id"] == fid)


def post(world, w, n=1, did=None, child=None):
  return world.run("review", "post", "--unit", UNIT, "--round", n, "--dispatch", did or w.did, "--runcard", child or w.child)


def next_round(world, w, n, comments=""):
  """Launch `n` exited, the next round dispatched, prepared and collected (`comments`, when given, is that round's
  `comments.md`); returns `(dispatch id, child card, collect's output)`."""
  launches = json.loads(w.st.path("launches", UNIT).read_text(encoding="utf-8"))
  launches["launches"].append({"round": n, "status": "exited 0"}); atomic_write(w.st.path("launches", UNIT), launches)
  code, out = world.run("foreman", "dispatch", "--unit", UNIT, "--runcard", w.card)
  assert code == 0, out
  did, child = out.split()
  code, out = world.run("prepare", "--unit", UNIT, "--dispatch", did, "--runcard", child)
  assert code == 0, out
  if comments:
    atomic_write(w.dir / f"r{n}" / "comments.md", comments)
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", did, "--runcard", child)
  assert code == 0, out
  return did, child, out


def test_deferral_and_followup_row(world, tmp_path, monkeypatch):
  """The first matching pattern; the row written by `count_posted` once per fid and round (recovery included), none
  for a round that never posts; the comment's **Deferred by triage** block; a refuted unmatched medium blocks as in
  1.2; a deferred medium is not carried as blocking by `collect`."""
  claim = "a forged payload reaches the hook"
  w = head(world, tmp_path, monkeypatch, {"change-review": M("change-review", claim=claim) + M("change-review", 2, claim="b")},
           base_files=A_PY)
  reply = (f"{F1} | reach: forged | later: easy | critical: no | verified: confirmed src/a.py:3\n"
           f"{F2} | reach: config | later: easy | critical: no | verified: refuted no caller reaches it\n")
  code, out = triage_file(world, w, reply)
  assert (code, out.splitlines()) == (0, [f"{F1} deferred: triage 2"]), out
  finding = finding_of(w, F1)
  assert finding["disposition"] == "deferred: triage 2"
  refuted_medium_unmatched_disposition = finding_of(w, F2)["disposition"]
  assert refuted_medium_unmatched_disposition is None
  journal = w.st.path("journal").read_text(encoding="utf-8")
  assert sum(f"{F1} deferred: triage 2" in line for line in journal.splitlines()) == 1
  assert foreman(w).get("followups", []) == []  # recorded, not yet posted: no row
  # the refuted medium blocks as in 1.2 until it is settled; then the round is clean with the deferral standing
  assert world.run("review", "status", "--review", w.rid, "--runcard", w.child)[0] == 3
  assert world.run("review", "settle", "--review", w.rid, "--finding", F2, "--disposition", "declined", "--owner",
                   "--runcard", w.child)[0] == 0
  code, out = post(world, w)
  outcome = foreman(w)["rounds"][0]["outcome"]
  assert (code, out.strip(), outcome) == (0, "posted clean", "clean"), (out, round_text(w), w.posted)
  comment = w.posted[0]["body"]
  assert "**Deferred by triage**" in comment and f"{F1} | deferred: triage 2" in comment.split("**Deferred by triage**")[1]
  followups = foreman(w)["followups"]
  assert followups == [{"fid": "change-review-1-1", "round": 1, "claim": claim,
                        "triage": {"reach": "forged", "later": "easy", "critical": "no", "verified": "confirmed src/a.py:3"},
                        "pattern": 2}]
  # recovery: the round's review already on the PR is counted again, the row not written twice
  data = foreman(w); data["rounds"][0].update({"phase": "collected"}); data["rounds"][0].pop("outcome"); save_foreman(w, data)
  assert post(world, w)[1].strip() == "posted clean (already on the PR)"
  followups_after_recovery_repost = foreman(w)["followups"]
  assert followups_after_recovery_repost == followups
  # round 2: the builder contests the deferred medium; collect raises nothing for it; round 2 is triaged, then superseded
  contest = ("builder: builder-bot\n### pr #70 comment 9 by builder-bot at 2026-11-04T13:00:00Z\n"
             f"**Reply {F1}:** contested — not reachable\n")
  did2, child2, _ = next_round(world, w, 2, comments=contest)
  collect_blocking_fids = {fid for f in json.loads(round_text(w, 2))["reviewers"]["foreman"]["findings"]
                           for fid in [F1, F2] if fid in f["claim"]}
  assert "F1" not in collect_blocking_fids and F1 not in collect_blocking_fids
  record(world, w.st, w.rid, 2, w.head, child2, {"change-review": M("change-review", n=2, claim=claim)})
  code, out = triage_file(world, w, reply.splitlines()[0].replace(F1, "change-review-2-1") + "\n", n=2)
  assert (code, out.strip()) == (0, "change-review-2-1 deferred: triage 2"), out
  next_round(world, w, 3)  # round 2 never posts: superseded by the next dispatch
  assert foreman(w)["rounds"][1]["outcome"] == "not run (superseded)"
  superseded_round_rows = [row for row in foreman(w)["followups"] if row["round"] == 2]
  assert superseded_round_rows == [] and foreman(w)["followups"] == followups


ISSUE = 2  # the unit's issue in `test_foreman.seed`
UPHELD = f"**Ruling:** {F1} finding upheld\n"


def owner_comment(world, cid, body, at="2026-11-03T10:00:00Z", login="owner"):
  """An owner's comment on the unit's issue, as `gh api repos/<repo>/issues/comments/<id>` returns it."""
  world.gh.comments.setdefault(ISSUE, []).append({
      "id": cid, "user": {"login": login}, "body": body, "created_at": at, "updated_at": at,
      "issue_url": f"https://api.github.com/repos/example-org/webhooks/issues/{ISSUE}"})


@pytest.mark.parametrize("patterns, deferred", [
    (PATTERNS, False), ([{"reach": "agent", "verified": "refuted"}], True),
])
def test_refuted_matches_only_a_verified_refuted_pattern(world, tmp_path, monkeypatch, patterns, deferred):
  """A medium triaged `refuted` matches a pattern only if the pattern names `verified: refuted` (section 5.2): a
  refuted line whose other fields match pattern 1 (`reach: agent`, no `verified`) is not deferred and blocks."""
  w = head(world, tmp_path, monkeypatch, {"change-review": M("change-review")}, patterns=patterns)
  code, out = triage_file(world, w, f"{F1} | reach: agent | later: easy | critical: no | verified: refuted no caller\n")
  assert (code, out.splitlines()) == (0, [f"{F1} deferred: triage 1"] if deferred else []), out
  assert finding_of(w, F1)["disposition"] == ("deferred: triage 1" if deferred else None)
  code, out = post(world, w)
  assert (code, foreman(w)["rounds"][0]["outcome"] == "clean") == (0, deferred), out


def deferred_round(world, tmp_path, monkeypatch, cap_one=False):
  """Round 1 posted `clean` with F1 deferred by triage (pattern 2) and F2 declined by the owner: one follow-up row."""
  from test_foreman import cap_at_one
  w = head(world, tmp_path, monkeypatch, {"change-review": M("change-review", claim="a forged payload reaches the hook")
                                          + M("change-review", 2, claim="b")}, base_files=A_PY)
  if cap_one:
    cap_at_one(w.st, w.rid)
  reply = (f"{F1} | reach: forged | later: easy | critical: no | verified: confirmed src/a.py:3\n"
           f"{F2} | reach: config | later: easy | critical: no | verified: refuted no caller reaches it\n")
  assert triage_file(world, w, reply)[0] == 0
  assert world.run("review", "settle", "--review", w.rid, "--finding", F2, "--disposition", "declined", "--owner",
                   "--runcard", w.child)[0] == 0
  code, out = post(world, w)
  assert (code, out.strip()) == (0, "posted clean"), out
  assert [r["fid"] for r in foreman(w)["followups"]] == [F1]
  world.gh.issues.setdefault(ISSUE, {"number": ISSUE, "id": 9002, "title": "U01", "body": "", "labels": [],
                                     "state": "open", "state_reason": None})  # what the undo's stopped-label check reads
  return w


def rule_posted(world, w, ruling, cid, by="owner"):
  return world.run("decision", "rule", "--unit", UNIT, "--ruling", ruling, "--by", by, "--posted", cid, "--runcard", w.card)


def open_point(world, w, tmp_path, point, text, source):
  path = tmp_path / f"q-{point}.md"
  path.write_text(text, encoding="utf-8")
  code, out = world.run("decision", "open", "--unit", UNIT, "--point", point, "--question", str(path), "--source", source,
                        "--runcard", w.card)
  assert code == 0, out
  return out.splitlines()[0]


@pytest.mark.parametrize("at_cap", [False, True])
def test_undo_on_latest_round(world, tmp_path, monkeypatch, at_cap):
  """`decision rule` without `--decision` checks an `upheld` on a deferred fid as the undo before `fid_decisions`: the
  disposition none, `undone_by`, a standalone `kind: undo` ruling, the row dropped, the latest posted `clean` rewritten
  (`revise`, `cap-reached` at the cap), an accept on the round lapsed, an older point-1 decision left unbound, triage
  off; the record binds, so a `fixed` reply before the undo leaves it unsettled after its comment is deleted."""
  from superegm.decision import recorded_rulings
  w = deferred_round(world, tmp_path, monkeypatch, cap_one=at_cap)
  if not at_cap:  # an accept given on the round below the cap, which the undo lapses
    path = w.st.path("reviews", w.rid, "review.json")
    rev = json.loads(path.read_text(encoding="utf-8"))
    rev["rulings"].append({"id": "R1", "ruling": "accept", "by": "owner", "at": "2026-11-03T09:30:00Z"})
    rev["converged"], rev["converged_round"] = "by ruling R1", 1
    atomic_write(path, rev)
    assert world.run("review", "status", "--review", w.rid, "--runcard", w.child)[0] == 0
  older = open_point(world, w, tmp_path, 1, "Is round 1 right?\n", f"review {w.rid} round 1")  # no finding line: any fid's
  owner_comment(world, 77, UPHELD)
  code, out = rule_posted(world, w, f"{F1} finding upheld", 77)
  assert code == 0, out
  finding = finding_of(w, F1)
  assert finding["disposition"] is None and finding["undone_by"] == "77"
  data = foreman(w)
  undo = next(r for r in data["rulings"] if r.get("kind") == "undo")
  assert undo["kind"] == "undo" and undo["decision"] is None and undo["posted"] == "comment 77"
  assert (undo["fid"], undo["by"], undo["ruling"], undo["posted_at"]) == (F1, "owner", f"{F1} finding upheld", "2026-11-03T10:00:00Z")
  assert undo["at"]
  followups, latest = data["followups"], data["rounds"][0]
  older_point1_decision_unbound = not any(r.get("decision") == older for r in data["rulings"])
  assert older_point1_decision_unbound
  assert followups == [] and latest["rewritten_from"] == "clean"
  assert any(f"{F1}" in line and "undo" in line for line in w.st.path("journal").read_text(encoding="utf-8").splitlines())
  recorded = recorded_rulings(data)
  assert any(r.kind == "upheld" and r.subject == F1 and r.comment_id == 77 for r in recorded)
  assert eligible(world, w) == ""  # triage off for the unit
  if at_cap:
    at_cap_latest = latest
    assert at_cap_latest["outcome"] == "cap-reached"
    return
  assert latest["outcome"] == "revise"
  early_accept_lapsed = any("R1 accept lapsed" in line for line in w.st.path("journal").read_text(encoding="utf-8").splitlines())
  assert early_accept_lapsed and world.run("review", "status", "--review", w.rid, "--runcard", w.child)[0] == 3
  assert rule_posted(world, w, f"{F1} finding upheld", 77)[0] == 1  # recorded once
  # the record's undo entry (decision null) breaks no reader that compares `r["decision"]`
  owner_comment(world, 79, f"**Ruling:** {F2} finding upheld\n")
  other_fid_upheld_after_undo = rule_posted(world, w, f"{F2} finding upheld", 79)
  assert other_fid_upheld_after_undo[0] == 0, other_fid_upheld_after_undo[1]
  open_point(world, w, tmp_path, 2, "One more round?\n", f"review {w.rid} cap")
  owner_comment(world, 80, "**Ruling:** one more round\n")
  one_more_round_after_undo = rule_posted(world, w, "one more round", 80)
  assert one_more_round_after_undo[0] == 0, one_more_round_after_undo[1]
  # round 2: the builder's `fixed` before the undo, the undo's comment deleted: the recorded undo still asks for one
  fixed = "builder: builder-bot\n### pr #70 comment 9 by builder-bot at 2026-11-03T09:00:00Z\n" f"**Reply {F1}:** fixed\n"
  _, child2, _ = next_round(world, w, 2, comments=fixed)
  claims = [f["claim"] for f in json.loads(round_text(w, 2))["reviewers"]["foreman"]["findings"]]
  fixed_reply_before_undo_then_comment_deleted_still_unsettled = f"upheld {F1}: no `fixed` reply" in claims
  assert fixed_reply_before_undo_then_comment_deleted_still_unsettled, claims
  record(world, w.st, w.rid, 2, w.head, child2, {"change-review": M("change-review", n=2, claim="a forged payload reaches the hook")})
  eligible_next_round = eligible(world, w, 2).split()
  assert eligible_next_round == []


@pytest.mark.parametrize("case", [
    "deferral of an earlier round", "foreman.stopped after a round with a deferred medium",
    "issue labelled stopped", "pull request merged, issue open", "pull request closed",
])
def test_undo_refusals_keep_the_followup(world, tmp_path, monkeypatch, case):
  """`decision rule` refuses the undo on a deferral of an earlier round, a stopped unit (`foreman.stopped` or the
  stopped label) and a merged or closed pull request: nothing recorded, the follow-up row kept, and the live `upheld`,
  dropped by `binding_rulings(..., deferred=)`, never reaches `collect`, the builder prompt or a later round."""
  from test_foreman import PR
  from superegm.decision import binding_rulings, overridden_comments, recorded_rulings
  w = deferred_round(world, tmp_path, monkeypatch)
  if case == "deferral of an earlier round":  # round 2 reviewed and posted on the moved head
    did2, child2, _ = next_round(world, w, 2)
    record(world, w.st, w.rid, 2, w.head, child2, {"change-review": M("change-review", n=2, sev="low", claim="c")})
    code, out = post(world, w, 2, did2, child2)
    assert code == 0, out
  elif case.startswith("foreman.stopped"):
    data = foreman(w)
    data["stopped"] = {"by": "owner", "reason": "enough", "at": "2026-11-03T09:00:00Z"}
    save_foreman(w, data)
  elif case == "issue labelled stopped":
    world.gh.issues[ISSUE]["labels"].append(w.st.config["labels"]["stopped"])
  elif case == "pull request merged, issue open":
    world.gh.prs[PR].update({"state": "MERGED", "mergedAt": "2026-11-03T08:00:00Z"})
  else:
    world.gh.prs[PR]["state"] = "CLOSED"
  followups_before, round_before = foreman(w)["followups"], round_text(w, 1)
  owner_comment(world, 77, UPHELD)
  code, out = rule_posted(world, w, f"{F1} finding upheld", 77)
  followups = foreman(w)["followups"]
  assert code == 1 and followups == followups_before, out
  assert round_text(w, 1) == round_before and not any(r.get("kind") == "undo" for r in foreman(w)["rulings"])
  comments = world.gh.comments[ISSUE]
  recorded = recorded_rulings(foreman(w))
  assert binding_rulings(comments, ["owner"], recorded, deferred=[F1]) == []
  overridden = overridden_comments(comments, ["owner"], foreman(w))
  assert overridden == {77: None}  # the builder prompt drops the live upheld
  if case == "deferral of an earlier round":  # a later round's `collect` reads the live comment and carries nothing
    upheld = f"### issue #{ISSUE} comment 77 by owner at 2026-11-03T10:00:00Z\n{UPHELD}"
    next_round(world, w, 3, comments=upheld)
    claims = [f["claim"] for f in json.loads(round_text(w, 3))["reviewers"]["foreman"]["findings"]]
    collect_blocking_fids = [c.split()[1].rstrip(":") for c in claims if c.startswith("upheld ")]
    assert F1 not in collect_blocking_fids, claims
