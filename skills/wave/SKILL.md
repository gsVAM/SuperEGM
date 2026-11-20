---
name: wave
license: Apache-2.0
effects: external
effect_kinds: [start-session, github-write, remote-branch, state-store, destructive-local]
disable-model-invocation: true
description: >-
  Launches the next wave of a handoff's GitHub issues, watches each in-flight
  issue through a foreman (a named or unnamed subagent), runs
  the single review (Astra review lane plus Claude goldfish) on every PR
  head with CI as evidence, posts one confirmed review comment per round,
  and detects landed units. Builders are local; shipping stays human.
  Claude Code only.
---

<!-- Modified by SuperEGM (gsVAM), 2026: the driver loop of §11; the admin-bypass merge line (U19); `[--handoff <id>]` passed on every call (U20); the batch's `review ingest` step 3b (U21); the `ruling` event and its step 4 (U22); the board in the tracking issue (U30); the batch's `notify` (U23); the decision points, rulings and leavemealone-mode moved to `references/`; a head's Decision point 5 and `clean` by accept (U35); `launch-builder` alone and the driver role (U24); `stalled` (U31); the frozen mode, driven normal-mode decisions (U45); `waiting proceed` (U92); the merge round (U62); failed resume (U63); the merge line's inbox (U70); respecs (U86). -->

<!-- Added by the elephant-goldfish-model Astra fork (gsVAM), 2026: the wave skill. Not part of google/elephant-goldfish-model. -->

# Wave: launch, review and land a handoff's units

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

This skill runs in Claude Code only. In any other host reply with one line,
`wave runs in Claude Code only`, and stop.

## What it does

You, the elephant, drive one loop from this conversation over a filed
handoff's units (§11). `superegm launch` marks the ready units
up to `max_in_flight`; you launch one
builder per marked unit as the builder account; the builder pushes its unit branch and opens a draft PR it can never merge. Every head
with concluded CI gets one review round from a **foreman**: a per-unit
elephant dispatched through its own adapter (`superegm:foreman`,
`omitClaudeMd: true`), which dispatches the head's goldfish panel
(zero-context, read-only, each via its own adapter), records the
findings, posts one review comment bound to the reviewed commit, and returns
one word (the word table).

Your only GitHub writes are the `**Ruling:**` comment `decision rule` posts, a respec's comment,
the `superegm:stopped` label a stop adds and the board `status` writes into
the tracking issue. Merge is human: the owner alone updates `<base>`; nothing
here approves, merges, closes an issue or pushes to a builder's branch. One
command at a time (the helper is single-writer). `<HELPER>` =
`${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`; run every helper call
as one Bash call, `python3 '<HELPER>' <subcommand> …`, absolute paths in
single quotes, no chaining; `superegm <subcommand>` below stands for that.
Every writing call carries `--runcard '<CARD>'`; a refusal is one `superegm: <reason>` line.

