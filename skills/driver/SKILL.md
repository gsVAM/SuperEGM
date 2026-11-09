---
name: driver
license: Apache-2.0
effects: external
effect_kinds: [start-session, state-store]
disable-model-invocation: true
description: Installs, inspects and resets the owner's timer that types one leavemealone wave per store when there is something to do.
---

<!-- Added by SuperEGM (gsVAM), 2026: the driver skill (spec section 11.2, U24). -->

# driver

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

Typed by the owner, never invoked by a model: `/superegm:driver install [--interval <minutes>] | uninstall | status | register [--remove] | reset [--handoff <id>]`.
The driver runs on the owner's machine alone. A timer runs `superegm driver tick` every interval (15 minutes
by default; the machine's, never a repository's key); each tick reads one `status` per open handoff of each
registered store and, when there is something to do and no session of that store is live, starts one
`claude -p '/superegm:wave <spec> --handoff <id> --leavemealone' --permission-mode bypassPermissions --output-format json`
in the registered root under `SUPEREGM_ROLE=driver`, its result and exit code written to files the tick names.
That session is unattended: it runs with no allow-list and no prompt, under the credential `~/.superegm/env` names,
so install the driver only on a machine and for repositories you would let a session act on alone. A tick that
finds nothing writes nothing. It never merges, and never types `plan`, `file`, `integrate` or `review-plan`.

`<HELPER>` is `${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`; pass `--handoff <id>` to every call
when the owner typed it.

## The card

Every action but `status` runs under a `driver` card on the handoff's spec (the `design.path` of its
`state.json`): `python3 '<HELPER>' runcard open --skill driver --artifact <spec>` prints `<CARD>`; run the
action with `--runcard '<CARD>'`, then `python3 '<HELPER>' runcard close '<CARD>'` after each action, a
refusal included. `status` is read-only and takes no card.

## Before the first install (by hand, once)

1. Write `~/.superegm/env`, mode `0600` (`chmod 600 ~/.superegm/env`), as `KEY=value` lines: a timer has no
   shell, so each value literal: no quotes, no `$VAR`, no `~` (write `PATH=/opt/homebrew/bin:/usr/bin:/bin`, absolute
   paths alone). `PATH` (where `claude`, `gh`, `python3` and `openssl` resolve), `CLAUDE_CONFIG_DIR` (the profile the
   tick's session runs under, one without SubagentStart hooks) and the credential the shell holds today,
   `SUPEREGM_APP_KEY` (a path; the App is the driver's credential of choice) or `SUPEREGM_BUILDER_TOKEN`. The
   timer file carries no secret and no environment of its own.
2. Optionally write `~/.superegm/notify`, the hook `notify` feeds the inbox's new lines.
3. On Linux, run `loginctl enable-linger` so the user timer runs while you are logged out.
4. On macOS, check `pmset -g`: a sleeping machine runs no tick; `doctor`'s `sleep:` line shows the setting.

## Actions

- `register`: from a checkout of the repository, `python3 '<HELPER>' register --runcard '<CARD>'` adds this
  store to `~/.superegm/registry.json` (`--remove` removes it). One entry per store: registering from another
  worktree moves its `root`, the one checkout a tick's sessions run in.
- `/superegm:driver install [--interval <minutes>]`: `python3 '<HELPER>' driver install [--interval <minutes>] --runcard '<CARD>'`
  writes the launchd agent (`~/Library/LaunchAgents/com.superegm.driver.plist`, bootstrapped at once) or the
  systemd user timer, naming this plugin root's helper. The root is versioned: re-type `install`
  after every plugin update (`doctor` prints `driver: stale (…)` until you do).
- `uninstall`: `python3 '<HELPER>' driver uninstall --runcard '<CARD>'` removes the timer.
- `status`: `python3 '<HELPER>' driver status` prints, per open handoff, the last tick launch (its
  `started_at`, the wrapper's `pid`, whether its exit file exists), the open `wave` card with its age and the
  last refusal. A launch without an exit file is a live session, never guessed dead.
- `reset`: `python3 '<HELPER>' driver reset --runcard '<CARD>'` is the owner's interrupt for a tick launch the
  owner knows is dead (a kill, a crash): it records the launch `interrupted`, marks the handoff's open `wave`
  card `interrupted` and clears the tick's refusal; after two failed launches that both exited, it sets the two
  failures aside (`set_aside`, the second one's round), so the next tick counts afresh. A reboot needs no reset:
  the boot-id proof records it.

## What the tick refuses

Two consecutive tick launches that failed before the loop ran, or a registered `root` that is not a worktree
of the store's repository, stop the tick for that handoff: journaled `tick: refused (<handoff>: <reason>)` and
sent by `notify`. Re-type `/superegm:wave`, or `/superegm:driver reset` (the failures), or
`/superegm:driver register` from the right checkout (the root). While a tick's session may be live, a typed
`wave` (and that handoff's `plan`, `file`, `integrate`, `review-plan` and `orient`) refuses with
`driver: a tick's session may be live; /superegm:driver reset is the owner's interrupt`.
