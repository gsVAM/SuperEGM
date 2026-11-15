# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U73

"""U73: an external comment reaches the builder whole (`review ingest` reads a thread's root, spec section 5.3)."""

import pytest

import superegm
from superegm.review import read_threads, thread_line, thread_severity

from test_review import REPO, cm, rv


@pytest.mark.parametrize("root, claim, severity", [
  ('<!-- devin-review-comment {"id": 1} -->\n**Bug**: the lock is\nnever released', "**Bug**: the lock is never released", "high"),
  ("**Bug**: real text <!-- unterminated\nhidden", "**Bug**: real text", "high"),
  ("<!-- a -->\n<!-- b -->", "(no text outside hidden markup)", "low"),
  ("x" * 1200, "x" * 999 + "…", "low")])
def test_root_claim_strips_hidden_markup(world, root, claim, severity):
  # the root loses every HTML comment, to the end when unterminated; severity reads its first line with text
  config = superegm.load_config(world.repo)
  thread = {"path": "src/x.py", "line": 3, "commit_id": "c" * 40, "root": root, "body": root, "bot": True, "review_body": False}
  assert thread_line("external:devin-ai-integration[bot]", 1, 1, thread, severity, config).split(" | ", 4)[4] == claim
  assert thread_severity(thread, config, None) == severity


def test_replies_stay_out_of_the_claim_and_severity(world):
  # read_threads keeps the root as `root`; a reply only joins `body`
  config = superegm.load_config(world.repo)
  world.gh.threads[70] = [cm(1, "devin-ai-integration[bot]", "<!-- devin-review-comment {} -->"), cm(2, "alice", "bug: still broken", reply_to=1)]
  world.gh.reviews[70] = [rv(14, "erin", "**Issue**: the retry never backs off")]
  threads = read_threads(REPO, 70, skip=set())
  assert threads[0]["root"] == "<!-- devin-review-comment {} -->" and "bug: still broken" in threads[0]["body"]
  assert thread_severity(threads[0], config, None) == "low"
  assert thread_line("external:devin-ai-integration[bot]", 1, 1, threads[0], "low", config).endswith("| (no text outside hidden markup)")
  assert threads[1]["root"] == threads[1]["body"] == "**Issue**: the retry never backs off"
