# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the inbox and notify subcommands (spec section 11.2, U23); the driver lines, `--all` over the registry and notify under a driver card (U24); the `kill_failed` item's text and the stamps read through `core.epoch` (U31); its own `notify_timeout_seconds` config key and `init` line, moved from `__init__` and `init` (U32); `kill_group` renamed `sigkill_hook` (U48); the mode read card, then frozen, then `config.mode`, and a chained handoff's `waiting …` and `ready to integrate` lines (U45); the `proceed again` item and the merge on the authorizing outcome (U92); the `conflict` item (U62); a ruling's action the inbox with its `forms` and `on`, a review's its skill session, and `inbox withdrawn` (U72); no merge item for a head a `respec:` mark holds (U86); a contested item carries the unconverged panel's verdict line (U88), a head contest held only while the store's panel record for its review and round is open (U88); the `waiting respec R<n>` line of a respec from a review's design finding (U91); the `owner` item giving a spec fid `finding upheld`, `finding overruled` and `respec` in place of `<fid> allowed`, and a contest copy whose chain reaches a spec fid of the word listed through that fid's item alone (U104's owner-only spec findings, 1.3 design section 3.8).

"""superegm inbox [--all] [--json] [--handoff <id>]: one line per item that needs the owner across the
store's open handoffs, read-only and with no run card; superegm inbox withdrawn --pr <n> --reason <text>: the merge
step's `merge withdrawn <pr> <reason>` journal line, under its own inbox card unless --runcard names one (U72); superegm notify --runcard <id>: the owner's
~/.superegm/notify hook run once with the lines new since the last notify, a line being new when neither
`state.json.notified` nor `driver/<handoff>.json`'s `notified` holds it; the caller's set is rewritten,
`state.json`'s under a `wave` card, `driver/<handoff>.json`'s under a `driver` card (U24)."""

import argparse
import glob
import json
import os
import re
import signal
import subprocess
from pathlib import Path

import superegm as core
from superegm import approve_spec, decision, report, review, runcard
from superegm.decision import ruling_form
from superegm.launch import authorizing, conflict_again, finished, latest_clean, load_launches, waiting_proceed

WRITES = frozenset({"state", "driver", "runcards", "journal"})  # notify's `notified` (a driver card's in `driver/`); `inbox withdrawn`'s card and journal line (U72); a bare inbox writes nothing
WITHDRAW_SKILLS = frozenset({"wave", "driver", "inbox"})  # the open cards `inbox withdrawn --runcard` runs under (U72)
CONFIG_DEFAULTS = {  # its own config key and init line (U32)
    "notify_timeout_seconds": 30,  # how long `notify` waits on the owner's ~/.superegm/notify hook (spec section 11.2)
}
INIT_STEP = ("An executable ~/.superegm/notify, written outside every repository, is run by `wave` with the inbox lines new "
             "since the last notify on its stdin, bounded by config key notify_timeout_seconds; absent means no hook.")
DOCTOR_CHECKS = None
SKILLS = frozenset({"wave", "driver"})
KINDS = ("decision", "cap", "contested", "conflict", "merge", "stalled", "escalated", "redesign", "test-delta", "owner",
         "proceed", "undo", "kill_failed", "wave", "driver")
GITHUB = "https://github.com"


def item(repo: str, subject: str, kind: str, action: str, key) -> dict:
  return {"repo": repo, "subject": subject, "kind": kind, "action": action, "fingerprint": f"{subject}/{kind}/{key}"}


INBOX = "answer in the inbox"  # spec 1.2.1 section 7.3: the owner answers a ruling in words in the inbox (U72)
PROCEED = "**Ruling:** proceed — <reason>"  # spec section 4.2: the owner's go-ahead on a head
SESSION = {"spec": "review-spec", "plan": "review-plan", "integrate": "integrate"}  # a review's kind -> its skill


def session(skill: str) -> str:
  """The action of a question the owner answers in that skill's interactive session (spec 1.2.1 section 7.3)."""
  return f"answer in your {skill} session"


def ruling_item(repo: str, subject: str, kind: str, forms: list, number, key) -> dict:
  """A ruling the inbox asks in words (U72): its action the inbox, `forms` the `**Ruling:**` forms of the choices
  still open, `on` the issue the ruling reader looks at."""
  return item(repo, subject, kind, INBOX, key) | {"forms": forms, "on": f"{GITHUB}/{repo}/issues/{number}"}


