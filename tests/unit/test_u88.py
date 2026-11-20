# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U88's tests: the judges rule a builder's contest first (design section 7.8).

"""U88: a builder's contest of a head finding goes to the judges' panel first in normal mode as in leavemealone."""

import json
from pathlib import Path

import pytest

import superegm as core
from test_leavemealone_finish import head_review, put, seed
from test_review import A, F, head_round, hstore, opened, rjson, settle
from test_review import record as record_findings
from test_wave import REPO, fake_gh, foreman_of, wave_store
from test_wave import question as write_question

COMMENTS_TEXT = "change-review-1-1 | high | src/x.py:3 | the retry loop never backs off\n"
DIFF_TEXT = "--- a/src/x.py\n+++ b/src/x.py\n@@ -3 +3 @@\n-retry()\n+retry(backoff=1)\n"
BODY_TEXT = "### U07: Retry\n\n## Objective\nDeliver with a bounded retry.\n"
SPEC_RANGE_TEXT = "### 4.2 Retries\nA retry waits before it tries again.\n"
AMENDMENTS_TEXT = "amendment 1: the wait is one second.\n"


def evidence(world, body=BODY_TEXT):
  """The five evidence files of a head contest, written beside the repo: `comments.md`, the diff, the body, `r1/spec_range.md`, `r1/amendments.md`."""
  folder = world.repo.parent / "evidence"
  files = {"comments.md": COMMENTS_TEXT, "diff": DIFF_TEXT, "body": body,
           "r1/spec_range.md": SPEC_RANGE_TEXT, "r1/amendments.md": AMENDMENTS_TEXT}
  for name, text in files.items():
    (folder / name).parent.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")
  return [str(folder / name) for name in files]


def contest(world, tmp_path, body=BODY_TEXT):
  """A normal-mode head review of U07 with a high finding the builder contested; its opened panel and question text."""
  seed(world)
  runcard = world.card("wave")
  review = head_review(world, runcard, tmp_path)
  code, out = world.run("judges", "question", "--review", review, "--round", "1",
                        "--reason", "change-review-1-1=the test covers it", "--runcard", runcard)
  assert code == 0, out
  path = Path(out.splitlines()[0])
  flags = [part for item in evidence(world, body) for part in ("--evidence", item)]
  code, out = world.run("judges", "open", "--question", str(path), *flags, "--parent", runcard)
  assert code == 0, out
  return out.strip(), path.read_text(encoding="utf-8")


def test_head_contest_goes_to_the_panel(world, tmp_path):
  """A normal-mode head contest renders the panel question with the five evidence files, inlined for Astra."""
  pid, question = contest(world, tmp_path)
  assert all(f") {o}" in question for o in ("finding upheld", "finding overruled — ", "redesign — "))
  astra_brief = (world.artifacts / "judges" / pid / "round-1" / "brief-astra.md").read_text(encoding="utf-8")
  assert all(name in astra_brief for name in ("comments.md", "diff", "body", "r1/spec_range.md", "r1/amendments.md"))
  assert AMENDMENTS_TEXT in astra_brief and SPEC_RANGE_TEXT in astra_brief and COMMENTS_TEXT in astra_brief


def record_round(world, pid, card, rnd, votes):
  """Record each judge's vote for round `rnd` (`votes` maps judge to option letter), as `judges record` takes it."""
  for judge, option in votes.items():
    verdict = world.repo.parent / f"{pid}-r{rnd}-{judge}.md"
    verdict.write_text(f"Q1: ({option})\n", encoding="utf-8")
    code, text = world.run("judges", "record", "--panel", pid, "--round", rnd, "--judge", judge, "--verdict", verdict,
                           "--isolation", "clean", "--runcard", card)
    assert code == 0, text


def test_astra_evidence_fence_outgrows_the_evidence(world, tmp_path):
  """An evidence file holding a ``` line is fenced by a longer run, so it never ends its block early."""
  body = "### U07\n\n```python\nretry()\n```\n\n````markdown\nnested\n````\n"
  pid, _ = contest(world, tmp_path, body)
  astra = (world.artifacts / "judges" / pid / "round-1" / "brief-astra.md").read_text(encoding="utf-8")
  assert f"`````\n{body.rstrip(chr(10))}\n`````\n" in astra  # one longer than the body's longest run of four
  for text in (COMMENTS_TEXT, DIFF_TEXT):  # a file with no backtick keeps the three-backtick fence
    assert f"```\n{text.rstrip(chr(10))}\n```\n" in astra


