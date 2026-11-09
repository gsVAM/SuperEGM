# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the driver

"""superegm driver tick|install|uninstall|status|reset (spec section 11.2): the owner's timer. `tick` launches one
`wave --leavemealone` session per store when there is something to do; `install` and `uninstall` write and remove
the launchd agent (a systemd user timer on Linux); `status` reads, `reset` is the owner's interrupt."""

import argparse
import json
import os
import plistlib
import subprocess
from pathlib import Path

import superegm as core

WRITES = frozenset({"driver", "runcards", "launches"})
SKILLS = frozenset({"driver"})
ACTIONS = ("tick", "install", "uninstall", "status", "reset")
LABEL = "com.superegm.driver"


def plist_path() -> Path:
  return Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"


def systemd_dir() -> Path:
  return Path.home() / ".config" / "systemd" / "user"


def plist_helper():
  """The helper the installed timer runs: the plist's `ProgramArguments[1]`, else the systemd unit's `ExecStart`
  second word, whichever file exists; None when neither does (or it names none)."""
  try:
    if plist_path().is_file():
      argv = plistlib.loads(plist_path().read_bytes()).get("ProgramArguments") or []
      return argv[1] if len(argv) > 1 else None
    unit = systemd_dir() / "superegm-driver.service"
    if unit.is_file():
      for line in core.read_text(unit).splitlines():
        if line.startswith("ExecStart="):
          words = line[len("ExecStart="):].split()
          return words[1] if len(words) > 1 else None
  except (OSError, ValueError, plistlib.InvalidFileException):
    return None
  return None


def helper_root(helper) -> str:
  """The plugin root a helper path names (`<root>/skills/plan/scripts/superegm.py`)."""
  parents = Path(helper).parents
  return str(parents[3]) if len(parents) > 3 else str(helper)


def root_ok(root, artifacts_dir) -> bool:
  """The registered `root` is a git worktree whose `.superegm/config.json` names `artifacts_dir` (no remote read)."""
  try:
    if subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"], capture_output=True).returncode != 0:
      return False
    config = json.loads(core.read_text(Path(root) / ".superegm" / "config.json"))
  except (OSError, ValueError):
    return False
  named = config.get("artifacts_dir")
  return isinstance(named, str) and Path(os.path.expanduser(named)).resolve() == Path(artifacts_dir).resolve()


PHASES = ("plan", "file", "integrate", "review-plan", "orient")  # a handoff's own writers a tick waits for
TWICE = "two launches failed before the loop ran"


def register(subparsers):
  p = core.add_parser(subparsers, "driver", "the owner's timer: tick, install, uninstall, status, reset")
  p.add_argument("action", choices=ACTIONS)
  p.add_argument("--interval", type=int, help="install: minutes between ticks (default 15)")
  p.set_defaults(run=run, writes=WRITES)


def run(args):
  try:
    if args.action == "tick":
      return tick()
    if args.action == "reset":
      core.require_runcard(args, SKILLS)
      return reset()
    raise core.HandoffError(f"{args.action} is not available yet")
  except core.HandoffError as error:
    message = str(error)
    raise core.HandoffError(message if message.startswith("driver: ") else f"driver: {message}") from None


# ---------------------------------------------------------------- the tick


def env_file() -> Path:
  return Path.home() / ".superegm" / "env"


def read_env() -> dict:
  """`~/.superegm/env`'s `KEY=value` lines (a timer has no shell); blank and `#` lines skipped."""
  path, out = env_file(), {}
  if path.is_file():
    for line in core.read_text(path).splitlines():
      key, sep, value = line.strip().partition("=")
      if sep and key and not key.startswith("#"):
        out[key.strip()] = value.strip()
  return out


def registered_store(entry: dict) -> tuple:
  """(store, root ok) of a registry entry, as `inbox --all` builds it: its `root`'s config when `root_ok`, else
  the defaults with the entry's `repo` and `artifacts_dir`."""
  ok = root_ok(entry["root"], entry["artifacts_dir"])
  config = (core.load_config(Path(entry["root"])) if ok
            else {**core.DEFAULT_CONFIG, "repo": entry["repo"], "artifacts_dir": entry["artifacts_dir"]})
  return core.Store(Path(entry["artifacts_dir"]), config=config), ok


def open_ids(st: core.Store) -> list:
  return [r["id"] for r in core.handoffs(st.root) if r["id"] and not r.get("closed_at")]


def card_files(hs: core.Store) -> list:
  """(path, card) of every card of the handoff."""
  folder = (hs.root if hs.legacy else hs.base()) / "runcards"
  out = []
  for path in sorted(folder.glob("*.json")):
    card = json.loads(core.read_text(path))
    if card.get("handoff", hs.handoff_id) == hs.handoff_id:
      out.append((path, card))
  return out


def is_open(card: dict) -> bool:
  return not card.get("closed_at") and not card.get("interrupted_at")


