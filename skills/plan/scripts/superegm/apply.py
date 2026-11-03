# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_apply`, `Budget`, `apply_writes`, `create_issue` and `post_link` as the apply module.

"""superegm apply: create labels, issues and links (needs --yes)."""

import os
import tempfile
import time
import urllib.parse

import superegm.verify
import superegm as core


def register(subparsers):
  p = core.add_parser(subparsers, "apply", "create labels, issues and links (needs --yes)")
  p.add_argument("--yes", action="store_true")
  p.add_argument("--max-writes", type=int)
  p.set_defaults(run=run)


class Budget:
  """Counts content-creating writes and stops cleanly at --max-writes."""

  class Exhausted(Exception):
    pass

  def __init__(self, limit):
    self.limit, self.count = limit, 0

  def spend(self):
    if self.limit is not None and self.count >= self.limit:
      raise Budget.Exhausted()
    self.count += 1


def run(args):
  plan, st = core.locate(args)
  handoff = core.Handoff(plan, st)
  state = handoff.state
  repo = handoff.config["repo"]
  if not args.yes:
    raise core.HandoffError("apply writes to GitHub: run it with --yes only after the user confirmed the dry run")
  if not state.get("confirmed_sha256"):
    raise core.HandoffError("no confirmed_sha256 in the state: run dry-run and ask the user first")
  if (state.get("repo") or "").lower() != repo.lower():
    raise core.HandoffError(f"config repo {repo} differs from the state's {state.get('repo')}: run dry-run again")
  # Before any write: the canonical list carries the gate hashes as values, so
  # an edit the rendered bodies do not show leaves it identical while still
  # reaching the builder through unit_<id>.md.
  core.require_reviewed_pair(handoff)
  writes = handoff.writes()
  if core.sha256_text(core.canonical(writes)) != state["confirmed_sha256"]:
    raise core.HandoffError("the write list changed since the dry run (plan, config, template or repo): run dry-run again")
  # A banned_terms or mention rule added after the dry run leaves the write list
  # unchanged, so the hash above cannot catch it. Scan the outgoing text itself.
  problems = core.scan_handoff(handoff)
  if problems:
    raise core.HandoffError("the current scan refuses the text that would be written:\n  "
                       + "\n  ".join(problems))
  state.setdefault("confirmed_at", core.now_iso())
  budget = Budget(args.max_writes)
  save = lambda: core.save_state(handoff.artifact_dir, state)
  try:
    apply_writes(handoff, writes, budget, save)
  except Budget.Exhausted:
    state["verify"] = {"sha256": state["confirmed_sha256"], "complete": False,
                       "checked": "0 of 0", "problems": [], "note": f"stopped after {budget.count} writes"}
    save()
    print(f"stopped after {budget.count} writes (--max-writes): resume with `apply --yes`")
    return 0
  except core.GhError as error:
    save()
    if error.rate_limited:
      raise core.HandoffError(f"rate limited: resume with `apply --yes` after {time.strftime('%H:%M', time.gmtime(core.NOW() + 3600))} UTC") from error
    if error.http_status == 410:
      raise core.HandoffError(f"issues are disabled on {repo} (410)") from error
    raise core.HandoffError(str(error)) from error
  save()
  return core.verify.run_verify(handoff, writes)


