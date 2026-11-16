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
