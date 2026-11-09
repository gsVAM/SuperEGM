---
name: wave
license: Apache-2.0
effects: external
effect_kinds: [start-session, github-write, remote-branch, state-store]
disable-model-invocation: true
description: >-
  Launches the next wave of a handoff's GitHub issues, watches each in-flight
  issue through a foreman (a named or unnamed subagent), runs
  the single review (Astra review lane plus Claude goldfish) on every PR
  head with CI as evidence, posts one confirmed review comment per round,
  and detects landed units. Builders are local; shipping stays human.
  Claude Code only.
---

<!-- Modified by SuperEGM (gsVAM), 2026: the driver loop of §11; the admin-bypass merge line (U19); `[--handoff <id>]` passed on every call (U20); the batch's `review ingest` step 3b (U21); the `ruling` event and its step 4 (U22); the board in the tracking issue (U30); the batch's `notify` (U23); the decision points, rulings and leavemealone-mode moved to `references/`; `launch-builder` alone and the driver role (U24). -->

<!-- Added by the elephant-goldfish-model Astra fork (gsVAM), 2026: the wave skill. Not part of google/elephant-goldfish-model. -->

# Wave: launch, review and land a handoff's units

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

This skill runs in Claude Code only. In any other host reply with one line,
`wave runs in Claude Code only`, and stop.

## What it does

You, the elephant, drive one loop from this conversation over a filed
handoff's units (design section 11). `superegm launch` marks the ready units
up to `max_in_flight` (a unit pending a decision holds no slot); you launch one
builder per marked unit as the builder account (`launch-builder` starts the builder and records the launch); the builder pushes its unit branch and opens a draft pull request it can never merge. Every head
with concluded CI gets one review round from a **foreman**: a per-unit
elephant dispatched through its own adapter (`superegm:foreman`,
`omitClaudeMd: true`), which dispatches the head's goldfish panel
(zero-context, read-only, each through its own adapter), records the
findings, posts one review comment bound to the reviewed commit, and returns
one word (the word table). The builder answers the review in its next launch.

Your only GitHub writes are the `**Ruling:**` comment `decision rule` posts,
the `superegm:stopped` label a stop adds and the board `status` writes into
the tracking issue. Merge is human: the owner alone updates `<base>`; nothing
here approves, merges, closes an issue or pushes to a builder's branch. One
command at a time: the helper is single-writer. `<HELPER>` =
`${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`; run every helper call
as one Bash call, `python3 '<HELPER>' <subcommand> …`, absolute paths in
single quotes, no chaining; `superegm <subcommand>` below stands for that.
Every writing call carries `--runcard '<CARD>'`; a refusal is one
`superegm: <reason>` line, exit 1.

Under SUPEREGM_ROLE=driver (a tick of `/superegm:driver` started this session, always
`--leavemealone`), never ask: a decision the judges did not converge on is a journal line and
an inbox line, its unit is `pending a decision` (no slot) and the batch goes on; the session
ends on the loop's condition alone and the next tick resumes the rest.

Open a reference only when this file sends you to it:

- `references/foreman_brief.md`: the brief every foreman is dispatched with (batch step 5).
- `references/decision_points.md`: the `owner:` row and Decision points 1–3 (`decision open`, then
  `decision rule`, `review settle` or `review rule`), whenever a word, a step or a `pending:` item names one.
- `references/rulings.md`: a `ruling` line (batch step 4), an owner's `**Ruling:**` already posted
  (entry step 4), and the stops.
- `references/leavemealone_mode.md`: on a card opened with `--mode leavemealone`, before asking the
  owner at any decision point.

## Entry: resume from the store

0. The invocation is `/superegm:wave <spec> [--handoff <id>] [--leavemealone]`. With `--handoff`, pass
   `--handoff '<id>'` to `runcard open` and to every helper call below (an older handoff's filed units
   still run); without it the card carries the spec's latest approval's handoff. Fill the foreman brief's
   `<handoff-id>` with the card's handoff.
   `status` and `report` read the card's handoff alone; the inbox is the store-wide read.
1. Run `python3 '<HELPER>' runcard open --skill wave --artifact '<spec>'`
   (the approved spec the invocation named), adding `--mode leavemealone`
   when the invocation said `--leavemealone` or the config's `mode` is
   `leavemealone` (then follow `references/leavemealone_mode.md`). The
   printed id is `<CARD>`; a card still open on this spec is marked
   interrupted by the new one.
