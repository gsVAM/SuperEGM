# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the inbox and notify subcommands (spec section 11.2, U23).

"""superegm inbox [--all] [--json] [--handoff <id>]: one line per item that needs the owner across the
store's open handoffs, read-only and with no run card; superegm notify --runcard <id>: the owner's
~/.superegm/notify hook run once with the lines new since `state.json.notified`."""

import calendar
import json
import os
import signal
import subprocess
import time
from pathlib import Path

import superegm as core
from superegm import approve_spec, report, review
from superegm.decision import ruling_form
from superegm.launch import latest_clean, load_launches

WRITES = frozenset({"state"})  # notify's `notified`; inbox writes nothing
SKILLS = frozenset({"wave"})
KINDS = ("decision", "cap", "contested", "merge", "stalled", "escalated", "redesign", "test-delta", "owner",
         "kill_failed", "wave")
GITHUB = "https://github.com"


def item(repo: str, subject: str, kind: str, action: str, key) -> dict:
  return {"repo": repo, "subject": subject, "kind": kind, "action": action, "fingerprint": f"{subject}/{kind}/{key}"}


def latest_posted(foreman: dict):
  """The `rounds[]` entry of the unit's latest `posted` round, or None."""
  posted = [e for e in foreman.get("rounds") or [] if e.get("phase") == "posted"]
  return max(posted, key=lambda e: e["round"]) if posted else None


def source_round(source: str):
  """(review id, round) of a `review <rid> round <n>` source, else (None, None)."""
  words = (source or "").split()
  if len(words) == 4 and words[0] == "review" and words[2] == "round" and words[3].isdigit():
    return words[1], int(words[3])
  return None, None


def status_of(hs: core.Store, rid: str, rev: dict):
  """`review.evaluate` under the last round's run card (the review's own with no round); None when the
  artifact cannot be read."""
  try:
    rounds = review.rounds_of(hs, rid, rev)
    return review.evaluate(hs, rev, rounds[-1].get("runcard") if rounds else rev["runcard"])
  except (core.HandoffError, OSError):
    return None


def review_dirs(hs: core.Store, root_specs: bool) -> list:
  """The handoff's `reviews/*` and, when `root_specs`, the store's `reviews/spec-*`."""
  dirs = sorted(p for p in hs.path("reviews").glob("*") if (p / "review.json").is_file())
  if root_specs and hs.path("reviews") != hs.root / "reviews":
    dirs += sorted(p for p in (hs.root / "reviews").glob("spec-*") if (p / "review.json").is_file())
  return dirs


def unit_items(hs: core.Store, repo: str, state: dict, uid: str, foreman: dict) -> list:
  """The decisions, test-delta, owner-only and merge-ready lines of one unit neither stopped nor landed."""
  out = []
  number = (state["units"].get(uid) or {}).get("number")
  on_issue = f" on {GITHUB}/{repo}/issues/{number}"
  ruled_of = lambda did: {r["ruling"].partition(" — ")[0].strip().split(" ")[0]
                          for r in foreman.get("rulings") or [] if r.get("decision") == did}
  # point 1 takes one ruling per contested finding (decision.rule): its decision stays open for the fids no
  # ruling names yet, where `pending_decisions` drops it at its first ruling
  for d in [d for d in foreman.get("decisions") or [] if d.get("point") == 1 or d in report.pending_decisions(foreman)]:
    point, did = d.get("point"), d["id"]
    if point == 2:
      out.append(item(repo, uid, "cap", ruling_form(2, "one more round | stop | redesign") + on_issue, did))
    elif point in (3, 5):
      words = (d.get("source") or "").split()
      subject = words[1] if len(words) == 2 and words[0] == "comment" else did
      menu = f" ({' | '.join(d['options'])})" if d.get("options") else ""
      out.append(item(repo, uid, "decision", ruling_form(3, subject, "<option>") + menu + on_issue, did))
    elif point == 1:
      rid, n = source_round(d.get("source"))
      rev = review.load_review(hs, rid) if rid else None
      status = status_of(hs, rid, rev) if rev else None
      if status is None or status.code != 3:
        continue
      rnd = review.load_round(hs, rid, n) or {}
      fids = review.contested_fids(rnd) or [c["fid"] for c in rnd.get("builder_contested") or []]
      ruled = ruled_of(did)
      out += [item(repo, uid, "contested", ruling_form(1, fid, "finding upheld | finding overruled") + on_issue,
                   f"{did}/{fid}") for fid in fids if fid not in ruled]
  entry = latest_posted(foreman)
  if entry:
    n, rid = entry["round"], review.head_review_id(hs, uid)
    rnd = (review.load_round(hs, rid, n) if rid else None) or {}
    deltas = [f["id"] for f in ((rnd.get("reviewers") or {}).get("foreman") or {}).get("findings") or []
              if f["disposition"] is None and f["claim"].startswith("test-delta")]
    out += [item(repo, uid, "test-delta", ruling_form(1, fid, "allowed") + on_issue, f"{n}/{fid}") for fid in deltas]
    outcome = entry.get("outcome") or ""
    if outcome.startswith("owner: "):  # a finding the test-delta line names already is one line, not two
      out += [item(repo, uid, "owner", ruling_form(1, fid, "allowed") + on_issue, f"{n}/{fid}")
              for fid in (x.strip() for x in outcome.removeprefix("owner: ").split(",")) if fid and fid not in deltas]
  if latest_clean(foreman, load_launches(hs, uid)):
    pr = report.unit_view(state, uid)["pr"] or ((state["units"].get(uid) or {}).get("pr") or {}).get("number")
    rounds = foreman.get("rounds") or []
    out.append(item(repo, uid, "merge", f"{GITHUB}/{repo}/pull/{pr}", max(r["round"] for r in rounds)))
  return out


