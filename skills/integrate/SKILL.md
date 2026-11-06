---
name: integrate
license: Apache-2.0
effects: external
effect_kinds: [state-store, start-session]
disable-model-invocation: true
description: Merges the landed units of a wave into the base branch and closes the handoff.
---

# Integrate (phase 7)

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

    /superegm:integrate <spec-path> [--close]

Runs after every unit has landed or been closed by the owner (who closes a stopped unit's
unlanded dependants with it): one round of the review `spec-<spec-slug>-integrate-c<n>` of the
frozen spec against everything merged, then `close`, which writes `closed_at` and frees the store
for the next handoff. `--close` is the owner's typed close of a handoff they have given up on: it
runs `close` without a review round, journaling every unlanded unit. No judge panel sits in this
skill, in any mode (design anti-goal 6); nothing here approves, merges or pushes. `superegm`
below stands for `python3 '${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py'`, one Bash call
per command, run from the target repository, absolute paths in single quotes, nothing chained;
every writing call carries `--runcard`.

## Step 1: card and the landed set

1. `superegm runcard open --skill integrate --artifact <spec-path>` prints `<card>`; a card still
   open on this spec is marked interrupted by it.
2. The landed set `close` reads is the snapshot `status --wait` saves:
   `superegm status --wait 1 --runcard <card>` reads GitHub once and saves every unit's `landed`
   and `closed` facts.
3. From `state.json`'s `status.units`, list every unit that is neither `landed` nor closed by a
   non-builder login (`closed`'s issue entry). Without `--close`, one such unit ends the
   invocation here: print the list, say that the owner merges, closes or re-types
   `/superegm:wave`, and go to Step 4. With `--close`, go to Step 3.

## Step 2: one integrate round

1. `superegm review open --kind integrate --artifact <spec-path> --reviewers <config.reviewers.integrate> --runcard <card>`
   prints `<id>` (`design` is first; the Astra lane joins when `config.astra.enabled` is true).
2. Write the diff outside the store: `git diff <base_at_start>..<base>` (`base_at_start` from
   `state.json`, written by the first filing; `<base>` from the config) into
   `${TMPDIR:-/tmp}/superegm-integrate/<card>.diff`, the file every reviewer reads.
3. Dispatch every reviewer of the panel concurrently, in one message, each through its adapter
   `superegm:<id>` (`omitClaudeMd: true`, read-only tools), with the frozen spec's path and sha256
   (`approvals/<spec-slug>.json`), the diff file, the review id, round 1 and its own id, and the
   findings line of `${CLAUDE_PLUGIN_ROOT}/skills/review-spec/references/review_loop.md` section 2:
   `<reviewer>-1-<n> | high|medium|low | <location> | regression: no | <claim>`, written to
   `<artifacts_dir>/reviews/<id>/round-1-<reviewer>.txt`, empty when it found nothing. The Astra
   lane runs through the runner from this conversation, as `resources/astra_lane.md` says.
4. Record each result as it arrives:
   `superegm review record --review <id> --round 1 --sha256 <spec sha256> --reviewer <reviewer> --findings <file> --isolation <clean|exposed:what> --model <requested>:<effective> --effort <requested>:<effective> --runcard <card>`
   (one re-dispatch on a failed or empty return, then `--not-run '<reason>'`).
5. `superegm review status --review <id> --runcard <card>`; act on the exit code alone:

| Exit | Then |
| --- | --- |
| 0 | nothing to escalate: Step 3 |
| 5 | stalled (the round did not complete under this card): end with the record, Step 4 |
| any other | every high or medium is escalated: Step 2a |

### Step 2a: escalate

Per high or medium finding, in id order:

1. Append one row to the spec's `## Units` table for the unit that fixes it, with the note
   `(from integrate, review <id>)` in its scope cell; the spec changes nowhere else.
2. `superegm review settle --review <id> --finding <fid> --disposition escalated --runcard <card>`.

Then `superegm approve-spec --spec <spec-path> --amend-units --runcard <card>`: the approval is
re-recorded at the new bytes without a review round, the handoff id kept; it refuses when any
line outside `## Units` changed. Tell the owner in one line: push the approval commit to
`origin/<base>`, then type `plan` → `review-plan` → `file` → `wave` for the new units only. The
handoff stays open; Step 4.

## Step 3: close

`superegm close --runcard <card>` prints `closed <handoff-id>; unlanded: <ids | none>`, writes
`closed_at` into `state.json` and journals `close: <U> unlanded` for every unlanded unit (with
`--close`, the units the owner gave up on; after a clean round, none). A second `close` is
refused (`close: already closed at <ts>`). One `gh api repos/<repo>/issues/<n>` read per unit stopped for
redesign (its `foreman/<U>.json` carries `stopped.brief`) comes first; while that issue is open `close` exits 1 with
`close: <U> is stopped for redesign and #<n> is open: close it by hand once the re-planned unit is filed`, one line per
such unit, each read journaled and `state.json` untouched: the owner closes it by hand, since the plugin edits no issue it did not file, and `close`
runs again. The skill never closes it; it prints the refusal and ends at Step 4. The store is free for the next handoff: the next
`graph` starts a fresh state.

## Step 4: the end

`superegm runcard close <card>` is the last action of every path, including an error you cannot
recover from. In chat: the review id and its `review status` line, the escalated findings with
their new unit rows, or the `closed` line; never a report pasted.
