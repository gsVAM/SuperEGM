# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U37's tests: the `instructions` key, its freezing at approval, the one renderer, the stored first render and the builder's section.

"""U37: instructions, the key and the builder."""

import hashlib
import json
import shutil
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


# ---------------------------------------------- round 2: the review's findings


def test_identical_files_share_one_verified_copy(world):
  """Two files of the same bytes, or a file renamed between approvals, share instructions/<sha>.json: the copy is
  verified by its sha alone, so each file renders and none overwrites the other's copy."""
  from superegm import approve_spec
  from superegm.instructions import render
  commit_file(world, "a.md", "Same text.\n")
  commit_file(world, "b.md", "Same text.\n")
  configure(world, [{"file": "a.md", "to": ["builder"]}, {"file": "b.md", "to": ["builder"]}])
  spec, cid, rid = converged_spec(world)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0, out
  st, sha = hstore(world), blob_sha(b"Same text.\n")
  hid = entries_of(world)[-1]["handoff_id"]
  manifest, text = render(st, "builder", handoff_id=hid)
  assert manifest == [{"file": "a.md", "sha": sha}, {"file": "b.md", "sha": sha}]
  assert "## a.md\n```\nSame text.\n```" in text and "## b.md\n```\nSame text.\n```" in text
  approve_spec.write_copy(st, {"file": "renamed.md", "sha": sha, "text": "Same text.\n"})   # a later approval's rename
  assert approve_spec.read_copy(st, "a.md", sha) == approve_spec.read_copy(st, "renamed.md", sha) == "Same text.\n"
  assert render(st, "builder", handoff_id=hid) == (manifest, text)


def bare_repo(tmp_path, files):
  """A fresh repository whose one commit holds `files` ({path: text or bytes})."""
  root = tmp_path / "head-repo"
  root.mkdir()
  git(["init", "-q"], root)
  for rel, data in files.items():
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
  git(["add", "-A"], root)
  git(["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qm", "x"], root)
  return root


@pytest.mark.parametrize("files, named", [
  ({".superegm/config.json": json.dumps({"instructions": [{"file": "big.md", "to": ["reviewers"]}]}), "big.md": "x" * 8193},
   "big.md"),
  ({".superegm/config.json": "{not json"}, "instructions"),
  ({".superegm/config.json": "[1, 2]"}, "instructions"),
])
def test_head_render_refuses_an_oversized_file_and_a_malformed_config(world, tmp_path, files, named):
  """The HEAD path holds a file to the 8,192-byte limit and refuses a config that is not a JSON object, naming it."""
  from superegm.instructions import render
  root = bare_repo(tmp_path, files)
  with pytest.raises(superegm.HandoffError, match=named):
    render(hstore(world), "reviewers", root=root)


def test_head_render_defaults_root_to_the_checkout(world, tmp_path, monkeypatch):
  """`render` with neither a handoff id nor a root reads the checkout it runs in."""
  from superegm.instructions import render
  root = bare_repo(tmp_path, {".superegm/config.json": json.dumps({"instructions": [{"file": "a.md", "to": ["judges"]}]}),
                              "a.md": "Judge it.\n"})
  monkeypatch.chdir(root)
  assert render(hstore(world), "judges") == ([{"file": "a.md", "sha": blob_sha(b"Judge it.\n")}],
                                             "# Repository instructions\n\n## a.md\n```\nJudge it.\n```\n")


@pytest.mark.parametrize("case", ["review not opened", "review id escapes", "review of another spec",
                                  "integrate review of the spec", "--unit with --spec"])