def tick_prompt(spec, hid: str) -> str:
  """The tick's prompt (D1 (a)): the typed skill's form, which `claude -p` expands as the owner's command."""
  return f"/superegm:wave {spec} --handoff {hid} --leavemealone"


def tick_command(root, prompt: str, result, exit_file) -> str:
  """The shell line the detached wrapper runs: the session in the registered root, its exit code to the exit file
  on any exit (spec section 4's wrapper); a `'` refused, as `command_line` refuses one."""
  for value in (root, prompt, result, exit_file):
    if "'" in str(value):
      raise core.HandoffError(f"{value} holds a quote and cannot go on the command line")
  return (f"cd '{root}' && claude -p '{prompt}' --permission-mode bypassPermissions --output-format json "
          f"> '{result}'; echo $? > '{exit_file}'")


def exit_code(entry: dict):
  path = Path(entry["exit_file"])
  return core.read_text(path).strip() if path.is_file() else None


def twice_failed(hs: core.Store, launches: list, state: dict) -> bool:
  """Two consecutive launches of the tick's own that failed before the loop ran (spec section 11.2), counted after
  the last `interrupted` one and after the last typed top-level `wave` card opened at or before `state.status.at`
  (the intervening success): a non-zero exit, no top-level `wave` card naming the launch's card, or one opened
  after `state.status.at` (or with it absent: no `status --wait` ever saved)."""
  at = (state.get("status") or {}).get("at")
  cards = [c for _, c in core.top_wave_cards(hs)]
  start = max((i + 1 for i, e in enumerate(launches) if str(e.get("status") or "").startswith("interrupted")), default=0)
  typed = [c["opened_at"] for c in cards if not c.get("driver_card") and at and c["opened_at"] <= at]
  since = max(typed, default=None)
  counted = [e for e in launches[start:] if since is None or e["started_at"] > since]

  def failed(entry: dict) -> bool:
    if exit_code(entry) not in (None, "0"):
      return True
    mine = [c for c in cards if c.get("driver_card") == entry.get("card")]
    return not mine or any(at is None or c["opened_at"] > at for c in mine)

  return len(counted) >= 2 and failed(counted[-1]) and failed(counted[-2])


def exit_file_proof(hs: core.Store, launches: list) -> None:
  """A launch of the tick's own whose exit file exists while its top-level `wave` card is still open: a session that
  ended without closing its card; that card, and no other, marked `interrupted`."""
  if not launches or exit_code(launches[-1]) is None:
    return
  for path, card in core.top_wave_cards(hs):
    if card.get("driver_card") == launches[-1].get("card") and is_open(card):
      core.interrupt_card(hs, path, card, f"tick launch {launches[-1]['round']} exited")


def refuse(hs: core.Store, data: dict, reason: str) -> bool:
  """The tick's refusal, written once per reason: journaled, recorded in `refused`; True when written now."""
  if (data.get("refused") or {}).get("reason") == reason:
    return False
  data["refused"] = {"at": core.now_iso(), "reason": reason}
  core.atomic_write(hs.path("driver", hs.handoff_id), data)
  core.journal(hs, f"tick: refused ({hs.handoff_id}: {reason})")
  print(f"tick: refused ({hs.handoff_id}: {reason})")
  return True


def close_card(hs: core.Store, cid: str) -> None:
  card = core.load_card(hs, cid)
  card["closed_at"] = core.now_iso()
  core.atomic_write(hs.path("runcards", cid), card)
  core.journal(hs, f"runcard close {cid}")


def notify(hs: core.Store, spec: str) -> None:
  """`notify` under a `driver` card the tick opens for that alone, only when `notify`'s own predicate holds."""
  from superegm import inbox  # inbox imports this module
  if not inbox.notify_lines(hs, {"skill": "driver", "handoff": hs.handoff_id}):
    return
  cid = core.open_runcard(hs, "driver", spec)
  try:
    inbox.run_notify(argparse.Namespace(command="notify", runcard=cid, plan=None, handoff=None))
  finally:
    close_card(hs, cid)