def option_named(option: str, n: int) -> str:
  """The option as a form names it: its text, or, when the text holds ` — ` (which `decision.parse_form` reads as
  the reason's start), its own `(<letter>)` or its position's, the letter `decision.check_ruling` resolves."""
  if " — " not in option:
    return option
  letter = re.match(r"\([a-z]\)", option)
  return letter.group(0) if letter else f"({chr(97 + n)})"


def cap_forms(foreman: dict) -> list:
  """A head's cap menu, one form per choice; `one more round` is spent once ruled on any cap decision of the unit
  (decision.rule)."""
  caps = {c["id"] for c in foreman.get("decisions") or [] if c.get("point") == 2}
  spent = any(r.get("decision") in caps and r["ruling"].partition(" — ")[0].strip() == "one more round"
              for r in foreman.get("rulings") or [])
  return [ruling_form(2, o) for o in ("one more round", "stop", "redesign")[spent:]]


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


def panel_state(hs: core.Store, rid: str, n: int):
  """(`open` | `split` | None, the panel id) of the judges panels the store holds for review `rid` round `n` (`<rid>-r<n>-<6 hex>`,
  judges.panel_id): `open` while one has no `verdict.json` or an unconverged one with rounds to go (it may still rule), else
  `split` for one at its cap that did not converge (its verdict line goes to the owner); None for none, or only converged ones."""
  found = {"open": None, "split": None}
  for folder in sorted(hs.path("judges").glob(f"{glob.escape(rid)}-r{n}-*")):
    if not re.fullmatch(rf"{re.escape(rid)}-r{n}-[0-9a-f]{{6}}", folder.name) or not (folder / "panel.json").is_file():
      continue
    try:
      verdict = json.loads((folder / "verdict.json").read_text(encoding="utf-8")) if (folder / "verdict.json").is_file() else None
    except (OSError, ValueError):
      verdict = None
    if verdict is None or not verdict.get("converged") and not verdict.get("cap_reached"):
      found["open"] = found["open"] or folder.name
    elif not verdict.get("converged"):
      found["split"] = found["split"] or folder.name
  state = "open" if found["open"] else "split" if found["split"] else None
  return state, found["open"] or found["split"]


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
  """The decisions, test-delta, owner-only and merge-ready lines of one unit neither stopped nor landed, and its
  `proceed` item (the owner's proceed again, answered in the inbox, its `head` the head it covers) while it is
  waiting proceed (spec section 4.2), keyed on the later launch and the head (the pull request's, else the proceed's
  pinned one; none listed while neither exists). A merge item carries the `head` its authorizing outcome covers (a
  proceed's pinned head, else the clean round's) and is offered only while no decision is pending and the latest
  launch has ended (U72's merge guards); a merge a proceed authorizes names `gh pr merge <pr> --match-head-commit
  <sha>` on the proceed's pinned head and is keyed `<review>/<head>`; a proceed without a pinned head offers no
  merge, and lists its `proceed` item on the pull request's head once it has one. The latest posted round's triage
  deferrals ride on the merge item as `undo` while one is offered, else they are their own `undo` item."""
  out = []
  number = (state["units"].get(uid) or {}).get("number")
  spec = word_specs(hs, uid, foreman)  # U104: the spec fids of the latest posted `owner:` word, each listed by its own item alone
  ruled_of = lambda did: {r["ruling"].partition(" — ")[0].strip().split(" ")[0]
                          for r in foreman.get("rulings") or [] if r.get("decision") == did}
  # point 1 takes one ruling per contested finding (decision.rule): its decision stays open for the fids no
  # ruling names yet, where `pending_decisions` drops it at its first ruling
  for d in [d for d in foreman.get("decisions") or [] if d.get("point") == 1 or d in report.pending_decisions(foreman)]:
    point, did = d.get("point"), d["id"]
    if point == 2:
      out.append(ruling_item(repo, uid, "cap", cap_forms(foreman), number, did))
    elif point in (3, 5):
      words = (d.get("source") or "").split()
      subject = words[1] if len(words) == 2 and words[0] == "comment" else did
      forms = [ruling_form(3, subject, option_named(o, n)) for n, o in enumerate(d.get("options") or ["<option>"])]
      out.append(ruling_item(repo, uid, "decision", forms, number, did))
    elif point == 1:
      rid, n = source_round(d.get("source"))
      rev = review.load_review(hs, rid) if rid else None
      status = status_of(hs, rid, rev) if rev else None
      panel, pid = panel_state(hs, rid, n) if rid else (None, None)  # the store's panel record for this review and round, never the question's text (U88)
      verdict = next((l.strip() for l in (d.get("question") or "").splitlines() if f"(judges/{pid}/verdict.json)" in l), None) if pid else None
      if status is None or not (status.code == 3 or status.code == 2 and panel == "split"):  # a split panel's contest on the capped round still reaches the owner
        continue
      rnd = review.load_round(hs, rid, n) or {}
      fids = review.contested_fids(rnd) or [c["fid"] for c in rnd.get("builder_contested") or []]
      ruled = ruled_of(did)
      menu = lambda fid: [ruling_form(1, fid, o) for o in ("finding upheld", "finding overruled")]
      by_id = {f["id"]: f for f in review.findings_of(rnd)} if rnd else {}
      # a head review's high or medium contest goes to the judges first: no owner form while a panel on it is open; with no panel opened, or one converged, none will rule it
      held = lambda fid: rev["kind"] == "head" and panel == "open" and review.blocking(by_id.get(fid) or {"severity": "high"})
      # a contest copy whose chain reaches a spec fid of the word is that fid's `owner` item, never one of its own, and one
      # whose chain reaches a fid this decision ruled is closed with it, whatever the word now says (U104)
      copy = lambda fid: bool(set(review.contest_chain(hs, rid, fid, rnd)[1:]) & (spec | ruled))
      out += [ruling_item(repo, uid, "contested", menu(fid), number, f"{did}/{fid}") | ({"verdict": verdict} if verdict else {})
              for fid in fids if fid not in ruled and not held(fid) and not copy(fid)]
  entry = latest_posted(foreman)
  if entry:
    n, rid = entry["round"], review.head_review_id(hs, uid)
    rnd = (review.load_round(hs, rid, n) if rid else None) or {}
    # a posted proceed's `rulings[]` entry names no decision: it rules none, so the walk skips it (U92)
    book = {"decisions": foreman.get("decisions") or [],
            "rulings": [r for r in foreman.get("rulings") or [] if "decision" in r]}
    settled = {f["id"] for f in (review.findings_of(rnd) if rnd else []) if f.get("disposition") is not None}
    # the outcome keeps naming a fid settled since until the round converges (review.settle_finding)
    open_fid = lambda fid: fid not in settled and not decision.fid_ruled(book, fid, rid=rid)  # this head cycle's rulings (U104)
    # in leavemealone-mode `decision rule` refuses an allowance naming an open point-1 decision (refuse_allowance)
    form = lambda fid: [ruling_form(1, fid, "finding overruled" if mode == "leavemealone"
                                    and decision.fid_decisions(book, fid, strict=True) else "allowed")]
    deltas = [f["id"] for f in ((rnd.get("reviewers") or {}).get("foreman") or {}).get("findings") or []
              if f["disposition"] is None and f["claim"].startswith("test-delta")]
    out += [ruling_item(repo, uid, "test-delta", form(fid), number, f"{n}/{fid}") for fid in deltas if open_fid(fid)]
    outcome = entry.get("outcome") or ""
    if outcome.startswith("owner: "):  # a finding the test-delta line names already is one line, not two
      # a spec fid's three forms in place of `<fid> allowed`, which its decision refuses (U104)
      spec_forms = lambda fid: [ruling_form(1, fid, o) for o in ("finding upheld", "finding overruled", "respec")]
      out += [ruling_item(repo, uid, "owner", spec_forms(fid) if fid in spec else form(fid), number, f"{n}/{fid}")
              for fid in (x.strip() for x in outcome.removeprefix("owner: ").split(","))
              if fid and fid not in deltas and open_fid(fid)]
  launches, head = load_launches(hs, uid), report.unit_view(state, uid).get("head")
  conflict = report.conflicting(state, uid)  # U62: its `conflict` item is `conflict_items`', beside this unit's
  shown = head or (authorizing(foreman) or {}).get("head")
  # spec section 4.2: keyed on the later launch and the head it left; with no head at all there is none to
  # proceed on, so nothing is listed until the pull request has one
  if shown and waiting_proceed(foreman, launches, head):
    last = launches[-1]["round"] if launches else 0
    out.append(ruling_item(repo, uid, "proceed", [PROCEED], number, f"{last}/{shown}") | {"head": shown})
  auth = authorizing(foreman) or {}
  # a proceed with no pinned head has nothing for `--match-head-commit` to pin: no merge is offered on it, and
  # once the pull request has a head the owner is asked to proceed again on it, as the board's action says
  unpinned = bool(auth.get("ruling")) and not auth.get("head")
  if unpinned and head and latest_clean(foreman, launches, head):
    last = launches[-1]["round"] if launches else 0
    out.append(ruling_item(repo, uid, "proceed", [PROCEED], number, f"{last}/{head}") | {"head": head})
  # U62: no merge is offered while GitHub reads the pull request `CONFLICTING`: it would refuse it
  # U72: no merge is offered while a decision is pending or a launch is live (a proceed may rule on a running one)
  live = bool(launches) and not finished(launches[-1])
  # spec 1.2.1 section 7.3, 5.2: the owner's undo of a triage deferral, a medium the latest posted round deferred
  # (decision.refuse_undo refuses an earlier round's), posted on the unit's issue as a ruling with no decision; no
  # merge guard holds it back: on the merge item while one is offered, else its own `undo` item
  rounds = foreman.get("rounds") or []
  latest = max((e["round"] for e in rounds if e.get("phase") == "posted"), default=None)
  undo = [ruling_form(1, r["fid"], "finding upheld") for r in foreman.get("followups") or [] if r.get("round") == latest]
  # spec section 7.6: no merge for a head a standing `respec: R<n>` mark holds, however its review ended
  if (latest_clean(foreman, launches, head) and not unpinned and not conflict and not live
      and not report.pending_decisions(foreman) and not respec_held(hs, uid)):
    pr = report.unit_view(state, uid)["pr"] or ((state["units"].get(uid) or {}).get("pr") or {}).get("number")
    url = f"{GITHUB}/{repo}/pull/{pr}"
    # U61: the shared-file merge order from `handoff_units.json`, none when the file or the key is absent
    order, merge_after = merge_order(hs)
    after = [m for m in order if m in merge_after.get(uid, []) and not report.unit_view(state, m)["landed"]]
    if auth.get("ruling"):  # spec section 4.2: a proceed authorizes; the owner merges that head and no other
      target = f"gh pr merge {pr} --match-head-commit {auth.get('head')} · {url}"
      base = f"{auth.get('review')}/{auth.get('head')}"  # a head cycle may have no foreman round at all
    else:
      target, base = url, str(max(r["round"] for r in rounds))
    action = f"await-merge after {', '.join(after)} · {target}" if after else target
    # the unlanded `after` list is in the fingerprint: the item is new again to `notify` each time an `after` unit
    # lands, the last one included
    key = "".join([base] + [f"/after-{m}" for m in after])
    merge = item(repo, uid, "merge", action, key) | {"head": auth.get("head") or head}
    if undo:
      merge |= {"undo": undo, "on": f"{GITHUB}/{repo}/issues/{number}"}
    out.append(merge)
  elif undo:
    out.append(ruling_item(repo, uid, "undo", undo, number, f"{latest}/undo"))
  return out