def test_spec_render_binds_the_review_to_the_spec(world, case):
  """`--spec` stores a round's render only under a review opened on that spec; a review id that is no plain name,
  a review never opened or one of another spec is refused and nothing is written."""
  commit_file(world, RULES, "Run the suite.\n")
  configure(world, [{"file": RULES, "to": ["reviewers"]}])
  git(["commit", "-qam", "config"], world.repo)
  spec, cid, rid = converged_spec(world)
  st = hstore(world)
  integrate = f"spec-{superegm.spec_slug(spec)}-integrate-c1"   # its review.json names the same spec
  review = {"review not opened": "never-opened", "review id escapes": "../../escaped", "review of another spec": "other",
            "integrate review of the spec": integrate, "--unit with --spec": rid}[case]
  if case in ("review of another spec", "integrate review of the spec"):
    other = json.loads(st.path("reviews", rid, "review.json").read_text(encoding="utf-8"))
    if case == "review of another spec":
      other["artifact"] = str(world.repo / "docs/other-design.md")
    st.path("reviews", review, "review.json").parent.mkdir(parents=True, exist_ok=True)
    st.path("reviews", review, "review.json").write_text(json.dumps(other), encoding="utf-8")
  unit = ["--unit", "U01"] if case == "--unit with --spec" else []   # --unit belongs to --handoff alone
  if unit:   # a unit's card: --unit alone would pass the artifact check for any --spec
    path = st.path("runcards", cid)
    path.write_text(json.dumps({**json.loads(path.read_text(encoding="utf-8")), "artifact": "U01"}), encoding="utf-8")
  before = sorted(p for p in st.root.parent.rglob("*") if p.is_file())
  code, out = world.run("instructions", "--role", "reviewers", "--spec", spec, "--review", review, "--round", 1,
                        *unit, "--runcard", cid, card=None)
  assert code == 1 and "instructions" in out, out
  assert sorted(p for p in st.root.parent.rglob("*") if p.is_file()) == before


def test_handoff_render_refuses_another_handoff_than_the_cards(world):
  """`--handoff` must name the handoff the card was opened under: another handoff's list never lands on the card."""
  commit_file(world, RULES, "Run the suite.\n")
  configure(world, [{"file": RULES, "to": ["reviewers"]}])
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  hid = entries_of(world)[-1]["handoff_id"]
  seed_handoff(world, spec)
  other = card(world, spec, "review-plan", handoff=hid)
  st = hstore(world)
  path = st.path("runcards", other)
  record = json.loads(path.read_text(encoding="utf-8"))
  path.write_text(json.dumps({**record, "handoff": "sample-000000"}), encoding="utf-8")   # a card of an older handoff
  code, out = world.run("instructions", "--role", "reviewers", "--handoff", hid, "--runcard", other, card=None)
  assert code == 1 and "instructions" in out, out
  assert "instructions" not in superegm.load_card(hstore(world), other)
  used = card(world, spec, "review-plan", handoff=hid)   # a card of this handoff (opening it interrupts `other`)
  code, out = world.run("instructions", "--role", "reviewers", "--handoff", hid, "--runcard", used, card=None)
  assert code == 0, out
  path = st.path("runcards", used)
  record = json.loads(path.read_text(encoding="utf-8"))
  del record["handoff"]                                   # a card opened before cards recorded their handoff
  path.write_text(json.dumps(record), encoding="utf-8")
  assert hstore(world).handoff_id == hid
  code, out = world.run("instructions", "--role", "builder", "--handoff", hid, "--runcard", used, card=None)
  assert code == 0, out


