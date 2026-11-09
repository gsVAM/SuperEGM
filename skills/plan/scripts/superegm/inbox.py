# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the inbox and notify subcommands (spec section 11.2, U23); the driver lines, `--all` over the registry and notify under a driver card (U24); the `kill_failed` item's text (U31).

"""superegm inbox [--all] [--json] [--handoff <id>]: one line per item that needs the owner across the
store's open handoffs, read-only and with no run card; superegm notify --runcard <id>: the owner's
~/.superegm/notify hook run once with the lines new since the last notify, a line being new when neither
`state.json.notified` nor `driver/<handoff>.json`'s `notified` holds it; the caller's set is rewritten,
`state.json`'s under a `wave` card, `driver/<handoff>.json`'s under a `driver` card (U24)."""

import calendar
import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

import superegm as core
from superegm import approve_spec, decision, report, review
from superegm.decision import ruling_form
from superegm.launch import latest_clean, load_launches

WRITES = frozenset({"state", "driver"})  # notify's `notified` (a driver card's in `driver/`); inbox writes nothing
SKILLS = frozenset({"wave", "driver"})
KINDS = ("decision", "cap", "contested", "merge", "stalled", "escalated", "redesign", "test-delta", "owner",
         "kill_failed", "wave", "driver")
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


def review_dirs(hs: core.Store, spec, read: bool = False) -> list:
  """The handoff's reviews: its `reviews/*` and the spec reviews of its `spec` (`spec-<slug>-c<n>`, review.review_id)
  at the store's `reviews/`, unless `read` (another handoff of the spec listed them). A spec review lives at the
  store's `reviews/` whatever the handoff, an integrate review under the handoff's own `reviews/` (Store.path). In a
  legacy (flat) store that folder is the store's, shared by every flat handoff and spec: there the handoff keeps its
  own spec's integrate reviews and its own `<6 hex>-` plan and head reviews (review.hex_prefix) alone; a 1.2
  handoff never reads the root's integrate reviews, the legacy handoff's."""
  shared, slug = hs.root / "reviews", re.escape(core.spec_slug(spec)) if spec else None

  def keep(p: Path) -> bool:
    if not (p / "review.json").is_file():
      return False
    if p.parent != shared:
      return True
    if not p.name.startswith("spec-"):
      return hs.legacy and p.name.startswith(review.hex_prefix(hs))
    if slug and re.fullmatch(rf"spec-{slug}-integrate-c\d+", p.name):
      return hs.legacy
    return bool(slug) and not read and bool(re.fullmatch(rf"spec-{slug}-c\d+", p.name))
  return sorted(p for p in set(hs.path("reviews").glob("*")) | set(shared.glob("spec-*")) if keep(p))


def unit_items(hs: core.Store, repo: str, state: dict, uid: str, foreman: dict, mode: str = "normal") -> list:
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
      # one form per choice; `one more round` is spent once ruled on any cap decision of the unit (decision.rule)
      caps = {c["id"] for c in foreman.get("decisions") or [] if c.get("point") == 2}
      spent = any(r.get("decision") in caps and r["ruling"].partition(" — ")[0].strip() == "one more round"
                  for r in foreman.get("rulings") or [])
      menu = " | ".join(ruling_form(2, o) for o in ("one more round", "stop", "redesign")[spent:])
      out.append(item(repo, uid, "cap", menu + on_issue, did))
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
      menu = lambda fid: " | ".join(ruling_form(1, fid, o) for o in ("finding upheld", "finding overruled"))
      out += [item(repo, uid, "contested", menu(fid) + on_issue, f"{did}/{fid}") for fid in fids if fid not in ruled]
  entry = latest_posted(foreman)
  if entry:
    n, rid = entry["round"], review.head_review_id(hs, uid)
    rnd = (review.load_round(hs, rid, n) if rid else None) or {}
    book = {"decisions": foreman.get("decisions") or [], "rulings": foreman.get("rulings") or []}
    settled = {f["id"] for f in (review.findings_of(rnd) if rnd else []) if f.get("disposition") is not None}
    # the outcome keeps naming a fid settled since until the round converges (review.settle_finding)
    open_fid = lambda fid: fid not in settled and not decision.fid_ruled(book, fid)
    # in leavemealone-mode `decision rule` refuses an allowance naming an open point-1 decision (refuse_allowance)
    form = lambda fid: ruling_form(1, fid, "finding overruled" if mode == "leavemealone"
                                   and decision.fid_decisions(book, fid, strict=True) else "allowed") + on_issue
    deltas = [f["id"] for f in ((rnd.get("reviewers") or {}).get("foreman") or {}).get("findings") or []
              if f["disposition"] is None and f["claim"].startswith("test-delta")]
    out += [item(repo, uid, "test-delta", form(fid), f"{n}/{fid}") for fid in deltas if open_fid(fid)]
    outcome = entry.get("outcome") or ""
    if outcome.startswith("owner: "):  # a finding the test-delta line names already is one line, not two
      out += [item(repo, uid, "owner", form(fid), f"{n}/{fid}")
              for fid in (x.strip() for x in outcome.removeprefix("owner: ").split(","))
              if fid and fid not in deltas and open_fid(fid)]
  if latest_clean(foreman, load_launches(hs, uid)):
    pr = report.unit_view(state, uid)["pr"] or ((state["units"].get(uid) or {}).get("pr") or {}).get("number")
    rounds = foreman.get("rounds") or []
    out.append(item(repo, uid, "merge", f"{GITHUB}/{repo}/pull/{pr}", max(r["round"] for r in rounds)))
  return out