def word_specs(hs: core.Store, uid: str, foreman: dict) -> set:
  """The fids of the latest posted round's `owner: <ids>` word that are foreman spec findings (`deviation (spec)`, U104),
  read in the unit's head review."""
  entry = latest_posted(foreman)
  outcome = str((entry or {}).get("outcome") or "")
  rid = review.head_review_id(hs, uid) if outcome.startswith("owner: ") else None
  out = set()
  for fid in (x.strip() for x in outcome.removeprefix("owner: ").split(",")) if rid else ():
    try:
      if review.locate_finding(hs, rid, fid)[3]["claim"].startswith(decision.SPEC_CLAIM):
        out.add(fid)
    except core.HandoffError:
      continue
  return out


def respec_held(hs: core.Store, uid: str) -> bool:
  """Whether `respec.marks` marks the unit (spec section 7.6): its head is held, no merge offered. A filed unit whose
  comment file is missing reads `replan: R<n>` and is held as `respec: R<n>` is: its correction is still to come.
  Read here on every call, never from `state.json`, which other commands replace whole. A failed read holds the unit
  (fail closed): no merge is offered on a head a mark may hold, and the inbox's `respec` item (`respec_read_items`)
  names the failure, so the owner sees why the merge is withheld."""
  from superegm import respec  # at call time: `respec` reads `launch`'s records
  if not hs.handoff_id:
    return False
  try:
    return bool(respec.marks(hs, hs.handoff_id).get(uid))
  except (core.HandoffError, ValueError, OSError):
    return True


