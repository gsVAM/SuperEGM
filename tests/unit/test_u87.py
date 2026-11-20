# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U87's tests, spec sections 7.5 and 7.7: the post-mortem's Lessons table, `postmortem --retro` and the retro skill.

"""U87: the Lessons table, `superegm postmortem --retro <file>` and the `/superegm:retro` skill."""

import json

import pytest
from conftest import ROOT
from test_u43 import SLUG, jread, jwrite
from test_u43 import registry  # noqa: F401  (the autouse fixture: no test reads the owner's registry)
from test_u78 import two_units

DEVIATION = ("**Deviation (spec):** the retry delay the spec states cannot hold.\n\n"
             "Evidence: `docs/specs/x.md:12` says 5s; the builder's test needs 6s.\n\n**Builder status:** BLOCKED\n")


def lessons(report):
  """The Lessons section's rows, each as one line of text."""
  body = report.split("## Lessons\n", 1)[1].split("\n## ", 1)[0]
  return [line for line in body.splitlines() if line.startswith("|")][2:]


def respec_world(world, comment):
  """`two_units`' handoff with respec R1 applied (opened for U02 on comment 901, its approval entry ranges `12-14`);
  `comment(args)` answers the one `gh api` read of that comment. U01's second launch is escalated."""
  c, _, _ = two_units(world)
  for round_file in (c.root / "reviews").glob("spec-*-c1/round-1.json"):  # each spec reviewer kept one finding: none is a silent one
    record = jread(round_file)
    for name, entry in record["reviewers"].items():
      entry["findings"] = [{"id": f"{name}-1-1", "severity": "low", "regression": "no", "disposition": "fixed"}]
    jwrite(round_file, record)
  answer = world.gh.handlers["api"]

  def api(args, cwd, token=None):
    return comment(args) if "issues/comments/901" in args[1] else answer(args, cwd, token=token)
  world.gh.extend("api", api)
  path = c.root / "approvals" / f"{SLUG}.json"
  record = jread(path)
  record["entries"].append({**record["entries"][-1], "kind": "respec", "respec": "R1", "ranges": [[12, 14], [30, 31]]})
  jwrite(path, record)
  jwrite(c.hs.path("file", "respec", "R1.open.json"), {"id": "R1", "unit": "U02", "comment_id": 901, "at": "2026-11-16T00:00:00Z"})
  return c


def test_lessons_rows(world):
  # a store with one respec and one escalated unit gives two Lessons rows, facts with their source record
  c = respec_world(world, lambda args: (0, json.dumps({"id": 901, "body": DEVIATION}), ""))
  code, out = world.run("postmortem", "--handoff", c.hid)
  assert code == 0, out
  rows = lessons(c.hs.path("file", "postmortem.md").read_text(encoding="utf-8"))
  spec = c.spec.resolve().relative_to(world.repo.resolve()).as_posix()
  assert len(rows) == 2
  assert "R1" in rows[0] and "U02" in rows[0] and f"{spec}:12-14" in rows[0] and "R1.open.json" in rows[0]
  assert "the builder's test needs 6s" in rows[0] and "retry delay" in rows[0] and "30-31" not in rows[0]
  assert "U01" in rows[1] and "escalated" in rows[1]


def test_lessons_respec_evidence_unread(world):
  # a comment read that fails leaves the row and says so
  c = respec_world(world, lambda args: (1, "", "HTTP 404"))
  code, out = world.run("postmortem", "--handoff", c.hid)
  assert code == 0, out
  rows = lessons(c.hs.path("file", "postmortem.md").read_text(encoding="utf-8"))
  assert len(rows) == 2 and "evidence unread (comment 901)" in rows[0]


def report_of(world, c):
  code, out = world.run("postmortem", "--handoff", c.hid)
  assert code == 0, out
  return c.hs.path("file", "postmortem.md").read_text(encoding="utf-8")


def signal_rows(world, c, signal):
  return [r for r in lessons(report_of(world, c)) if f"| {signal} |" in r]


def head_review(c, found, rulings=()):
  """One head review of U02 (the reviewers in `found`) and U02's foreman record, overruling the findings `rulings` names."""
  from test_u78 import reviewed
  reviewed(c, "head-U02-c1", "head", "U02", list(found), found)
  jwrite(c.hs.path("foreman", "U02"), {"dispatch_id": None, "decisions": [], "rounds": [{"round": 1, "phase": "posted", "outcome": "posted"}],
                                       "rulings": [{"ruling": f"{fid} finding overruled — not a defect", "by": "owner"} for fid in rulings]})


def finding(reviewer, n, **more):
  return {"id": f"{reviewer}-1-{n}", "severity": "high", "regression": "no", **more}