def launch(hs: core.Store, entry: dict, spec: str, reason: str) -> bool:
  """Record the launch, then start it: the card opened, the entry written before the start (a crash between the
  two leaves a launch without an exit file), the store's cards re-read once (a typed `wave` card opened since: the
  launch `interrupted`, the tick backs off), the wrapper started detached, its `pid` written, the card closed."""
  from superegm import launch_builder
  hid, data = hs.handoff_id, core.load_driver(hs)
  n = len(data["launches"]) + 1
  cid = core.open_runcard(hs, "driver", spec)
  base = lambda suffix: hs.path("driver", f"{hid}_r{n}{suffix}")
  record = {"round": n, "card": cid, "started_at": core.now_iso(), "boot_id": core.boot_id(), "status": "running",
            "reason": reason, "result_file": str(base("_result.json")), "exit_file": str(base(".exit")),
            "log": str(base(".log"))}
  record["command"] = tick_command(Path(entry["root"]).resolve(), tick_prompt(spec, hid), record["result_file"],
                                   record["exit_file"])
  data["launches"].append(record)
  data["refused"] = None
  core.atomic_write(hs.path("driver", hid), data)
  typed = [path.stem for h in open_ids(core.Store(hs.root, config=hs.config))
           for path, card in core.top_wave_cards(core.handoff_store(hs, h)) if is_open(card)]
  if typed:
    record["status"] = "interrupted"
    core.atomic_write(hs.path("driver", hid), data)
    core.journal(hs, f"driver: tick backed off: wave card {typed[0]} open")
    close_card(hs, cid)
    return False
  env = {**os.environ, "SUPEREGM_ROLE": "driver", "SUPEREGM_RUNCARD": cid}
  record["pid"] = launch_builder.start_detached(["/bin/sh", "-c", record["command"]], Path(record["log"]), env)
  core.atomic_write(hs.path("driver", hid), data)
  core.journal(hs, f"tick: {hid} launch {n} running (pid {record['pid']})")
  print(f"tick: {hid} launch {n} running (pid {record['pid']})")
  close_card(hs, cid)
  return True


def last_started(st: core.Store, hid: str) -> str:
  launches = core.load_driver(core.handoff_store(st, hid))["launches"]
  return launches[-1]["started_at"] if launches else ""


def tick_store(entry: dict) -> None:
  """One store's tick: per open handoff, the one that waited longest first, the proofs, then the spec's conditions
  in order; at most one launch (one `.git`), a skip silent and writing nothing."""
  from superegm import status
  st, ok = registered_store(entry)
  current, ids = core.boot_id(), open_ids(st)
  for hid in sorted(ids, key=lambda h: last_started(st, h)):
    hs = core.handoff_store(st, hid)
    core.STORE = hs
    state = core.load_state(hs.root)
    spec = (state.get("design") or {}).get("path") or ""
    units = list(state.get("units") or {})
    saved = ((state.get("status") or {}).get("units") or {})
    if not [u for u in units if not (saved.get(u) or {}).get("landed") and not core.load_foreman(hs, u).get("stopped")]:
      continue
    core.reboot_proof(hs, current)
    data = core.load_driver(hs)
    exit_file_proof(hs, data["launches"])
    stores = [core.handoff_store(st, h) for h in ids]
    if any(not core.tick_terminal(e) for h in stores for e in core.load_driver(h)["launches"]):
      continue
    if any(is_open(c) for h in stores for _, c in core.top_wave_cards(h)):
      continue
    if any(c.get("skill") in PHASES and is_open(c) for _, c in card_files(hs)):
      continue
    if not ok:
      if refuse(hs, data, f"root {entry['root']} is not a worktree of {entry['repo']}"):
        notify(hs, spec)
      continue
    if twice_failed(hs, data["launches"], state):
      if refuse(hs, data, TWICE):
        notify(hs, spec)
      continue
    reason = status.tick_trigger(core.Handoff(Path(state["plan"]), hs))
    if reason is None:
      notify(hs, spec)
      continue
    if launch(hs, entry, spec, reason):
      notify(hs, spec)
      return
  return


def tick() -> int:
  """`driver tick`: `~/.superegm/env` applied first (restored after), then every registered store."""
  saved = dict(os.environ)
  os.environ.update(read_env())
  try:
    for entry in core.load_registry():
      tick_store(entry)
  finally:
    os.environ.clear()
    os.environ.update(saved)
  return 0


# ---------------------------------------------------------------- reset


def reset() -> int:
  """`driver reset`, the owner's interrupt for the card's handoff: its launch without an exit file recorded
  `interrupted`, its open top-level `wave` card marked `interrupted`, the refusal cleared; each journaled."""
  hs = core.STORE
  hid, data = hs.handoff_id, core.load_driver(hs)
  live = [e for e in data["launches"] if not core.tick_terminal(e)]
  cards = [(path, card) for path, card in core.top_wave_cards(hs) if is_open(card)]
  if not live and not cards and not data.get("refused"):
    raise core.HandoffError(f"{hid} has no live tick launch or open wave card")
  parts = []
  for e in live:
    e["status"] = "interrupted"
    core.journal(hs, f"driver: {hid} launch {e['round']} interrupted by reset")
    parts.append(f"launch {e['round']} interrupted")
  if data.get("refused"):
    core.journal(hs, f"driver: {hid} refusal cleared by reset ({data['refused']['reason']})")
    data["refused"] = None
  core.atomic_write(hs.path("driver", hid), data)
  for path, card in cards:
    core.interrupt_card(hs, path, card, "driver reset")
    parts.append(f"card {path.stem} interrupted")
  print(f"reset {hid}: {'; '.join(parts) or 'refusal cleared'}")
  return 0
