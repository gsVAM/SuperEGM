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
from superegm import review
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
