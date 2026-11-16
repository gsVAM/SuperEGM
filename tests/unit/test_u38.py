# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U38's tests: the records' manifests, the judge panel's render, the Astra brief's section and the skills' placement of the section.

"""U38: instructions to the foreman, reviewers and judges."""

import json

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import REPO, git
from test_review import A, SLUG, F, approve, card, converged_spec, head_round, hstore, opened, record, rounds, seed_handoff, spec_file
from test_u37 import RULES, blob_sha, commit_file, configure, entries_of

TEXT = "Run the suite.\n"
MANIFEST = [{"file": RULES, "sha": blob_sha(TEXT.encode())}]


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
    edited = [{"file": RULES, "sha": blob_sha(b"Skip the suite.\n")}]
    if expected != []:
      render(world, "--spec", spec, "--review", rid, "--round", 2, "--runcard", cid)
      commit_file(world, RULES, "Skip the suite.\n")
      render(world, "--spec", spec, "--review", rid, "--round", 2, "--lane", "astra", "--runcard", cid)
      commit_file(world, RULES, "Run it twice.\n")
    assert record(world, rid, 2, "design", [], cid)[0] == 0
    assert record(world, rid, 2, "astra", [], cid)[0] == 0
    local, astra = recorded(world, rid, 2, "design"), recorded(world, rid, 2, "astra")
    if dispatch.endswith("astra lane"):
      assert astra == edited and astra != MANIFEST       # rendered with --lane astra after a HEAD edit, not the local file
    elif dispatch.endswith("local lane"):
      assert local == MANIFEST and local != edited       # the local render, whatever HEAD is at the record
    else:
      assert local == [] and astra == []


def open_judges(world, parent=None, name="q38"):
  """A judge panel on a one-question file, under `parent` or its own card; `(panel id, card to record under, panel.json)`."""
  from test_judges import ONE, open_card
  question = world.repo.parent / f"{name}.md"
  question.write_text(ONE, encoding="utf-8")
  cid = parent or open_card(world, "judges", question)
  code, out = world.run("judges", "open", "--question", question, "--parent" if parent else "--runcard", cid)
  assert code == 0, out
  return out.strip(), cid, panel_json(world, out.strip())


def panel_dir(world, pid):
  """The panel's folder: it lands in the store of its card's handoff, wherever that is."""
  return next(world.artifacts.glob(f"**/judges/{pid}"))


def panel_json(world, pid):
  return json.loads((panel_dir(world, pid) / "panel.json").read_text(encoding="utf-8"))


def brief_of(world, pid, n):
  return (panel_dir(world, pid) / f"round-{n}" / "brief.md").read_text(encoding="utf-8")


def set_card_handoff(world, cid, handoff):
  """The card as a store written before the handoff existed leaves it: `handoff` rewritten."""
  path = hstore(world).path("runcards", cid)
  superegm.atomic_write(path, {**json.loads(path.read_text(encoding="utf-8")), "handoff": handoff})


