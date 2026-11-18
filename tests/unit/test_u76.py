# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U76's tests: the reviewers module, its doctor line, `review open` taking a loaded reviewer and the frozen persona.

"""U76: custom reviewers, the helper."""

import pytest

import superegm  # the harness reloads the package per test: read its names at call time


def write_reviewer(root, name, text):
  """`.superegm/reviewers/<name>` under `root`, written as UTF-8 text."""
  path = root / ".superegm" / "reviewers" / name
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(text, encoding="utf-8")


@pytest.mark.parametrize("name, text", [
  ("Bad_id.md", "---\nname: X\nkinds: [spec]\n---\nbody"),
  ("nameless.md", "---\nkinds: [spec]\n---\nbody"),
  ("nokinds.md", "---\nname: X\nkinds: []\n---\nbody"),
  ("big.md", "---\nname: X\nkinds: [spec]\n---\n" + "b" * 8193),
  ("foreman.md", "---\nname: X\nkinds: [head]\n---\nbody")])
def test_a_bad_reviewer_file_is_refused_naming_it(world, name, text):
  """An id outside [a-z][a-z0-9-]{1,31}, no name, empty kinds, a body over 8,192 bytes and a non-reviewer override are each refused naming the file."""
  from superegm import reviewers
  write_reviewer(world.repo, "fine.md", "---\nname: Fine\nkinds: [spec, head]\n---\nA persona.\n")
  write_reviewer(world.repo, name, text)
  with pytest.raises(superegm.HandoffError) as refusal:
    reviewers.load(world.repo)
  assert f".superegm/reviewers/{name}" in str(refusal.value)


def test_doctor_prints_the_reviewers_line_after_mcp(world, monkeypatch, tmp_path):
  """With no reviewer file the line after `mcp:` is `reviewers: none`."""
  from test_doctor import arranged
  arranged(world, monkeypatch, tmp_path, None)
  got, out = world.run("doctor")
  lines = out.splitlines()
  assert got == 0, out
  assert lines[lines.index(next(l for l in lines if l.startswith("mcp:"))) + 1] == "reviewers: none"


@pytest.mark.parametrize("kind, reviewers, code, expect", [
  ("spec", "design,zoom-out,security", 0, "design"),
  ("head", "security", 1, "review open: security does not review head")])
def test_review_open_takes_a_loaded_reviewer_for_its_kinds(world, kind, reviewers, code, expect):
  """A loaded id whose kinds holds the review's kind opens; one that does not is refused; an overridden design keeps its id."""
  from test_review import SKILL_OF, approve, card, converged_spec, rjson, seed_handoff, spec_file
  from test_u37 import commit_file
  commit_file(world, ".superegm/reviewers/security.md", "---\nname: Security\nkinds: [spec]\n---\nHunt for secrets.\n")
  commit_file(world, ".superegm/reviewers/design.md", "---\nname: Design\nkinds: [spec]\n---\nA new design persona.\n")
  if kind == "spec":
    spec = spec_file(world)
  else:  # a plan, head or integrate review reads the frozen files: approve the spec first
    spec, acid, _ = converged_spec(world)
    assert approve(world, spec, acid, "--yes")[0] == 0
  seed_handoff(world, spec)
  cid = card(world, spec, SKILL_OF[kind])
  artifact = str(spec) if kind == "spec" else "U07"
  got, out = world.run("review", "open", "--kind", kind, "--artifact", artifact, "--reviewers", reviewers, "--astra", "off", "--runcard", cid)
  assert got == code and (expect in out if code else rjson(world, out.splitlines()[0])["reviewers"][0] == expect), out