def kill_failed_items(hs: core.Store, repo: str, uid: str) -> list:
  """U31: a `kill_failed` launch still `running`, for the owner's typed interrupt; the pid named for `no exit file`
  alone (the group signalled and alive), the other reasons naming no process of the launch's."""
  entry = report.kill_failed(load_launches(hs, uid))
  if not entry:
    return []
  mark, n = entry["kill_failed"], entry["round"]
  why = f"{mark}, pid {entry.get('pid')}" if mark == "no exit file" else mark
  return [{"repo": repo, "subject": uid, "kind": f"kill_failed ({why})",
           "action": f"/superegm:interrupt --unit {uid} --launch {n}, then /superegm:wave", "fingerprint": f"{uid} launch {n} kill_failed"}]


def review_items(hs: core.Store, repo: str, spec: str, rid: str, rev: dict, foremen: dict, mode: str = "normal") -> list:
  """A review's cap or stalled line (cap: `review status` exit 2 with no `stop` ruled; stalled: a head's exit 5)
  and an integrate review's `escalated` findings (in leavemealone the owner declines a blocking one with the id of
  their `**Ruling:** <fid> finding overruled — <reason>` comment, `--posted`, review.check_settle)."""
  out = []
  if rev["kind"] == "integrate":
    for rnd in review.rounds_of(hs, rid, rev):
      for f in review.findings_of(rnd):
        if f.get("disposition") != "escalated":
          continue
        posted = " --posted <comment id>" if mode == "leavemealone" and review.blocking(f) else ""
        out.append(item(repo, rid, "escalated", f"superegm review settle --review {rid} --finding {f['id']} "
                        f"--disposition fixed | declined --owner{posted} --runcard <card>", f["id"]))
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
  elif status.code == 2:  # `continue` is spent once ruled (review rule)
    spent = any(r["ruling"] == "continue" for r in rev.get("rulings") or [])
    choices = "accept|stop" if spent else "continue|accept|stop"
    out.append(item(repo, rid, "cap", f"superegm review rule --review {rid} --ruling {choices} --owner "
                    "--runcard <card>", rounds[-1]["round"] if rounds else 0))
  return out


def wave_cards(hs: core.Store, hid: str) -> list:
  """(card id, card) of the handoff's open top-level `wave` cards."""
  folder = (hs.root if hs.legacy else hs.base()) / "runcards"
  out = []
  for path in sorted(folder.glob("*.json")):
    card = json.loads(core.read_text(path))
    if card.get("handoff", hid) != hid:
      continue
    if card.get("skill") == "wave" and not card.get("parent") and not card.get("closed_at") and not card.get("interrupted_at"):
      out.append((path.stem, card))
  return out