def test_an_undecodable_diff_opens_the_panel_and_reaches_astra_with_a_replacement(world, tmp_path, monkeypatch):
  """Round 5 (astra-4-3): a diff of a Latin-1 file is not UTF-8; the panel still opens, nothing is left half-written, and the Astra brief
  carries the diff decoded with replacement characters, as `prepare.cut_diff` decodes it."""
  real = evidence
  def latin_diff(world, body=BODY_TEXT):
    files = real(world, body)
    Path(files[1]).write_bytes(DIFF_TEXT.encode("utf-8") + "+caf\xe9 = 1\n".encode("latin-1"))
    return files
  monkeypatch.setitem(globals(), "evidence", latin_diff)
  pid, _ = contest(world, tmp_path)
  folder = world.artifacts / "judges" / pid
  astra = (folder / "round-1" / "brief-astra.md").read_text(encoding="utf-8")
  assert "+caf� = 1" in astra and (folder / "panel.json").is_file() and (folder / "round-1" / "brief.md").is_file()


def panel_with_round_one(world, tmp_path):
  pid, _ = contest(world, tmp_path)
  folder = world.artifacts / "judges" / pid
  card = json.loads((folder / "panel.json").read_text(encoding="utf-8"))["runcard"]
  record_round(world, pid, card, 1, {"fable": "a", "opus": "b", "astra": "a"})
  return pid, card, folder


@pytest.mark.parametrize("change", ["edited", "removed"])
def test_a_changed_evidence_file_refuses_the_astra_brief(world, tmp_path, change):
  """`judges: evidence <path> changed since open` when an evidence file's sha256 differs or the file is gone; the refused
  `judges diff` leaves the round as it was: no `diff.md`, no next round's briefs."""
  pid, card, folder = panel_with_round_one(world, tmp_path)
  target = world.repo.parent / "evidence" / "r1" / "amendments.md"
  if change == "edited":
    target.write_text("amendment 1: the wait is two seconds.\n", encoding="utf-8")
  else:
    target.unlink()
  code, text = world.run("judges", "diff", "--panel", pid, "--round", 1, "--runcard", card)
  assert code != 0 and f"judges: evidence {target.resolve()} changed since open" in text, text
  assert not (folder / "round-1" / "diff.md").exists()
  assert not (folder / "round-2").exists()


def journal_of(st):
  return st.path("journal").read_text(encoding="utf-8")


PANEL_QUESTION = ("## Q1 change-review-1-1 (high, src/x.py): claim 1\n- (a) finding upheld\n- (b) finding overruled — the test covers it\n"
                  "- (c) redesign — claim 1\n")


def settled_panel(world, converged="b", pid="p1", question=PANEL_QUESTION, split=None):
  """A panel `pid` in the head's store whose verdict converged on option `converged` of Q1 (None: not converged); `split`: a
  second question Q2, still split at the cap, appended to the question file."""
  folder = hstore(world).path("judges", pid, "question.md").parent
  folder.mkdir(parents=True, exist_ok=True)
  (folder / "question.md").write_text(question + (split or ""), encoding="utf-8")
  q1 = {"converged": converged is not None, "option": converged, "round": 1, "positions": {}, "vendors": [], "reason": None}
  questions = {"Q1": q1} | ({"Q2": q1 | {"converged": False, "option": None}} if split else {})
  core.atomic_write(folder / "verdict.json", {"panel": pid, "questions": questions, "open": [k for k, q in questions.items() if not q["converged"]],
                                              "converged": all(q["converged"] for q in questions.values())})


def panel_of(rid, rnd=1, tail="a1b2c3"):
  """The id of a panel opened for review `rid` round `rnd`: `<question stem>-<6 hex>`, the stem as `question_name` gives it."""
  return f"{rid}-r{rnd}-{tail}"


@pytest.mark.parametrize("kind, disposition, rc, out", [
    ("head", "declined", 0, "Ruling (judges {pid}, contest): U07 change-review-1-1 declined"),
    ("head", "contested", 0, "Ruling (judges {pid}, contest): U07 change-review-1-1 contested"),
    ("spec", "declined", 1, "review settle: design-1-1 is high: --owner required in normal mode"),
    ("plan", "declined", 1, "review settle: set-1-1 is high: --owner required in normal mode"),
    ("integrate", "declined", 1, "review settle: design-1-1 is high: --owner required in normal mode")])