def test_the_brief_prints_the_frozen_persona_and_the_record_carries_it(world):
  """approve-spec freezes each reviewer file by blob sha; a builder's branch edit changes neither the handoff's brief nor its record."""
  import json
  from test_review import A, SLUG, approve, card, converged_spec, head_round, hstore, opened, record, rjson, seed_handoff
  from test_u37 import blob_sha, commit_file
  frozen_bytes = b"---\nname: Security\nkinds: [spec, plan, head, integrate]\n---\nfrozen persona\n"
  commit_file(world, ".superegm/reviewers/security.md", frozen_bytes)
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  st = hstore(world)
  entry = json.loads(st.path("approvals", SLUG).read_text(encoding="utf-8"))["entries"][-1]
  sha = blob_sha(frozen_bytes)
  stored = json.loads(st.path("reviewers", sha).read_text(encoding="utf-8"))
  assert entry["reviewers"] == [{"id": "security", "sha": sha}] and stored["text"] == "frozen persona"
  assert [stored[k] for k in ("id", "sha", "name", "kinds")] == ["security", sha, "Security", ["spec", "plan", "head", "integrate"]]
  head_bytes = b"---\nname: Security\nkinds: [spec, plan, head, integrate]\n---\nhead persona\n"
  commit_file(world, ".superegm/reviewers/security.md", head_bytes)  # a builder's branch edits the file
  hid = entry["handoff_id"]
  seed_handoff(world, spec)
  plancard = card(world, spec, "review-plan", handoff=hid)
  got, brief_out = world.run("reviewers", "--brief", "security", "--handoff", hid, "--runcard", plancard, card=None)
  assert got == 0 and brief_out.strip() == "frozen persona", brief_out
  got, spec_out = world.run("reviewers", "--brief", "security", "--spec", str(spec), "--review", rid, "--round", 1, "--runcard", cid, card=None)
  assert got == 0 and spec_out.strip() == "head persona", spec_out
  spec_read = json.loads(st.path("reviews", rid, "persona-1-security.json").read_text(encoding="utf-8"))
  assert spec_read == {"id": "security", "sha": blob_sha(head_bytes), "text": "head persona"}
  got, out = world.run("reviewers", "--brief", "nobody", "--handoff", hid, "--runcard", plancard, card=None)
  assert got == 1 and "reviewers: " in out, out
  _, wcid, hrid = opened(world, "head", reviewers="change-review,security")
  head_round(world, 1, "posted", wcid, "revise")
  for reviewer in ("change-review", "security"):
    assert record(world, hrid, 1, reviewer, [], wcid, sha=A)[0] == 0
  reviewers = rjson(world, hrid, "round-1.json")["reviewers"]
  assert reviewers["security"]["persona"] == {"id": "security", "sha": sha} and "persona" not in reviewers["change-review"]


# ---------------------------------------------------------------- round 2

def approved_with(world, files):
  """`files` ({name: bytes}) committed, the spec approved, and a plan card of the handoff: (spec, cid, rid, hid, plancard, st, out)."""
  import json
  from test_review import SLUG, approve, card, converged_spec, hstore, seed_handoff
  from test_u37 import commit_file
  for name, data in files.items():
    commit_file(world, f".superegm/reviewers/{name}", data)
  spec, cid, rid = converged_spec(world)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0, out
  st = hstore(world)
  hid = json.loads(st.path("approvals", SLUG).read_text(encoding="utf-8"))["entries"][-1]["handoff_id"]
  seed_handoff(world, spec)
  return spec, cid, rid, hid, card(world, spec, "review-plan", handoff=hid), st, out


def brief_of(world, reviewer, hid, plancard):
  return world.run("reviewers", "--brief", reviewer, "--handoff", hid, "--runcard", plancard, card=None)


def test_files_of_one_content_each_read_their_own_id(world):
  """Reviewer files of the same bytes share one store copy named by the blob sha: each id still reads its frozen persona (U76 round 2)."""
  same = b"---\nname: Same\nkinds: [spec, plan, head, integrate]\n---\nsame persona\n"
  _, _, _, hid, plancard, _, _ = approved_with(world, {"alpha.md": same, "beta.md": same})
  for reviewer in ("alpha", "beta"):
    got, out = brief_of(world, reviewer, hid, plancard)
    assert got == 0 and out.strip() == "same persona", out


def test_the_store_copy_is_verified_against_its_sha(world):
  """An edited store copy is refused naming the file: the copy carries the file's bytes and the sha is re-derived from them (U76 round 2)."""
  import json
  from test_u37 import blob_sha
  data = b"---\nname: Security\nkinds: [plan]\n---\nfrozen persona\n"
  _, _, _, hid, plancard, st, _ = approved_with(world, {"security.md": data})
  path = st.path("reviewers", blob_sha(data))
  copy = json.loads(path.read_text(encoding="utf-8"))
  path.write_text(json.dumps({**copy, "text": "edited persona"}), encoding="utf-8")  # a field the bytes decide is read from the bytes
  got, out = brief_of(world, "security", hid, plancard)
  assert got == 0 and out.strip() == "frozen persona", out
  path.write_text(json.dumps({**copy, "source": copy["source"].replace("frozen", "edited")}), encoding="utf-8")
  got, out = brief_of(world, "security", hid, plancard)
  assert got == 1 and ".superegm/reviewers/security.md" in out, out


