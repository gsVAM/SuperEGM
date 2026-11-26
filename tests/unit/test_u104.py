# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U104's tests: a foreman spec finding reaches the owner (1.3 design section 3.8).

"""U104: a `deviation (spec)` finding raised by `collect --spec` is the owner's alone, never the judges', and opens the round's
one point-1 decision at once, offering `<fid> respec` beside `finding upheld` and `finding overruled`."""

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

import superegm as core
from conftest import REPO, set_config
from superegm import collect, decision, report, review
from test_foreman import POSTED_R1, UNIT, c, open_head_review, prepared, seed
from test_wave import fake_gh, foreman_of, question, wave_store

ROOT = Path(__file__).resolve().parents[2]
SPEC = "deviation (spec) unruled: docs/designs/sample.md:12 says 3; `pytest -k t` fails"
HEAD = "a" * 40
LOCATIONS = {"deviation (spec)": "docs/designs/sample.md:12", "test-delta": "tests/unit/test_q.py:3", "tdd-order": "tests/unit/test_q.py"}


def finding(fid, claim, severity="high"):
  location = next((loc for prefix, loc in LOCATIONS.items() if claim.startswith(prefix)), "src/x.py:3")
  return {"id": fid, "severity": severity, "location": location, "regression": "no", "claim": claim,
          "disposition": None, "ruling": None}


def round_of(fid) -> int:
  return int(fid.split("-")[1])


def unit_world(world, open_findings, builder_contested, mode="normal", posted=False):
  """A wave card in `mode`, U01 with an opened head review whose round `n` (the round of the first fid) holds `open_findings` and
  `builder_contested`, round 1 an ordinary high foreman-1-1 when `n` is 2; U01's earlier rounds posted `revise`, round `n` collected
  with its gates run (or posted `revise` when `posted`), its dispatch `d<n>`."""
  extra = ["--mode", "leavemealone"] if mode == "leavemealone" else []
  card = world.run("runcard", "open", "--skill", "wave", "--artifact", world.spec, *extra, card=None)[1].strip()
  n = round_of(open_findings[0][0])
  s = wave_store(world, U01={"pr": 70, "head": HEAD, "ci": "green"})
  set_config(world, repo=REPO, owners=["owner"], reviewers={"spec": [], "plan": [], "head": ["change-review"], "integrate": []})
  rid = review.review_id(s, "head", "U01", 1)
  core.atomic_write(s.path("reviews", rid, "review.json"),
                    {"kind": "head", "artifact": "U01", "cycle": 1, "handoff_id": s.handoff_id, "scope": None,
                     "reviewers": ["change-review"], "cap": 5, "runcard": card, "artifact_sha256": "a" * 64,
                     "astra_incomplete": 0, "converged": "no", "converged_round": None, "rulings": []})
  for k in range(1, n + 1):
    found = [finding(fid, claim) for fid, claim in open_findings] if k == n else [finding("foreman-1-1", "the hook never fires")]
    core.atomic_write(s.path("reviews", rid, f"round-{k}.json"),
                      {"round": k, "runcard": card, "artifact_sha256": "a" * 64, "what_ran": "completed",
                       "builder_contested": [{"fid": fid, "reason": "r"} for fid in builder_contested] if k == n else [],
                       "reviewers": {"change-review": {"findings": []}, "foreman": {"findings": found}}})
  entry = lambda k: {"round": k, "runcard": card, "launch": 1, "head": HEAD, "dispatch_id": f"d{k}", "dod_runs": {}, "test_delta": []} \
      | ({"phase": "posted", "outcome": "revise", "posted_at": "2026-11-03T08:00:00Z"} if k < n or posted else {"phase": "collected"})
  core.atomic_write(s.path("foreman", "U01"), foreman_of(s, "U01") | {"dispatch_id": f"d{n}", "rounds": [entry(k) for k in range(1, n + 1)]})
  return SimpleNamespace(card=card, s=s, rid=rid, n=n)


def post_round(world, w) -> str:
  """`superegm review post` on round `n`, its review already on the pull request: the word it writes."""
  world.gh.reviews[70] = [{"id": 5, "commit_id": HEAD, "submitted_at": "2026-11-03T09:00:00Z", "body": review.header(w.n, HEAD)}]
  code, out = world.run("review", "post", "--unit", "U01", "--round", w.n, "--dispatch", f"d{w.n}", "--runcard", w.card)
  assert code == 0, out
  return next(e for e in foreman_of(w.s, "U01")["rounds"] if e["round"] == w.n)["outcome"]


def round_json(w, n=None) -> dict:
  return json.loads(w.s.path("reviews", w.rid, f"round-{n or w.n}.json").read_text(encoding="utf-8"))


# ---------------------------------------------------------------- S1: the owner's word


@pytest.mark.parametrize("open_findings, builder_contested, owner_fids", [
    ([("foreman-1-1", SPEC)], [], ["foreman-1-1"]),
    ([("foreman-1-1", "tdd-order: S1: no test commit"), ("foreman-1-2", SPEC)], [], ["foreman-1-2"]),
    ([("foreman-1-1", "test-delta: tests/unit/test_q.py:3 removed"), ("foreman-1-2", SPEC)], [], ["foreman-1-2", "foreman-1-1"]),
    ([("foreman-2-1", SPEC), ("foreman-2-2", "contested foreman-2-1: the code is right")], ["foreman-2-2"], ["foreman-2-1"]),
    ([("foreman-2-1", SPEC), ("foreman-2-3", "contested foreman-1-1: the test came first")], ["foreman-2-3"], ["foreman-2-1"]),
    ([("foreman-1-1", "tdd-order: S1: no test commit")], [], []),
])
def test_a_foreman_spec_finding_is_the_owners_word(world, open_findings, builder_contested, owner_fids):
  # a spec finding is owner-only, contested or not, even while the round has other blockers; `round_json` the round record
  # holding `open_findings` and `builder_contested`, `posted_outcome` the word `superegm review post` writes for it
  w = unit_world(world, open_findings, builder_contested)
  posted_outcome = post_round(world, w)
  assert review.owner_only_fids(round_json(w)) == owner_fids
  assert posted_outcome == ("owner: " + ", ".join(owner_fids) if owner_fids else "revise")


