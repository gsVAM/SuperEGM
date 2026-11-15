# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U73

"""U73: an external comment reaches the builder whole (`review ingest` reads a thread's root, spec section 5.3)."""

import pytest

import superegm
from superegm.review import thread_line, thread_severity


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