def test_launch_builder_refuses_a_card_of_another_handoff(world, monkeypatch):
  """launch-builder never stores or reuses a render on a card opened under another handoff than the store's."""
  from superegm import launch_builder
  from test_builders import UNIT, seed
  s, card_id, hid, _ = seed(world)
  monkeypatch.setenv("SUPEREGM_BUILDER_TOKEN", "ghp_builder")
  monkeypatch.setattr(launch_builder, "start_detached", lambda command, log, env: 4242)
  assert world.run("launch", "--runcard", card_id)[0] == 0
  path = s.path("runcards", card_id)
  record = json.loads(path.read_text(encoding="utf-8"))
  record["instructions"] = {"builder": {"local": {"approved_at": None, "manifest": [{"file": RULES, "sha": "0" * 12}],
                                                  "text": "# Repository instructions\n\n## x\n```\nhandoff A's\n```\n"}}}
  path.write_text(json.dumps(record), encoding="utf-8")   # handoff A's card, its builder render cached
  other = "sample-design-0b0b0b"                           # handoff B of the same spec, opened beside it
  shutil.copytree(s.root / hid, s.root / other, ignore=shutil.ignore_patterns("runcards"))
  state = json.loads((s.root / other / "state.json").read_text(encoding="utf-8"))
  (s.root / other / "state.json").write_text(json.dumps({**state, "handoff_id": other}), encoding="utf-8")
  handoff = json.loads(s.path("handoffs", hid).read_text(encoding="utf-8"))
  s.path("handoffs", other).write_text(json.dumps({**handoff, "id": other}), encoding="utf-8")
  (approvals,) = (s.root / "approvals").glob("*.json")    # B's own approval entry, the spec's latest
  log = json.loads(approvals.read_text(encoding="utf-8"))
  log = log if "entries" in log else {"path": log.get("path"), "entries": [log]}
  log["entries"].append({**log["entries"][-1], "handoff_id": other})
  approvals.write_text(json.dumps(log), encoding="utf-8")
  code, out = world.run("launch-builder", "--handoff", other, "--unit", UNIT, "--round", 1, "--runcard", card_id)
  assert code == 1 and out.startswith("superegm: launch-builder: ") and f"opened under handoff {hid}" in out, out
  assert not list((s.root / other).rglob(f"{UNIT}_r1_prompt.md"))


# ---------------------------------------------- round 3: the review's findings


@pytest.mark.parametrize("bad", ["/etc/rules.md", "../rules.md", "docs/../../rules.md", "rules\x00.md"])
def test_instructions_key_refuses_a_path_outside_the_repository(world, bad):
  """A `file` that is absolute, climbs out with `..` or holds a NUL is refused by both readers, naming the key."""
  commit_file(world, RULES, "Run the suite.\n")
  configure(world, [{"file": bad, "to": ["reviewers"]}])
  spec, cid, rid = converged_spec(world)
  code, err = approve(world, spec, cid, "--yes")
  assert code == 1 and "instructions" in err and "Traceback" not in err, err
  git(["add", "-A"], world.repo)
  git(["commit", "-qm", "config at HEAD", "--allow-empty"], world.repo)
  code, err = world.run("instructions", "--role", "reviewers", "--spec", str(spec), "--review", rid, "--round", 1, "--runcard", cid)
  assert code == 1 and "instructions" in err and "Traceback" not in err, err


def test_head_render_refuses_a_file_not_utf8(world, tmp_path):
  """The HEAD path refuses a file that is not UTF-8, naming it."""
  from superegm.instructions import render
  root = bare_repo(tmp_path, {".superegm/config.json": json.dumps({"instructions": [{"file": "bad.md", "to": ["judges"]}]}),
                              "bad.md": b"\xff\xfe rules\n"})
  with pytest.raises(superegm.HandoffError, match="bad.md is not UTF-8"):
    render(hstore(world), "judges", root=root)


def test_head_render_reads_one_commit(world, tmp_path, monkeypatch):
  """The config and the files come from the one commit `HEAD` named when the render began, even when `HEAD` moves
  between the reads."""
  from superegm import instructions
  root = bare_repo(tmp_path, {".superegm/config.json": json.dumps({"instructions": [{"file": "a.md", "to": ["reviewers"]}]}),
                              "a.md": "First.\n"})
  real, moved = instructions.blob, []

  def blob(r, ref, rel):
    data = real(r, ref, rel)
    if rel == instructions.CONFIG and not moved:   # another process commits between the config read and the files'
      (root / "a.md").write_text("Second.\n", encoding="utf-8")
      git(["-c", "user.name=t", "-c", "user.email=t@example.invalid", "commit", "-qam", "moved"], root)
      moved.append(True)
    return data
  monkeypatch.setattr(instructions, "blob", blob)
  manifest, text = instructions.render(hstore(world), "reviewers", root=root)
  assert moved and "First." in text and "Second." not in text
  assert manifest == [{"file": "a.md", "sha": blob_sha(b"First.\n")}]