# ---------------------------------------------------------------- S2: the judges never ask it


def judges_question(world, w):
  code, out = world.run("judges", "question", "--review", w.rid, "--round", w.n, "--runcard", w.card)
  return code, out, (Path(out.splitlines()[0]).read_text(encoding="utf-8") if code == 0 else "")


@pytest.mark.parametrize("mode", ["normal", "leavemealone"])
def test_the_judges_never_rule_a_spec_finding(world, mode):
  # round 2 holds foreman-2-1 (SPEC) and the builder's contest of it, foreman-2-2 `contested foreman-2-1: the code is right`;
  # `superegm judges question --review <rid> --round 2`; then the same round with foreman-2-3, a contest of an ordinary high, as well
  contest = ("foreman-2-2", "contested foreman-2-1: the code is right")
  w = unit_world(world, [("foreman-2-1", SPEC), contest], ["foreman-2-2"], mode)
  posted_outcome = post_round(world, w)
  question_code, question_out, _ = judges_question(world, w)
  rnd = round_json(w)
  rnd["reviewers"]["foreman"]["findings"].append(finding("foreman-2-3", "contested foreman-1-1: the test came first"))
  rnd["builder_contested"].append({"fid": "foreman-2-3", "reason": "the test came first"})
  core.atomic_write(w.s.path("reviews", w.rid, "round-2.json"), rnd)
  code, out, question_with_an_ordinary_contest = judges_question(world, w)
  assert code == 0, out
  assert posted_outcome == "owner: foreman-2-1"
  assert question_code == 1 and "question: nothing to ask in round 2 of " in question_out
  assert "## Q1 foreman-2-3 (" in question_with_an_ordinary_contest and "foreman-2-1" not in question_with_an_ordinary_contest


# ---------------------------------------------------------------- S3: review settle leaves it to the owner


@pytest.mark.parametrize("mode", ["normal", "leavemealone"])
def test_review_settle_leaves_a_spec_finding_to_the_owner(world, mode):
  # round 2 holds foreman-2-1 (SPEC); `superegm review settle --review <rid> --finding foreman-2-1 --disposition contested
  # --judges <rid>-r2-abcdef`
  w = unit_world(world, [("foreman-2-1", SPEC)], [], mode, posted=True)
  settle_code, settle_err = world.run("review", "settle", "--review", w.rid, "--finding", "foreman-2-1", "--disposition", "contested",
                                      "--judges", f"{w.rid}-r2-abcdef", "--runcard", w.card)
  assert settle_code == 1 and "review settle: foreman-2-1 is the owner's alone: --owner required" in settle_err
  assert round_json(w)["reviewers"]["foreman"]["findings"][0]["disposition"] is None


# ---------------------------------------------------------------- S4: the owner's decision offers respec


SPEC_LINE = "foreman-1-2 | high | docs/designs/sample.md:12 | regression: no | " + SPEC
DELTA_LINE = "foreman-1-1 | high | tests/unit/test_q.py:3 | regression: no | test-delta: tests/unit/test_q.py:3 removed"


def word_world(world, word, mode="normal", comments=None):
  """A wave card in `mode`, U01 whose round 1 posted `word` (its head review never opened), and the owner's comments `comments`
  (id to body) on U01's issue."""
  extra = ["--mode", "leavemealone"] if mode == "leavemealone" else []
  card = world.run("runcard", "open", "--skill", "wave", "--artifact", world.spec, *extra, card=None)[1].strip()
  rounds = [{"round": 1, "phase": "posted", "outcome": word, "launch": 1, "runcard": card, "head": HEAD, "dispatch_id": "d1",
             "posted_at": "2026-11-03T09:00:00Z"}]
  s = wave_store(world, U01={"pr": 70, "head": HEAD, "ci": "green", "rounds": rounds})
  set_config(world, repo=REPO, owners=["owner"])
  routes = {f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": "owner"}, "body": body}
            for cid, body in (comments or {}).items()}
  fake_gh(world, routes)
  return SimpleNamespace(card=card, s=s, rid=review.review_id(s, "head", "U01", 1))


def open_q(world, w, text, n=1, unit="U01"):
  code, out = world.run("decision", "open", "--unit", unit, "--point", 1, "--question", question(world, text),
                        "--source", f"review {w.rid} round {n}", "--runcard", w.card)
  assert code == 0, out
  return out.splitlines()[0]


def rule(world, w, ruling, qid="q1", posted=None, unit="U01"):
  where = ["--posted", posted] if posted else ["--decision", qid]
  return world.run("decision", "rule", "--unit", unit, "--ruling", ruling, "--by", "owner", *where, "--runcard", w.card)