def test_settle_judges_by_card_kind(world, kind, disposition, rc, out):
  """`--judges` settles a contested head finding on a normal-mode card, opening no owner question; every other review keeps `--owner`."""
  reviewer = {"head": "change-review", "spec": "design", "plan": "set", "integrate": "design"}[kind]
  spec, cid, rid = opened(world, kind)
  pid = panel_of(rid)
  out = out.format(pid=pid)
  if kind == "head":
    head_round(world, 1, "posted", cid, "revise")
    settled_panel(world, pid=pid)
  loc = "src/x.py" if kind == "head" else "§1"
  assert record_findings(world, rid, 1, reviewer, [F(reviewer, 1, 1, "high", loc=loc)], cid, sha=A if kind == "head" else None)[0] == 0
  code, text = settle(world, rid, f"{reviewer}-1-1", disposition, cid, "--judges", pid)
  finding = rjson(world, rid, "round-1.json")["reviewers"][reviewer]["findings"][0]
  journal = journal_of(hstore(world)) if rc == 0 else ""
  assert code == rc and out in (journal if rc == 0 else text), text
  assert (finding["disposition"], finding["ruling"]) == ((disposition, f"judges:{pid}") if rc == 0 else (None, None))
  # what still waits for the owner: a decision or owner outcome in the unit's record, or the finding left unsettled
  foreman = foreman_of(hstore(world), "U07") if kind == "head" else {"decisions": [], "rounds": []}
  owner_questions = foreman["decisions"] + [e for e in foreman["rounds"] if str(e.get("outcome") or "").startswith("owner:")] \
      + (["unsettled finding"] if finding["disposition"] is None else [])
  assert (owner_questions == []) is (rc == 0)
  if rc == 0:  # the contest line stands in place of the `review settle … by …` line
    assert f"review settle {rid} change-review-1-1" not in journal


OTHER_FINDING = PANEL_QUESTION.replace("change-review-1-1", "change-review-1-2")


@pytest.mark.parametrize("mode", ["normal", "leavemealone"])
@pytest.mark.parametrize("panel, why", [
    (None, "judges {pid} has no verdict"),
    ({"converged": None}, "judges {pid} has not converged"),
    ({"converged": "a"}, "judges {pid} did not overrule change-review-1-1"),
    ({"converged": "c"}, "judges {pid} did not overrule change-review-1-1"),
    ({"converged": "b", "question": OTHER_FINDING}, "judges {pid} did not overrule change-review-1-1"),
    ({"converged": "b", "pid": "p1"}, "judges p1 was not opened for {rid} round 1"),
    ({"converged": "b", "pid": "head-U08-c1-r1-a1b2c3"}, "judges head-U08-c1-r1-a1b2c3 was not opened for {rid} round 1"),
    ({"converged": "b", "pid": "{rid}-r2-a1b2c3"}, "judges {rid}-r2-a1b2c3 was not opened for {rid} round 1")])
def test_settle_judges_needs_a_converged_panel_overruling_the_finding(world, panel, why, mode):
  """The wider gate stays narrow, in either mode: a panel with no verdict, an unconverged one, one that upheld or asked for a redesign,
  one that ruled another finding, or one opened for another review or round (the same finding id recurs in every unit) settles nothing."""
  spec, cid, rid = opened(world, "head", mode=None if mode == "normal" else mode)
  head_round(world, 1, "posted", cid, "revise")
  pid = panel_of(rid)
  if panel is not None:
    settled_panel(world, **({"pid": pid} | {k: v.format(rid=rid) if k == "pid" else v for k, v in panel.items()}))
  assert record_findings(world, rid, 1, "change-review", [F("change-review", 1, 1, "high", loc="src/x.py")], cid, sha=A)[0] == 0
  used = panel["pid"].format(rid=rid) if panel and "pid" in panel else pid
  code, text = settle(world, rid, "change-review-1-1", "declined", cid, "--judges", used)
  assert code == 1 and f"review settle: change-review-1-1: {why.format(pid=pid, rid=rid)}" in text, text
  assert rjson(world, rid, "round-1.json")["reviewers"]["change-review"]["findings"][0]["disposition"] is None


def test_settle_judges_settles_one_converged_question_of_a_split_panel(world):
  """Q1 converged `finding overruled`, Q2 split at the cap: the panel's own `converged` is false, yet Q1's finding settles
  and Q2's does not."""
  spec, cid, rid = opened(world, "head")
  head_round(world, 1, "posted", cid, "revise")
  pid = panel_of(rid)
  settled_panel(world, pid=pid, split=OTHER_FINDING.replace("## Q1", "## Q2"))
  found = [F("change-review", 1, 1, "high", loc="src/x.py"), F("change-review", 1, 2, "high", loc="src/y.py")]
  assert record_findings(world, rid, 1, "change-review", found, cid, sha=A)[0] == 0
  assert settle(world, rid, "change-review-1-1", "declined", cid, "--judges", pid)[0] == 0
  code, text = settle(world, rid, "change-review-1-2", "declined", cid, "--judges", pid)
  assert code == 1 and f"change-review-1-2: judges {pid} has not converged" in text, text


