# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the driver

"""superegm driver tick|install|uninstall|status|reset (spec section 11.2): the owner's timer. `tick` launches one
`wave --leavemealone` session per store when there is something to do; `install` and `uninstall` write and remove
the launchd agent (a systemd user timer on Linux); `status` reads, `reset` is the owner's interrupt."""

import argparse
import json
import os
import plistlib
import shlex
import subprocess
import sys
from pathlib import Path

import superegm as core

WRITES = frozenset({"driver", "runcards", "launches", "tick", "chain"})
CONFIG_DEFAULTS, INIT_STEP, DOCTOR_CHECKS = {}, "", None  # no written config key, init line or doctor line of its own (U32)
CONFIG_UNWRITTEN = {"driver": {"chain": False}}  # its own key, registered but never written by `init`: absent reads false (U44)
SKILLS = frozenset({"driver"})
ACTIONS = ("tick", "install", "uninstall", "status", "reset")
LABEL = "com.superegm.driver"
RUN = subprocess.run  # launchctl and systemctl: a test fakes it
PLATFORM = sys.platform


def chain_on(config: dict) -> bool:
  """`driver.chain` (spec section 7.1): true only when the store's config says so; absent or false is 1.2's tick."""
  return isinstance((config or {}).get("driver"), dict) and config["driver"].get("chain") is True


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
          words = shlex.split(line[len("ExecStart="):])
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
    if args.action == "status":
      return status()
    core.require_runcard(args, SKILLS)
    if args.action == "install":
      return install(15 if args.interval is None else args.interval)
    if args.action == "uninstall":
      return uninstall()
    return reset()
  except core.HandoffError as error:
    message = str(error)
    raise core.HandoffError(message if message.startswith("driver: ") else f"driver: {message}") from None


# ---------------------------------------------------------------- the tick


def env_file() -> Path:
  return Path.home() / ".superegm" / "env"


def read_env() -> dict:
  """`~/.superegm/env`'s `KEY=value` lines (a timer has no shell); blank and `#` lines skipped; each value literal
  (no quotes stripped, no `$VAR` or `~` expanded)."""
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


def tick_prompt(spec, hid: str, phase: str = "wave", leavemealone: bool = True) -> str:
  """The tick's prompt (D1 (a)): the typed skill's form, which `claude -p` expands as the owner's command; with the
  chain off always 1.2's `wave` with `--leavemealone`."""
  return f"/superegm:{phase} {spec} --handoff {hid}" + (" --leavemealone" if leavemealone else "")


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


def counted_failures(hs: core.Store, launches: list, state: dict, set_aside: int = 0) -> list:
  """The two consecutive launches of the tick's own that failed before the loop ran (spec section 11.2), or []:
  counted after the last `interrupted` one, after the rounds `driver reset` set aside, and after the last typed
  top-level `wave` card opened at or before `state.status.at` (the intervening success); a failure is a non-zero
  exit, no top-level `wave` card naming the launch's card, or one opened after `state.status.at` (or with it
  absent: no `status --wait` ever saved)."""
  at = (state.get("status") or {}).get("at")
  chain = chain_on(hs.config)
  cards = [c for _, c in (core.top_phase_cards(hs) if chain else core.top_wave_cards(hs))]
  launches = [e for e in launches if not core.backed_off(e)]  # never started: no failure, no reset
  start = max((i + 1 for i, e in enumerate(launches) if str(e.get("status") or "").startswith("interrupted")
               or e.get("round", 0) <= set_aside), default=0)
  # the intervening success: a typed `wave` card opened at or before the save; with the chain on, a typed top-level
  # card of any other chain phase restarts the count too (U44)
  typed = [c["opened_at"] for c in cards if not c.get("driver_card")
           and ((at and c["opened_at"] <= at) if c.get("skill") == "wave" else chain)]
  since = max(typed, default=None)
  counted = [e for e in launches[start:] if since is None or e["started_at"] > since]

  def failed(entry: dict) -> bool:
    if entry.get("outcome"):  # decided once, when the session ended (U44)
      return entry["outcome"] == "failed"
    return wave_failed(entry, cards, at)

  return counted[-2:] if len(counted) >= 2 and failed(counted[-1]) and failed(counted[-2]) else []


def wave_failed(entry: dict, cards: list, at) -> bool:
  """1.2's failure test of a `wave` launch: a non-zero exit, no top-level card naming the launch's card, or one
  opened after `state.status.at` (or with it absent)."""
  if exit_code(entry) not in (None, "0"):
    return True
  mine = [c for c in cards if c.get("driver_card") == entry.get("card")]
  return not mine or any(at is None or c["opened_at"] > at for c in mine)