Under SUPEREGM_ROLE=driver (a tick of `/superegm:driver` started this session), never ask. In
normal mode open points 1, 2, 3 and 5 as `decision open` records, as leavemealone-mode does (an
unconverged judges' question stays open alike). That unit is `pending a decision`
(no slot) and the batch goes on handling every event of the batch; the session ends on the
loop's condition alone: `status.wait_events` acked every event, so an early exit loses another unit's exit.

Open a reference only when sent to it:

- `references/foreman_brief.md`: every foreman's brief (batch step 5).
- `references/decision_points.md`: the `owner:` row and Decision points 1–3 and 5 (`decision open`, then
  `decision rule`, `review settle` or `review rule`), whenever a word, step or `pending:` item names one.
- `references/rulings.md`: a `ruling` line (batch step 4), a posted owner `**Ruling:**` (entry step 4), the stops.
- `references/leavemealone_mode.md`: on a `leavemealone` card, before asking the owner at a decision point.

## Entry: resume from the store

0. The invocation is `/superegm:wave <spec> [--handoff <id>] [--leavemealone]`. With `--handoff`, pass `--handoff '<id>'` to `runcard open` and to every helper call below (an older handoff's filed units still run); without it the card carries the spec's latest approval's handoff. Fill the foreman brief's `<handoff-id>` with the card's handoff.
   `status` and `report` read the card's handoff alone; the inbox is the store-wide read.
1. Run `superegm runcard open --skill wave --artifact '<spec>'`, adding `--mode leavemealone` only when the invocation said `--leavemealone`, else `runcard open`'s default, the approval's frozen mode (`config.mode` for an entry with no `mode`). The printed id is `<CARD>`; a card still open on this spec is marked interrupted.
2. Run `superegm status --wait 1 --runcard '<CARD>'` as a batch runs its wait (`run_in_background: true`, Bash timeout 1,800,000 ms: the first pass reads every issue, PR and check). It reads GitHub once, saves the snapshot `report` derives from (`report` never reads GitHub: skipping this ends the loop on a stale snapshot) and returns every event since its last save, or `deadline`. Handle every line as a batch's steps 1–3 before going on, and `ruling` lines as its step 4; then run batch step 3b.
   Every `status` pass under this card rewrites the board (the `## Units` table `report` prints) between `<!-- superegm:board -->` and `<!-- /superegm:board -->` in the tracking issue's body:
   one GitHub write per pass and none when the rows are unchanged; the inbox stays the action list.
3. Run `superegm report --runcard '<CARD>'`. It derives all from the store, the plan and the spec (refusing as `status` does on a spec changed since its approval); idle units come from this card alone. Its lines: the report path, the board, `idle:`, `pending:`, `loop:`.
4. Rule every `pending:` item first, at its decision point in `references/decision_points.md`: the record's `point`, printed as `(point <p>, <source>)`, names the point, never the source's words (a point-5 decision's source is `review <id> round <n>`, as point 1's is). Before asking, read the issue's comments (`GH_HOST=github.com gh api repos/<repo>/issues/<n>/comments --paginate`): an owner's `**Ruling:**` already posted binds once `decision rule --posted <comment id>` records it, as `references/rulings.md`'s `ruling` bullet says; then an `interrupted` launch with no decision on it → Decision point 3.
5. Run `report` again. `loop: ended` and no 5b line in step 2 → The end. Otherwise run batches, the
   first from its step 5: step 2 was its wait, and its lines are handled.

Builders a previous invocation left running report through `status --wait`'s
`exit` lines. Nothing recorded is launched, ruled or reviewed twice (`launch`,
`launch-builder`, `decision rule` and `foreman dispatch` refuse): take a refusal as fact, never retry it.
A `held: respec` unit never gets a direct `launch-builder`: step 6's `launch` marks it.

## A batch

Run `superegm status --wait 1500 --runcard '<CARD>'` from this
conversation with `run_in_background: true` (Bash timeout 1,800,000
ms). It returns every unreported event since its last save, one line each
(`head`, `exit`, `status`, `landed`, `closed`, `ruling`, `stalled`, `conflict`), or `deadline`, then respec lines (`open: respec`, `held: respec`, `respec: read failed`: none to do; `respec post`, `respec relaunch`: 5b). Handle every
line before calling it again, in this order; lines for a stopped unit are
ignored except `landed` and `stalled`; `conflict` lines need nothing before step 6:

1. `landed` lines: the unit is done; its dependants become ready (`launch` sees them at step 6).
2. `closed` lines: a non-builder actor closed the PR unmerged or the issue → the owner has ruled; run `superegm decision rule --unit <U> --ruling 'stop the unit' --by <login> --posted closed:<n> --runcard '<CARD>'`. The builder account closed it → Decision point 3 (source `closed <n>`).
3. `exit` and `status` lines, one folded decision per unit. Record the exit: `superegm record-launch --unit <U> --exit <code> --runcard '<CARD>'`. It prints `failed resume` → step 6's `launch-builder` now (fresh), no decision. Then: `DONE` and `DONE_WITH_CONCERNS` need nothing (the head is reviewed at step 5); `BLOCKED` or `NEEDS_CONTEXT`, an exit with no PR (`pr=none`), or an interrupted launch → Decision point 3. `stalled`: `superegm record-launch --unit <U> --exit stalled --runcard '<CARD>'`, then Decision point 3 with the stall facts unless stopped; `kill_failed` idle.
3b. `superegm review ingest` for every unit with an open PR (never a landed unit), awaiting-merge units included, stopped units excluded: `--unit <U> --runcard '<CARD>'` records the PR's new review threads as `external:<login>` findings into the latest posted round and prints `<n> ingested` (`0 ingested` before its first posted round). `outcome: revise`: the unit is ready again; `launch` marks it at step 6 when a slot is free (never `launch-builder` here). `outcome: cap-reached` → Decision point 2 (source `review <head-review-id> cap`). Exit 1: report the unit and the refusal line in chat; the batch goes on. A GitHub read or record refusal may clear on the next batch's retry, as does `unfinished ingest is not on the latest posted round`; `comment over 65,536 bytes`, `is not set: the builder's login is unknown`, `header present on` and a `review ingest: comment:<n>:` scan refusal repeat until the owner resolves them by hand, so say so each batch.
4. `ruling` lines: an owner's `**Ruling:**` comment; apply it as `references/rulings.md`'s `ruling` bullet says.
5. `superegm foreman dispatch` for every active unit with a head, `deadline` included: `--unit <U> --runcard '<CARD>'`. It alone evaluates §11's predicate (CI concluded, latest launch terminal, no round posted since it, no decision pending, review not stalled): it prints `<dispatch-id> <child-card>` when it holds and refuses otherwise: skip a refused unit, except exit 1 `recovered <word>`, which is the foreman's word for a round the PR already carries. Dispatch every accepted unit's foreman **in one message**, each through the `superegm:foreman` adapter, named `foreman-<U>-<dispatch-id>`, in the foreground, with `references/foreman_brief.md`'s brief filled in. Then `word_action` per returned word (the table below).
5b. `respec.actionable` (§7.6; the raising unit waits): `respec post R<n> <U> #<i> '<f>'` → `superegm scan --comment '<f>'` (a finding: say so, post nothing), then `GH_HOST=github.com gh issue comment <i> -R OWNER/NAME --body-file '<f>'`, then `superegm respec posted --respec R<n> --unit <U> --comment <the URL's id>`; `respec relaunch` → step 6, reason `respec`.
6. `superegm launch`: `--idle <the report's idle list> --runcard '<CARD>'` (omit `--idle` on `none`) marks the ready units up to the free slots and prints `in flight:` and `marked:`; a clean `conflict` unit is marked once for its **merge round**. Per marked unit: `superegm launch-builder --unit <U> --round <n> --runcard '<CARD>'` (`<n>` is the launch count) alone: `launch-builder` starts the builder and records the launch, detached in its own session, and returns at once. A `launch-builder` refusal makes the unit idle for this invocation, no retry: `superegm report --idle '<U>=launch-builder: <reason>' --runcard '<CARD>'`.
7. `superegm report`: `python3 '<HELPER>' report --runcard '<CARD>'`, then `python3 '<HELPER>' notify --runcard '<CARD>'` (the owner's `~/.superegm/notify` hook gets the new inbox lines; a failing or slow hook never stops the wave). If a decision was opened this batch, pause (outside SUPEREGM_ROLE=driver, above): ask the owner at its decision point and run `report` again once ruled. Else `loop: ended` and no 5b line of a non-idle unit → The end; else the next batch.

A launched unit's `unit_state`, in order: `landed`, `stopped`, `pending`,
`idle`, `waiting proceed` (no slot; ask the owner to proceed again), CI-wait
`idle`, `clean`, else `active`; `active`/`clean` with an open respec: `waiting respec`; only `active` is dispatched. `loop_ended`: no
active unit, no ready unlaunched unit with a free slot, nor a merge round `launch` would mark. CI pending or absent
`ci_wait_minutes` (default 30) after the card saw the head: CI-wait `idle`;
a new head restarts it.

## The word table

`word_action(word, review_exit)`, where `review_exit` is the exit code of
`superegm review status --review <head-review-id> --runcard '<CARD>'`
(the unit's `head-<U>-c<n>` review under `reviews/`, opened by its first
dispatch):

- `clean` → await-merge: nothing runs; the unit awaits the owner's merge and
  its slot is free; so after accept (point 5) or a proceed, but one pinning no head: `proceed again`.
  `await-merge after <unit>, …`: the owner merges in that order.
- `revise` → in normal mode, when `review status` printed `acceptable: yes` → Decision point 5 first (no launch
  while it is pending). Otherwise, and on a ruled `revise`, `launch-builder` for the next
  round (the prompt carries the review); a ruled `revise` spends no relaunch.
- `contested: <ids>` → Decision point 1: on a head, the judges' panel rules a contested or declined high or medium finding
  first, in normal mode as in leavemealone; only a panel that does not converge reaches the owner, with point 1's question
  and the line naming `judges/<panel>/verdict.json`. The owner-only rulings stay the owner's.
- `cap-reached` → Decision point 2.
- `owner: <ids>` → `decision open` for the owner's findings, ruled by the owner alone (no judge panel):
  no relaunch, no slot.
- `error`, `target-moved`, or a return that is none of these words (no word
  included) → redispatch: the head is reviewed again at
  the next step 5, unless `review status` exits 5 (stalled) →
  `superegm report --idle '<U>=review stalled' --runcard '<CARD>'`.
- `blocked` (step 2's builder close, step 3's cases) → Decision point 3.
- `recovered <word>` from `foreman dispatch` → the row of `<word>`.

## Retries

- `status --wait` exiting non-zero: retry once; failing again, run `report` and end.
- A `decision rule` whose post or label request fails (a `gh` error, not a refusal) records nothing: run it again, a `--posted` one included. A journaled `<U> <qid>: label superegm:stopped left on issue #<n>` means the label stayed on: run `gh issue edit <n> --remove-label superegm:stopped` first.
## The end

Before the close, run batch step 3b once and `report` again (a thread posted before the last round's review is read now): an `outcome:` line or no longer `loop: ended` → back to the batches.

`loop: ended` → run `superegm runcard close '<CARD>'`. Then report in chat from `wave_<n>_report.md`: per unit: state, head, rounds; non-terminal launches (builders still running report to the next `wave`); heads with pending or absent CI; idle units and why; ready units without a slot; pending decisions; stopped units with their unlanded dependants: what stayed open for the owner to merge,
close, or re-type `/superegm:wave`. The owner merges in the inbox, which runs `gh pr merge --admin` once the owner says yes, where the base ruleset restricts updates to config.owners.