def respec_read_items(hs: core.Store, repo: str, hid: str) -> list:
  """Spec section 7.6: one `respec` item naming the error when the handoff's marks cannot be read (`respec_held` then
  holds every unit: no merge is offered on a held head until it reads); else one when its open respecs cannot be read
  (`respec.marks` reads only the applied `R<n>.json`, so no unit is held, while `file`, `integrate` and `next` wait);
  when both read, one `waiting respec R<n>` item per open respec raised from a review's design finding (`unit: null`,
  U91), chained or not (`chain_items` leaves those lines, and `next`'s read-failed one, to this one), none else."""
  from superegm import respec  # at call time: `respec` reads `launch`'s records
  if not hs.handoff_id:
    return []
  try:
    respec.marks(hs, hs.handoff_id)
  except (core.HandoffError, ValueError, OSError) as error:
    return [item(repo, hid, "respec", f"read failed: {error}: no merge is offered on a held head until it reads", "read-failed")]
  try:
    waiting = respec.review_open(hs, hs.handoff_id)
  except (core.HandoffError, ValueError, OSError) as error:
    return [item(repo, hid, "respec", f"read failed: {error}: the open respecs are unread; no unit is held, and file "
                 "and integrate wait until it reads", "read-failed")]
  # U91: a respec raised from a review's design finding waits for the owner's `/superegm:review-spec`
  return [item(repo, hid, "respec", f"waiting respec {r['id']}", f"waiting:{r['id']}") for r in waiting]