@pytest.mark.parametrize("lines, word, options", [
    ([SPEC_LINE], "owner: foreman-1-2", ["finding upheld", "finding overruled", "foreman-1-2 respec"]),
    (["## Q1 foreman-1-2 (high, docs/designs/sample.md:12): " + SPEC], "owner: foreman-1-2",
     ["finding upheld", "finding overruled", "foreman-1-2 respec"]),
    ([SPEC_LINE, DELTA_LINE], "owner: foreman-1-2, foreman-1-1",
     ["finding upheld", "finding overruled", "foreman-1-2 respec", "foreman-1-1 allowed"]),
])
def test_the_owner_decision_on_a_spec_finding_offers_respec(world, lines, word, options):
  # `superegm decision open --point 1` on the round whose word is `word`, the question file holding `lines`;
  # `stored_options` the decision's `options` in the unit's foreman file; on the last, `superegm decision rule --ruling
  # 'foreman-1-1 finding overruled — kept'` (read as the allowance) exits `allowance_code`, and on a fresh copy of it
  # `--ruling 'test-delta tests/unit/test_q.py allowed'` exits `file_code`
  w = word_world(world, word, comments={601: "**Ruling:** test-delta tests/unit/test_q.py allowed — kept"})
  open_q(world, w, "\n".join(lines) + "\n")
  stored_options = foreman_of(w.s, "U01")["decisions"][-1]["options"]
  fresh = w.s.path("foreman", "U01").read_bytes()
  allowance_code, allowance_out = rule(world, w, "foreman-1-1 finding overruled — kept")
  allowance_rulings = foreman_of(w.s, "U01")["rulings"]
  w.s.path("foreman", "U01").write_bytes(fresh)
  file_code, file_out = rule(world, w, "test-delta tests/unit/test_q.py allowed", posted=601)
  file_rulings = foreman_of(w.s, "U01")["rulings"]
  assert stored_options == options
  assert len(lines) == 1 or allowance_code == file_code == 0, (allowance_out, file_out)
  if len(lines) > 1:  # each recorded as the allowance of the test-delta fid, the spec fid left to its own ruling
    assert [r["ruling"] for r in allowance_rulings] == ["foreman-1-1 finding overruled — kept"]
    assert [r["ruling"] for r in file_rulings] == ["test-delta tests/unit/test_q.py allowed", "foreman-1-1 allowed"]


# ---------------------------------------------------------------- S5: the respec form; a doubled fid refused


SPEC_1_1 = "foreman-1-1 | high | docs/designs/sample.md:12 | regression: no | " + SPEC + "\n"


def open_respec_files(w) -> list:
  folder = w.s.path("file", "respec")
  return sorted(p.name for p in folder.iterdir()) if folder.is_dir() else []


def test_a_respec_ruling_parses_and_a_doubled_fid_is_refused(world):
  # `**Ruling:** foreman-1-1 respec — the spec is wrong` posted on the unit's issue and recorded with `superegm decision rule
  # --posted <comment id>`; then `--ruling 'foreman-1-1 foreman-1-1 respec'` typed on another spec finding's decision
  w = word_world(world, "owner: foreman-1-1", comments={601: "**Ruling:** foreman-1-1 respec — the spec is wrong"})
  open_q(world, w, SPEC_1_1)
  posted_code, posted_out = rule(world, w, "foreman-1-1 respec — the spec is wrong", posted=601)
  open_respec_files_before = open_respec_files(w)
  world.run("decision", "open", "--unit", "U01", "--point", 1, "--question",  # the next head round's spec finding, again foreman-1-1
            question(world, SPEC_1_1.replace("sample.md:12", "sample.md:40")), "--source", f"review {w.rid} round 2", "--runcard", w.card)
  rulings_before = foreman_of(w.s, "U01")["rulings"]
  doubled_code, doubled_err = rule(world, w, "foreman-1-1 foreman-1-1 respec", qid="q2")
  rulings_after, open_respec_files_after = foreman_of(w.s, "U01")["rulings"], open_respec_files(w)
  assert decision.parse_form("**Ruling:** foreman-1-1 respec — the spec is wrong")[:2] == ("respec", "foreman-1-1")
  assert posted_code == 0 and open_respec_files_before == ["R1.open.json"], posted_out
  assert doubled_code == 1 and doubled_err.startswith("decision: ") and "KeyError" not in doubled_err and "Traceback" not in doubled_err
  assert rulings_after == rulings_before and open_respec_files_after == open_respec_files_before


# ---------------------------------------------------------------- S6: an open respec file per unit, head cycle and fid


def test_open_respec_files_are_keyed_by_unit_cycle_and_fid(world):
  # foreman-1-1 ruled `respec` on a decision of head cycle c1 (its source naming c1's head review), then a new
  # foreman-1-1 of head cycle c2 ruled `respec` while R1 is still open; then c1's ruling is rerun
  w = word_world(world, "owner: foreman-1-1")
  c1, c2 = (review.review_id(w.s, "head", "U01", cycle) for cycle in (1, 2))
  for cycle, rid in ((1, c1), (2, c2)):
    code, out = world.run("decision", "open", "--unit", "U01", "--point", 1, "--question", question(world, SPEC_1_1),
                          "--source", f"review {rid} round 1", "--runcard", w.card)
    assert code == 0, out
    code, out = rule(world, w, "foreman-1-1 respec — the spec is wrong", qid=f"q{cycle}")
    assert code == 0, out
  open_files_after_c2 = open_respec_files(w)
  data = foreman_of(w.s, "U01")  # a crash after c1's open file and before its ruling was saved: the same ruling is rerun
  core.atomic_write(w.s.path("foreman", "U01"), data | {"rulings": [r for r in data["rulings"] if r["decision"] != "q1"]})
  rerun_code, rerun_out = rule(world, w, "foreman-1-1 respec — the spec is wrong", qid="q1")
  open_files_after_c1_rerun = open_respec_files(w)
  assert rerun_code == 0, rerun_out
  assert open_files_after_c2 == ["R1.open.json", "R2.open.json"]
  assert open_files_after_c1_rerun == ["R1.open.json", "R2.open.json"]
  held = {p: json.loads(w.s.path("file", "respec", p).read_text(encoding="utf-8")) for p in open_files_after_c1_rerun}
  assert [(h["finding"], h["cycle"]) for h in held.values()] == [("foreman-1-1", c1), ("foreman-1-1", c2)]
  assert "review" not in held["R1.open.json"]  # `approve-spec --respec` reads `review` as a closed review cycle
  legacy = {"id": "R1", "unit": "U01", "finding": "foreman-1-1", "at": "2026-11-03T09:00:00Z"}  # a 1.2.1 file, no `cycle`
  core.atomic_write(w.s.path("file", "respec", "R1.open.json"), legacy)
  assert decision.respec_held(w.s, "U01", finding="foreman-1-1", cycle=c1)[1] == legacy


