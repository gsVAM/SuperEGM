# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: EGM's `cmd_apply`, `Budget`, `apply_writes`, `create_issue` and `post_link` on the confirmed write list of unfiled units; `filings[]` and `base_at_start` before the first write; the labels of spec section 10; an adopted issue re-read before any write (U13).

"""superegm apply: create labels, issues and links (needs --yes)."""

import os
import tempfile
import time
import urllib.parse
from pathlib import Path

import superegm.verify
import superegm as core
from superegm import gate, scan

WRITES = frozenset(['file', 'state'])  # the store kinds this subcommand writes
SKILLS = frozenset(['file'])  # the skills whose card this subcommand accepts


def register(subparsers):
  p = core.add_parser(subparsers, "apply", "create labels, issues and links (needs --yes)")
  p.add_argument("--spec", dest="design", required=True, help="the approved spec the filing is for")
  p.add_argument("--yes", action="store_true")
  p.add_argument("--max-writes", type=int)
  p.set_defaults(run=run, writes=WRITES)


def handoff_label(handoff) -> str:
  """The 6-hex handoff label (spec section 10)."""
  return handoff.labels["handoff_prefix"] + handoff.handoff_id[-6:]


def derived_labels(handoff) -> list:
  """Creation order: unit, tracking, the handoff label, stopped, then one per wave."""
  names = [handoff.labels["unit"], handoff.labels["tracking"], handoff_label(handoff), handoff.labels["stopped"]]
  return names + [handoff.wave_label(w) for w in sorted(handoff.graph.waves)]


def unit_labels(handoff, uid) -> list:
  return sorted({handoff.labels["unit"], handoff.wave_label(handoff.graph.wave[uid]), handoff_label(handoff),
                 *handoff.labels["extra"]})


def tracking_labels(handoff) -> list:
  return sorted({handoff.labels["tracking"], handoff_label(handoff)})


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
  card = core.require_runcard(args, SKILLS)
  handoff = gate.open_handoff(Path(args.design))
  state, st = handoff.state, handoff.store
  repo = handoff.config["repo"]
  if not args.yes:
    raise core.HandoffError("apply writes to GitHub: run it with --yes only after the owner chose Create (or in leavemealone-mode)")
  confirmed = state.get("confirmed") or {}
  if not confirmed.get("sha256"):
    raise core.HandoffError("no confirmed write list in the state: run dry-run first")
  if (state.get("repo") or "").lower() != repo.lower():
    raise core.HandoffError(f"config repo {repo} differs from the state's {state.get('repo')}: run dry-run again")
  gate.require_gate(handoff)
  # The unit set is the dry run's, so a resumed apply recomputes the same list; an adopted
  # unit's number and old body sha256 come from that list too (the dry run's read, spec section 10).
  units = {w[1] for w in confirmed["writes"] if w[0] == "issue" and w[1] != "tracking"}
  adopted = {w[1]: (w[5], w[6]) for w in confirmed["writes"] if w[0] == "issue" and len(w) == 7}
  writes = gate.pending_writes(handoff, units, adopted)
  if core.sha256_text(core.canonical(writes)) != confirmed["sha256"] \
      or core.canonical(writes) != core.canonical(confirmed["writes"]):
    raise core.HandoffError("the write list changed since the dry run (plan, config, template or repo): run dry-run again")
  hashes = gate.body_hashes(handoff)
  for uid in sorted(units):
    converged, sha = gate.converged_review(handoff.artifact_dir, uid)
    if not converged or sha != hashes[uid]:
      raise core.HandoffError(f"apply: {uid} body differs from its converged round")
  # A banned_terms or mention rule added after the dry run leaves the write list
  # unchanged, so the hash above cannot catch it. Scan the outgoing text itself.
  problems = scan.scan_handoff(handoff)
  if problems:
    raise core.HandoffError("the current scan refuses the text that would be written:\n  "
                            + "\n  ".join(problems))
  check_adopted(handoff, writes)
  sha = confirmed["sha256"]
  if not any(f.get("sha256") == sha for f in state.get("filings") or []):
    # Once per write-list hash, before the first write: the list a resumed or
    # later filing is verified against, and the base the integrate diff starts from.
    state.setdefault("filings", []).append({"sha256": sha, "writes": confirmed["writes"], "at": core.now_iso()})
    state.setdefault("base_at_start", core.run_git(["rev-parse", handoff.config["base"]], handoff.repo_root).strip())
    core.journal(st, f"filing {sha[:12]}: {len(units)} units ({', '.join(sorted(units))})")
    if card["mode"] == "leavemealone":
      core.journal(st, "Create: automatic (leavemealone)")
    core.save_state(handoff.artifact_dir, state)
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


