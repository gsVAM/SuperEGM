# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U37's tests: the `instructions` key, its freezing at approval, the one renderer, the stored first render and the builder's section.

"""U37: instructions, the key and the builder."""

import hashlib
import json
import subprocess

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import REPO, git, set_config
from test_review import SLUG, approve, card, converged_spec, hstore, seed_handoff

BANNED = ["(?i)secret-codename"]
RULES = ".superegm/rules.md"


def configure(world, value):
  """The repository's config with `instructions` set to `value` (a malformed value stays as written)."""
  set_config(world, repo=REPO, banned_terms=BANNED, instructions=value)


def commit_file(world, rel, data):
  """`rel` written (text or bytes) and committed."""
  path = world.repo / rel
  path.parent.mkdir(parents=True, exist_ok=True)
  (path.write_bytes if isinstance(data, bytes) else lambda d: path.write_text(d, encoding="utf-8"))(data)
  git(["add", "--", rel], world.repo)
  git(["commit", "-qm", f"add {rel}"], world.repo)


@pytest.mark.parametrize("value, refused", [
  ([], False),
  ([{"file": RULES, "to": ["builder", "judges"]}], False),
  ([{"file": RULES, "to": []}], True),
  ([{"file": RULES, "to": ["owner"]}], True),
  ([{"to": ["builder"]}], True),
  ({"file": "x"}, True),
])
def test_instructions_key_validated(world, value, refused):
  """approve-spec and instructions --spec refuse a malformed key, naming it."""
  assert superegm.DEFAULT_CONFIG["instructions"] == []
  commit_file(world, RULES, "Run the suite.\n")
  configure(world, value)
  spec, cid, rid = converged_spec(world)
  code, err = approve(world, spec, cid, "--yes")
  assert "unknown keys" not in err
  assert (code == 1 and "instructions" in err) if refused else code == 0, err
  git(["add", "-A"], world.repo)
  git(["commit", "-qm", "config at HEAD", "--allow-empty"], world.repo)
  code, err = world.run("instructions", "--role", "reviewers", "--spec", str(spec), "--review", rid, "--round", 1, "--runcard", cid)
  assert (code == 1 and "instructions" in err) if refused else code == 0, err


def blob_sha(data: bytes) -> str:
  """git's blob sha of `data`, 12 hex."""
  return hashlib.sha1(b"blob %d\0" % len(data) + data).hexdigest()[:12]


def entries_of(world):
  return json.loads(hstore(world).path("approvals", SLUG).read_text(encoding="utf-8"))["entries"]


@pytest.mark.parametrize("case", [
  "file present", "file absent at the approval commit", "file of 8,193 bytes", "file not UTF-8",
  "first approval prints every file with its sha", "re-approval prints the changed file alone",
  "--amend-units copies list and shas", "approval commit pruned", "store copy edited",
])
def test_approve_spec_freezes_the_files(world, case):
  """Each file frozen with its 12-hex blob sha and copied to instructions/<sha>.json; refusals name the file."""
  from superegm import approve_spec
  text = "Run the suite.\n"
  base = git(["rev-parse", "HEAD"], world.repo).strip()
  if case == "file absent at the approval commit":
    (world.repo / RULES).parent.mkdir(parents=True, exist_ok=True)
    (world.repo / RULES).write_text(text, encoding="utf-8")   # in the tree, never committed
  else:
    commit_file(world, RULES, {"file of 8,193 bytes": "x" * 8193, "file not UTF-8": b"\xff\xfe rules\n"}.get(case, text))
  commit_file(world, "b.md", "Be brief.\n")
  configure(world, [{"file": RULES, "to": ["builder"]}, {"file": "b.md", "to": ["judges"]}])
  spec, cid, rid = converged_spec(world)
  code, out = approve(world, spec, cid, "--yes")
  if case in ("file absent at the approval commit", "file of 8,193 bytes", "file not UTF-8"):
    assert code == 1 and RULES in out and "instructions" in out, out
    assert not hstore(world).path("approvals", SLUG).exists()
    return
  assert code == 0, out
  sha12, bsha = blob_sha(text.encode()), blob_sha(b"Be brief.\n")
  frozen = [{"file": RULES, "to": ["builder"], "sha": sha12}, {"file": "b.md", "to": ["judges"], "sha": bsha}]
  assert entries_of(world)[-1]["instructions"] == frozen
  st = hstore(world)
  assert json.loads(st.path("instructions", sha12).read_text(encoding="utf-8")) == {"file": RULES, "sha": sha12, "text": text}
  assert "instructions" in approve_spec.FROZEN_FIELDS
  if case == "first approval prints every file with its sha":
    assert f"{RULES} {sha12}" in out and f"b.md {bsha}" in out, out
  elif case == "re-approval prints the changed file alone":
    commit_file(world, "b.md", "Be briefer.\n")
    code, out = approve(world, spec, cid, "--yes")
    assert code == 0, out
    changed = blob_sha(b"Be briefer.\n")
    assert f"b.md {changed}" in out and RULES not in out, out
    assert entries_of(world)[-1]["instructions"][1]["sha"] == changed
  elif case == "--amend-units copies list and shas":
    commit_file(world, RULES, "Changed after the approval.\n")
    configure(world, [{"file": RULES, "to": ["foreman"]}])
    git(["commit", "-qam", "config edit"], world.repo)
    icid = card(world, spec, "integrate")
    spec.write_text(spec.read_text(encoding="utf-8") + "| U02 | more | U01 | S |\n", encoding="utf-8")
    code, out = approve(world, spec, icid, "--amend-units")
    assert code == 0, out
    assert entries_of(world)[-1]["kind"] == "amend-units" and entries_of(world)[-1]["instructions"] == frozen
  elif case == "approval commit pruned":
    git(["reset", "-q", "--hard", base], world.repo)
    git(["reflog", "expire", "--expire=now", "--all"], world.repo)
    git(["gc", "-q", "--prune=now"], world.repo)
    assert subprocess.run(["git", "cat-file", "-e", sha12], cwd=world.repo, capture_output=True).returncode != 0
    assert approve_spec.read_copy(hstore(world), RULES, sha12) == text
  elif case == "store copy edited":
    path = st.path("instructions", sha12)
    path.write_text(json.dumps({"file": RULES, "sha": sha12, "text": "Skip the suite.\n"}), encoding="utf-8")
    with pytest.raises(superegm.HandoffError, match=RULES):
      approve_spec.read_copy(hstore(world), RULES, sha12)