# ---------------------------------------------------------------- S7: a ruling on a contest copy settles the spec finding


@pytest.mark.parametrize("ruling, raised", [
    ("**Ruling:** foreman-2-1 finding overruled — the code is right", False),
    ("**Ruling:** foreman-1-2 finding overruled — unrelated", True),
])
def test_a_ruling_on_a_contest_copy_settles_the_spec_finding(world, tmp_path, monkeypatch, ruling, raised):
  # round 1 raised foreman-1-1 (SPEC); round 2 held foreman-2-1 `contested foreman-1-1: the code is right`; round 3 runs without --spec
  posted_r2 = {**POSTED_R1, "round": 2, "dispatch_id": "d2", "posted_at": "2026-11-02T12:30:00Z"}
  kw = dict(rounds=[POSTED_R1, posted_r2], launches=[{"round": k, "status": "exited 0"} for k in (1, 2, 3)],
            comments={2: [c(20, "owner", ruling)]})
  st0, card0, _ = seed(world, **kw)
  rid = open_head_review(world, st0, card0, "0" * 40, {"change-review": "", "foreman": SPEC_1_1})
  first = json.loads(st0.path("reviews", rid, "round-1.json").read_text(encoding="utf-8"))
  held = first["reviewers"]["foreman"]["findings"][0] | {"carried_from": 1}
  contest = finding("foreman-2-1", "contested foreman-1-1: the code is right")
  core.atomic_write(st0.path("reviews", rid, "round-2.json"), first | {
      "round": 2, "builder_contested": [{"fid": "foreman-2-1", "reason": "the code is right"}],
      "reviewers": first["reviewers"] | {"foreman": {**first["reviewers"]["foreman"], "findings": [held, contest]}}})
  w = prepared(world, tmp_path, monkeypatch, **kw)
  code, out = world.run("collect", "--unit", UNIT, "--dispatch", w.did, "--runcard", w.child)
  assert code == 0, out
  round_3_foreman_claims = [f["claim"] for f in json.loads(w.st.path("reviews", w.rid, "round-3.json").read_text(encoding="utf-8"))
                            ["reviewers"]["foreman"]["findings"]]
  assert any(claim.startswith("deviation (spec) unruled: ") for claim in round_3_foreman_claims) is raised
  assert collect.SPEC_CLAIM is decision.SPEC_CLAIM
  assert "SPEC_CLAIM = " not in (ROOT / "skills/plan/scripts/superegm/collect.py").read_text(encoding="utf-8")


# ---------------------------------------------------------------- S8: the decision points name it


def test_decision_points_name_the_spec_finding_owner_only():
  # `spec_row` the line of `## The owner's findings` naming `deviation (spec)`: the owner's, never the judges', contested or not,
  # with respec offered; one decision for the round, its question also carrying the round's other contests, still asked of the
  # judges and ruled as Decision point 1 rules them
  text = (ROOT / "skills/wave/references/decision_points.md").read_text(encoding="utf-8")
  section = text.split("## The owner's findings")[1].split("\n## ")[0]
  spec_row = next(line for line in section.splitlines() if "deviation (spec)" in line)
  assert all(word in spec_row for word in ("finding upheld", "finding overruled", "<fid> respec", "contested or not",
                                           "one decision for the round"))
  assert "judges question --review <head-review-id> --round <n>" in spec_row and "Decision point 1" in spec_row


# ---------------------------------------------------------------- S9: a ruling on the spec finding closes its contest copy


COPY = ("foreman-2-2", "contested foreman-2-1: the code is right")
ORDINARY = ("foreman-2-3", "contested foreman-1-1: the test came first")


def line_of(f) -> str:
  return f"{f['id']} | {f['severity']} | {f['location']} | regression: no | {f['claim']}\n"


def spec_round_world(world, word="owner: foreman-2-1"):
  """U01's round 2 posted `word`, holding foreman-2-1 (SPEC), its contest copy foreman-2-2 and foreman-2-3, a contest of round
  1's ordinary high, both in `builder_contested`."""
  w = unit_world(world, [("foreman-2-1", SPEC), COPY, ORDINARY], ["foreman-2-2", "foreman-2-3"], posted=True)
  data = foreman_of(w.s, "U01")
  data["rounds"][-1]["outcome"] = word
  core.atomic_write(w.s.path("foreman", "U01"), data)
  return w