def test_a_handoff_with_no_approval_reads_no_reviewer_at_head(world):
  """A plan, head or integrate review of a handoff with no approval entry has no frozen reviewer: a file at HEAD is not one (U76 round 2)."""
  from test_review import SKILL_OF, card, seed_handoff, spec_file
  from test_u37 import commit_file
  commit_file(world, ".superegm/reviewers/security.md", "---\nname: Security\nkinds: [head]\n---\nHunt.\n")
  spec = spec_file(world)
  seed_handoff(world, spec)
  cid = card(world, spec, SKILL_OF["head"])
  got, out = world.run("review", "open", "--kind", "head", "--artifact", "U07", "--reviewers", "change-review,security", "--astra", "off", "--runcard", cid)
  assert got == 1 and "review open: unknown reviewer security" in out, out


def test_a_spec_round_records_the_persona_it_read_and_no_other(world):
  """A spec round's `persona` is the stored read a `--brief` made, never inferred from HEAD at record time; a bad file at HEAD blocks no record (U76 round 2)."""
  from test_review import opened, record, rjson
  from test_u37 import blob_sha, commit_file
  read = b"---\nname: Security\nkinds: [spec]\n---\nread persona\n"
  commit_file(world, ".superegm/reviewers/security.md", read)
  spec, cid, rid = opened(world, "spec", reviewers="design,zoom-out,security")
  got, _ = world.run("reviewers", "--brief", "security", "--spec", str(spec), "--review", rid, "--round", 1, "--runcard", cid, card=None)
  assert got == 0
  commit_file(world, ".superegm/reviewers/security.md", b"---\nname: Security\nkinds: [spec]\n---\nlater persona\n")
  commit_file(world, ".superegm/reviewers/design.md", b"---\nname: Design\nkinds: [spec]\n---\ncommitted after design was dispatched\n")
  commit_file(world, ".superegm/reviewers/bad.md", b"no frontmatter")
  assert record(world, rid, 1, "design", [], cid)[0] == 0
  assert record(world, rid, 1, "security", [], cid)[0] == 0
  reviewers = rjson(world, rid, "round-1.json")["reviewers"]
  assert reviewers["security"]["persona"] == {"id": "security", "sha": blob_sha(read)} and "persona" not in reviewers["design"]


def test_a_not_run_record_carries_no_persona_and_one_missing_copy_blocks_no_other_reviewer(world):
  """A `--not-run` record read no persona; a missing store copy refuses only the reviewer it belongs to (U76 round 2)."""
  from test_review import A, head_round, opened, record, rjson
  from test_u37 import blob_sha
  a = b"---\nname: Alpha\nkinds: [head]\n---\nalpha persona\n"
  b = b"---\nname: Beta\nkinds: [head]\n---\nbeta persona\n"
  _, _, _, hid, _, st, _ = approved_with(world, {"alpha.md": a, "beta.md": b})
  _, wcid, hrid = opened(world, "head", reviewers="change-review,alpha,beta")
  head_round(world, 1, "posted", wcid, "revise")
  st.path("reviewers", blob_sha(b)).unlink()
  assert record(world, hrid, 1, "change-review", [], wcid, sha=A)[0] == 0
  assert record(world, hrid, 1, "alpha", [], wcid, sha=A)[0] == 0
  got, out = record(world, hrid, 1, "beta", [], wcid, sha=A)
  assert got == 1 and ".superegm/reviewers/beta.md" in out, out
  assert record(world, hrid, 1, "beta", [], wcid, not_run="timed out")[0] == 0
  reviewers = rjson(world, hrid, "round-1.json")["reviewers"]
  assert "persona" not in reviewers["beta"] and "persona" not in reviewers["change-review"] and reviewers["alpha"]["persona"]["id"] == "alpha"


@pytest.mark.parametrize("text, says", [
  ("---\nname: X\nkinds: [spec]\nmodel: Not A Model\n---\nbody", "model"),
  ("---\nname: X\nkinds: [spec]\neffort: extreme\n---\nbody", "effort"),
  ("---\nname: X\nkinds: [spec, spec]\n---\nbody", "kinds"),
  ("---\nname: X\nname: Y\nkinds: [spec]\n---\nbody", "name"),
  ("---\nname: X\nkinds: [spec]\n", "not closed"),
  ("name: X\nkinds: [spec]\n", "frontmatter"),
  (b"---\nname: X\nkinds: [spec]\n---\n\xff\xfe", "UTF-8"),
  ("---\nname: X\nkinds: [other]\n---\nbody", "kinds")])