def twice_failed(hs: core.Store, data: dict, state: dict) -> bool:
  return bool(counted_failures(hs, data["launches"], state, data.get("set_aside") or 0))


def settle_outcomes(st: core.Store, hs: core.Store) -> None:
  """With the chain on, each launch whose session ended (its exit file written, or interrupted after it started)
  and has no `outcome` gets one, once: a `wave` launch by 1.2's test; any other phase `succeeded` when its driven
  card closed, its exit code is 0, and `next` now prints another line or a wait record exists, else `failed`."""
  from superegm import phase
  data = core.load_driver(hs)
  ended = [e for e in data["launches"] if not core.backed_off(e) and not e.get("outcome") and core.tick_terminal(e)]
  if not ended:
    return
  cards = [c for _, c in core.top_phase_cards(hs)]
  at = ((core.load_state(hs.root).get("status") or {}).get("at"))
  for entry in ended:
    kind = entry.get("phase") or "wave"
    if kind == "wave":
      entry["outcome"] = "failed" if wave_failed(entry, cards, at) else "succeeded"
      continue
    mine = [c for c in cards if c.get("driver_card") == entry.get("card")]
    closed = bool(mine) and all(c.get("closed_at") and not c.get("interrupted_at") for c in mine)
    moved = closed and exit_code(entry) == "0" and (
      st.path("chain", hs.handoff_id).is_file() or phase.next_line(st, hs.handoff_id).split(" ")[0] != kind)
    entry["outcome"] = "succeeded" if moved else "failed"
  core.atomic_write(hs.path("driver", hs.handoff_id), data)


def exit_file_proof(hs: core.Store, launches: list) -> None:
  """A launch of the tick's own whose exit file exists while its top-level `wave` card is still open: a session that
  ended without closing its card; that card, and no other, marked `interrupted`."""
  if not launches or exit_code(launches[-1]) is None:
    return
  for path, card in core.top_phase_cards(hs):
    if card.get("driver_card") == launches[-1].get("card") and is_open(card):
      core.interrupt_card(hs, path, card, f"tick launch {launches[-1]['round']} exited")


def refuse(hs: core.Store, data: dict, reason: str) -> None:
  """The tick's refusal, written once per reason: journaled, recorded in `refused`."""
  if (data.get("refused") or {}).get("reason") == reason:
    return
  data["refused"] = {"at": core.now_iso(), "reason": reason}
  core.atomic_write(hs.path("driver", hs.handoff_id), data)
  core.journal(hs, f"tick: refused ({hs.handoff_id}: {reason})")
  print(f"tick: refused ({hs.handoff_id}: {reason})")


def notify(hs: core.Store, spec: str) -> None:
  """`notify` under a `driver` card the tick opens for that alone, only when `notify`'s own predicate holds."""
  from superegm import inbox, runcard  # inbox imports this module
  if not inbox.notify_lines(hs, {"skill": "driver", "handoff": hs.handoff_id}):
    return
  cid = core.open_runcard(hs, "driver", spec)
  try:
    inbox.run_notify(argparse.Namespace(command="notify", runcard=cid, plan=None, handoff=None))
  finally:
    runcard.close_card(hs, cid)