def wave_items(hs: core.Store, repo: str, hid: str) -> list:
  """The handoff's open top-level `wave` card, as information, with its age in minutes."""
  out = []
  for cid, card in wave_cards(hs, hid):
    opened = calendar.timegm(time.strptime(card["opened_at"], "%Y-%m-%dT%H:%M:%SZ"))
    minutes = int((core.NOW() - opened) // 60)
    out.append({"repo": repo, "subject": cid, "kind": "wave", "action": f"information: open {minutes} min",
                "fingerprint": cid})
  return out


def minutes_since(stamp: str) -> int:
  return int((core.NOW() - calendar.timegm(time.strptime(stamp, "%Y-%m-%dT%H:%M:%SZ"))) // 60)


def driver_items(hs: core.Store, repo: str, hid: str) -> list:
  """The handoff's driver lines (spec section 11.2): the tick's refusal, its newest launch while it has no exit
  file (information, with its age, sent once by the launch's id), and a timer whose plist names another plugin
  root than this helper's (`install` re-typed after every plugin update)."""
  from superegm import driver, launch_builder  # driver imports this module
  data, out = core.load_driver(hs), []
  line = lambda action, key: {"repo": repo, "subject": hid, "kind": "driver", "action": action, "fingerprint": key}
  if data.get("refused"):
    out.append(line(f"refused: {data['refused']['reason']}; /superegm:driver status, then re-type /superegm:wave or "
                    "/superegm:driver reset", f"refused:{hid}"))
  launches = data.get("launches") or []
  if launches and not core.tick_terminal(launches[-1]):
    n = launches[-1]["round"]
    out.append(line(f"tick launch {n} live {minutes_since(launches[-1]['started_at'])} min, no exit file (information)",
                    f"launch:{hid}:{n}"))
  helper = driver.plist_helper()
  if helper is not None and Path(helper) != launch_builder.HELPER:
    out.append(line(f"stale: {driver.helper_root(helper)}; /superegm:driver install", f"stale:{hid}"))
  return out


def inbox_items(store: core.Store, handoff_ids: list) -> list:
  """What needs the owner across the handoffs `handoff_ids` (spec section 11.2), one dict per item: `repo`,
  `subject`, `kind`, `action`, `fingerprint`; ordered by handoff id, subject, then kind, the `wave` card and the
  driver's lines last."""
  repo, rows = store.config["repo"], {r["id"]: r for r in core.handoffs(store.root)}
  out, read_specs, seen = [], set(), set()  # a spec's store-level reviews are read once, under its first handoff
  for hid in sorted(handoff_ids):
    hs, spec = core.handoff_store(store, hid), (rows.get(hid) or {}).get("spec")
    state = approve_spec.handoff_state(store, hid)
    units = state.get("units") or {}
    foremen = {uid: core.load_foreman(hs, uid) for uid in units}
    # an escalation is the spec's: two handoffs of one spec list it once; unit ids repeat across handoffs
    found = [i for i in escalations(hs, repo, hid, spec, foremen, state) if i["fingerprint"] not in seen]
    seen |= {i["fingerprint"] for i in found}
    cards = wave_cards(hs, hid)
    mode = (cards[-1][1].get("mode") if cards else None) or store.config.get("mode", "normal")
    live = set()
    for uid, foreman in foremen.items():
      found += kill_failed_items(hs, repo, uid)  # a stopped unit's launch too: the kill is what is left (U31)
      stopped = foreman.get("stopped")
      if stopped:
        if stopped.get("brief"):
          found.append(item(repo, uid, "redesign", f"/superegm:brainstorming {stopped['brief']}", Path(stopped["brief"]).name))
        continue
      if report.unit_view(state, uid)["landed"]:
        continue
      live.add(uid)
      found += unit_items(hs, repo, state, uid, foreman, mode)
    if units:
      for path in review_dirs(hs, spec, spec in read_specs):
        rev = json.loads(core.read_text(path / "review.json"))
        if rev["kind"] in ("head", "plan") and rev["artifact"] not in live:
          continue
        found += review_items(hs, repo, spec, path.name, rev, foremen, mode)
      read_specs.add(spec)
    found.sort(key=lambda i: (i["subject"], KINDS.index(i["kind"].split(" ")[0])))
    out += found + wave_items(hs, repo, hid) + driver_items(hs, repo, hid)
  return out


def registry_items(entry: dict) -> list:
  """`inbox_items` of a registered store's open handoffs: the store as its `root`'s config names it, else (a `root`
  that is not a worktree of the store's repository) on the defaults, with the bad-root line per open handoff."""
  from superegm import driver  # driver imports this module
  root, adir = entry["root"], entry["artifacts_dir"]
  ok = driver.root_ok(root, adir)
  config = core.load_config(Path(root)) if ok else {**core.DEFAULT_CONFIG, "repo": entry["repo"], "artifacts_dir": adir}
  st = core.Store(Path(adir), config=config)
  ids = [r["id"] for r in core.handoffs(st.root) if r["id"] and not r.get("closed_at")]
  items = inbox_items(st, ids)
  if not ok:
    items += [{"repo": entry["repo"], "subject": hid, "kind": "driver", "fingerprint": f"root:{hid}",
               "action": f"root {root} is not a worktree of {entry['repo']}; /superegm:driver register"} for hid in sorted(ids)]
  return items


def escalations(hs: core.Store, repo: str, hid: str, spec, foremen: dict, state: dict) -> list:
  """The `escalated[]` pairs of the latest approval entry the handoff owns (the spec's latest when no entry names
  a handoff) that the owner has not handled: a pair the spec's `## Units` section names, or a unit's decision
  carries in its question, is handled; a pair a plan's `blocking: yes` D<n> line names (graph's other route) is
  handled once `decide` records its answer in `state.decisions`, and until then the line is that `decide` call."""
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
  try:
    plan = core.parse_plan(Path(state["plan"])).units if state.get("plan") else {}
  except (core.HandoffError, OSError):
    plan = {}
  routed = [(uid, d) for uid, unit in plan.items() for d in unit.decisions if d["blocking"]]
  answered = state.get("decisions") or {}
  out = []
  for pair in pairs:
    if pair in named or any(pair in q for q in asked):
      continue
    rid, _, fid = pair.partition(":")
    plan_ds = [(uid, d) for uid, d in routed if pair in d["question"]]
    if any(f"{uid}/{d['id']}" in answered for uid, d in plan_ds):
      continue
    action = (f"superegm decide --unit {plan_ds[0][0]} --decision {plan_ds[0][1]['id']} --answer <option> --runcard <card>"
              if plan_ds else f"/superegm:plan {spec}")
    out.append(item(repo, rid, "escalated", action, fid))
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
    entries = core.load_registry() if args.all else []
    if entries:
      items = [i for entry in entries for i in registry_items(entry)]
    else:
      st, ids = open_store(args)
      if args.all and not args.json:  # --json prints one object per line and nothing else
        print("registry: none")  # then this store's items
      items = inbox_items(st, ids)
    for i in items:
      print(json.dumps(i) if args.json else line_of(i))
    return 0
  return run_notify(args)


def run_notify(args):
  """`notify`: the hook run once with the card's handoff's new lines; the set rewritten as every current line's
  fingerprint, `state.json`'s under a `wave` card, `driver/<handoff>.json`'s under a `driver` card (U24)."""
  card = core.require_runcard(args, SKILLS)
  st = core.STORE
  hid = card.get("handoff") or st.handoff_id
  hs = core.handoff_store(st, hid)  # the card's handoff, whichever `--handoff` resolved: its lines, journal and set
  items = inbox_items(st, [hid])
  new = notify_lines(st, card, items)
  if new:
    word = run_hook("".join(line_of(i) + "\n" for i in new), st.config)  # a failing or slow hook never stops the wave
    core.journal(hs, f"notify: {word} ({len(new)} new)")
  fingerprints = sorted(i["fingerprint"] for i in items)  # replaced whole: a settled line leaves the set
  if card.get("skill") == "driver":
    data = core.load_driver(hs)
    data["notified"] = fingerprints
    core.atomic_write(hs.path("driver", hs.handoff_id), data)
    return 0
  state = approve_spec.handoff_state(st, hid)
  state["notified"] = fingerprints
  core.atomic_write(hs.path("state"), state)
  return 0


def notify_lines(store: core.Store, card: dict, items=None) -> list:
  """The `inbox_items` of the card's handoff whose `fingerprint` neither `notified` set holds (spec section 11.2):
  `state.json.notified`, the `wave` sessions' set, and `driver/<handoff>.json`'s, the tick's."""
  hid = card.get("handoff") or store.handoff_id
  if items is None:
    items = inbox_items(store, [hid])
  seen = (set(core.load_driver(core.handoff_store(store, hid)).get("notified") or [])
          | set(approve_spec.handoff_state(store, hid).get("notified") or []))
  return [i for i in items if i["fingerprint"] not in seen]


def run_hook(text: str, config: dict) -> str:
  """Run `~/.superegm/notify` once with `text` on stdin, bounded by `notify_timeout_seconds`; the journal word."""
  hook = Path.home() / ".superegm" / "notify"
  if not hook.is_file():
    return "no hook"
  # its own process group, so the timeout ends whatever the hook started there; its output is unused and goes to
  # /dev/null, so no child that leaves the group holds a pipe notify waits on
  try:
    proc = subprocess.Popen([str(hook)], stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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
  proc.wait()