def test_a_malformed_reviewer_file_is_refused_with_its_reason(world, text, says):
  """A model or effort outside its form, a duplicated kind or key, an unclosed or missing frontmatter and a non-UTF-8 body are each refused naming the file and the reason."""
  from superegm import reviewers
  path = world.repo / ".superegm" / "reviewers" / "odd.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_bytes(text if isinstance(text, bytes) else text.encode("utf-8"))
  with pytest.raises(superegm.HandoffError) as refusal:
    reviewers.load(world.repo)
  assert ".superegm/reviewers/odd.md" in str(refusal.value) and says in str(refusal.value)


def test_astra_is_not_a_reviewer_file(world):
  """The Astra lane is not a goldfish: `astra.md` is refused as `foreman.md` is (U76 round 2)."""
  from superegm import reviewers
  write_reviewer(world.repo, "astra.md", "---\nname: X\nkinds: [head]\n---\nbody")
  with pytest.raises(superegm.HandoffError, match="astra"):
    reviewers.load(world.repo)


def test_the_frontmatter_takes_comments_and_block_lists_and_the_limit_is_the_persona(world):
  """`#` lines and a block list are valid frontmatter; a persona of exactly 8,192 bytes is not refused for its final newline (U76 round 2)."""
  from superegm import reviewers
  write_reviewer(world.repo, "listed.md", "---\n# who reviews\nname: Listed\nkinds:\n  - spec\n  - head\nmodel: opus\neffort: high\n---\n" + "b" * 8192 + "\n")
  loaded = reviewers.load(world.repo)["listed"]
  assert (loaded["kinds"], loaded["model"], loaded["effort"], len(loaded["text"])) == (["spec", "head"], "opus", "high", 8192)


def test_load_refuses_what_it_cannot_read(world):
  """A git failure at `ref` and an unreadable file are refusals, not an empty list (U76 round 2)."""
  import os
  from superegm import reviewers
  with pytest.raises(superegm.HandoffError, match="nosuchref"):
    reviewers.load(world.repo, "nosuchref")
  write_reviewer(world.repo, "locked.md", "---\nname: X\nkinds: [head]\n---\nbody")
  path = world.repo / ".superegm" / "reviewers" / "locked.md"
  path.chmod(0)
  try:
    if os.access(path, os.R_OK):
      pytest.skip("the file stays readable (root)")
    with pytest.raises(superegm.HandoffError, match="locked.md"):
      reviewers.load(world.repo)
  finally:
    path.chmod(0o644)


@pytest.mark.parametrize("files, expect", [
  ({"alpha.md": "---\nname: A\nkinds: [spec, head]\n---\nbody"}, "reviewers: alpha (spec, head)"),
  ({"alpha.md": "---\nname: A\nkinds: [spec]\n---\nbody", "beta.md": "---\nname: B\nkinds: [plan]\n---\nbody"}, "reviewers: alpha (spec), beta (plan)"),
  ({"alpha.md": "---\nkinds: [spec]\n---\nbody"}, "reviewers: .superegm/reviewers/alpha.md: name is required")])
def test_doctor_prints_each_loaded_reviewer_or_the_first_refusal(world, monkeypatch, tmp_path, files, expect):
  """The `reviewers:` line lists each loaded id with its kinds, or names the first refused file and its reason; it never fails the exit (U76 round 2)."""
  from test_doctor import arranged
  for name, text in files.items():
    write_reviewer(world.repo, name, text)
  arranged(world, monkeypatch, tmp_path, None)
  got, out = world.run("doctor")
  assert expect in out.splitlines() and got == 0, out