def conflict_items(repo: str, state: dict, uid: str, foreman: dict, launches: list, parallel: bool,
                   held: bool = False) -> list:
  """U62 (spec section 6.1): one `conflict` item beside an unlanded unit while its saved view is `conflict`, a
  stopped unit's included, naming what resolves it: the merge round `launch` marks (`launch.conflict_again`), the
  owner's hand (a stopped unit, or an approval without `rounds`, 1.2's rule), or the rule applied again once the
  running launch ends or the owner rules; a revising unit's next fix round carries the merge orders. A unit `held` by a
  standing `respec: R<n>` mark (spec section 7.6) gets no merge round: its respec relaunch carries the correction."""
  view = report.unit_view(state, uid)
  if not report.conflicting(state, uid) or view["landed"]:
    return []
  if foreman.get("stopped"):
    then = "the unit is stopped: the owner resolves it"
  elif not parallel:
    then = "approved under 1.2.0: the owner resolves it"
  elif held:
    then = "held by a respec: its relaunch comes first"
  elif conflict_again({**view, "conflict": True}, foreman, launches, parallel):
    then = "a merge round is marked at the next `launch`"
  elif ((latest_posted(foreman) or {}).get("outcome") == "revise" and not report.pending_decisions(foreman)
        and (not launches or finished(launches[-1]))  # an open decision (point 5's accept) may end the fixes
        and not waiting_proceed(foreman, launches, view["head"])):  # spec section 4.2: no fix round, the owner's proceed
    then = "the next fix round carries the merge orders"
  else:
    then = "the rule is applied again once the launch ends or the owner rules"
  return [item(repo, uid, "conflict", f"conflict: {uid} pull request {GITHUB}/{repo}/pull/{view['pr']} reads CONFLICTING"
               f" · {then}", view["head"])]


def parallel_of(store: core.Store, hid: str, spec) -> bool:
  """Whether handoff `hid`'s approval entry carries `rounds` (spec section 6.1, `core.Graph.parallel`): its own
  latest entry (`core.own_approval`, as `core.frozen_mode` finds it), else its spec's latest entry; False with none."""
  own = core.own_approval(store, hid)
  if own is not None:
    return "rounds" in own
  entries = core.load_approvals(store, spec) if spec else []
  return bool(entries) and "rounds" in entries[-1]


def merge_order(hs: core.Store) -> tuple:
  """`handoff_units.json`'s top-level `order` list and each unit's `merge_after` list, read as `core.unit_tier`
  reads the file (no plan parse): ([], {}) when the file is absent; a missing `order` list empties only the list
  and a missing `merge_after` key (a file written before U61) only that unit's list."""
  path = hs.path("units")
  data = json.loads(core.read_text(path)) if path.is_file() else {}
  return data.get("order") or [], {u: (v or {}).get("merge_after") or [] for u, v in (data.get("units") or {}).items()}


def in_merge_order(hs: core.Store, found: list) -> list:
  """`found` with its `merge` items put in the file's `order` (units outside it after, by id), each in a slot a
  `merge` item held; every other item as it was."""
  order = merge_order(hs)[0]
  slots = [n for n, i in enumerate(found) if i["kind"] == "merge"]
  merges = sorted((found[n] for n in slots),
                  key=lambda i: (order.index(i["subject"]) if i["subject"] in order else len(order), i["subject"]))
  for n, i in zip(slots, merges):
    found[n] = i
  return found


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