def launch(hs: core.Store, entry: dict, spec: str, reason: str, phase: str = "wave", leavemealone: bool = True) -> bool:
  """Record the launch, then start it: the card opened, the entry written before the start (a crash between the
  two leaves a launch without an exit file), the store's cards re-read once (an open top-level `wave` card of any open
  handoff of the store, typed or a tick's, or an open `plan`, `file`, `integrate`, `review-plan` or `orient` card of
  this handoff: the launch `interrupted`, journaled `driver: tick backed off: <skill> card <id> open`, the tick backs
  off), the wrapper started detached, its `pid` written, the card closed."""
  from superegm import launch_builder, runcard
  hid, data = hs.handoff_id, core.load_driver(hs)
  n = len(data["launches"]) + 1
  base = lambda suffix: hs.path("driver", f"{hid}_r{n}{suffix}")
  record = {"round": n, "card": None, "started_at": core.now_iso(), "boot_id": core.boot_id(), "status": "running",
            "reason": reason, "phase": phase, "result_file": str(base("_result.json")), "exit_file": str(base(".exit")),
            "log": str(base(".log"))}
  record["command"] = tick_command(Path(entry["root"]).resolve(),
                                   tick_prompt(core.rebased(spec, entry["root"]), hid, phase, leavemealone),
                                   record["result_file"], record["exit_file"])
  record["card"] = cid = core.open_runcard(hs, "driver", spec)
  data["launches"].append(record)
  data["refused"] = None
  core.atomic_write(hs.path("driver", hid), data)
  found = [("wave", path.stem) for h in open_ids(core.Store(hs.root, config=hs.config))
           for path, card in core.top_wave_cards(core.handoff_store(hs, h)) if is_open(card)]
  found += [(card["skill"], path.stem) for path, card in card_files(hs) if card.get("skill") in PHASES and is_open(card)]
  if found:
    record["status"] = "interrupted"
    core.atomic_write(hs.path("driver", hid), data)
    core.journal(hs, f"driver: tick backed off: {found[0][0]} card {found[0][1]} open")
    runcard.close_card(hs, cid)
    return False
  env = {**os.environ, "SUPEREGM_ROLE": "driver", "SUPEREGM_RUNCARD": cid}
  record["pid"] = launch_builder.start_detached(["/bin/sh", "-c", record["command"]], Path(record["log"]), env)
  core.atomic_write(hs.path("driver", hid), data)
  core.journal(hs, f"tick: {hid} launch {n} running (pid {record['pid']})")
  print(f"tick: {hid} launch {n} running (pid {record['pid']})")
  runcard.close_card(hs, cid)
  return True


def fetch_base(root, remote: str, base: str) -> tuple:
  """(ok, stderr) of the tick's own fetch of `<base>` into `refs/superegm/tick-base` in the registered root, with the
  owner's git credentials (a ref no session reads, spec section 7.1)."""
  from superegm import phase
  done = subprocess.run(["git", "-C", str(root), "fetch", "-q", remote, f"+refs/heads/{base}:{phase.TICK_BASE}"],
                        capture_output=True, text=True)
  return done.returncode == 0, done.stderr


def fetch_store(st: core.Store, entry: dict, ids: list) -> None:
  """The store's one fetch of a tick (chain on): its outcome to `tick/fetch.json` (`at`, `ok`, the first stderr
  line); a failure journaled `driver: fetch <remote> failed: <line>` once per distinct line; after a good one, each
  superseded handoff's wait record removed (`driver: <handoff> superseded: wait record removed`)."""
  from superegm import phase
  config = st.config or {}
  remote = config.get("remote") or "origin"
  path = st.path("tick", "fetch")
  before = json.loads(core.read_text(path)) if path.is_file() else {}
  ok, stderr = fetch_base(Path(entry["root"]).resolve(), remote, config.get("base") or "main")
  line = phase.first_line(stderr)
  core.atomic_write(path, {"at": core.now_iso(), "ok": bool(ok), "stderr": line})
  if not ok:
    if before.get("ok") is not False or before.get("stderr") != line:
      core.journal(st, f"driver: fetch {remote} failed: {line}")
    return
  for hid in ids:
    record = st.path("chain", hid)
    if not record.is_file():
      continue
    hs = core.handoff_store(st, hid)
    try:
      core.require_latest_handoff(hs)
    except core.HandoffError:
      record.unlink()
      core.journal(hs, f"driver: {hid} superseded: wait record removed")


SKIP_LINES = ("none", "integrate")  # with `waiting …`, the lines `next` prints on which the tick runs nothing


def last_started(st: core.Store, hid: str) -> str:
  launches = core.load_driver(core.handoff_store(st, hid))["launches"]
  return launches[-1]["started_at"] if launches else ""