def test_approve_spec_prints_the_changed_reviewer_files_and_amend_units_copies_them(world):
  """The first approval prints each reviewer file with its sha, a re-approval only the changed one; `--amend-units` copies the frozen list (U76 round 2)."""
  from test_review import approve, approval, card, converged_spec
  from test_u37 import blob_sha, commit_file
  a = b"---\nname: A\nkinds: [spec]\n---\nalpha\n"
  b = b"---\nname: B\nkinds: [spec]\n---\nbeta\n"
  commit_file(world, ".superegm/reviewers/alpha.md", a)
  commit_file(world, ".superegm/reviewers/beta.md", b)
  spec, cid, rid = converged_spec(world)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0 and f"approve-spec: reviewers .superegm/reviewers/alpha.md {blob_sha(a)}" in out, out
  assert f"approve-spec: reviewers .superegm/reviewers/beta.md {blob_sha(b)}" in out, out
  changed = b"---\nname: B\nkinds: [spec]\n---\nbeta, changed\n"
  commit_file(world, ".superegm/reviewers/beta.md", changed)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0, out
  assert f"approve-spec: reviewers .superegm/reviewers/beta.md {blob_sha(changed)}" in out and "alpha.md" not in out, out
  frozen = approval(world)["entries"][-1]["reviewers"]
  assert [r["id"] for r in frozen] == ["alpha", "beta"]
  icid = card(world, spec, "integrate")
  commit_file(world, ".superegm/reviewers/alpha.md", b"---\nname: A\nkinds: [spec]\n---\nalpha, changed after\n")
  spec.write_text(spec.read_text(encoding="utf-8") + "| U02 | more | U01 | S |\n", encoding="utf-8")
  code, out = approve(world, spec, icid, "--amend-units")
  assert code == 0, out
  last = approval(world)["entries"][-1]
  assert last["kind"] == "amend-units" and last["reviewers"] == frozen


# ---------------------------------------------------------------- round 3

def test_an_effort_of_max_is_loaded(world):
  """`config.reviewers.effort` takes `low` to `max`: a file's `effort` takes the same forms (U76 round 3)."""
  from superegm import reviewers
  write_reviewer(world.repo, "deep.md", "---\nname: Deep\nkinds: [spec]\neffort: max\n---\nbody")
  assert reviewers.load(world.repo)["deep"]["effort"] == "max"


@pytest.mark.parametrize("body", [" " * 8193, " " * 5000 + "x" + " " * 5000, "x" * 8193 + "\n", "\n" * 8193 + "x"],
                         ids=["spaces", "padded", "newline-last", "newlines-first"])
def test_the_limit_counts_the_body_as_written(world, body):
  """A body over 8,192 bytes is refused whatever surrounds the persona; only the file's last newlines are not counted (U76 round 3)."""
  from superegm import reviewers
  write_reviewer(world.repo, "wide.md", "---\nname: Wide\nkinds: [spec]\n---\n" + body)
  with pytest.raises(superegm.HandoffError, match="wide.md"):
    reviewers.load(world.repo)


def test_the_persona_keeps_its_indentation(world):
  """The printed persona loses its leading and trailing blank lines and no indentation of its first line (U76 round 3)."""
  from superegm import reviewers
  write_reviewer(world.repo, "indent.md", "---\nname: I\nkinds: [spec]\n---\n\n  \n    - first\n  - second  \n\n")
  assert reviewers.load(world.repo)["indent"]["text"] == "    - first\n  - second"


def spec_briefed(world, files):
  """A spec review with `files` at HEAD: (spec, cid, rid, st, brief), `brief(id, round)` running `reviewers --brief --spec`."""
  from test_review import hstore, opened
  from test_u37 import commit_file
  for name, data in files.items():
    commit_file(world, f".superegm/reviewers/{name}", data)
  spec, cid, rid = opened(world, "spec", reviewers="design,zoom-out,security")
  brief = lambda reviewer, n: world.run("reviewers", "--brief", reviewer, "--spec", str(spec), "--review", rid, "--round", n, "--runcard", cid, card=None)
  return spec, cid, rid, hstore(world), brief


def test_a_second_brief_of_a_round_prints_the_read_the_first_stored(world):
  """A spec review stores what it read on the round: a later brief of that round prints it though HEAD moved; the next round reads HEAD again (U76 round 3)."""
  from test_u37 import commit_file
  _, _, _, _, brief = spec_briefed(world, {"security.md": b"---\nname: S\nkinds: [spec]\n---\nfirst persona\n"})
  assert brief("security", 1)[1].strip() == "first persona"
  commit_file(world, ".superegm/reviewers/security.md", b"---\nname: S\nkinds: [spec]\n---\nsecond persona\n")
  assert brief("security", 1)[1].strip() == "first persona"
  assert brief("security", 2)[1].strip() == "second persona"