@pytest.mark.parametrize("mode, word", [("normal", "contest"), ("leavemealone", "leavemealone")])
def test_the_judges_ruling_word_is_the_cards_mode(world, mode, word):
  """`decision rule --by judges:<panel>` journals and posts `contest` on a normal-mode card, `leavemealone` on a leavemealone one;
  `<fid> allowed` stays the owner's alone in normal mode."""
  from test_u84 import SPEC_COMMENT, open_decision, rule_on, spec_world
  card, s = spec_world(world, mode)
  qid = open_decision(world, card, SPEC_COMMENT)
  code, text = rule_on(world, card, qid, "(a)", "judges:p1")
  assert code == 0, text
  assert f"Ruling (judges p1, {word}): U02 {qid} " in journal_of(s)
  assert f"\n(judges p1, {word})\n" in [c for posted in world.gh.comments.values() for c in posted][-1]["body"]
  data = foreman_of(s, "U02")  # the owner-only decision: a test-delta finding the foreman raised, which the judges never settle
  core.atomic_write(s.path("foreman", "U02"), data | {"rounds": [{"round": 1, "phase": "posted", "outcome": "owner: foreman-1-1"}]})
  td = "foreman-1-1 | high | tests/unit/test_q.py:3 | regression: no | test-delta: tests/unit/test_q.py:3 removed\n"
  owner_qid = world.run("decision", "open", "--unit", "U02", "--point", 1, "--question", write_question(world, td),
                        "--source", "review head-U02-c1 round 1", "--runcard", card)[1].splitlines()[0]
  code, text = world.run("decision", "rule", "--unit", "U02", "--decision", owner_qid, "--ruling", "foreman-1-1 allowed",
                         "--by", "judges:p1", "--runcard", card)
  assert code != 0 and "decision: foreman-1-1 allowed is the owner's alone" in text, text


def test_unconverged_verdict_reaches_the_owner(world, tmp_path):
  """No convergence at the cap: the owner's point 1 question gains one line naming `verdict.json` and each judge's last choice."""
  pid, question = contest(world, tmp_path)
  folder = world.artifacts / "judges" / pid
  card = json.loads((folder / "panel.json").read_text(encoding="utf-8"))["runcard"]
  votes = {"fable": "a", "opus": "b", "astra": "a"}
  for rnd in range(1, 6):
    for judge, option in votes.items():
      verdict = world.repo.parent / f"{pid}-r{rnd}-{judge}.md"
      verdict.write_text(f"Q1: ({option})\n", encoding="utf-8")
      assert world.run("judges", "record", "--panel", pid, "--round", rnd, "--judge", judge, "--verdict", verdict,
                       "--isolation", "clean", "--runcard", card)[0] == 0
    assert world.run("judges", "diff", "--panel", pid, "--round", rnd, "--runcard", card)[0] == 0
    if rnd == 1:  # below the cap the verdict leaves the owner no question
      assert world.run("judges", "verdict", "--panel", pid, "--runcard", card)[0] == 2
      assert not (folder / "owner-question.md").exists()
  assert world.run("judges", "verdict", "--panel", pid, "--runcard", card)[0] == 2
  owner = (folder / "owner-question.md").read_text(encoding="utf-8")
  assert owner.startswith(question), "point 1's question as today"
  added = owner[len(question):].splitlines()
  assert len(added) == 1, "one added line"
  assert f"judges/{pid}/verdict.json" in added[0] and "fable: finding upheld" in added[0] and "opus: finding overruled" in added[0]


def test_verdict_line_keeps_each_judges_last_recorded_choice(world, tmp_path):
  """A judge recorded `not run` in the last round keeps the choice it made earlier; one that never answered is named."""
  pid, _ = contest(world, tmp_path)
  folder = world.artifacts / "judges" / pid
  card = json.loads((folder / "panel.json").read_text(encoding="utf-8"))["runcard"]
  for rnd in range(1, 6):
    record_round(world, pid, card, rnd, {"fable": "a", "opus": "b"} | ({"astra": "a"} if rnd < 5 else {}))
    if rnd == 5:
      assert world.run("judges", "record", "--panel", pid, "--round", 5, "--judge", "astra", "--not-run", "killed",
                       "--runcard", card)[0] == 0
    assert world.run("judges", "diff", "--panel", pid, "--round", rnd, "--runcard", card)[0] == 0
  assert world.run("judges", "verdict", "--panel", pid, "--runcard", card)[0] == 2
  line = (folder / "owner-question.md").read_text(encoding="utf-8").splitlines()[-1]
  assert "astra: finding upheld" in line and "fable: finding upheld" in line and "opus: finding overruled" in line, line


FINDING_LINE = "change-review-1-1 | high | src/x.py:3 | regression: no | the retry loop never backs off\n"