2. Run `python3 '<HELPER>' status --wait 1 --runcard '<CARD>'` as a batch
   runs its wait (`run_in_background: true`, Bash timeout 1,800,000 ms: the
   first pass reads every unit's issue, PR and checks). It reads GitHub
   once, saves the snapshot `report` derives from (`report` reads GitHub
   never, so skipping this ends the loop on a stale snapshot) and returns every event since that
   invocation's last save, or `deadline`. Handle every line as a batch's
   steps 1–3 before going on, and `ruling` lines as its step 4; then run
   batch step 3b.
   Every `status` pass under this card rewrites the board (the `## Units` table `report` prints) between `<!-- superegm:board -->` and `<!-- /superegm:board -->` in the tracking issue's body:
   one GitHub write per pass and none when the rows are unchanged; the inbox stays the action list.
3. Run `python3 '<HELPER>' report --runcard '<CARD>'`. Everything is derived
   from the store, the plan and the spec (it refuses as `status` does when the spec changed since
   its approval); idle units come from this card alone (idle never carries over). Its lines: the
   report path, the board, `idle:`, `pending:`, `loop:`.
4. Rule every `pending:` item first, at its decision point in
   `references/decision_points.md` (the source names the point: `comment <id>`,
   `launch <n>` and `closed <n>` are point 3; `review <id> round <n>` is point 1;
   `review <id> cap` is point 2). Before asking any of them, read the issue's comments
   (`GH_HOST=github.com gh api repos/<repo>/issues/<n>/comments --paginate`): an owner's
   `**Ruling:**` already posted binds once `decision rule --posted <comment id>` records it,
   as the `ruling` bullet of `references/rulings.md` says.
5. Run `report` again. `loop: ended` → The end. Otherwise run batches, the
   first from its step 5: step 2 was its wait, and its lines are handled.

Builders a previous invocation left running report through `status --wait`'s
`exit` lines. Nothing recorded is launched, ruled or reviewed twice: `launch`,
`launch-builder`, `decision rule` and `foreman dispatch` refuse, and you take
a refusal as the fact it states, never as an error to retry.

## A batch

Run `python3 '<HELPER>' status --wait 1500 --runcard '<CARD>'` from this
main conversation with `run_in_background: true` (Bash timeout 1,800,000
ms). It returns every unreported event since its last save, one line each
(`head`, `exit`, `status`, `landed`, `closed`, `ruling`), or `deadline`. Handle every
line before calling it again, in this order; lines for a stopped unit are
ignored except `landed`:

1. `landed` lines: the unit is done; its dependants become ready (`launch`
   sees them at step 6).
2. `closed` lines: a non-builder actor closed the PR unmerged or the issue
   → the owner has ruled; run
   `python3 '<HELPER>' decision rule --unit <U> --ruling 'stop the unit' --by <login> --posted closed:<n> --runcard '<CARD>'`.
   The builder account closed it → Decision point 3 (source `closed <n>`).
3. `exit` and `status` lines, one folded decision per unit. First record the
   exit: `python3 '<HELPER>' record-launch --unit <U> --exit <code> --runcard '<CARD>'`.
   Then: `DONE` and `DONE_WITH_CONCERNS` need nothing (the head is reviewed
   at step 5); `BLOCKED` or `NEEDS_CONTEXT`, an exit with no PR
   (`pr=none`), or an interrupted launch → Decision point 3.
3b. `superegm review ingest` for every unit with an open PR (never a landed unit),
   awaiting-merge units included, stopped units excluded:
   `python3 '<HELPER>' review ingest --unit <U> --runcard '<CARD>'` records
   the PR's new review threads as `external:<login>` findings into the latest
   posted round and prints `<n> ingested` (`0 ingested` before its first posted round).
   `outcome: revise`: the unit is ready again; `launch` marks it at step 6 when a
   slot is free (never `launch-builder` here).
   `outcome: cap-reached` → Decision point 2 (source `review <head-review-id> cap`).
   Exit 1: report the unit and the refusal line in chat; the batch goes on. A GitHub read or a record
   refusal may clear on the next batch's retry, and `unfinished ingest is not on the latest posted round` clears on the re-run it names;
   `comment over 65,536 bytes`, `is not set: the builder's login is unknown`,
   `header present on` and a `review ingest: comment:<n>:` scan refusal repeat until the owner resolves them by hand, so say so in chat each batch.
4. `ruling` lines: an owner's `**Ruling:**` comment; apply it as the `ruling`
   bullet of `references/rulings.md` says.
5. `superegm foreman dispatch` for every active unit with a head, `deadline`
   included: `python3 '<HELPER>' foreman dispatch --unit <U> --runcard '<CARD>'`.
   It prints `<dispatch-id> <child-card>` when section 11's predicate holds
   (CI concluded, the latest launch terminal, no round posted since it, no
   decision pending, the review not stalled) and refuses otherwise: skip a
   refused unit, except exit 1 `recovered <word>`, which is the foreman's
   word for a round the PR already carries. Never evaluate the predicate
   yourself: `foreman dispatch` is its one place. Dispatch every accepted unit's
   foreman **in one message**, each through the `superegm:foreman` adapter,
   named `foreman-<U>-<dispatch-id>`, in the foreground, with the brief of
   `references/foreman_brief.md` filled in. Then `word_action` per returned
   word (the table below).
6. `superegm launch`:
   `python3 '<HELPER>' launch --idle <the report's idle list> --runcard '<CARD>'`
   (omit `--idle` when the list is `none`) marks the ready units up to the
   free slots and prints `in flight:` and `marked:`. Per marked unit:
   `python3 '<HELPER>' launch-builder --unit <U> --round <n> --runcard '<CARD>'`
   (`<n>` is the launch count) alone: `launch-builder` starts the builder and records the launch,
   detached in its own session, and returns at once. A
   `launch-builder` refusal makes the unit idle for this invocation, no retry:
   `python3 '<HELPER>' report --idle '<U>=launch-builder: <reason>' --runcard '<CARD>'`.
7. `superegm report`: `python3 '<HELPER>' report --runcard '<CARD>'`, then `python3 '<HELPER>' notify --runcard '<CARD>'`
   (the owner's `~/.superegm/notify` hook gets the inbox lines new since the last notify; a failing or slow hook never stops the wave). If a
   decision was opened this batch, pause: ask the owner at its decision
   point and run `report` again once ruled. Else `loop: ended` → The end;
   otherwise the next batch.

`report` derives each launched unit's state with `unit_state`, one of six:
`landed`, `stopped`, `pending`, `idle`, `clean`, else `active`; only an
active unit is dispatched. `loop_ended` is the end condition: no active
unit, and no ready unit unlaunched while a slot is free. A head whose CI is
pending or absent for `ci_wait_minutes` (default 30) since this card first
saw it is idle and holds no slot; a new head restarts the clock.

## The word table

`word_action(word, review_exit)`, where `review_exit` is the exit code of
`python3 '<HELPER>' review status --review <head-review-id> --runcard '<CARD>'`
(the unit's `head-<U>-c<n>` review under `reviews/`, opened by its first
dispatch):

- `clean` → await-merge: nothing runs; the unit awaits the owner's merge and
  its slot is free.
- `revise` → `launch-builder` for the next round (the prompt carries the
  review).
- `contested: <ids>` → Decision point 1.
- `cap-reached` → Decision point 2.
- `owner: <ids>` → `decision open` for the owner's findings, ruled by the owner alone (no judge panel):
  no relaunch, no slot. The row is in `references/decision_points.md`.
- `error`, `target-moved`, or a return that is none of these words (no word
  included) → redispatch: nothing runs now; the head is reviewed again at the
  next batch's step 5, unless `review status` exits 5 (stalled) →
  `python3 '<HELPER>' report --idle '<U>=review stalled' --runcard '<CARD>'`.
- `blocked` (step 2's builder close, step 3's cases) → Decision point 3.
- `recovered <word>` from `foreman dispatch` → the row of `<word>`.

## Retries

- `status --wait` exiting non-zero: run it once more; if it fails again, run
  `report`, say so in chat, and end this invocation.
- A `decision rule` whose post or label request fails (a `gh` error, not a refusal) records nothing: run it again, a `--posted` one included. A journaled `<U> <qid>: label superegm:stopped left on issue #<n>` means the label stayed on: run `gh issue edit <n> --remove-label superegm:stopped` first.
- `error`, `target-moved` and a `launch-builder` refusal are retried only as
  the word table and step 6 say; a refusal is handled by the batch order.

## The end

Before the close, run batch step 3b once and `report` again (a thread posted before the last round's review is read now): an `outcome:` line or no longer `loop: ended` → back to the batches.

`loop: ended` → run `python3 '<HELPER>' runcard close '<CARD>'`. Then
report in chat from `wave_<n>_report.md`: per unit its state, head and
rounds; the non-terminal launches (builders still running report to the
next `wave`); the heads with pending or absent CI; the idle units and why;
the ready units without a slot; the pending decisions; the stopped units
with their unlanded dependants. That is what stayed open, for the owner to
merge, close, or re-type `/superegm:wave`. Where the base ruleset restricts updates to config.owners, the owner merges with the admin bypass: `gh pr merge --admin`.