def review_items(hs: core.Store, repo: str, spec: str, rid: str, rev: dict, foremen: dict) -> list:
  """A review's cap or stalled line (cap: `review status` exit 2 with no `stop` ruled; stalled: a head's exit 5)
  and an integrate review's `escalated` findings."""
  out = []
  if rev["kind"] == "integrate":
    for rnd in review.rounds_of(hs, rid, rev):
      out += [item(repo, rid, "escalated", f"superegm review settle --review {rid} --finding {f['id']} --disposition "
                   "fixed | declined --owner --runcard <card>", f["id"])
              for f in review.findings_of(rnd) if f.get("disposition") == "escalated"]
  if rev.get("converged") != "no" or any(r["ruling"] == "stop" for r in rev.get("rulings") or []):
    return out
  status = status_of(hs, rid, rev)
  if status is None:
    return out
  rounds = review.rounds_of(hs, rid, rev)
  if rev["kind"] == "head":
    unit = rev["artifact"]
    if status.code == 5:
      out.append(item(repo, unit, "stalled", f"/superegm:wave {spec}", f"{rid}/{rounds[-1]['round']}"))
    elif status.code == 2 and not any(d.get("point") == 2 for d in report.pending_decisions(foremen.get(unit) or {})):
      out.append(item(repo, unit, "cap", f"/superegm:wave {spec}", rid))
  elif status.code == 2:
    out.append(item(repo, rid, "cap", f"superegm review rule --review {rid} --ruling continue|accept|stop --owner "
                    "--runcard <card>", rounds[-1]["round"] if rounds else 0))
  return out