def open_point_one(world, pid, question=FINDING_LINE):
  """The unit's open point 1 decision `decision open` recorded before the panel (U07's foreman file)."""
  foreman = json.loads(core.store(world.repo).path("foreman", "U07").read_text(encoding="utf-8"))
  decision = {"id": "q1", "point": 1, "source": f"review {pid.rsplit('-r1-', 1)[0]} round 1", "head": "a" * 64,
              "question": question, "asked_at": "t", "options": ["finding upheld", "finding overruled"]}
  put(world, foreman | {"decisions": [decision]}, "foreman", "U07")


def test_an_unconverged_panel_gives_its_verdict_line_to_the_open_decision(world, tmp_path):
  """The cap leaves the verdict line in the open point 1 decision's `question`, the record the inbox and the ruling comment read."""
  pid, _ = contest(world, tmp_path)
  open_point_one(world, pid)
  folder = world.artifacts / "judges" / pid
  card = json.loads((folder / "panel.json").read_text(encoding="utf-8"))["runcard"]
  for rnd in range(1, 6):
    record_round(world, pid, card, rnd, {"fable": "a", "opus": "b", "astra": "a"})
    assert world.run("judges", "diff", "--panel", pid, "--round", rnd, "--runcard", card)[0] == 0
    if rnd < 5:
      assert world.run("judges", "verdict", "--panel", pid, "--runcard", card)[0] == 2
      assert foreman_of(core.store(world.repo), "U07")["decisions"][0]["question"] == FINDING_LINE
  assert world.run("judges", "verdict", "--panel", pid, "--runcard", card)[0] == 2
  assert world.run("judges", "verdict", "--panel", pid, "--runcard", card)[0] == 2  # the line is added once
  question = foreman_of(core.store(world.repo), "U07")["decisions"][0]["question"]
  assert question.startswith(FINDING_LINE) and question.count(f"judges/{pid}/verdict.json") == 1
  assert "fable: finding upheld" in question and "opus: finding overruled" in question


def test_the_verdict_line_goes_only_to_this_reviews_unruled_decision(world, tmp_path):
  """The same finding id recurs in every unit and cycle: the line goes to the point 1 decision whose `source` is this panel's review
  and round and that still has an unruled finding of the panel, never to another unit's, another round's, or a ruled one."""
  pid, _ = contest(world, tmp_path)
  rid = pid.rsplit("-r1-", 1)[0]
  foreman = json.loads(core.store(world.repo).path("foreman", "U07").read_text(encoding="utf-8"))
  base = {"id": "q1", "point": 1, "source": f"review {rid} round 1", "head": "a" * 64, "question": FINDING_LINE, "asked_at": "t",
          "options": ["finding upheld", "finding overruled"]}
  other_unit = {"decisions": [base | {"source": "review head-U08-c1 round 1"}], "rulings": []}
  other_round = base | {"id": "q2", "source": f"review {rid} round 2"}
  ruled = base | {"id": "q3"}
  closed = base | {"id": "q4"}
  put(world, foreman | {"decisions": [base, other_round, ruled, closed],
                        "rulings": [{"decision": "q3", "ruling": "change-review-1-1 finding upheld — a"},
                                    {"decision": "q4", "ruling": "redesign — b"}]}, "foreman", "U07")
  put(world, foreman | other_unit, "foreman", "U08")
  folder = world.artifacts / "judges" / pid
  card = json.loads((folder / "panel.json").read_text(encoding="utf-8"))["runcard"]
  for rnd in range(1, 6):
    record_round(world, pid, card, rnd, {"fable": "a", "opus": "b", "astra": "a"})
    assert world.run("judges", "diff", "--panel", pid, "--round", rnd, "--runcard", card)[0] == 0
  assert world.run("judges", "verdict", "--panel", pid, "--runcard", card)[0] == 2
  mark = f"judges/{pid}/verdict.json"
  by_id = {d["id"]: d for d in foreman_of(core.store(world.repo), "U07")["decisions"]}
  assert mark in by_id["q1"]["question"]
  assert all(mark not in by_id[i]["question"] for i in ("q2", "q3", "q4")), "another round's, a ruled and a closed decision stay as they were"
  assert foreman_of(core.store(world.repo), "U08")["decisions"][0]["question"] == FINDING_LINE


VERDICT_LINE = "The judges did not converge (judges/p1/verdict.json), their last choices: Q1 fable: finding upheld; opus: finding overruled\n"