def check_adopted(handoff, writes) -> None:
  """Before the first write, re-read every adopted issue not yet done: one whose body already
  carries this handoff's marker for the unit is done (a crash past the edit resumes); otherwise
  refuse one whose body no longer hashes to the dry run's old body sha256, or that is gone
  (spec section 10)."""
  repo, units = handoff.config["repo"], handoff.state.setdefault("units", {})
  for item in writes:
    if item[0] != "issue" or len(item) != 7 or units.get(item[1], {}).get("done"):
      continue
    number, old_sha = item[5], item[6]
    try:
      issue = core.gh_json(["api", f"repos/{repo}/issues/{number}"])
    except core.GhError as error:
      if error.http_status == 404:
        raise core.HandoffError(f"adopt: #{number} not in {repo}") from error
      raise core.HandoffError(str(error)) from error
    match = core.body.MARKER_RE.match((issue.get("body") or "").lstrip())
    if match and match.groups()[:2] == (handoff.handoff_id, item[1]):
      units.setdefault(item[1], {}).update({"number": number, "id": issue["id"], "done": True})
    elif core.sha256_text(issue.get("body") or "") != old_sha:
      raise core.HandoffError(f"adopt: #{number} body changed since the dry run")


def apply_writes(handoff: core.Handoff, writes, budget: Budget, save):
  state, repo = handoff.state, handoff.config["repo"]
  labels = state.setdefault("labels", {})
  for item in writes:
    if item[0] != "label" or labels.get(item[1]) in ("done", "exists"):
      continue
    budget.spend()
    try:
      core.gh_retry(["label", "create", item[1], "-R", repo, "--color", core.LABEL_COLOR,
                "--description", f"SuperEGM label ({item[1]})"])
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
  # Marker recovery: the issues this handoff created before a crash lost the
  # state write, found by the 6-hex label and the section 9.1 marker line.
  listing = core.gh_pages(f"repos/{repo}/issues?labels="
                          f"{urllib.parse.quote(handoff_label(handoff), safe='')}"
                          f"&state=all&per_page=100")
  for issue in listing:
    if "pull_request" in issue:
      continue
    match = core.body.MARKER_RE.match((issue.get("body") or "").lstrip())
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
    if kind != "tracking":
      target["wave"] = handoff.graph.wave[kind]
    numbers = {u: d["number"] for u, d in units.items() if d.get("number")}
    text = core.body.fill_numbers(body, numbers, tracking.get("number"))
    if kind == "tracking" and target.get("number"):
      # The tracking issue belongs to the latest filing: a later filing (or a
      # recovered issue with no `filing`) re-asserts its body once, an edit.
      if target.get("filing") != state["confirmed_sha256"]:
        budget.spend()
        edit_issue(repo, target["number"], text, handoff.artifact_dir)
        target["filing"] = state["confirmed_sha256"]
        save()
        core.SLEEP(1)
      continue
    if target.get("done"):
      continue
    if kind != "tracking" and not tracking.get("number"):
      raise core.HandoffError("tracking issue missing: it is created first")
    budget.spend()
    if len(item) == 7:
      # An adopted issue (spec section 10): the unit labels first, then the body, one write.
      number = item[5]
      core.gh_retry(["issue", "edit", str(number), "-R", repo, "--add-label", ",".join(label_set)])
      edit_issue(repo, number, text, handoff.artifact_dir)
    else:
      number = create_issue(repo, title, text, label_set, handoff.artifact_dir)
    # Record the number before the id read: a failure between them must leave a
    # resumable state, not an issue that later stages treat as complete.
    target["number"] = number
    save()
    target["id"] = core.gh_json(["api", f"repos/{repo}/issues/{number}"])["id"]
    target["done"] = True
    if kind == "tracking":
      target["filing"] = state["confirmed_sha256"]
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


def body_file(body, artifact_dir) -> str:
  """The body in a temp file beside the store for `--body-file`; the caller unlinks it."""
  with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".md", prefix=".superegm_body_",
                                   dir=str(artifact_dir), delete=False) as handle:
    handle.write(body)
    return handle.name


def edit_issue(repo, number, body, artifact_dir) -> None:
  path = body_file(body, artifact_dir)
  try:
    core.gh_retry(["issue", "edit", str(number), "-R", repo, "--body-file", path])
  finally:
    os.unlink(path)


def create_issue(repo, title, body, labels, artifact_dir):
  path = body_file(body, artifact_dir)
  try:
    args = ["issue", "create", "-R", repo, "--title", title, "--body-file", path]
    for label in labels:
      args += ["--label", label]
    url = core.gh_retry(args).strip().splitlines()[-1]
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
