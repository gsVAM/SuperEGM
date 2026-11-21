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
2. Run the one subcommand with the owner's typed arguments: `superegm clean --unit <unit> --runcard <id>`. It removes a review worktree only when `git worktree list --porcelain` names it: the `review/<unit>/pr<n>/worktree` child, removed with force (its `pr<n>/` folder and the round records `r<n>` stay), or a legacy `review/<unit>/pr<n>` itself, removed only when it is clean (otherwise `kept <path>: uncommitted changes`, nothing signalled there, and the run goes on). It then deletes `refs/superegm/pr/<n>` and `refs/superegm/pr-base/<n>` of each tree it removed, and removes each `worktrees/<unit>/r<n>/` that a launch records and git names, dirty or not (the typed skill is the owner's decision). A `pr<n>` folder no worktree names, or a recorded `r<n>` git does not name, prints `kept <path>: not a worktree`; a worktree folder no launch records prints `kept <path>: no launch records it`; a path that resolves, symlinks followed, outside the unit's `review/<unit>/` and `worktrees/<unit>/` folders prints `kept <path>: resolves outside the store` and is neither signalled nor removed. Before removing a tree it stops each `node` or `python*` process whose cwd lies inside it (`lsof -a -d cwd -Fn`): SIGTERM, then SIGKILL after 5 seconds, journalled `<unit> killed <pid> <command>`. A tree stays, with a `kept` line, when `lsof` cannot list the processes (`kept <path>: cannot list its processes (<reason>)`), when one cannot be signalled (`kept <path>: process <pid> cannot be signalled`) or when one survives SIGKILL. It prunes the worktree list and journals `<unit> cleaned` only when nothing was kept for one of those reasons.
   `superegm clean --auto --runcard <id>` (never with `--unit`) is the form the wave and integrate skills run at their end: the same code over every landed, merged or stopped unit that is terminal, one `<unit> cleaned` line per unit cleaned, silence for a folder that holds only round records, a `kept` line for a reason above, and exit 0 always.
3. Close the card: `superegm runcard close <id>`.

With `--unit` it refuses, exit 1, while a launch of the unit has no exit file and no `interrupted`, while a round is not `posted` nor `collected` with a `not run` outcome (design section 4: silence proves nothing), and under any card that is not an open `clean` card (the typed skill's) or an open `wave` or `integrate` card (the two skills that run `--auto`).