def named(rows, *names):
  """The rows whose fact opens with one of the reviewers `names` (the fixture's spec reviewers `design` and `zoom-out` ran quiet)."""
  return [r for r in rows if r.split("|")[4].strip().split(":")[0] in names]


def test_reviewer_rows_most_overruled(world):
  # a reviewer with no finding kept and the one overruled most each get a row; the others none
  c, _, _ = two_units(world)
  head_review(c, {"kept": {"findings": [finding("kept", 1), finding("kept", 2)]}, "quiet": {"findings": []},
                  "lost": {"findings": [finding("lost", 1)]}, "most": {"findings": [finding("most", 1), finding("most", 2)]}},
              rulings=["lost-1-1", "most-1-1"])
  nothing = named(signal_rows(world, c, "reviewer kept nothing"), "kept", "quiet", "lost", "most")
  assert len(nothing) == 2 and "lost: 1 raised, 1 overruled" in nothing[0] and "quiet: 0 raised, 0 overruled" in nothing[1]
  [most] = signal_rows(world, c, "reviewer most overruled")
  assert "most: 1 of 2 overruled" in most


def test_reviewer_rows_no_overrule_anywhere(world):
  # nothing overruled: no reviewer is the most overruled, and a quiet one is still a reviewer with no finding kept
  c, _, _ = two_units(world)
  head_review(c, {"kept": {"findings": [finding("kept", 1)]}, "quiet": {"findings": []}})
  assert signal_rows(world, c, "reviewer most overruled") == []
  [row] = named(signal_rows(world, c, "reviewer kept nothing"), "kept", "quiet")
  assert "quiet: 0 raised" in row


def test_reviewer_rows_an_allowance_is_an_overrule(world):
  # spec 13.2: an allowance is recorded as an overrule, so a reviewer whose every finding was allowed kept none
  c, _, _ = two_units(world)
  head_review(c, {"kept": {"findings": [finding("kept", 1)]}, "allowed": {"findings": [finding("allowed", 1)]}})
  record = jread(c.hs.path("foreman", "U02"))
  record["rulings"] = [{"ruling": "allowed-1-1 allowed — a known gap", "by": "owner"}]
  jwrite(c.hs.path("foreman", "U02"), record)
  [row] = named(signal_rows(world, c, "reviewer kept nothing"), "kept", "allowed")
  assert "allowed: 1 raised, 1 overruled" in row
  assert signal_rows(world, c, "reviewer most overruled") == []


def test_reviewer_rows_every_reviewer_quiet(world):
  # every reviewer raised nothing: each is a reviewer with no finding kept
  c, _, _ = two_units(world)
  head_review(c, {"a": {"findings": []}, "b": {"findings": []}})
  assert len(named(signal_rows(world, c, "reviewer kept nothing"), "a", "b", "design", "zoom-out")) == 4
  assert signal_rows(world, c, "reviewer most overruled") == []


def test_fix_design_rows(world):
  # a fix-design finding is a row naming its review
  c, _, _ = two_units(world)
  head_review(c, {"a": {"findings": [finding("a", 1, disposition="fix-design", claim="the spec contradicts itself"), finding("a", 2)]}})
  [row] = signal_rows(world, c, "fix-design finding")
  assert "U02" in row and "reviews/head-U02-c1" in row and "a-1-1" in row and "the spec contradicts itself" in row


def test_amendment_rows_need_a_ruling(world):
  # an amendment file counts once a ruling names its comment; the legacy state entry counts; an unruled file does not
  c, _, _ = two_units(world)
  entry = {"unit": "U01", "name": "dequeue", "text": "dequeue returns null", "at": "2026-11-16T01:00:00Z"}
  jwrite(c.hs.path("file", "amendments", "77.json"), [{**entry, "comment_id": 77}])
  jwrite(c.hs.path("file", "amendments", "78.json"), [{**entry, "name": "peek", "text": "abandoned", "comment_id": 78}])
  jwrite(c.hs.path("foreman", "U02"), {"dispatch_id": None, "rounds": [], "decisions": [
      {"id": "D1", "point": 3, "source": "comment 77", "asked_at": "2026-11-16T00:00:00Z"}],
      "rulings": [{"decision": "D1", "ruling": "amend — dequeue returns null", "by": "owner", "posted": "comment 5"}]})
  c.state["amendments"] = [{"unit": "U01", "name": "legacy", "text": "an old one", "at": "2026-11-14T00:00:00Z"}]
  c.save()
  rows = signal_rows(world, c, "interface amendment")
  assert len(rows) == 2 and "state.json amendments" in rows[0] and "legacy: an old one" in rows[0]
  assert "amendments/77.json" in rows[1] and "dequeue: dequeue returns null" in rows[1] and "U01" in rows[1]
  assert not any("abandoned" in r for r in rows)


