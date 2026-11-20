# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U88's tests: the judges rule a builder's contest first (design section 7.8).

"""U88: a builder's contest of a head finding goes to the judges' panel first in normal mode as in leavemealone."""

from pathlib import Path

from test_leavemealone_finish import head_review, seed

COMMENTS_TEXT = "change-review-1-1 | high | src/x.py:3 | the retry loop never backs off\n"
DIFF_TEXT = "--- a/src/x.py\n+++ b/src/x.py\n@@ -3 +3 @@\n-retry()\n+retry(backoff=1)\n"
BODY_TEXT = "### U07: Retry\n\n## Objective\nDeliver with a bounded retry.\n"
SPEC_RANGE_TEXT = "### 4.2 Retries\nA retry waits before it tries again.\n"
AMENDMENTS_TEXT = "amendment 1: the wait is one second.\n"


def evidence(world):
  """The five evidence files of a head contest, written beside the repo: `comments.md`, the diff, the body, `r1/spec_range.md`, `r1/amendments.md`."""
  folder = world.repo.parent / "evidence"
  files = {"comments.md": COMMENTS_TEXT, "diff": DIFF_TEXT, "body": BODY_TEXT,
           "r1/spec_range.md": SPEC_RANGE_TEXT, "r1/amendments.md": AMENDMENTS_TEXT}
  for name, text in files.items():
    (folder / name).parent.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")
  return [str(folder / name) for name in files]


def contest(world, tmp_path):
  """A normal-mode head review of U07 with a high finding the builder contested; its opened panel and question text."""
  seed(world)
  runcard = world.card("wave")
  review = head_review(world, runcard, tmp_path)
  code, out = world.run("judges", "question", "--review", review, "--round", "1",
                        "--reason", "change-review-1-1=the test covers it", "--runcard", runcard)
  assert code == 0, out
  path = Path(out.splitlines()[0])
  flags = [part for item in evidence(world) for part in ("--evidence", item)]
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