@pytest.mark.parametrize("named, rulings, open_after", [
    (["foreman-2-1", "foreman-2-2"], ["foreman-2-1 respec — the spec is wrong"], []),
    (["foreman-2-1", "foreman-2-2"], ["foreman-2-1 finding upheld"], []),
    (["foreman-2-1", "foreman-2-2", "foreman-2-3"], ["foreman-2-1 respec — the spec is wrong"], ["q1"]),
    (["foreman-2-1", "foreman-2-2", "foreman-2-3"], ["foreman-2-1 respec — the spec is wrong", "foreman-2-3 finding upheld"], []),
])
def test_a_ruling_on_the_spec_finding_closes_its_contest_copy(world, named, rulings, open_after):
  # round 2 holds foreman-2-1 (SPEC) and, in `builder_contested`, foreman-2-2 `contested foreman-2-1: the code is right` and
  # foreman-2-3, a contest of an ordinary high; q1, the round's point-1 decision on the word `owner: foreman-2-1`, its question
  # naming the fids `named` (a `<fid> |` line each), is ruled `rulings` with `superegm decision rule`;
  # `open_ids` the ids of `review.open_decisions` for the unit, what a respec's eligibility reads
  w = spec_round_world(world)
  found = {f["id"]: f for f in round_json(w)["reviewers"]["foreman"]["findings"]}
  open_q(world, w, "".join(line_of(found[fid]) for fid in named), n=2)
  for ruling in rulings:
    code, out = rule(world, w, ruling)
    assert code == 0, out
  open_ids = [d["id"] for d in review.open_decisions(w.s, "U01")]
  assert open_ids == open_after


# ---------------------------------------------------------------- S10: pending until each fid is ruled


def ruled_file(word, options, split, rulings, found=None) -> dict:
  """The unit's foreman file: round 2 posted `word`, q1 its point-1 decision with `options` opened on that word (its `word`,
  as `decision open` records it, absent on a 1.2.1 decision when `word` is None), ruled `rulings` in order; its question names
  `found` (findings), else the split panel's three findings and verdict line, else one line per option's fid."""
  if found is not None:
    text = "".join(line_of(f) for f in found)
  elif split:
    found = [finding("foreman-2-1", SPEC), finding(*COPY), finding(*ORDINARY)]
    text = "".join(line_of(f) for f in found) + "The panel split: see (judges/p-1/verdict.json).\n"
  else:
    text = "".join(line_of(finding(o.split(" ")[0], SPEC if o.endswith(" respec") else "test-delta: tests/unit/test_q.py:3 removed"))
                   for o in options if o.endswith((" respec", " allowed")))
  return {"rounds": [{"round": 2, "phase": "posted", "outcome": word or "contested: foreman-1-2"}],
          "decisions": [{"id": "q1", "point": 1, "source": "review head-U01-c1 round 2", "question": text, "options": options}
                        | ({"word": word} if word else {})],
          "rulings": [{"decision": "q1", "ruling": r, "by": "owner"} for r in rulings]}


@pytest.mark.parametrize("word, options, split, first, second", [
    ("owner: foreman-1-1, foreman-1-2", ["finding upheld", "finding overruled", "foreman-1-1 respec", "foreman-1-2 respec"],
     False, "foreman-1-1 respec — the spec is wrong", "foreman-1-2 finding upheld"),
    ("owner: foreman-1-2, foreman-1-1", ["finding upheld", "finding overruled", "foreman-1-2 respec", "foreman-1-1 allowed"],
     False, "foreman-1-2 respec — the spec is wrong", "foreman-1-1 allowed — kept"),
    ("owner: foreman-2-1", ["finding upheld", "finding overruled", "foreman-2-1 respec"],
     True, "foreman-2-1 respec — the spec is wrong", "foreman-2-3 finding upheld"),
])
def test_a_spec_finding_decision_stays_pending_until_each_fid_is_ruled(word, options, split, first, second):
  # q1, the point-1 decision on `word` with `options`; with `split`, its question names foreman-2-1 (SPEC), its contest copy
  # foreman-2-2 `contested foreman-2-1: the code is right` and foreman-2-3, an ordinary high's contest, and holds the split
  # panel's `(judges/p-1/verdict.json)` line; `after_first` the unit's foreman file once q1 is ruled `first`,
  # `after_both` once it is ruled `second` too
  after_first, after_both = ruled_file(word, options, split, [first]), ruled_file(word, options, split, [first, second])
  assert [d["id"] for d in report.pending_decisions(after_first)] == ["q1"]
  assert report.pending_decisions(after_both) == []


# ---------------------------------------------------------------- S11: the inbox offers its rulings