def test_a_damaged_persona_read_is_refused_naming_it(world):
  """A truncated or keyless `persona-<n>-<id>.json` ends `--brief` and `review record` in a refusal naming the file, not a traceback (U76 round 3)."""
  from test_review import record
  _, cid, rid, st, brief = spec_briefed(world, {"security.md": b"---\nname: S\nkinds: [spec]\n---\npersona\n"})
  assert brief("security", 1)[0] == 0
  path = st.path("reviews", rid, "persona-1-security.json")
  for damage in ('{"id": "sec', '{"text": "x"}', "[]"):
    path.write_text(damage, encoding="utf-8")
    got, out = brief("security", 1)
    assert got == 1 and "persona-1-security.json" in out and "Traceback" not in out, out
    got, out = record(world, rid, 1, "security", [], cid)
    assert got == 1 and "persona-1-security.json" in out and "Traceback" not in out, out


def test_a_spec_round_of_a_repository_reviewer_needs_its_read(world):
  """A completed spec record of a repository reviewer with no stored read is refused, so the panel never completes without evidence of its persona; a not-run one needs none (U76 round 3)."""
  from test_review import record, rjson
  _, cid, rid, _, brief = spec_briefed(world, {"security.md": b"---\nname: S\nkinds: [spec]\n---\npersona\n"})
  got, out = record(world, rid, 1, "security", [], cid)
  assert got == 1 and "security" in out and "reviewers --brief" in out, out
  assert record(world, rid, 1, "security", cid=cid, not_run="timed out")[0] == 0
  assert brief("security", 2)[0] == 0
  assert record(world, rid, 2, "security", [], cid)[0] == 0
  assert rjson(world, rid, "round-2.json")["reviewers"]["security"]["persona"]["id"] == "security"


@pytest.mark.parametrize("make, expect", [
  ("other_card", "was opened under handoff"),
  ("no_entry", "no approval entry"),
  ("unfrozen", "is not frozen in handoff"),
  ("no_review", "--spec requires --review and --round"),
  ("round_zero", "a round is 1 or more"),
  ("unknown_at_head", "unknown reviewer nobody"),
  ("both", "exactly one of --handoff and --spec"),
  ("neither", "exactly one of --handoff and --spec"),
  ("handoff_round", "--review and --round go with --spec"),
  ("unit_with_spec", "--unit goes with --handoff")])
def test_the_brief_refuses_each_misuse(world, make, expect):
  """`reviewers --brief` refuses a card of another handoff, a handoff with no approval entry or no such frozen reviewer, a spec read missing its review or round, an unknown id and each bad flag combination (U76 round 3)."""
  import test_review
  spec, cid, rid, hid, plancard, st, _ = approved_with(world, {"security.md": b"---\nname: S\nkinds: [spec, plan]\n---\npersona\n"})
  base = ["reviewers", "--brief", "security"]
  if make == "other_card":  # a card the handoff's store holds, opened under another handoff
    path = st.path("runcards", plancard)
    path.write_text(path.read_text(encoding="utf-8").replace(f'"handoff": "{hid}"', '"handoff": "elsewhere"'), encoding="utf-8")
  if make == "no_entry":  # the handoff's approval entry is gone
    superegm.atomic_write(st.path("approvals", test_review.SLUG), {"entries": []})
  argv = {
    "other_card": [*base, "--handoff", hid, "--runcard", plancard],
    "no_entry": [*base, "--handoff", hid, "--runcard", plancard],
    "unfrozen": ["reviewers", "--brief", "design", "--handoff", hid, "--runcard", plancard],
    "no_review": [*base, "--spec", str(spec), "--runcard", cid],
    "round_zero": [*base, "--spec", str(spec), "--review", rid, "--round", 0, "--runcard", cid],
    "unknown_at_head": ["reviewers", "--brief", "nobody", "--spec", str(spec), "--review", rid, "--round", 1, "--runcard", cid],
    "both": [*base, "--handoff", hid, "--spec", str(spec), "--runcard", plancard],
    "neither": [*base, "--runcard", plancard],
    "handoff_round": [*base, "--handoff", hid, "--round", 1, "--runcard", plancard],
    "unit_with_spec": [*base, "--spec", str(spec), "--unit", "U07", "--runcard", cid]}[make]
  got, out = world.run(*argv, card=None)
  assert got == 1 and expect in out and "Traceback" not in out, out