def test_amendment_row_cites_its_file_by_the_deviation_comment(world):
  # the file is named for the deviation comment; the `comment_id` inside is the ruling's, and a pipe in the text stays verbatim
  c, _, _ = two_units(world)
  entry = {"unit": "U01", "name": "dequeue", "text": "dequeue() -> int | None", "at": "2026-11-16T01:00:00Z", "comment_id": 21}
  jwrite(c.hs.path("file", "amendments", "11.json"), [entry])
  jwrite(c.hs.path("foreman", "U02"), {"dispatch_id": None, "rounds": [], "decisions": [
      {"id": "D1", "point": 3, "source": "comment 11", "asked_at": "2026-11-16T00:00:00Z"}],
      "rulings": [{"decision": "D1", "ruling": "amend — dequeue returns null", "by": "owner", "posted": "comment 21"}]})
  [row] = signal_rows(world, c, "interface amendment")
  assert "amendments/11.json" in row and "amendments/21.json" not in row
  assert "dequeue() -> int \\| None" in row


def test_pipes_in_a_cell_are_escaped_not_replaced():
  from superegm import postmortem
  assert postmortem.cell("a | b\nc") == "a \\| b c" and postmortem.cell(None) == ""


def cap_world(world, rulings, stopped):
  c, _, _ = two_units(world)
  decisions = [{"id": f"D{n}", "point": 2, "source": f"review head-U02-c{n} cap", "asked_at": "2026-11-16T00:00:00Z"} for n in (1, 2)]
  jwrite(c.hs.path("foreman", "U02"), {"dispatch_id": None, "rounds": [], "decisions": decisions, "stopped": stopped,
                                       "rulings": [{"decision": d, "ruling": r, "by": "owner"} for d, r in rulings]})
  return c


def test_cap_stop_rows_follow_the_cap_decision_that_stopped(world):
  # only the cap decision answered stop is a stop at the cap, once; a later stop of another cause is not its cap's
  c = cap_world(world, [("D1", "one more round"), ("D2", "stop")], {"reason": "later", "by": "owner"})
  [row] = signal_rows(world, c, "unit stopped at the cap")
  assert "U02" in row and "foreman/U02.json D2" in row


def test_a_stop_after_a_proceeded_cap_is_no_cap_stop(world):
  c = cap_world(world, [("D1", "one more round"), ("D2", "one more round")], {"reason": "launch failed", "by": "owner"})
  assert signal_rows(world, c, "unit stopped at the cap") == []


def test_default_answered_decisions_are_rows(world):
  # a `decide --default` answer (marked in the record) and a foreman decision answered by `superegm` are rows; an owner's own is not
  c, _, _ = two_units(world)
  stamp = {"decided_at": "2026-11-16T00:00:00Z", "mode": "typed"}
  c.state["decisions"] = {"U01/D1": {"answer": "(a)", "by": "owner", "default": True, **stamp},
                          "U01/D2": {"answer": "(b)", "by": "owner", **stamp}}
  c.save()
  jwrite(c.hs.path("foreman", "U02"), {"dispatch_id": None, "rounds": [], "stopped": None, "decisions": [
      {"id": "D1", "point": 2, "source": "review head-U02-c1 round 2", "asked_at": "2026-11-16T00:00:00Z"}],
      "rulings": [{"decision": "D1", "ruling": "one more round", "by": "superegm"}]})
  rows = signal_rows(world, c, "decision answered by default")
  assert len(rows) == 2 and "U01" in rows[0] and "state.json decisions U01/D1" in rows[0] and "U01/D2" not in "".join(rows)
  assert "U02" in rows[1] and "foreman/U02.json D1" in rows[1]


def test_decide_default_marks_the_record(world):
  # `decide --default` stores `default: true` beside the answer; an answer given with `--answer` does not
  from test_plan import BLOCKED, graph, planned, state
  spec, sha, plan, card = planned(world, BLOCKED)
  assert graph(world, plan, card)[0] == 0
  assert world.run("decide", "--unit", "U02", "--decision", "D1", "--default", "--runcard", card)[0] == 0
  assert state(world)["decisions"]["U02/D1"]["default"] is True
  assert world.run("decide", "--unit", "U02", "--decision", "D1", "--answer", "(b)", "--runcard", card)[0] == 0
  assert "default" not in state(world)["decisions"]["U02/D1"]


def test_respec_rows_keep_to_their_own_handoff(world):
  # another handoff's R1, approved later, does not lend its ranges to this handoff's R1
  c = respec_world(world, lambda args: (0, json.dumps({"id": 901, "body": DEVIATION}), ""))
  path = c.root / "approvals" / f"{SLUG}.json"
  record = jread(path)
  record["entries"].append({**record["entries"][-1], "handoff_id": "2026-11-20-other", "ranges": [[99, 100]]})
  jwrite(path, record)
  [row] = signal_rows(world, c, "respec")
  assert ":12-14" in row and "99-100" not in row


