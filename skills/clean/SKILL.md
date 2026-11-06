---
name: clean
license: Apache-2.0
effects: external
effect_kinds: [destructive-local, state-store]
disable-model-invocation: true
description: Removes the worktrees, refs and local files a finished or abandoned wave left behind.
---

# clean

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

Typed by the owner to remove what a unit's finished or abandoned work left behind: its review worktrees and their private refs, and every builder worktree a recorded launch owns. Removing a worktree is a destructive decision and is never taken on a guess: `clean` refuses while any launch or round of the unit is not terminal, and keeps what it cannot prove, and every effect refuses without an open run card.

The owner types `/superegm:clean <unit> [--handoff <id>]`; `--handoff` names the handoff when the unit is filed in more than one open handoff (the helper refuses naming both), and is passed to `runcard open` and to every helper call below.

1. Open the card on the unit id: `superegm runcard open --skill clean --artifact <unit>`; it prints `<id>`.
2. Run the one subcommand with the owner's typed arguments: `superegm clean --unit <unit> --runcard <id>`. It removes each `review/<unit>/pr<n>/` worktree that is clean (an uncommitted change there refuses the whole run and removes nothing) and deletes `refs/superegm/pr/<n>` and `refs/superegm/pr-base/<n>`; removes each `worktrees/<unit>/r<n>/` that a launch records, dirty or not (the typed skill is the owner's decision); prints `kept <path>: no launch records it` for a worktree folder no launch records; then prunes the worktree list and journals `<unit> cleaned`.
3. Close the card: `superegm runcard close <id>`.

It refuses, exit 1, while a launch of the unit has no exit file and no `interrupted`, while a round is not `posted` nor `collected` with a `not run` outcome (design section 4: silence proves nothing), and under any card that is not an open `clean` card on this unit.