def review_items(hs: core.Store, repo: str, spec: str, rid: str, rev: dict, foremen: dict, mode: str = "normal",
                 state: dict | None = None) -> list:
  """A review's cap or stalled line (cap: `review status` exit 2 with no `stop` ruled; stalled: a head's exit 5)
  and an integrate review's `escalated` findings. A head's cap or stall is a ruling the inbox asks, posted on the
  unit's issue (`state`'s number); a spec, plan or integrate review's is answered in that review's skill session
  (spec 1.2.1 section 7.3, U72)."""
  out = []
  if rev["kind"] == "integrate":
    for rnd in review.rounds_of(hs, rid, rev):
      for f in review.findings_of(rnd):
        if f.get("disposition") != "escalated":
          continue
        out.append(item(repo, rid, "escalated", session(SESSION["integrate"]), f["id"]))
  if rev.get("converged") != "no" or any(r["ruling"] == "stop" for r in rev.get("rulings") or []):
    return out
  status = status_of(hs, rid, rev)
  if status is None:
    return out
  rounds = review.rounds_of(hs, rid, rev)
  if rev["kind"] == "head":
    unit = rev["artifact"]
    foreman, number = foremen.get(unit) or {}, (((state or {}).get("units") or {}).get(unit) or {}).get("number")
    if status.code == 5:  # spec section 4.2: a stall ends the invocation and `proceed` is the way past it; no point-2
      # decision is open on a stall, so a cap form would rule nothing (decision.verify_posted)
      out.append(ruling_item(repo, unit, "stalled", [PROCEED], number, f"{rid}/{rounds[-1]['round']}")
                 | {"head": review.pinned_head(hs, rid, rev, state or {})})  # the head its proceed would pin
    elif status.code == 2 and not any(d.get("point") == 2 for d in report.pending_decisions(foreman)):
      # the capped round is posted but its point-2 decision is not open yet: a posted cap form would name no open
      # decision (decision.verify_posted drops it), so the item offers none until the next wave opens it
      out.append(item(repo, unit, "cap", "its decision point 2 opens at the next wave", rid))
  elif status.code == 2:
    out.append(item(repo, rid, "cap", session(SESSION.get(rev["kind"], rev["kind"])), rounds[-1]["round"] if rounds else 0))
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
    opened = core.epoch(card["opened_at"])
    minutes = int((core.NOW() - opened) // 60)
    out.append({"repo": repo, "subject": cid, "kind": "wave", "action": f"information: open {minutes} min",
                "fingerprint": cid})
  return out


def minutes_since(stamp: str) -> int:
  return int((core.NOW() - core.epoch(stamp)) // 60)


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


def integrate_line(state: dict, foremen: dict) -> str:
  """`ready to integrate`, or, while a stopped unit's issue is still open (`decision.stop_unit` leaves it open), the
  ids to close: `close` or `integrate --close` for a stopped unit, by hand alone for one stopped for redesign
  (`stopped.brief`), which `close` refuses while its issue is open (spec section 7.1, U45)."""
  stale, by_hand = [], []
  for uid, foreman in sorted(foremen.items()):
    stopped = foreman.get("stopped")
    if not stopped or not ((state.get("units") or {}).get(uid) or {}).get("number"):
      continue
    view = ((state.get("status") or {}).get("units") or {}).get(uid) or {}
    if view.get("landed") or (view.get("closed") or [None, None])[1]:
      continue
    (by_hand if stopped.get("brief") else stale).append(uid)
  line = "ready to integrate"
  if by_hand:
    line += f": close the issues of {', '.join(by_hand)} by hand (stopped for redesign)"
  if stale:
    line += (", then close" if by_hand else ": close") + f" the issues of {', '.join(stale)}, or type /superegm:integrate --close"
  return line


def chain_items(store: core.Store, hs: core.Store, repo: str, hid: str, state: dict, foremen: dict) -> list:
  """A chained handoff's (the chain on and a frozen `mode` on its approval) `waiting …` line and `ready to integrate`
  line, from `phase.next_line`; a 1.2.0 entry (no `mode`) or the chain off keeps 1.2's lines, since no tick fetches
  there and `waiting fetch` would never clear (spec section 7.1, U45)."""
  from superegm import phase  # phase imports review, launch and graph
  if not (core.chain_on(store.config) and core.frozen_mode(hs)):
    return []
  try:
    printed = phase.next_line(store, hid)
  except core.HandoffError:
    return []
  if printed.startswith("waiting respec"):  # U91: `respec_read_items` carries it (or its read failure), chained or not
    return []
  if printed.startswith("waiting "):
    action = printed
  elif printed == "integrate":
    action = integrate_line(state, foremen)
  else:
    return []
  return [{"repo": repo, "subject": hid, "kind": "driver", "action": action, "fingerprint": f"chain:{hid}:{action}"}]


def inbox_items(store: core.Store, handoff_ids: list) -> list:
  """What needs the owner across the handoffs `handoff_ids` (spec section 11.2), one dict per item: `repo`,
  `subject`, `kind`, `action`, `fingerprint` and `handoff`, a ruling's `forms` and `on` too (U72), a `merge`,
  `proceed` or `stalled` item's `head`, and a `merge` item's `undo` and `on` while its latest posted round deferred a
  medium by triage (an `undo` item carrying them as its `forms` while no merge is offered); ordered by handoff id, subject, then kind, the `wave` card and the
  driver's lines last, except that a handoff's `merge` items follow the `order` list of its `handoff_units.json` (U61)."""
  repo, rows = store.config["repo"], {r["id"]: r for r in core.handoffs(store.root)}
  out, read_specs, seen = [], set(), set()  # a spec's store-level reviews are read once, under its first handoff
  for hid in sorted(handoff_ids):
    hs, spec = core.handoff_store(store, hid), (rows.get(hid) or {}).get("spec")
    state = approve_spec.handoff_state(store, hid)
    units = state.get("units") or {}
    foremen = {uid: core.load_foreman(hs, uid) for uid in units}
    # an escalation is the spec's: two handoffs of one spec list it once; unit ids repeat across handoffs
    chained = bool(core.chain_on(store.config) and core.frozen_mode(hs))  # as `chain_items` reads it
    found = [i for i in escalations(hs, repo, hid, spec, foremen, state, chained) if i["fingerprint"] not in seen]
    seen |= {i["fingerprint"] for i in found}
    cards = wave_cards(hs, hid)
    mode = (cards[-1][1].get("mode") if cards else None) or core.run_mode(hs)  # the card's, else the frozen, else config.mode
    live, parallel = set(), parallel_of(store, hid, spec)
    for uid, foreman in foremen.items():
      found += kill_failed_items(hs, repo, uid)  # a stopped unit's launch too: the kill is what is left (U31)
      stopped = foreman.get("stopped")
      if stopped:
        if stopped.get("brief"):
          found.append(item(repo, uid, "redesign", f"/superegm:brainstorming {stopped['brief']}", Path(stopped["brief"]).name))
        found += conflict_items(repo, state, uid, foreman, load_launches(hs, uid), parallel)  # U62: a stop shows it too
        continue
      if report.unit_view(state, uid)["landed"]:
        continue
      live.add(uid)
      found += unit_items(hs, repo, state, uid, foreman, mode)
      held = report.conflicting(state, uid) and respec_held(hs, uid)  # spec section 7.6: read only where it matters
      found += conflict_items(repo, state, uid, foreman, load_launches(hs, uid), parallel, held)  # U62 (spec section 6.1)
    if units:
      for path in review_dirs(hs, spec, spec in read_specs):
        rev = json.loads(core.read_text(path / "review.json"))
        if rev["kind"] in ("head", "plan") and rev["artifact"] not in live:
          continue
        if chained and rev["kind"] == "plan":  # spec 1.2.1 section 7.3: a plan review's cap is the wait record's
          continue
        found += review_items(hs, repo, spec, path.name, rev, foremen, mode, state)
      read_specs.add(spec)
    found.sort(key=lambda i: (i["subject"], KINDS.index(i["kind"].split(" ")[0])))
    found = in_merge_order(hs, found)
    found += respec_read_items(hs, repo, hid) + wave_items(hs, repo, hid) + driver_items(hs, repo, hid) + chain_items(store, hs, repo, hid, state, foremen)
    out += [i | {"handoff": hid} for i in found]  # U72: the inbox answers each item under its own handoff
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
    items += [{"repo": entry["repo"], "subject": hid, "kind": "driver", "fingerprint": f"root:{hid}", "handoff": hid,
               "action": f"root {root} is not a worktree of {entry['repo']}; /superegm:driver register"} for hid in sorted(ids)]
  return items


def escalations(hs: core.Store, repo: str, hid: str, spec, foremen: dict, state: dict, chained: bool = False) -> list:
  """The `escalated[]` pairs of the latest approval entry the handoff owns (the spec's latest when no entry names
  a handoff) that the owner has not handled: a pair the spec's `## Units` section names, or a unit's decision
  carries in its question, is handled; a pair a plan's `blocking: yes` D<n> line names (graph's other route) is
  handled once `decide` records its answer in `state.decisions`, and until then it is answered in the plan session
  (U72), except on a `chained` handoff, where the driven plan's wait record asks it (spec 1.2.1 section 7.3)."""
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
    if plan_ds and chained:  # the chain's `waiting …` line carries the plan's question
      continue
    out.append(item(repo, rid, "escalated", session("plan"), fid))  # a plan decision or the plan's own question (U72)
  return out


def register(subparsers):
  p = core.add_parser(subparsers, "inbox", "list what needs the owner across the open handoffs (read-only, no run "
                      "card); withdrawn: journal a withdrawn merge under its own inbox card or --runcard's",
                      runcard=False)
  p.add_argument("--all", action="store_true", help="every store the registry lists")
  p.add_argument("--json", action="store_true", help="one JSON object per line")
  # U72: on the leaf parser, not a nested subparser, so the leaf keeps the common --handoff flag and a bare inbox lists
  p.add_argument("action", nargs="?", choices=["withdrawn"], help="withdrawn: journal `merge withdrawn <pr> <reason>`")
  p.add_argument("--pr", help="withdrawn: the pull request whose merge offer is withdrawn")
  p.add_argument("--reason", help="withdrawn: what changed since the question")
  p.add_argument("--runcard", help="withdrawn: an open wave, driver or inbox card (default: its own inbox card)")
  p.set_defaults(run=run, writes=WRITES)
  p = core.add_parser(subparsers, "notify", "run ~/.superegm/notify once with the inbox lines new since the last notify")
  p.set_defaults(run=run, writes=WRITES)


def line_of(i: dict) -> str:
  return f"{i['repo']} {i['subject']} | {i['kind']} | {i['action']}" + (f" | {i['verdict']}" if i.get("verdict") else "")


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


def run_withdrawn(args):
  """`inbox withdrawn --pr <n> --reason <text>` (U72): `merge withdrawn <pr> <reason>` in the journal of the handoff
  the card or `--handoff` names. Under `--runcard` the card is a wave, driver or inbox one and its handoff's journal
  is written (a `--handoff` naming another handoff is refused); typed without it the handoff is the one
  `core.resolve_handoff` names from `--handoff` (or `--plan`'s spec's latest approval; refused before any write
  when nothing names it) and its own `inbox` card is opened and closed around the write, as `approve-spec
  --amend-units` does."""
  if not (args.pr and args.reason):
    raise core.HandoffError("inbox withdrawn: --pr and --reason are required")
  if args.runcard:
    card = core.require_runcard(args, WITHDRAW_SKILLS)
    hid = card.get("handoff") or core.STORE.handoff_id
    named = getattr(args, "handoff", None)
    if named and named != hid:  # the card's handoff is the journal's; a different --handoff is refused, not followed
      raise core.HandoffError(f"inbox withdrawn: --handoff {named} is not card {args.runcard}'s handoff {hid}")
    core.journal(core.handoff_store(core.STORE, hid), f"merge withdrawn {args.pr} {args.reason}")
    return 0
  root = core.git_toplevel(Path.cwd())
  config = core.load_config(root)
  if core.resolve_handoff(core.Store(Path(config["artifacts_dir"]), config=config), args) is None:
    raise core.HandoffError("inbox withdrawn: no handoff named: pass --handoff <id> (or --plan) or --runcard <card>")
  st = core.store(root, args)
  args.runcard = core.open_runcard(st, "inbox", core.handoff_spec(args, st))
  try:
    core.require_runcard(args, WITHDRAW_SKILLS)
    core.journal(st, f"merge withdrawn {args.pr} {args.reason}")
  finally:
    runcard.run(argparse.Namespace(action="close", id=args.runcard, note=None))
  return 0


def run(args):
  if args.command == "inbox" and args.action == "withdrawn":
    return run_withdrawn(args)
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
    sigkill_hook(proc)
    return "hook timeout"
  except OSError as exc:
    sigkill_hook(proc)
    return f"hook failed: {exc.strerror}"
  return f"hook exit {proc.returncode}"


def sigkill_hook(proc) -> None:
  """SIGKILL the hook's process group (its leader may be gone already), then reap the hook."""
  try:
    os.killpg(proc.pid, signal.SIGKILL)
  except (ProcessLookupError, PermissionError):
    pass
  proc.wait()
