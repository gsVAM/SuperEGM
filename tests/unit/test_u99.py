# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U99's GitHub calls (1.3 design section 3.2)

"""U99: `gh_retry`'s one loop (5xx, connection reset, rate limit), the one-line `gh:` exit and `discover_pr`'s branch lookup."""

import pytest


@pytest.mark.parametrize("call, stderr, failures, sleeps, raises", [
    ("gh_json", "HTTP 502", 1, [1], False),
    ("gh_json", "HTTP 503", 2, [1, 4], False),
    ("gh_json", "HTTP 504", 3, [1, 4, 16], False),
    ("gh_json", "read: connection reset by peer", 3, [1, 4, 16], False),
    ("gh_json", "HTTP 504", 4, [1, 4, 16], True),
    ("gh_json", "HTTP 404", 1, [], True),
    ("gh_json", "HTTP 422", 1, [], True),
    ("gh_json", "HTTP 403: You have exceeded a secondary rate limit", 1, [60], False),
    ("gh_retry", "HTTP 502", 1, [1], False),
    ("gh_retry", "read: connection reset by peer", 2, [1, 4], False),
])
def test_gh_retry_retries_5xx_and_reset(world, call, stderr, failures, sleeps, raises):
  import superegm
  gh_calls = []

  def flaky(args, cwd, token=None):
    gh_calls.append(list(args))
    if len(gh_calls) <= failures:
      return 1, "", stderr
    return 0, "{}", ""

  world.ns["GH"] = flaky
  raised = False
  try:
    getattr(superegm, call)(["api", "repos/example-org/webhooks"])
  except superegm.GhError:
    raised = True
  assert raised == raises
  assert world.sleeps == sleeps
  assert len(gh_calls) == len(sleeps) + 1