def test_respec_from_a_foreman_finding_quotes_the_decision(world):
  # a respec opened on the foreman's spec finding carries `finding`, not `comment_id`: its evidence is the finding's claim in the decision's question
  c = respec_world(world, lambda args: (1, "", "HTTP 404"))
  jwrite(c.hs.path("file", "respec", "R1.open.json"), {"id": "R1", "unit": "U02", "finding": "foreman-1-1", "at": "2026-11-16T00:00:00Z"})
  question = ("foreman-1-2 | low | a.py:1 | regression: no | an ordinary finding\n"
              "foreman-1-1 | high | docs/specs/x.md:12 | regression: no | deviation (spec) unruled: the retry count is wrong; `pytest -k retry` fails\n")
  jwrite(c.hs.path("foreman", "U02"), {"dispatch_id": None, "rounds": [], "rulings": [], "decisions": [
      {"id": "D1", "point": 1, "source": "review head-U02-c1 round 1", "question": question, "asked_at": "2026-11-16T00:00:00Z"}]})
  [row] = signal_rows(world, c, "respec")
  assert "the retry count is wrong; `pytest -k retry` fails" in row and "foreman-1-1" in row and "an ordinary finding" not in row


def test_respec_evidence_unread_without_gh(world):
  # gh missing (FileNotFoundError): the row says `evidence unread`, the report is still written
  def comment(args):
    raise FileNotFoundError("gh")
  c = respec_world(world, comment)
  [row] = signal_rows(world, c, "respec")
  assert "evidence unread (comment 901)" in row


def test_retro_needs_a_file(world, tmp_path):
  c, _, _ = two_units(world)
  code, out = world.run("postmortem", "--handoff", c.hid, "--retro", str(tmp_path / "none.md"))
  assert code == 1 and "postmortem: --retro" in out and "is not a file" in out


def test_retro_copy(world, tmp_path):
  # --retro copies the file in, needs no run card, writes only the store's file kind
  from superegm import postmortem
  from test_u78 import snapshot
  c, _, _ = two_units(world)
  source = tmp_path / "agreed-retro.md"
  source.write_bytes("# Retro\n\n- the reviewer file gains one line\né\n".encode())
  before = snapshot(c.root)
  code, out = world.run("postmortem", "--handoff", c.hid, "--retro", str(source))
  after = snapshot(c.root)
  retro_md = c.hs.path("file", "retro.md")
  assert code == 0, out
  assert retro_md.read_bytes() == source.read_bytes() and set(after) - {retro_md} == set(before)
  assert {p for p in before if after[p] != before[p]} == set()
  assert postmortem.WRITES == frozenset(["file"])


def text(path):
  return (ROOT / path).read_text(encoding="utf-8")


def frontmatter(path):
  import yaml
  return yaml.safe_load(text(path).split("---", 2)[1])


@pytest.mark.parametrize("phrase", ["reference document", "reviewer file", "`.superegm/config.json`", "`.superegm/brainstorm.md`",
                                    "owner's yes", "suggested answer", "one question at a time", "`retro: <handoff>`",
                                    "superegm postmortem --handoff <id> --retro <file>", "never edits the approved spec", "every open handoff",
                                    "`handoffs/<id>.json`", "latest non-null `closed_at`", "`closed_at` null", "`approvals/<spec-slug>.json`",
                                    "writes nothing to the store but `retro.md`", "`artifacts_dir`", "`<artifacts_dir>/<handoff id>/`",
                                    "`(closed: voided)`", "legacy flat-store handoff", "the helper's write, not this skill's"])
def test_retro_skill_text(phrase):
  # the retro skill names its four targets, asks per edit, and never touches an approved spec
  assert phrase in text("skills/retro/SKILL.md") and frontmatter("skills/retro/SKILL.md")["effect_kinds"] == ["state-store"]


@pytest.mark.parametrize("path, phrase", [("skills/integrate/SKILL.md", "/superegm:retro"), ("skills/using-superegm/SKILL.md", "/superegm:retro")])
def test_integrate_offers_retro_and_phase_list(path, phrase):
  # integrate offers the retrospective once after the post-mortem; the typed-skills list names it
  assert phrase in text(path)


def test_retro_folder_complete():
  # every section-14 skill folder carries SKILL.md, assets/icon.svg and test_scenarios.yaml
  import yaml
  assert all((ROOT / "skills/retro" / n).is_file() for n in ("SKILL.md", "assets/icon.svg", "test_scenarios.yaml"))
  assert yaml.safe_load((ROOT / "skills/retro/test_scenarios.yaml").read_text())["skill"] == "retro"