def tick_store(entry: dict) -> None:
  """One store's tick: per open handoff, the one that waited longest first, the proofs, then the spec's conditions
  in order; at most one launch (one `.git`). The reboot and exit-file proofs may write before any skip; a skip
  (the store's live launch or open `wave` card, a phase card, nothing left, `tick_trigger` None) prints nothing and
  writes nothing unless `notify`'s own predicate holds, a new line then sent under a `driver` card opened for that."""
  from superegm import phase
  st, ok = registered_store(entry)
  current, ids = core.boot_id(), open_ids(st)
  chain = ok and chain_on(st.config)
  if chain:  # once per store per tick, before any `next` (spec section 7.1)
    fetch_store(st, entry, ids)
  stores = [core.handoff_store(st, h) for h in ids]
  for hs in stores:  # the proofs first, for every open handoff: a store-wide skip below reads them all
    core.STORE = hs  # the one mid-run STORE switch: it reaches every reader by intent, the notify hook's included
    core.reboot_proof(hs, current)
    exit_file_proof(hs, core.load_driver(hs)["launches"])
    if chain:
      settle_outcomes(st, hs)
  for hid in sorted(ids, key=lambda h: last_started(st, h)):
    hs = core.handoff_store(st, hid)
    core.STORE = hs  # the one mid-run STORE switch: it reaches every reader by intent, the notify hook's included
    word, leavemealone = "wave", True
    if chain:  # `next` first: nothing on `none`, `waiting …` or `integrate`; a 1.2.0 entry runs its `wave` row alone
      word = phase.next_line(st, hid)
      mode = core.frozen_mode(hs)
      if word in SKIP_LINES or word.startswith("waiting") or (mode is None and word != "wave"):
        continue
      wait = st.path("chain", hid)
      answered = wait.is_file() and bool(json.loads(core.read_text(wait)).get("answer"))
      leavemealone = mode != "normal" and not (answered and word == "file")  # an answered file wait: any mode
    state = core.load_state(hs.root)
    spec = (state.get("design") or {}).get("path") or ""
    if chain:  # the handoff record's spec: no phase before `plan` writes `state.json`
      spec = next((r.get("spec") for r in core.handoffs(st.root) if r["id"] == hid), None) or spec
    if word == "wave":
      units = list(state.get("units") or {})
      saved = ((state.get("status") or {}).get("units") or {})
      if not [u for u in units if not (saved.get(u) or {}).get("landed") and not core.load_foreman(hs, u).get("stopped")]:
        notify(hs, spec)  # nothing to launch, but its typed `wave` card may block the store's other handoffs
        continue
    data = core.load_driver(hs)
    if (any(not core.tick_terminal(e) for h in stores for e in core.load_driver(h)["launches"])
        or any(is_open(c) for h in stores for _, c in core.top_wave_cards(h))
        or any(c.get("skill") in PHASES and is_open(c) for _, c in card_files(hs))):
      notify(hs, spec)  # a skip, silent unless `notify`'s own predicate holds (a typed `wave` card, a launch)
      continue
    if not ok or twice_failed(hs, data, state):  # `notify`'s own predicate decides: a refusal recorded and never sent
      refuse(hs, data, TWICE if ok else f"root {entry['root']} is not a worktree of {entry['repo']}")
      notify(hs, spec)
      continue
    if data.get("refused"):  # the refusal no longer holds: the owner re-typed `wave` or re-registered the root
      core.journal(hs, f"tick: {hid} refusal cleared ({data['refused']['reason']})")
      data["refused"] = None
      core.atomic_write(hs.path("driver", hid), data)
    reason = wave_trigger(hs, entry, state) if word == "wave" else word
    if reason is None:
      notify(hs, spec)
      continue
    if launch(hs, entry, spec, reason, word, leavemealone):
      notify(hs, spec)
    return  # one launch per store, and a back-off ends the tick (spec section 11.2)


def wave_trigger(hs: core.Store, entry: dict, state: dict):
  """A `wave` launch's reason: 1.2's `status.tick_trigger` on the handoff's plan, None when nothing happened."""
  from superegm import status
  return status.tick_trigger(core.Handoff(core.rebased(state["plan"], entry["root"]), hs))


def tick() -> int:
  """`driver tick`: `~/.superegm/env` applied first (restored after), then every registered store."""
  saved, code = dict(os.environ), 0
  os.environ.update(read_env())
  try:
    for entry in core.load_registry():
      try:
        tick_store(entry)
      except (core.HandoffError, core.GhError, OSError, ValueError, KeyError) as error:  # one store's error never stops the next
        print(f"driver: {entry.get('artifacts_dir')}: {error}")
        code = 1
  finally:
    os.environ.clear()
    os.environ.update(saved)
  return code


# ---------------------------------------------------------------- install, uninstall, status


def service_path() -> Path:
  return systemd_dir() / "superegm-driver.service"


def timer_path() -> Path:
  return systemd_dir() / "superegm-driver.timer"


def call(argv: list, check=True) -> None:
  """One `launchctl` or `systemctl` call; a non-zero exit refused when `check`."""
  result = RUN(argv, capture_output=True, text=True)
  if check and result.returncode != 0:
    raise core.HandoffError(f"{' '.join(argv)} exited {result.returncode}")