def apply_writes(handoff: core.Handoff, writes, budget: Budget, save):
  state, repo = handoff.state, handoff.config["repo"]
  labels = state.setdefault("labels", {})
  for item in writes:
    if item[0] != "label" or labels.get(item[1]) in ("done", "exists"):
      continue
    budget.spend()
    try:
      core.gh_retry(["label", "create", item[1], "-R", repo, "--color", core.LABEL_COLOR,
                "--description", f"EGM handoff label ({item[1]})"])
      labels[item[1]] = "done"
      core.SLEEP(1)
    except core.GhError as error:
      if error.http_status == 422 or "already exists" in (error.stderr + error.stdout):
        existing = {l["name"] for l in core.gh_pages(f"repos/{repo}/labels")}
        if item[1] not in existing:
          raise
        labels[item[1]] = "done"
      else:
        raise
    save()
  units = state.setdefault("units", {})
  tracking = state.setdefault("tracking", {})
  listing = core.gh_pages(f"repos/{repo}/issues?labels="
                     f"{urllib.parse.quote(handoff.handoff_label(), safe='')}"
                     f"&state=all&per_page=100")
  for issue in listing:
    if "pull_request" in issue:
      continue
    match = core.MARKER_RE.match((issue.get("body") or "").lstrip())
    if not match or match.group(1) != handoff.handoff_id:
      continue
    target = tracking if match.group(2) == "tracking" else units.setdefault(match.group(2), {})
    if not target.get("number"):
      target.update({"number": issue["number"], "id": issue["id"], "done": True})
  save()
  for record in [tracking, *units.values()]:
    if record.get("number") and not record.get("id"):
      record["id"] = core.gh_json(["api", f"repos/{repo}/issues/{record['number']}"])["id"]
      record["done"] = True
      save()
  for item in writes:
    if item[0] != "issue":
      continue
    kind, title, label_set, body = item[1], item[2], item[3], item[4]
    target = tracking if kind == "tracking" else units.setdefault(kind, {})
    if kind != "tracking" and not target.get("deferred"):
      target["wave"] = handoff.graph.wave[kind]
    if target.get("done"):
      continue
    if kind != "tracking" and not tracking.get("number"):
      raise core.HandoffError("tracking issue missing: it is created first")
    numbers = {u: d["number"] for u, d in units.items() if d.get("number")}
    text = core.fill_numbers(body, numbers, tracking.get("number"))
    budget.spend()
    number = create_issue(repo, title, text, label_set, handoff.artifact_dir)
    # Record the number before the id read: a failure between them must leave a
    # resumable state, not an issue that later stages treat as complete.
    target["number"] = number
    save()
    target["id"] = core.gh_json(["api", f"repos/{repo}/issues/{number}"])["id"]
    target["done"] = True
    save()
    core.SLEEP(1)
  links = state.setdefault("links", {})
  existing_subs = None
  for item in writes:
    if item[0] != "sub_issue" or links.get(f"sub:{item[1]}") == "done":
      continue
    if existing_subs is None:
      existing_subs = {s["id"] for s in core.gh_pages(f"repos/{repo}/issues/{tracking['number']}/sub_issues")}
    child = units[item[1]]
    if child["id"] in existing_subs:
      links[f"sub:{item[1]}"] = "done"
      save()
      continue
    budget.spend()
    post_link(f"repos/{repo}/issues/{tracking['number']}/sub_issues", {"sub_issue_id": child["id"]},
              lambda: child["id"] in {s["id"] for s in core.gh_pages(f"repos/{repo}/issues/{tracking['number']}/sub_issues")},
              links, f"sub:{item[1]}")
    save()
    core.SLEEP(1)
  blocked_cache = {}
  for item in writes:
    if item[0] != "blocked_by":
      continue
    key = f"blocked:{item[1]}<-{item[2]}"
    if links.get(key) == "done":
      continue
    blocked, blocker = units[item[1]], units[item[2]]
    endpoint = f"repos/{repo}/issues/{blocked['number']}/dependencies/blocked_by"
    if item[1] not in blocked_cache:
      blocked_cache[item[1]] = {b["id"] for b in core.gh_pages(endpoint)}
    if blocker["id"] in blocked_cache[item[1]]:
      links[key] = "done"
      save()
      continue
    budget.spend()
    post_link(endpoint, {"issue_id": blocker["id"]},
              lambda: blocker["id"] in {b["id"] for b in core.gh_pages(endpoint)}, links, key)
    blocked_cache.pop(item[1], None)
    save()
    core.SLEEP(1)


def create_issue(repo, title, body, labels, artifact_dir):
  with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", prefix=".egm_body_",
                                   dir=str(artifact_dir), delete=False) as handle:
    handle.write(body)
    path = handle.name
  try:
    args = ["issue", "create", "-R", repo, "--title", title, "--body-file", path]
    for label in labels:
      args += ["--label", label]
    for attempt in range(4):
      try:
        url = core.gh(args).strip().splitlines()[-1]
        break
      except core.GhError as error:
        if error.rate_limited and attempt < 3:
          core.SLEEP(error.retry_after or 60)
          continue
        raise
  finally:
    os.unlink(path)
  number = url.rstrip("/").split("/")[-1]
  if not number.isdigit():
    raise core.HandoffError(f"gh issue create printed no issue URL: {url}")
  return int(number)


def post_link(endpoint, fields, present, links, key):
  try:
    core.gh_post(endpoint, fields)
    links[key] = "done"
  except core.GhError as error:
    if error.http_status in (422, 409):
      if present():
        links[key] = "done"
      else:
        links[key] = f"error: HTTP {error.http_status}"
      return
    raise