@pytest.mark.parametrize("argv, says", [
  (["--spec", "SPEC"], "--spec requires --review and --round"),
  (["--spec", "SPEC", "--review", "RID"], "--spec requires --review and --round"),
  (["--spec", "SPEC", "--review", "RID", "--round", 0], "--round"),
  (["--spec", "SPEC", "--review", "RID", "--round", -1], "--round"),
  (["--handoff", "HID", "--review", "RID"], "--review and --round go with --spec"),
  (["--handoff", "HID", "--round", 1], "--review and --round go with --spec"),
])
def test_instructions_refuses_misplaced_flags(world, argv, says):
  """`--spec` needs `--review` and a `--round` of 1 or more; `--review` and `--round` never go with `--handoff`;
  nothing is written."""
  commit_file(world, RULES, "Run the suite.\n")
  configure(world, [{"file": RULES, "to": ["reviewers"]}])
  git(["commit", "-qam", "config"], world.repo)
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  hid = entries_of(world)[-1]["handoff_id"]
  used = cid
  if "--handoff" in argv:
    seed_handoff(world, spec)
    used = card(world, spec, "review-plan", handoff=hid)
  names = {"SPEC": str(spec), "RID": rid, "HID": hid}
  argv = [names.get(a, a) if isinstance(a, str) else a for a in argv]
  st = hstore(world)
  before = sorted(p for p in st.root.parent.rglob("*") if p.is_file())
  code, out = world.run("instructions", "--role", "reviewers", *argv, "--runcard", used, card=None)
  assert code == 1 and says in out, out
  assert sorted(p for p in st.root.parent.rglob("*") if p.is_file()) == before


def test_approval_repairs_an_edited_store_copy(world):
  """A store copy edited after approval is rewritten from the approval commit's bytes at the next approval."""
  from superegm import approve_spec
  text = "Run the suite.\n"
  commit_file(world, RULES, text)
  configure(world, [{"file": RULES, "to": ["builder"]}])
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  sha12, st = blob_sha(text.encode()), hstore(world)
  st.path("instructions", sha12).write_text(json.dumps({"file": RULES, "sha": sha12, "text": "Skip the suite.\n"}),
                                            encoding="utf-8")
  with pytest.raises(superegm.HandoffError, match=RULES):
    approve_spec.read_copy(st, RULES, sha12)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0, out
  assert approve_spec.read_copy(hstore(world), RULES, sha12) == text


def test_freeze_names_the_ref_it_read(world):
  """A file absent from `HEAD` before the approval commit is refused as absent at HEAD."""
  (world.repo / RULES).parent.mkdir(parents=True, exist_ok=True)
  (world.repo / RULES).write_text("Run the suite.\n", encoding="utf-8")   # in the tree, never committed
  configure(world, [{"file": RULES, "to": ["builder"]}])
  spec, cid, rid = converged_spec(world)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 1 and f"{RULES} is absent at HEAD" in out, out


def test_a_card_without_a_handoff_renders_nothing(world):
  """A card render with no handoff id (a flat 1.0 store's launch) reads no `HEAD`: it stores and returns nothing."""
  from superegm.instructions import render_stored
  configure(world, [{"file": "missing.md", "to": ["builder"]}])
  git(["add", "-A"], world.repo)
  git(["commit", "-qm", "config naming a file HEAD lacks"], world.repo)
  spec, cid, rid = converged_spec(world)
  st = hstore(world)
  assert render_stored(st, "builder", card=cid, handoff_id=None, root=world.repo) == ([], "")
  assert superegm.load_card(st, cid)["instructions"]["builder"]["local"] == {"approved_at": None, "manifest": [], "text": ""}