@pytest.mark.parametrize("parent, rendered", [
  ("review-spec card in a legacy flat store", "judges section of HEAD"),
  ("review-plan card of an approved handoff", "judges section of its frozen list"),
  ("wave card whose handoff has no approval entry", ""),
  ("a parent card with no handoff", ""),
  ("no parent (typed /superegm:judges)", ""),
])
def test_judge_panel_renders_once_by_parent_skill(world, parent, rendered):
  """Rendered once per lane at open, stored on the panel, reused by every later round, placed last in each brief."""
  from superegm import instructions
  from test_judges import record as judge_record
  head_text = "Judge by the suite.\n"
  if parent.startswith("review-spec"):
    commit_file(world, RULES, head_text)
    configure(world, [{"file": RULES, "to": ["judges"]}])
    git(["commit", "-qam", "config", "--allow-empty"], world.repo)
    spec = spec_file(world)
    seed_handoff(world, spec)                       # a flat store: the card carries the legacy id, which is not the spec's
    cid = card(world, spec, "review-spec")
    want = instructions.section([(RULES, head_text)])
  elif parent.startswith("review-plan"):
    spec, approved_cid, hid = approved_handoff(world, ["judges"])
    cid = card(world, spec, "review-plan", handoff=hid)
    move_on(world, spec, approved_cid)              # a same-id re-approval: the last approval entry is the frozen list
    want = instructions.section([(RULES, "Skip the suite.\n")])
  elif parent.startswith("wave"):
    spec, approved_cid, hid = approved_handoff(world, ["judges"])
    cid = card(world, spec, "wave", handoff=hid)
    set_card_handoff(world, cid, "2026-01-01-nowhere-aaaaaa")
    want = ""
  elif parent.startswith("a parent"):
    spec, approved_cid, hid = approved_handoff(world, ["judges"])
    cid = card(world, spec, "wave", handoff=hid)
    set_card_handoff(world, cid, None)
    want = ""
  else:
    commit_file(world, RULES, head_text)
    configure(world, [{"file": RULES, "to": ["judges"]}])
    git(["commit", "-qam", "config", "--allow-empty"], world.repo)
    cid, want = None, ""
  assert (want == "") == (rendered == "")
  pid, record_card, panel = open_judges(world, parent=cid)
  assert set(panel["instructions"]) == {"local", "astra"}
  for lane in ("local", "astra"):
    assert panel["instructions"][lane]["text"] == want
    assert [i["file"] for i in panel["instructions"][lane]["manifest"]] == ([RULES] if want else [])
  assert brief_of(world, pid, 1).endswith(want)

  # a later edit changes nothing: round 2 reuses the stored text, last in the brief, and each member records its lane's manifest
  commit_file(world, RULES, "Changed after the panel opened.\n")
  for judge, option in (("fable", "a"), ("opus", "b")):
    assert judge_record(world, pid, record_card, 1, judge, {"Q1": option})[0] == 0
  assert judge_record(world, pid, record_card, 1, "astra", not_run="not installed")[0] == 0
  code, out = world.run("judges", "diff", "--panel", pid, "--round", 1, "--runcard", record_card)
  assert code == 0, out
  round_2 = brief_of(world, pid, 2)
  assert round_2.endswith(want) and round_2.count("# Repository instructions") == (1 if want else 0)
  after = panel_json(world, pid)
  assert after["instructions"] == panel["instructions"]
  for judge, lane in (("fable", "local"), ("opus", "local"), ("astra", "astra")):
    assert after["rounds"]["1"][judge]["instructions"] == panel["instructions"][lane]["manifest"]


def test_astra_brief_appends_the_section(world, tmp_path, monkeypatch):
  """`astra_brief` renders role reviewers, lane astra, on the child card when none is stored; the section goes last,
  and the Astra record copies the manifest the brief carried, whatever a later edit or the reviewers' own render does."""
  import test_foreman as tf
  from superegm import approve_spec, foreman as foreman_mod
  monkeypatch.setattr(foreman_mod, "runner_path", lambda: None)
  target, base, head, g = tf.pr_repo(world, tmp_path, monkeypatch)
  st, wave, child, did, _ = tf.dispatched(world, head=head, astra={"enabled": True})
  # the handoff's frozen list, as `approve-spec` leaves it: the approval entry and the file's store copy
  approve_spec.write_copy(st, {"file": RULES, "sha": MANIFEST[0]["sha"], "text": TEXT})
  path = st.path("approvals", "sample")        # conftest's approval record of the sample spec: it carries the commit `prepare` reads
  record = json.loads(path.read_text(encoding="utf-8"))
  superegm.atomic_write(path, {**record, "instructions": [{"file": RULES, "to": ["reviewers"], "sha": MANIFEST[0]["sha"]}]})
  code, out = world.run("prepare", "--unit", tf.UNIT, "--dispatch", did, "--runcard", child)   # before any reviewers' render
  assert code == 0 and out.strip().endswith("astra: not installed"), out
  card = json.loads(st.path("runcards", child).read_text(encoding="utf-8"))
  stored = card["instructions"]["reviewers"]["astra"]
  assert stored["manifest"] == MANIFEST and stored["text"].startswith("# Repository instructions\n") and TEXT in stored["text"]
  brief = (st.path("review", tf.UNIT, f"pr{tf.PR}") / "r1" / "astra_brief.md").read_text(encoding="utf-8")
  assert brief.rstrip().endswith(stored["text"].rstrip()) and brief.count("# Repository instructions") == 1

  # a HEAD edit and a later render change nothing: the Astra record copies what the brief carried
  commit_file(world, RULES, "Skip the suite.\n")
  rid = tf.head_rid(st)
  tf.record(world, st, rid, 1, head, child, {"change-review": ""})
  assert world.run("review", "record", "--review", rid, "--round", 1, "--sha256", head, "--reviewer", "astra",
                   "--not-run", "not installed", "--runcard", child)[0] == 0
  rnd = json.loads(st.path("reviews", rid, "round-1.json").read_text(encoding="utf-8"))
  assert rnd["reviewers"]["astra"]["instructions"] == stored["manifest"] and rnd["reviewers"]["change-review"]["instructions"] == []