def test_the_inbox_offers_a_spec_findings_rulings(world):
  # U01's latest posted round (round 2) holds foreman-2-1 (SPEC) and, in `builder_contested`, its contest copy foreman-2-2
  # `contested foreman-2-1: the code is right`; its word `owner: foreman-2-1`, q1 open; `items` and `after_items` U01's items of
  # `superegm inbox --json` before and after q1 is ruled `foreman-2-1 finding overruled — the code is right`
  w = unit_world(world, [("foreman-2-1", SPEC), COPY], ["foreman-2-2"], posted=True)
  data = foreman_of(w.s, "U01")
  data["rounds"][-1]["outcome"] = "owner: foreman-2-1"
  core.atomic_write(w.s.path("foreman", "U01"), data)
  core.atomic_write(w.s.path("handoffs", w.s.handoff_id), {"id": w.s.handoff_id, "spec": str(world.spec), "opened_at": "t", "closed_at": None})
  found = {f["id"]: f for f in round_json(w)["reviewers"]["foreman"]["findings"]}
  open_q(world, w, line_of(found["foreman-2-1"]) + line_of(found["foreman-2-2"]), n=2)
  inbox = lambda: [i for i in map(json.loads, world.run("inbox", "--json")[1].splitlines()) if i["subject"] == "U01"]
  items = inbox()
  code, out = rule(world, w, "foreman-2-1 finding overruled — the code is right")
  assert code == 0, out
  after_items = inbox()
  assert [i["forms"] for i in items if i["kind"] == "owner"] == [["**Ruling:** foreman-2-1 finding upheld",
                                                                "**Ruling:** foreman-2-1 finding overruled — <reason>",
                                                                "**Ruling:** foreman-2-1 respec — <reason>"]]
  assert not any(i["fingerprint"].endswith("/foreman-2-2") for i in items + after_items)  # the pair is one item
  assert not any(i["kind"] in ("owner", "contested") for i in after_items)
  # the owner's overrule settles the spec finding `declined`, as on any `owner: <ids>` decision
  assert {f["id"]: f["disposition"] for f in round_json(w)["reviewers"]["foreman"]["findings"]}["foreman-2-1"] == "declined"


# ---------------------------------------------------------------- review round 1 (PR #301)


def pair_world(world, mode="normal", comments=None, more=()):
  """U01's round 2 posted `owner: foreman-2-1`, holding foreman-2-1 (SPEC), its contest copy foreman-2-2 (in
  `builder_contested`) and `more`; q1 open on the word, its question naming the pair; the owner's comments `comments` (id to
  body) on U01's issue."""
  w = unit_world(world, [("foreman-2-1", SPEC), COPY, *more], ["foreman-2-2"], mode, posted=True)
  data = foreman_of(w.s, "U01")
  data["rounds"][-1]["outcome"] = "owner: foreman-2-1"
  core.atomic_write(w.s.path("foreman", "U01"), data)
  core.atomic_write(w.s.path("handoffs", w.s.handoff_id), {"id": w.s.handoff_id, "spec": str(world.spec), "opened_at": "t", "closed_at": None})
  fake_gh(world, {f"repos/{REPO}/issues/comments/{cid}": {"id": cid, "user": {"login": "owner"}, "body": body}
                  for cid, body in (comments or {}).items()})
  found = {f["id"]: f for f in round_json(w)["reviewers"]["foreman"]["findings"]}
  open_q(world, w, line_of(found["foreman-2-1"]) + line_of(found["foreman-2-2"]), n=2)
  return w


def dispositions(w) -> dict:
  return {f["id"]: f["disposition"] for f in round_json(w)["reviewers"]["foreman"]["findings"]}


@pytest.mark.parametrize("mode", ["normal", "leavemealone"])
def test_the_judges_never_rule_a_spec_findings_contest_copy(world, mode):
  # astra-1-1: the copy foreman-2-2 `contested foreman-2-1: …` is the owner's as its spec original is: `review settle --judges`
  # refuses it, `decision rule --by judges:<panel>` refuses it, nothing recorded; and `collect` reads no judges' ruling on a
  # copy as settling the spec finding it reaches
  w = pair_world(world, mode)
  panel = f"{w.rid}-r2-abcdef"
  settle_code, settle_err = world.run("review", "settle", "--review", w.rid, "--finding", "foreman-2-2", "--disposition", "contested",
                                      "--judges", panel, "--runcard", w.card)
  before = foreman_of(w.s, "U01")["rulings"]
  rule_code, rule_err = world.run("decision", "rule", "--unit", "U01", "--decision", "q1", "--ruling",
                                  "foreman-2-2 finding overruled — the panel", "--by", f"judges:{panel}", "--runcard", w.card)
  assert settle_code == 1 and "review settle: foreman-2-2 is the owner's alone: --owner required" in settle_err
  assert rule_code == 1 and "decision: foreman-2-2 is the owner's alone" in rule_err
  assert foreman_of(w.s, "U01")["rulings"] == before and dispositions(w)["foreman-2-2"] is None
  last = {"reviewers": {"foreman": {"findings": [finding("foreman-2-1", SPEC)]}}}
  judges = decision.Ruling("overruled", "foreman-2-2", None, "the panel", f"judges:{panel}", 0)
  owners = decision.Ruling("overruled", "foreman-2-2", None, "the code is right", "owner", 0)
  links = {"foreman-2-2": "foreman-2-1"}
  assert [claim for _, claim in collect.unruled_specs(last, [judges], links)] == [SPEC]
  assert collect.unruled_specs(last, [owners], links) == []


@pytest.mark.parametrize("mode, ruled", [("normal", "foreman-2-2"), ("normal", "foreman-2-1"),
                                         ("leavemealone", "foreman-2-2"), ("leavemealone", "foreman-2-1")])
def test_an_overrule_of_either_of_the_pair_settles_both(world, mode, ruled):
  # astra-1-3, codebase-details-1-1: the owner's overrule of the copy settles the spec finding too; codebase-details-1-2: the
  # owner's overrule of the spec finding closes its copy in the round record; either way the round is clean, q1 closed, and the
  # inbox lists neither; in leavemealone-mode by the owner's posted comment
  w = pair_world(world, mode, comments={601: f"**Ruling:** {ruled} finding overruled — the code is right"})
  code, out = rule(world, w, f"{ruled} finding overruled — the code is right", posted=601 if mode == "leavemealone" else None)
  assert code == 0, out
  assert dispositions(w) == {"foreman-2-1": "declined", "foreman-2-2": "contested"}
  assert report.pending_decisions(foreman_of(w.s, "U01")) == [] and review.open_decisions(w.s, "U01") == []
  assert next(e for e in foreman_of(w.s, "U01")["rounds"] if e["round"] == 2)["outcome"] == "clean"