def wave_items(hs: core.Store, repo: str, hid: str) -> list:
  """The handoff's open top-level `wave` card, as information, with its age in minutes."""
  folder = (hs.root if hs.legacy else hs.base()) / "runcards"
  out = []
  for path in sorted(folder.glob("*.json")):
    card = json.loads(core.read_text(path))
    if card.get("handoff", hid) != hid:
      continue
    if card.get("skill") == "wave" and not card.get("parent") and not card.get("closed_at") and not card.get("interrupted_at"):
      opened = calendar.timegm(time.strptime(card["opened_at"], "%Y-%m-%dT%H:%M:%SZ"))
      minutes = int((core.NOW() - opened) // 60)
      out.append({"repo": repo, "subject": path.stem, "kind": "wave", "action": f"information: open {minutes} min",
                  "fingerprint": path.stem})
  return out


def inbox_items(store: core.Store, handoff_ids: list) -> list:
  """What needs the owner across the handoffs `handoff_ids` (spec section 11.2), one dict per item: `repo`,
  `subject`, `kind`, `action`, `fingerprint`; ordered by handoff id, subject, then kind, the `wave` card last."""
  repo, rows = store.config["repo"], {r["id"]: r for r in core.handoffs(store.root)}
  out, root_specs, seen = [], True, set()
  for hid in sorted(handoff_ids):
    hs, spec = core.handoff_store(store, hid), (rows.get(hid) or {}).get("spec")
    state = approve_spec.handoff_state(store, hid)
    units = state.get("units") or {}
    foremen = {uid: core.load_foreman(hs, uid) for uid in units}
    found = escalations(hs, repo, hid, spec, foremen)
    live = set()
    for uid, foreman in foremen.items():
      stopped = foreman.get("stopped")
      if stopped:
        if stopped.get("brief"):
          found.append(item(repo, uid, "redesign", f"/superegm:brainstorming {stopped['brief']}", Path(stopped["brief"]).name))
        continue
      if report.unit_view(state, uid)["landed"]:
        continue
      live.add(uid)
      found += unit_items(hs, repo, state, uid, foreman)
    if units:
      for path in review_dirs(hs, root_specs):
        rev = json.loads(core.read_text(path / "review.json"))
        if rev["kind"] in ("head", "plan") and rev["artifact"] not in live:
          continue
        found += review_items(hs, repo, spec, path.name, rev, foremen)
      root_specs = False
    found.sort(key=lambda i: (i["subject"], KINDS.index(i["kind"])))
    out += [i for i in found if i["fingerprint"] not in seen] + wave_items(hs, repo, hid)
    seen |= {i["fingerprint"] for i in found}
  return out


def escalations(hs: core.Store, repo: str, hid: str, spec, foremen: dict) -> list:
  """The `escalated[]` pairs of the latest approval entry the handoff owns (the spec's latest when no entry names
  a handoff) that the owner has not handled: a pair the spec's `## Units` section names, or a unit's decision
  carries in its question, is handled (graph's reading of the same list)."""
  entries = core.load_approvals(hs, Path(spec)) if spec else []
  owned = [e for e in entries if e.get("handoff_id") == hid]
  if not owned and not any(e.get("handoff_id") for e in entries):
    owned = entries[-1:]
  pairs = (owned[-1].get("escalated") or []) if owned else []
  if not pairs:
    return []
  try:
    named = approve_spec.units_section(core.read_text(Path(spec)))
  except OSError:
    named = ""
  asked = [d.get("question") or "" for f in foremen.values() for d in f.get("decisions") or []]
  out = []
  for pair in pairs:
    if pair in named or any(pair in q for q in asked):
      continue
    rid, _, fid = pair.partition(":")
    out.append(item(repo, rid, "escalated", f"/superegm:plan {spec}", fid))
  return out


def register(subparsers):
  p = core.add_parser(subparsers, "inbox", "list what needs the owner across the open handoffs (read-only, no run card)",
                      runcard=False)
  p.add_argument("--all", action="store_true", help="every store the registry lists")
  p.add_argument("--json", action="store_true", help="one JSON object per line")
  p.set_defaults(run=run, writes=WRITES)
  p = core.add_parser(subparsers, "notify", "run ~/.superegm/notify once with the inbox lines new since the last notify")
  p.set_defaults(run=run, writes=WRITES)


def line_of(i: dict) -> str:
  return f"{i['repo']} {i['subject']} | {i['kind']} | {i['action']}"


def open_store(args) -> tuple:
  """The repository's store (no handoff resolved) and the handoff ids to read: `--handoff`'s, else every open
  row of its `handoffs/` index."""
  config = core.load_config(core.git_toplevel(Path.cwd()))
  st = core.Store(Path(config["artifacts_dir"]), config=config)
  rows = core.handoffs(st.root)
  named = getattr(args, "handoff", None)
  if named:
    if named not in {r["id"] for r in rows}:
      raise core.HandoffError(f"store: {named}: no such handoff")
    return st, [named]
  return st, [r["id"] for r in rows if r["id"] and not r.get("closed_at")]


def run(args):
  if args.command == "inbox":
    st, ids = open_store(args)
    if args.all:
      print("registry: none")  # U24 builds the registry; until then the one store
    for i in inbox_items(st, ids):
      print(json.dumps(i) if args.json else line_of(i))
    return 0
  card = core.require_runcard(args, SKILLS)
  st = core.STORE
  items = inbox_items(st, [card.get("handoff") or st.handoff_id])
  new = notify_lines(st, card, items)
  if new:
    word = run_hook("".join(line_of(i) + "\n" for i in new), st.config)  # a failing or slow hook never stops the wave
    core.journal(st, f"notify: {word} ({len(new)} new)")
  state = core.load_state(st.root)
  state["notified"] = sorted(i["fingerprint"] for i in items)  # replaced whole: a settled line leaves the set
  core.save_state(st.root, state)
  return 0


def notify_lines(store: core.Store, card: dict, items=None) -> list:
  """The `inbox_items` of the card's handoff whose `fingerprint` its `state.json.notified` lacks."""
  hid = card.get("handoff") or store.handoff_id
  if items is None:
    items = inbox_items(store, [hid])
  seen = set(approve_spec.handoff_state(store, hid).get("notified") or [])
  return [i for i in items if i["fingerprint"] not in seen]


def run_hook(text: str, config: dict) -> str:
  """Run `~/.superegm/notify` once with `text` on stdin, bounded by `notify_timeout_seconds`; the journal word."""
  hook = Path.home() / ".superegm" / "notify"
  if not hook.is_file():
    return "no hook"
  try:  # its own process group, so the timeout ends whatever the hook started; its output is bytes, never decoded
    proc = subprocess.Popen([str(hook)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            start_new_session=True)
  except OSError as exc:
    return f"hook failed: {exc.strerror}"
  try:
    proc.communicate(text.encode("utf-8"), timeout=config.get("notify_timeout_seconds", 30))
  except subprocess.TimeoutExpired:
    kill_group(proc)
    return "hook timeout"
  except OSError as exc:
    kill_group(proc)
    return f"hook failed: {exc.strerror}"
  return f"hook exit {proc.returncode}"


def kill_group(proc) -> None:
  """SIGKILL the hook's process group (its leader may be gone already), then reap the hook."""
  try:
    os.killpg(proc.pid, signal.SIGKILL)
  except (ProcessLookupError, PermissionError):
    pass
  proc.communicate()