@pytest.mark.parametrize("path, phrase", [
  ("skills/review-spec/references/review_loop.md", "superegm instructions --role reviewers --spec"),
  ("skills/review-spec/references/review_loop.md", "superegm instructions --role reviewers --handoff"),
  ("skills/review-spec/references/review_loop.md", "equals the `instructions[]` recorded on round n-1's Astra record"),
  ("skills/wave/references/foreman_brief.md", "superegm instructions --role reviewers --handoff"),
  ("skills/wave/references/foreman_brief.md", "--unit"),
  ("skills/judges/SKILL.md", "# Repository instructions"),
])
def test_skill_texts_place_the_section(world, path, phrase):
  """The skills render the section, paste it last, and resume Astra only on an equal manifest."""
  from pathlib import Path
  assert phrase in (Path(__file__).resolve().parents[2] / path).read_text(encoding="utf-8")
  if path.endswith("review_loop.md") and "equals" in phrase:
    # a same-id re-approval that changed the Astra instructions: the plan review's new card renders a manifest that
    # differs from round 1's Astra record, so round 2 launches fresh
    spec, cid, hid = approved_handoff(world, ["reviewers"])
    used = card(world, spec, "review-plan", handoff=hid)
    code, out = world.run("review", "open", "--kind", "plan", "--artifact", "U07", "--reviewers", "readiness", "--astra", "on",
                          "--runcard", used)
    assert code == 0, out
    rid = out.splitlines()[0]
    render(world, "--handoff", hid, "--lane", "astra", "--runcard", used)
    assert record(world, rid, 1, "astra", [], used)[0] == 0
    round_one = recorded(world, rid, 1, "astra")
    assert round_one == MANIFEST
    move_on(world, spec, cid)
    renewed = card(world, spec, "review-plan", handoff=hid)
    render(world, "--handoff", hid, "--lane", "astra", "--runcard", renewed)
    stored = json.loads(superegm.store(world.repo).path("runcards", renewed).read_text(encoding="utf-8"))
    assert stored["instructions"]["reviewers"]["astra"]["manifest"] != round_one


def test_a_foreman_and_a_thread_record_carry_no_manifest(world):
  """No section reached the foreman's own findings or an external thread's: their records say `[]` with a render stored."""
  spec, cid, hid = approved_handoff(world, ["reviewers"])
  wave = card(world, spec, "wave", handoff=hid)
  child = card(world, "U07", "wave", parent=wave, handoff=hid)
  code, out = world.run("review", "open", "--kind", "head", "--artifact", "U07", "--reviewers", "change-review", "--astra", "off",
                        "--runcard", wave)
  assert code == 0, out
  rid = out.splitlines()[0]
  render(world, "--handoff", hid, "--runcard", child, "--unit", "U07")
  head_round(world, 1, "prepared", child)
  assert record(world, rid, 1, "change-review", [], child, sha=A)[0] == 0
  assert record(world, rid, 1, "foreman", [F("foreman", 1, 1)], child, sha=A)[0] == 0
  assert recorded(world, rid, 1, "change-review") == MANIFEST and recorded(world, rid, 1, "foreman") == []
  # a spec round: the thread beside the panel copies nothing from the round's stored local lane
  _, scid, srid = opened(world)
  render(world, "--spec", spec, "--review", srid, "--round", 1, "--runcard", scid)
  ext = "external:devin-ai-integration[bot]"
  assert record(world, srid, 1, "design", [], scid)[0] == 0
  assert record(world, srid, 1, ext, [F(ext, 1, 1)], scid)[0] == 0
  assert recorded(world, srid, 1, "design") == MANIFEST and recorded(world, srid, 1, ext) == []


def test_a_refused_panel_render_leaves_no_open_judges_card(world):
  """The render runs before the card opens: a configured file absent at HEAD refuses the open and leaves no card behind."""
  from test_judges import ONE
  configure(world, [{"file": "absent.md", "to": ["judges"]}])
  git(["commit", "-qam", "config", "--allow-empty"], world.repo)
  spec = spec_file(world)
  seed_handoff(world, spec)
  cid = card(world, spec, "review-spec")
  def cards():
    return sorted(p.name for p in world.artifacts.glob("**/runcards/*.json"))
  before = cards()
  question = world.repo.parent / "q-refused.md"
  question.write_text(ONE, encoding="utf-8")
  code, out = world.run("judges", "open", "--question", question, "--parent", cid)
  assert code == 1 and "absent.md" in out, out
  assert cards() == before