def test_a_point_one_decision_stays_pending_on_each_unconverged_finding():
  """F1 converged and ruled, F2 split at the cap: the decision stays pending on F2 alone, until F2 is ruled or a `redesign` rules the whole."""
  from superegm.report import pending_decisions
  lines = "change-review-1-1 | high | src/x.py:3 | regression: no | a\nchange-review-1-2 | high | src/x.py:9 | regression: no | b\n"
  decision = {"id": "q1", "point": 1, "source": "review head-U07-c1 round 1", "question": lines + VERDICT_LINE,
              "options": ["finding upheld", "finding overruled"]}
  ruling = lambda text: {"decision": "q1", "ruling": text}
  assert pending_decisions({"decisions": [decision], "rulings": []}) == [decision]
  assert pending_decisions({"decisions": [decision], "rulings": [ruling("change-review-1-1 finding overruled — judges")]}) == [decision]
  both = [ruling("change-review-1-1 finding overruled — judges"), ruling("change-review-1-2 finding upheld")]
  assert pending_decisions({"decisions": [decision], "rulings": both}) == []
  assert pending_decisions({"decisions": [decision], "rulings": [ruling("redesign — x")]}) == []
  plain = decision | {"question": lines}  # a decision with no verdict line is ruled whole by its first ruling, as before
  assert pending_decisions({"decisions": [plain], "rulings": [ruling("change-review-1-1 finding upheld")]}) == []


def test_the_inbox_listing_shows_the_verdict_line(world):
  """A contested finding whose decision carries the panel's verdict line lists it, in the item and in its printed line."""
  from superegm.inbox import line_of
  (item,) = contested_items(world, CONTEST.format("high") + SPLIT_LINE, panel="capped", full=True)
  assert SPLIT_LINE.strip() in item["verdict"] and "judges/head-U01-c1-r1-a1b2c3/verdict.json" in line_of(item)


def test_the_wave_report_names_each_judges_ruling_with_its_panel(world):
  """Section 7.8: a ruling made by a panel, converged or by `decision rule`, is listed with the panel and the finding; an owner's is not."""
  from test_wave import open_wave_card
  card = open_wave_card(world)
  rulings = [{"decision": "q1", "ruling": "change-review-1-1 finding overruled — the panel", "by": "judges:p-7"},
             {"decision": "q2", "ruling": "change-review-1-2 finding upheld", "by": "gsVAM"}]
  decisions = [{"id": "q1", "point": 1, "source": "review r round 1", "question": "x"}, {"id": "q2", "point": 1, "source": "review r round 1", "question": "y"}]
  s = wave_store(world, U01={"pr": 70, "head": "a" * 40, "ci": "green", "launches": [{"round": 1, "status": "exited 0"}],
                             "decisions": decisions, "rulings": rulings})
  assert world.run("report", "--runcard", card)[0] == 0
  text = s.path("wave_report", 1).read_text(encoding="utf-8")
  section = text.split("## Judges' rulings\n")[1].split("\n##")[0]
  assert section.strip() == "- U01 q1 (judges p-7): change-review-1-1 finding overruled — the panel"


PANELS = {"open": None, "between": {"converged": False, "cap_reached": False, "open": ["Q1"]},
          "capped": {"converged": False, "cap_reached": True, "open": ["Q1"]}, "converged": {"converged": True, "cap_reached": False, "open": []}}


def contested_items(world, question, n=1, findings=("high",), contested=(1,), panel=None, full=False):
  """The inbox's `contested` items (their fingerprints, else the items) of one head review at round `n`, its point-1 decision asking
  `question`; `panel`: the record of a panel opened for this review and round in the store, a key of PANELS (`open`: a panel.json and no
  verdict.json; the others add that verdict.json), none: no panel was opened."""
  from test_inbox import D, HEAD, POSTED, U, F as found, open_wave_card, seed as inbox_seed
  from superegm.inbox import inbox_items
  open_wave_card(world)
  s = inbox_seed(world, **U(decisions=D(1, f"review head-U01-c1 round {n}", question=question), rounds=POSTED(n),
                            reviews=HEAD(n, found(*findings), builder_contested=[{"fid": f"foreman-1-{i}", "reason": "r"} for i in contested])))
  if panel:
    pid = f"head-U01-c1-r{n}-a1b2c3"
    core.atomic_write(s.path("judges", pid, "panel.json"), {"id": pid, "rounds": {}})
    if PANELS[panel]:
      core.atomic_write(s.path("judges", pid, "verdict.json"), {"panel": pid} | PANELS[panel])
  items = [i for i in inbox_items(s, [s.handoff_id]) if i["kind"] == "contested"]
  return items if full else [i["fingerprint"] for i in items]


SPLIT_LINE = VERDICT_LINE.replace("judges/p1/", "judges/head-U01-c1-r1-a1b2c3/")
CONTEST = "foreman-1-1 | {} | src/x.py:3 | regression: no | c\n"