def test_a_closed_pairs_copy_stays_out_of_the_inbox_once_the_word_moves_on(world):
  # change-review-1-1: the spec finding ruled, the round still open on another high, its word rewritten past the spec fid: the
  # copy, whose chain reaches a fid q1 ruled, is never a `contested` item of its own
  w = pair_world(world, more=[("foreman-2-4", "tdd-order: S1: no test commit")])
  code, out = rule(world, w, "foreman-2-1 finding upheld")
  assert code == 0, out
  data = foreman_of(w.s, "U01")
  data["rounds"][-1]["outcome"] = "revise"
  core.atomic_write(w.s.path("foreman", "U01"), data)
  items = [i for i in map(json.loads, world.run("inbox", "--json")[1].splitlines()) if i["subject"] == "U01"]
  assert not any(i["fingerprint"].endswith("/foreman-2-2") for i in items)


@pytest.mark.parametrize("posted_with_decision", [False, True])
def test_a_spec_fid_ruled_in_one_head_cycle_is_ruled_again_in_the_next(world, posted_with_decision):
  # astra-1-2: foreman-1-1 ruled `respec` on c1's q1; the owner's posted `foreman-1-1 respec` for c2's q2 is recorded there,
  # with or without --decision, and writes c2's own open file
  w = word_world(world, "owner: foreman-1-1", comments={601: "**Ruling:** foreman-1-1 respec — again"})
  c1, c2 = (review.review_id(w.s, "head", "U01", cycle) for cycle in (1, 2))
  for qid, rid in (("q1", c1), ("q2", c2)):
    code, out = world.run("decision", "open", "--unit", "U01", "--point", 1, "--question", question(world, SPEC_1_1),
                          "--source", f"review {rid} round 1", "--runcard", w.card)
    assert code == 0, out
    if qid == "q1":
      assert rule(world, w, "foreman-1-1 respec — the spec is wrong")[0] == 0
  argv = ["decision", "rule", "--unit", "U01", "--ruling", "foreman-1-1 respec — again", "--by", "owner", "--posted", 601,
          "--runcard", w.card] + (["--decision", "q2"] if posted_with_decision else [])
  code, out = world.run(*argv)
  assert code == 0, out
  assert [r["decision"] for r in foreman_of(w.s, "U01")["rulings"]] == ["q1", "q2"]
  assert open_respec_files(w) == ["R1.open.json", "R2.open.json"]


def test_a_spec_decision_stays_pending_on_each_contest_its_question_names(world):
  # astra-1-4: q1 names foreman-2-1 (SPEC) and foreman-2-3, an ordinary contest with no verdict line yet: pending until both are
  # ruled, so `decision open` refuses a second decision meanwhile
  found = [finding("foreman-2-1", SPEC), finding(*ORDINARY)]
  options = ["finding upheld", "finding overruled", "foreman-2-1 respec"]
  first = ruled_file("owner: foreman-2-1", options, False, ["foreman-2-1 respec — the spec is wrong"], found)
  both = ruled_file("owner: foreman-2-1", options, False, ["foreman-2-1 respec — the spec is wrong", "foreman-2-3 finding upheld"], found)
  assert [d["id"] for d in report.pending_decisions(first)] == ["q1"] and report.pending_decisions(both) == []


def test_a_1_2_1_decision_with_a_respec_option_closes_at_its_first_ruling():
  # codebase-details-1-4: a 1.2.1 contest decision (no `word`) holding the foreman's spec line beside an ordinary finding, as
  # U84's `finding_decision`, closes at its first ruling as it did: a 1.2.1 store opens unchanged
  found = [finding("foreman-1-1", SPEC), finding("foreman-1-2", "the hook never fires")]
  options = ["finding upheld", "finding overruled", "foreman-1-1 respec"]
  assert report.pending_decisions(ruled_file(None, options, False, ["foreman-1-2 finding upheld"], found)) == []


# ---------------------------------------------------------------- review round 2 (PR #301)


def set_round(w, n, findings, contested=()):
  """Round `n`'s foreman findings and `builder_contested` rewritten in U01's head review."""
  rnd = round_json(w, n)
  rnd["reviewers"]["foreman"]["findings"] = [finding(fid, claim) for fid, claim in findings]
  rnd["builder_contested"] = [{"fid": fid, "reason": "r"} for fid in contested]
  core.atomic_write(w.s.path("reviews", w.rid, f"round-{n}.json"), rnd)


def set_word(w, word):
  data = foreman_of(w.s, "U01")
  data["rounds"][-1]["outcome"] = word
  core.atomic_write(w.s.path("foreman", "U01"), data)


def test_a_contest_chain_through_an_earlier_round_reaches_its_spec_finding(world):
  # astra-2-2: q1 names the spec finding foreman-1-1 and foreman-3-1 `contested foreman-2-1: …`, where foreman-2-1, held in
  # round 2 alone, contests foreman-1-1: the chain the question cannot show is the one `decision open` records, so the respec
  # of foreman-1-1 rules foreman-3-1 too and q1 closes
  w = unit_world(world, [("foreman-3-1", "contested foreman-2-1: the code is right"), ("foreman-1-1", SPEC)], ["foreman-3-1"], posted=True)
  set_round(w, 2, [("foreman-2-1", "contested foreman-1-1: the code is right")])
  set_word(w, "owner: foreman-1-1")
  found = {f["id"]: f for f in round_json(w)["reviewers"]["foreman"]["findings"]}
  open_q(world, w, line_of(found["foreman-1-1"]) + line_of(found["foreman-3-1"]), n=3)
  code, out = rule(world, w, "foreman-1-1 respec — the spec is wrong")
  assert code == 0, out
  assert report.pending_decisions(foreman_of(w.s, "U01")) == [] and review.open_decisions(w.s, "U01") == []


