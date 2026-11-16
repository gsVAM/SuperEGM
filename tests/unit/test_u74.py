# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U74's tests: the `dir` entry of `instructions`, its freezing, the index and the Astra lane's pastes.

"""U74: reference documents, the helper."""

import pytest

from conftest import git
from test_review import approve, converged_spec
from test_u37 import RULES, configure

DIR = "docs/reference"
ROLES = ["builder", "foreman", "reviewers", "judges"]


def commit_files(world, files):
  """`files` ({path: text or bytes}) written and committed together."""
  for rel, data in files.items():
    path = world.repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
  git(["add", "-A", "--", *files], world.repo)
  git(["commit", "-qm", "add reference documents"], world.repo)


@pytest.mark.parametrize("case, named", [
  ("51 files", "docs/reference/f51.md"), ("a 65,537-byte file", "docs/reference/big.md"),
  ("an absent folder", "docs/reference"), ("an empty folder", "docs/reference"),
  ("both file and dir", "instructions")])
def test_a_dir_entry_outside_the_limits_is_refused(world, case, named):
  """At most 50 files, each at most 65,536 bytes; the folder present and non-empty; exactly one of file and dir."""
  entry = {"dir": DIR, "to": ROLES}
  files = {
    "51 files": {f"{DIR}/f{n:02d}.md": "x\n" for n in range(1, 52)},
    "a 65,537-byte file": {f"{DIR}/big.md": "x" * 65537},
    "an absent folder": {},
    "an empty folder": {f"{DIR}/notes.txt": "no markdown here\n"},   # no *.md file in the folder
    "both file and dir": {f"{DIR}/a.md": "A first line.\n", RULES: "Run the suite.\n"},
  }[case]
  if case == "both file and dir":
    entry["file"] = RULES
  commit_files(world, {"README-seed.txt": "seed\n", **files})
  configure(world, [entry])
  spec, cid, rid = converged_spec(world)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 1 and named in out, out
  assert "must be a list of" not in out, out   # refused for its reason, not as a malformed shape
  if case == "both file and dir":
    assert "exactly one of file and dir" in out, out


def test_a_folder_freezes_each_document_with_its_raw_copy(world):
  """Each document frozen by its 12-hex blob sha, the raw bytes beside the .json."""
  from test_review import hstore
  from test_u37 import blob_sha, entries_of
  texts = {f"{DIR}/b.md": "B first line.\nmore\n", f"{DIR}/a.md": "A first line.\n", f"{DIR}/sub/c.md": "C é line.\n"}
  commit_files(world, {**texts, f"{DIR}/skip.txt": "not markdown\n"})
  configure(world, [{"dir": DIR, "to": ROLES}])
  spec, cid, rid = converged_spec(world)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0, out
  entry = entries_of(world)[-1]["instructions"][0]
  assert entry["dir"] == DIR and entry["to"] == ROLES
  assert [f["file"] for f in entry["files"]] == ["docs/reference/a.md", "docs/reference/b.md", "docs/reference/sub/c.md"]
  for f in entry["files"]:
    assert f["sha"] == blob_sha(texts[f["file"]].encode("utf-8")) and set(f) == {"file", "sha"}
    assert f"{f['file']} {f['sha']}" in out, out
  store_dir = hstore(world).path("instructions", entry["files"][0]["sha"]).parent
  assert sorted(p.name for p in store_dir.iterdir()) == sorted(
    [f"{f['sha']}.json" for f in entry["files"]] + [f"{f['sha']}.md" for f in entry["files"]])
  for f in entry["files"]:
    assert (store_dir / f"{f['sha']}.md").read_bytes() == texts[f["file"]].encode("utf-8")


def test_the_index_lists_each_document_after_the_pasted_files(world):
  """One heading, one line per document addressed to the role, then the verbatim sentence."""
  from superegm.instructions import render
  from test_review import hstore
  from test_u37 import blob_sha, commit_file, entries_of
  a_text = "\n  \n" + "z" * 130 + "\nrest\n"
  commit_file(world, RULES, "Run the suite.\n")
  commit_files(world, {f"{DIR}/a.md": a_text, f"{DIR}/b.md": "# B title\n"})
  configure(world, [{"file": RULES, "to": ["builder"]}, {"dir": DIR, "to": ["builder", "reviewers"]}])
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  hid = entries_of(world)[-1]["handoff_id"]
  st = hstore(world)
  sha, sha_b = blob_sha(a_text.encode()), blob_sha(b"# B title\n")
  store = st.path("instructions", sha).parent.parent   # the store root: instructions/<sha>.md under it
  manifest, text = render(st, "builder", handoff_id=hid)
  assert text.index("## Reference documents") > text.index("rules.md")
  assert text.count("## Reference documents") == 1
  assert f"- docs/reference/a.md ({sha}): {'z' * 120} — read {store}/instructions/{sha}.md\n" in text
  assert f"- docs/reference/b.md ({sha_b}): # B title — read {store}/instructions/{sha_b}.md\n" in text
  assert "z" * 121 not in text
  assert text.rstrip().endswith("Read a reference document when your task touches what its first line names; "
                                "cite it by file when a finding rests on it.")
  assert manifest == [{"file": RULES, "sha": blob_sha(b"Run the suite.\n")},
                      {"file": "docs/reference/a.md", "sha": sha}, {"file": "docs/reference/b.md", "sha": sha_b}]
  # a role the folder is not addressed to gets nothing of it; a role with only the folder gets its heading
  assert render(st, "judges", handoff_id=hid) == ([], "")
  only = render(st, "reviewers", handoff_id=hid)
  assert only[1].startswith("# Repository instructions\n") and "```" not in only[1]
  assert only[0] == manifest[1:]
