---
name: interrupt
license: Apache-2.0
effects: external
effect_kinds: [state-store]
disable-model-invocation: true
description: Pauses a running wave at the next safe point and records why in the store.
---

# interrupt

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

Typed by the owner to record what the owner knows: that a builder launch was stopped, or that a prepared review round will not run. SuperEGM never infers either from silence; an owner's decision is not a guess, and every effect refuses without an open run card.

1. Open the card on the unit id: `superegm runcard open --skill interrupt --artifact <unit>`; it prints `<id>`.
2. Run the one subcommand with the owner's typed arguments: `superegm interrupt --unit <unit> (--launch <n> | --round <n>) --runcard <id>`. `--launch <n>` records `interrupted` on the unit's launch `<n>` (the launch count); `--round <n>` marks the unit's prepared round `<n>` `collected` with the outcome `not run (interrupted: owner)`.
3. Close the card: `superegm runcard close <id>`.

It refuses, exit 1, a launch that is terminal already (its exit file exists or it is `interrupted`), a round whose phase is not `fetched` or `prepared`, a launch or round the unit does not have, and any card that is not an open `interrupt` card on this unit. An interrupted launch is a decision point for the next `wave` (design section 11); this skill records, it never relaunches.
