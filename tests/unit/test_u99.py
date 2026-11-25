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
    ("gh_json", "HTTP 422: read: connection reset by peer", 1, [], True),  # a 4xx is never retried, whatever its text says
    ("gh_retry", "HTTP 404: connection reset", 1, [], True),
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


@pytest.mark.parametrize("stderr", ["HTTP 500", 'HTTP 500: Internal Server Error\n{"message": "Server Error"}\n'])
def test_gh_error_prints_one_line(world, monkeypatch, stderr):
  import argparse
  import superegm
  world.ns["GH"] = lambda args, cwd, token=None: (1, "", stderr)  # a 500 is not retried

  def probe(args):  # a subcommand whose one gh read fails
    return 0 if superegm.gh_json(["api", "repos/example-org/webhooks"]) else 0

  class Probe:
    def parse_args(self, argv=None):
      return argparse.Namespace(command="probe", writes=(), run=probe)

  monkeypatch.setattr(superegm, "build_parser", Probe)
  code = world.main(["probe"])
  out, err = world.capsys.readouterr()
  assert code == 1
  assert len(err.strip().splitlines()) == 1 and err.startswith("gh: ")
  assert "Traceback" not in out + err


@pytest.mark.parametrize("graphql, on_branch, matches, candidates", [
    ([41], [], [41], []),
    ([], [52], [], [52]),  # PR 52's closingIssuesReferences name the unit's issue
    ([], [53], [], [53]),  # PR 53 has none
])
def test_discover_pr_second_lookup_is_the_branch(world, graphql, on_branch, matches, candidates):
  import superegm
  from conftest import REPO, applied, handoff_store, make_pr, state_of
  gh = applied(world)
  state = state_of(world)
  handoff_id, issue = state["handoff_id"], state["units"]["U01"]["number"]
  branch = f"superegm/{handoff_id}/U01"
  handoff = superegm.Handoff(superegm.here(state["plan"]), handoff_store(world))
  gh.graphql[issue] = [{**make_pr(gh, n, "a" * 40, closes=[(REPO, issue)], branch=branch),
                        "repository": {"nameWithOwner": REPO}} for n in graphql]
  for n in on_branch:
    make_pr(gh, n, "b" * 40, closes=[(REPO, issue)] if n == 52 else [], branch=branch)
  found, cands = superegm.discover_pr(handoff, "U01", issue)
  pr_list_calls = [c for c in gh.calls if c[:2] == ["pr", "list"]]
  assert ([m["number"] for m in found], [c["number"] for c in cands]) == (matches, candidates)
  assert bool(pr_list_calls) == (not graphql)
  assert all(c[c.index("--head") + 1] == branch and c[c.index("--state") + 1] == "all"
             and "1000" not in c for c in pr_list_calls)