def install(minutes: int) -> int:
  """The timer that runs `superegm driver tick` through the absolute interpreter and this plugin root's helper
  every `minutes`: a launchd agent bootstrapped at once on darwin, else a systemd user timer enabled at once.
  The plist carries no secret and no environment: the tick reads `~/.superegm/env`."""
  from superegm.launch_builder import HELPER
  if minutes < 1:
    raise core.HandoffError("--interval must be at least 1 minute")
  argv = [sys.executable, str(HELPER), "driver", "tick"]
  if PLATFORM == "darwin":
    plist, log, domain = plist_path(), str(Path.home() / ".superegm" / "driver.log"), f"gui/{os.getuid()}"
    core.atomic_write(plist, plistlib.dumps({"Label": LABEL, "ProgramArguments": argv, "StartInterval": minutes * 60,
                                             "AbandonProcessGroup": True, "StandardOutPath": log, "StandardErrorPath": log}))
    call(["launchctl", "bootout", domain, str(plist)], check=False)
    call(["launchctl", "bootstrap", domain, str(plist)])
    print(f"installed ({minutes} min): {plist}")
    return 0
  core.atomic_write(service_path(), "[Unit]\nDescription=SuperEGM driver tick\n\n[Service]\nType=oneshot\n"
                    f"ExecStart={shlex.join(argv)}\nKillMode=process\n")
  core.atomic_write(timer_path(), "[Unit]\nDescription=SuperEGM driver timer\n\n[Timer]\nOnBootSec=1min\n"
                    f"OnUnitActiveSec={minutes}min\n\n[Install]\nWantedBy=timers.target\n")
  call(["systemctl", "--user", "daemon-reload"])
  call(["systemctl", "--user", "enable", "--now", timer_path().name])
  print(f"installed ({minutes} min): {timer_path()}")
  return 0


def uninstall() -> int:
  if PLATFORM == "darwin":
    plist = plist_path()
    if not plist.is_file():
      print("not installed")
      return 0
    call(["launchctl", "bootout", f"gui/{os.getuid()}", str(plist)], check=False)
    plist.unlink()
    print(f"uninstalled: {plist}")
    return 0
  if not timer_path().is_file() and not service_path().is_file():
    print("not installed")
    return 0
  call(["systemctl", "--user", "disable", "--now", timer_path().name], check=False)
  for path in (timer_path(), service_path()):
    if path.is_file():
      path.unlink()
  call(["systemctl", "--user", "daemon-reload"], check=False)
  print(f"uninstalled: {timer_path()}")
  return 0


def status() -> int:
  """`driver status`, read-only and under no card: per open handoff of each registered store, the last tick launch
  (`started_at`, the wrapper's `pid`, whether its exit file exists), the open top-level `wave` card with its age and
  the last refusal; an absent part's clause dropped."""
  from superegm.inbox import minutes_since  # inbox imports this module
  for entry in core.load_registry():
    st, _ = registered_store(entry)
    for hid in open_ids(st):
      hs = core.handoff_store(st, hid)
      data, parts = core.load_driver(hs), []
      if data["launches"]:
        last = data["launches"][-1]
        parts.append(f"launch {last['round']} started {last['started_at']} pid {last.get('pid', '-')} "
                     f"exit file {'yes' if Path(last['exit_file']).is_file() else 'no'}")
      for path, card in core.top_phase_cards(hs):
        if is_open(card):
          parts.append(f"{card['skill']} card {path.stem} open {minutes_since(card['opened_at'])} min")
      if data.get("refused"):
        parts.append(f"refused: {data['refused']['reason']}")
      print(f"{hid}: {'; '.join(parts) or 'no tick launch'}")
  return 0


# ---------------------------------------------------------------- reset


def reset() -> int:
  """`driver reset`, the owner's interrupt for the card's handoff: its launch without an exit file recorded
  `interrupted`, its open top-level `wave` card marked `interrupted`, the refusal cleared and, with no live launch,
  the two failures it counted set aside (`set_aside`: the next tick counts from the launch after them); each
  journaled."""
  hs = core.STORE
  hid, data = hs.handoff_id, core.load_driver(hs)
  live = [e for e in data["launches"] if not core.tick_terminal(e)]
  cards = [(path, card) for path, card in core.top_phase_cards(hs) if is_open(card)]
  failures = [] if live else counted_failures(hs, data["launches"], core.load_state(hs.root), data.get("set_aside") or 0)
  if not live and not cards and not data.get("refused") and not failures:
    raise core.HandoffError(f"{hid} has no live tick launch or open wave card")
  parts = [] if live or cards else ["refusal cleared"] * bool(data.get("refused"))
  if failures:
    rounds = f"{failures[0]['round']}-{failures[1]['round']}"
    data["set_aside"] = failures[1]["round"]
    core.journal(hs, f"driver: {hid} failures {rounds} set aside by reset")
    parts.append(f"failures {rounds} set aside")
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
  print(f"reset {hid}: {'; '.join(parts)}")
  return 0
