# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U37's tests: the `instructions` key, its freezing at approval, the one renderer, the stored first render and the builder's section.

"""U37: instructions, the key and the builder."""

import hashlib
import json
import subprocess

import pytest

import superegm  # the harness reloads the package per test: read its names at call time
from conftest import REPO, git, set_config
from test_review import SLUG, approve, card, converged_spec, hstore

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