@pytest.mark.parametrize("severity, n, panel, line, listed", [
    ("high", 1, "open", "", False), ("medium", 1, "open", "", False), ("high", 1, "between", "", False),
    ("high", 1, "capped", SPLIT_LINE, True), ("medium", 1, "capped", SPLIT_LINE, True),
    ("high", 5, "open", "", False), ("high", 5, "capped", SPLIT_LINE.replace("-r1-", "-r5-"), True)])
def test_a_blocking_contest_is_held_only_while_its_panel_is_open(world, severity, n, panel, line, listed):
  """Round 5 (codebase-details-4-1): a high or medium head contest lists no owner form while a panel opened for its review and round has
  no unconverged verdict at the cap yet (no verdict.json, or one with rounds to go), on the capped round (n = 5) too, and lists it with
  the panel's verdict line once the panel is done and split."""
  items = contested_items(world, CONTEST.format(severity) + line, n=n, findings=(severity,), panel=panel, full=True)
  assert [i["fingerprint"] for i in items] == (["U01/contested/q1/foreman-1-1"] if listed else [])
  assert all(line.strip() in i["verdict"] for i in items)


@pytest.mark.parametrize("severity, panel", [("high", None), ("medium", None), ("high", "converged"), ("medium", "converged")])
def test_a_blocking_contest_no_panel_will_rule_reaches_the_owner(world, severity, panel):
  """Round 5 (astra-4-1, codebase-details-4-1): no panel was opened (`judges question` refused the round: a low or CI finding beside
  it), or the panel converged on a `redesign` that `decision rule` refuses over mediums: no verdict line will come, the owner's forms list."""
  items = contested_items(world, CONTEST.format(severity), findings=(severity,), panel=panel, full=True)
  assert [i["fingerprint"] for i in items] == ["U01/contested/q1/foreman-1-1"] and all("verdict" not in i for i in items)


@pytest.mark.parametrize("panel, listed", [("open", False), (None, True)])
def test_the_hold_reads_the_panel_record_not_the_questions_text(world, panel, listed):
  """Round 5 (astra-4-2): a builder's reason carrying `(judges/old/verdict.json)` neither holds nor lifts the hold, and shows no verdict line."""
  question = "foreman-1-1 | high | src/x.py:3 | regression: no | see the old run (judges/old/verdict.json), their last choices: x\n"
  items = contested_items(world, question, panel=panel, full=True)
  assert [i["fingerprint"] for i in items] == (["U01/contested/q1/foreman-1-1"] if listed else []) and all("verdict" not in i for i in items)


def test_a_low_contest_beside_a_blocking_one_lists_at_once(world):
  """A low finding goes to no panel, so its owner form lists with no panel's verdict while the high one waits for an open panel."""
  question = "foreman-1-1 | high | src/x.py:3 | regression: no | c\nforeman-1-2 | low | src/x.py:3 | regression: no | c\n"
  assert contested_items(world, question, findings=("high", "low"), contested=(1, 2), panel="open") == ["U01/contested/q1/foreman-1-2"]