def test_an_upheld_contest_copy_rules_its_spec_finding_once(world):
  # astra-2-3: `foreman-2-2 finding upheld` on the copy rules the pair: the inbox offers foreman-2-1 no more, and a later ruling
  # on foreman-2-1 is refused as already ruled, nothing recorded
  w = pair_world(world)
  code, out = rule(world, w, "foreman-2-2 finding upheld")
  assert code == 0, out
  items = [i for i in map(json.loads, world.run("inbox", "--json")[1].splitlines()) if i["subject"] == "U01"]
  before = foreman_of(w.s, "U01")["rulings"]
  again_code, again_out = rule(world, w, "foreman-2-1 respec — the spec is wrong")
  assert not any(i["kind"] == "owner" for i in items)
  assert again_code == 1 and "already ruled" in again_out and foreman_of(w.s, "U01")["rulings"] == before


def test_a_file_allowance_on_a_spec_decision_rules_a_test_delta_contest_copy(world):
  # codebase-details-2-1: q1 names the spec finding foreman-2-1, the test-delta foreman-2-2 and foreman-2-3, the builder's copy
  # `contested foreman-1-1: …` of round 1's test-delta finding of the same file: the owner's `test-delta <file> allowed`
  # rules foreman-2-2 allowed and the copy overruled, as on a 1.2.1 contest decision
  w = unit_world(world, [("foreman-2-1", SPEC), ("foreman-2-2", "test-delta: tests/unit/test_q.py:5 removed"),
                         ("foreman-2-3", "contested foreman-1-1: the test moved")], ["foreman-2-3"], posted=True)
  set_round(w, 1, [("foreman-1-1", "test-delta: tests/unit/test_q.py:3 removed")])
  set_word(w, "owner: foreman-2-1, foreman-2-2")
  fake_gh(world, {f"repos/{REPO}/issues/comments/601": {"id": 601, "user": {"login": "owner"},
                                                       "body": "**Ruling:** test-delta tests/unit/test_q.py allowed — moved"}})
  open_q(world, w, "".join(line_of(f) for f in round_json(w)["reviewers"]["foreman"]["findings"]), n=2)
  code, out = rule(world, w, "test-delta tests/unit/test_q.py allowed", posted=601)
  assert code == 0, out
  assert [r["ruling"] for r in foreman_of(w.s, "U01")["rulings"]] == [
      "test-delta tests/unit/test_q.py allowed", "foreman-2-2 allowed", "foreman-2-3 finding overruled"]
  assert rule(world, w, "foreman-2-1 respec — the spec is wrong")[0] == 0
  assert report.pending_decisions(foreman_of(w.s, "U01")) == [] and review.open_decisions(w.s, "U01") == []


# ---------------------------------------------------------------- review round 3 (PR #301)


@pytest.mark.parametrize("copy_first", [True, False])
def test_a_test_delta_finding_and_its_contest_copy_are_ruled_apart(world, copy_first):
  # codebase-details-3-1: q1 names the spec finding foreman-2-1, the carried test-delta foreman-1-1 and the builder's copy
  # foreman-2-2 `contested foreman-1-1: …`; only a spec pair is ruled as one, so the copy's overrule leaves foreman-1-1 to its
  # own `allowed`, and foreman-1-1's allowance leaves the copy open to its own ruling, in the inbox too
  delta = "test-delta: tests/unit/test_q.py:3 removed"
  w = unit_world(world, [("foreman-2-1", SPEC), ("foreman-1-1", delta), ("foreman-2-2", "contested foreman-1-1: the test moved")],
                 ["foreman-2-2"], posted=True)
  set_round(w, 1, [("foreman-1-1", delta)])
  set_word(w, "owner: foreman-2-1, foreman-1-1")
  core.atomic_write(w.s.path("handoffs", w.s.handoff_id), {"id": w.s.handoff_id, "spec": str(world.spec), "opened_at": "t", "closed_at": None})
  open_q(world, w, "".join(line_of(f) for f in round_json(w)["reviewers"]["foreman"]["findings"]), n=2)
  order = ["foreman-2-2 finding overruled — the test moved", "foreman-1-1 allowed — kept"]
  first, second = order if copy_first else order[::-1]
  assert rule(world, w, first)[0] == 0
  between = [i["fingerprint"] for i in map(json.loads, world.run("inbox", "--json")[1].splitlines()) if i["subject"] == "U01"]
  pending_between = [d["id"] for d in report.pending_decisions(foreman_of(w.s, "U01"))]
  code, out = rule(world, w, second)
  assert code == 0, out
  assert pending_between == ["q1"]
  assert ("U01/owner/2/foreman-1-1" in between) if copy_first else ("U01/contested/q1/foreman-2-2" in between)
  assert dispositions(w)["foreman-1-1"] == "declined" and dispositions(w)["foreman-2-2"] == "contested"
  assert rule(world, w, "foreman-2-1 respec — the spec is wrong")[0] == 0
  assert report.pending_decisions(foreman_of(w.s, "U01")) == [] and review.open_decisions(w.s, "U01") == []