def test_render_section_form(world, tmp_path):
  """One heading, each addressed file in list order under ## <file>, fenced one backtick longer than its longest run
  (min 3); nothing for a role none is addressed to; a config HEAD lacks reads []; each handoff renders its own list."""
  from superegm import approve_spec
  from superegm.instructions import render
  commit_file(world, "a.md", "plain\n")
  commit_file(world, "b.md", "has `````five\n")
  configure(world, [{"file": "a.md", "to": ["builder"]}, {"file": "b.md", "to": ["reviewers", "builder"]}])
  spec, cid, rid = converged_spec(world)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0, out
  st = hstore(world)
  hid = entries_of(world)[-1]["handoff_id"]
  manifest, text = render(st, "builder", handoff_id=hid)
  assert manifest == [{"file": "a.md", "sha": blob_sha(b"plain\n")}, {"file": "b.md", "sha": blob_sha(b"has `````five\n")}]
  assert text.startswith("# Repository instructions\n")
  assert text.count("# Repository instructions") == 1 and text.index("## a.md") < text.index("## b.md")
  assert "## a.md\n```\nplain\n```" in text and "## b.md\n``````\nhas `````five\n``````" in text
  assert render(st, "reviewers", handoff_id=hid)[0] == [{"file": "b.md", "sha": blob_sha(b"has `````five\n")}]
  assert render(st, "foreman", handoff_id=hid) == ([], "")
  assert render(st, "builder", handoff_id="no-such-handoff") == ([], "")
  # the files at HEAD: the config's list there
  assert render(st, "builder", root=world.repo) == (manifest, text)
  bare = tmp_path / "bare-repo"
  bare.mkdir()
  git(["init", "-q"], bare)
  (bare / "x.md").write_text("x\n", encoding="utf-8")
  git(["add", "x.md"], bare)
  git(["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "x"], bare)
  assert render(st, "reviewers", root=bare) == ([], "")
  # two handoffs of one spec whose lists differ: each renders its own, from its store copies
  path = st.path("approvals", SLUG)
  record = json.loads(path.read_text(encoding="utf-8"))
  for other, data in (("h-a", b"first\n"), ("h-b", b"second\n")):
    sha = blob_sha(data)
    approve_spec.write_copy(st, {"file": "a.md", "sha": sha, "text": data.decode()})
    record["entries"].append({**record["entries"][-1], "handoff_id": other, "instructions": [{"file": "a.md", "to": ["builder"], "sha": sha}]})
  path.write_text(json.dumps(record), encoding="utf-8")
  ha, hb = render(st, "builder", handoff_id="h-a"), render(st, "builder", handoff_id="h-b")
  assert ha[0] != hb[0] and "first" in ha[1] and "second" in hb[1]


@pytest.mark.parametrize("form, stored_at", [
  ("--handoff h --runcard wave-child --unit U01", "card instructions.reviewers.local"),
  ("--handoff h --runcard plan-card --lane astra", "card instructions.reviewers.astra"),
  ("--spec s.md --review r --round 2 --runcard spec-card", "reviews/r/instructions-2-reviewers-local.json"),
])
def test_first_render_is_stored_and_reused(world, form, stored_at):
  """The first call per card, role and lane, or round, role and lane, renders and stores; later calls print it."""
  commit_file(world, RULES, "Run the suite.\n")
  configure(world, [{"file": RULES, "to": ["reviewers"]}])
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  entry = entries_of(world)[-1]
  hid = entry["handoff_id"]
  seed_handoff(world, spec)
  if "wave-child" in form:
    wave = card(world, spec, "wave", handoff=hid)
    used = card(world, "U01", "wave", parent=wave, handoff=hid)
    argv = ["--handoff", hid, "--runcard", used, "--unit", "U01"]
  elif "plan-card" in form:
    used = card(world, spec, "review-plan", handoff=hid)
    argv = ["--handoff", hid, "--runcard", used, "--lane", "astra"]
  else:
    used, argv = cid, ["--spec", spec, "--review", rid, "--round", 2, "--runcard", cid]

  def instructions(*more):
    return world.run("instructions", "--role", "reviewers", *argv, *more, card=None)

  code, first_out = instructions()
  assert code == 0 and first_out.startswith("# Repository instructions\n") and "Run the suite." in first_out, first_out
  manifest = [{"file": RULES, "sha": blob_sha(b"Run the suite.\n")}]
  st = hstore(world)
  if stored_at.startswith("card"):
    _, role, lane = stored_at.split()[1].split(".")
    record = superegm.load_card(st, used)["instructions"][role][lane]
    assert record == {"approved_at": entry["approved_at"], "manifest": manifest, "text": first_out}
  else:
    record = json.loads(st.path("reviews", rid, "instructions-2-reviewers-local.json").read_text(encoding="utf-8"))
    assert record == {"manifest": manifest, "text": first_out}
  commit_file(world, RULES, "Skip the suite.\n")                       # a HEAD edit and a re-approval
  assert approve(world, spec, cid, "--yes")[0] == 0
  assert entries_of(world)[-1]["instructions"][0]["sha"] != manifest[0]["sha"]
  code, second_out = instructions()
  assert code == 0 and second_out == first_out
  code, out = world.run("instructions", "--role", "builder", "--handoff", hid, card=None)
  assert code == 1 and out.removeprefix("superegm: ").startswith("runcard: "), out  # the helper prefixes its name
  code, out = world.run("instructions", "--role", "builder", "--handoff", hid, "--spec", spec, "--runcard", cid, card=None)
  assert code == 1, out
  git(["rm", "-q", RULES], world.repo)
  git(["commit", "-qm", "rules removed"], world.repo)
  code, out = world.run("instructions", "--role", "reviewers", "--spec", spec, "--review", rid, "--round", 1, "--runcard", cid, card=None)
  assert code == 1 and RULES in out, out


@pytest.mark.parametrize("to", [["builder", "judges"], ["judges"]])
def test_builder_prompt_carries_the_section(world, monkeypatch, to):
  """A first render through launch-builder, write enforcement on, places the section last and records the manifest."""
  from superegm import approve_spec, launch_builder
  from superegm.instructions import render
  from test_builders import UNIT, launches_of, seed
  s, card_id, hid, _ = seed(world)
  text = "Run the suite.\n"
  sha12 = blob_sha(text.encode())
  spec = json.loads(s.path("state").read_text(encoding="utf-8"))["design"]["path"]
  path = s.path("approvals", superegm.spec_slug(spec))
  record = json.loads(path.read_text(encoding="utf-8"))
  record["instructions"] = [{"file": RULES, "to": to, "sha": sha12}]       # the frozen list of the handoff's approval
  path.write_text(json.dumps(record), encoding="utf-8")
  approve_spec.write_copy(s, {"file": RULES, "sha": sha12, "text": text})
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  monkeypatch.setattr(launch_builder, "start_detached", lambda command, log, env: 4242)
  assert world.run("launch", "--runcard", card_id)[0] == 0
  code, out = world.run("launch-builder", "--unit", UNIT, "--round", 1, "--runcard", card_id)
  assert code == 0, out
  prompt = s.path("launches", f"{UNIT}_r1_prompt.md").read_text(encoding="utf-8")
  launch = launches_of(s)[-1]
  builder_section = render(s, "builder", handoff_id=hid)[1]
  stored = superegm.load_card(s, card_id)["instructions"]["builder"]["local"]
  if "builder" in to:
    assert builder_section.startswith("# Repository instructions\n") and "## .superegm/rules.md\n```\nRun the suite.\n```" in builder_section
    assert prompt.rstrip().endswith(builder_section.rstrip())
    assert launch["instructions"] == [{"file": RULES, "sha": sha12}]
    assert stored["manifest"] == launch["instructions"] and stored["text"] == builder_section
  else:
    assert builder_section == "" and "# Repository instructions" not in prompt
    assert launch["instructions"] == []