def test_the_wave_report_lists_a_judges_settlement_the_review_recorded(world):
  """Round 4 (astra-3-3): `review settle --judges` marks the finding `ruling: judges:<panel>` and adds no foreman ruling, so the
  report reads it from the head review's rounds; a finding the decision rule also ruled is listed once, an owner's settlement not."""
  from test_inbox import HEAD, ROUND, POSTED, U, F as found, open_wave_card, seed as inbox_seed
  card = open_wave_card(world)
  findings = found("high", "high", "high")
  for finding, (disposition, by) in zip(findings, (("declined", "judges:p-3"), ("declined", "owner"), ("contested", "judges:p-4"))):
    finding.update(disposition=disposition, ruling=by)
  rulings = [{"decision": "q1", "ruling": "foreman-1-3 finding overruled — the panel", "fid": "foreman-1-3", "by": "judges:p-4"}]
  s = inbox_seed(world, **U(launches=[{"round": 1, "status": "exited 0"}], rulings=rulings, rounds=POSTED(),
                            reviews=HEAD(1, findings)))
  assert world.run("report", "--runcard", card)[0] == 0
  section = s.path("wave_report", 1).read_text(encoding="utf-8").split("## Judges' rulings\n")[1].split("\n##")[0]
  assert section.strip().splitlines() == ["- U01 q1 (judges p-4): foreman-1-3 finding overruled — the panel", "- U01 foreman-1-1 (judges p-3): declined"]


ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("path, present, absent", [
    ("skills/wave/SKILL.md", ("the inbox is the store-wide read", "detached in its own session, and returns at once"), ()),
    ("skills/judges/references/leavemealone.md",
     ("the round's `comments.md` and diff, `r<n>/spec_range.md` and `r<n>/amendments.md`",
      "`decision rule --by\n   judges:<panel>` journals `Ruling (judges <panel>, leavemealone | contest): …`",
      "`Ruling (judges <panel>, contest): <unit> <fid> <disposition>`"), ("`Ruling (judges <panel>, leavemealone): …`",)),
    ("skills/judges/references/astra_judge.md",
     ("the judge lane; the lane's model and effort read from the panel's `astra` member (U28); inline evidence (U88)",
      "embeds the contents of every evidence file in the panel's `evidence[]`, for every question form",
      "whatever the question's form, and sits outside the repository folder, except the spec"),
     ("reads no paths", "On a head contest the brief")),
    ("skills/wave/references/decision_points.md",
     ("only `finding overruled` settles through `review settle --judges <panel>`",
      "`finding upheld` and `redesign` go through `decision rule --by judges:<panel>`"),
     ("a converged ruling settles through\n`review settle --judges <panel>`",)),
    ("skills/wave/references/builder_orders.md",
     ("`(judges <panel>, contest)` is the same ruling in normal mode, on every judges ruling of a normal-mode card",), (", on a head contest",)),
    # round 4 (codebase-details-3-1): leavemealone mode's panel opens with the same five evidence files as every other route
    ("skills/wave/references/leavemealone_mode.md",
     ("a head contest's evidence is the round's `comments.md`, the diff, the unit's body,\n`r<n>/spec_range.md` and `r<n>/amendments.md`",),
     ("the round's `comments.md` and diff, or the builder's comment, are the\nevidence",)),
    # round 4 (codebase-details-3-4): a spec review's evidence is the spec, inside the repository folder
    # round 5 (codebase-details-4-2): a plan review's and a `plan --unit <U> --decision D<n>` panel's evidence carries the spec too
    ("skills/judges/references/astra_judge.md",
     ("except the spec, which a spec review, a plan review and a `plan --unit <U> --decision D<n>` panel carry,\ninside the repository folder",),
     ("except a spec review's, which is the spec, inside the repository folder", "and sits outside the repository folder: that content goes to OpenAI too")),
    ("skills/plan/scripts/superegm/decision.py", ("judges' post (the `(judges <panel>, leavemealone | contest)` marker on any line",), ("judges' post (the `(judges <panel>, leavemealone)` marker",))])
def test_review_round_one_texts(path, present, absent):
  """The reference texts name what the code now does: the five evidence files, the `contest` word, the data sent to OpenAI, the marker."""
  body = (ROOT / path).read_text(encoding="utf-8")
  assert all(p in body for p in present), [p for p in present if p not in body]
  assert not any(p in body for p in absent), [p for p in absent if p in body]


@pytest.mark.parametrize("path, phrases", [
    ("skills/wave/SKILL.md", ("in normal mode as in leavemealone", "judges/<panel>/verdict.json")),
    ("skills/wave/references/decision_points.md", ("judges first in both modes", "`<fid> allowed`", "`amend`", "`respec`", "CI finding")),
    ("skills/judges/references/leavemealone.md", ("apply in normal mode", "contest")),
    ("skills/judges/references/astra_judge.md", ("evidence arrives inline",))])
def test_contest_reference_texts(path, phrases):
  """The skills route a head contest to the panel first and list the owner-only rulings."""
  body = (ROOT / path).read_text(encoding="utf-8")
  assert all(phrase in body for phrase in phrases), [p for p in phrases if p not in body]


KEPT_LINES = ("the owner gets `judges/<panel>/verdict.json`'s line only if the panel does not converge",
                    "the judges' rulings with their panels", "- `references/resume_notes.md`: at the entry, before step 5.",
                    "In any other host reply with one line,\n`wave runs in Claude Code only`, and stop.", "the builder pushes its unit branch",
                    "(the helper is single-writer)", "a card still open on this spec")


def test_the_wave_skill_keeps_its_unrelated_lines_and_points_to_the_moved_paragraph():
  """The owner's ruling on #172: U88 makes room under the 15,000-byte pin by moving unpinned text verbatim to `references/`, not by rewording."""
  body = (ROOT / "skills/wave/SKILL.md").read_text(encoding="utf-8")
  moved = (ROOT / "skills/wave/references/resume_notes.md").read_text(encoding="utf-8")
  present = [p for p in KEPT_LINES if p not in body]
  assert not present, present
  assert "take a refusal as fact, never retry it" not in body and "take a refusal as fact, never retry it" in moved
  assert "Builders a previous invocation left running report through `status --wait`'s\n`exit` lines." in moved
  assert len(body.encode("utf-8")) < 15_000
