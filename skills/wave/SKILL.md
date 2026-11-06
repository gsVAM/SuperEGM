---
name: wave
license: Apache-2.0
effects: external
effect_kinds: [start-session, github-write, remote-branch, state-store]
disable-model-invocation: true
description: >-
  Launches the next wave of a handoff's GitHub issues, watches each in-flight
  issue through a foreman (a named or unnamed subagent), runs
  the single review (Astra inspect lane plus Claude goldfish) on every PR
  head with CI as evidence, posts one confirmed review comment per round,
  and detects landed units. Builders are local; shipping stays human.
  Claude Code only.
---

<!-- Modified by SuperEGM (gsVAM), 2026: the driver loop of §11. -->

<!-- Added by the elephant-goldfish-model Astra fork (gsVAM), 2026: the wave skill. Not part of google/elephant-goldfish-model. -->

# Wave: launch, review and land a handoff's units

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

This skill runs in Claude Code only. In any other host reply with one line,
`wave runs in Claude Code only`, and stop.

## What it does

A filed handoff's units are built by builders and reviewed by foremen while
you, the elephant, drive one loop from this conversation (design section 11).
`superegm launch` marks the ready units up to `max_in_flight`; you launch one
builder per marked unit as the builder account (`launch-builder` writes the
prompt file and the command line, `record-launch` records the launch and,
later, its exit); the builder pushes its unit branch and opens a draft pull
request it can never merge. Every head with concluded CI gets one review
round from a **foreman**: a per-unit elephant dispatched through its own
adapter (`superegm:foreman`, `omitClaudeMd: true`), which dispatches the
head's goldfish panel (zero-context, read-only, each through its own
adapter), records the findings, posts one review comment bound to the
reviewed commit, and returns one word. You handle the word (the table
below); the builder answers the review in its next launch.

Your only GitHub writes are the `**Ruling:**` comment `decision rule` posts
and the `superegm:stopped` label a stop adds. Merge is human: the owner
alone updates `<base>`; nothing here approves, merges, closes an issue or
pushes to a builder's branch. One command at a time: the helper is
single-writer. `<HELPER>` = `${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`;
run every helper call as one Bash call, `python3 '<HELPER>' <subcommand> …`,
absolute paths in single quotes, no chaining; `superegm <subcommand>` below
stands for that. Every writing call carries `--runcard '<CARD>'`; a refusal
is one `superegm: <reason>` line, exit 1.

## Entry: resume from the store

1. Run `python3 '<HELPER>' runcard open --skill wave --artifact '<spec>'`
   (`<spec>` is the approved spec the invocation named), adding
   `--mode leavemealone` when the invocation said `--leavemealone` or the
   config's `mode` is `leavemealone`: the mode is recorded on the card and
   acted on by the leavemealone wiring. The printed id is `<CARD>`; a card
   still open on this spec is marked interrupted by the new one.
2. Run `python3 '<HELPER>' status --wait 1 --runcard '<CARD>'` as a batch
   runs its wait (`run_in_background: true`, Bash timeout 1,800,000 ms: the
   first pass reads every unit's issue, PR and checks). It reads GitHub
   once, saves the snapshot `report` derives from (`report` reads the store
   alone: on the previous invocation's snapshot it sees an empty ready set
   and ends the loop before any batch) and returns every event since that
   invocation's last save, or `deadline`. Handle every line as a batch's
   steps 1–3 before going on.
3. Run `python3 '<HELPER>' report --runcard '<CARD>'`. Everything is derived
   from the store: pending decisions from `decisions[]` minus `rulings[]`,
   launches in flight from `launches[].status`, rounds from `rounds[]`, idle
   units from this card alone (idle never carries over). Its lines: the
   report path, `idle:`, `pending:`, `loop:`.
4. Rule every `pending:` item first, through its decision point below (the
   source names the point: `comment <id>`, `launch <n>` and `closed <n>` are
   point 3; `review <id> round <n>` is point 1; `review <id> cap` is point
   2). Before asking a point-3 question, read the issue's comments (the
   by-hand rulings section): a `**Ruling:**` already posted rules it.
5. Run `report` again. `loop: ended` → The end. Otherwise run batches, the
   first from its step 4: step 2 was its wait, and its lines are handled.

Builders a previous invocation left running report through `status --wait`'s
`exit` lines. Nothing recorded is launched, ruled or reviewed twice: `launch`,
`launch-builder`, `decision rule` and `foreman dispatch` refuse, and you take
a refusal as the fact it states, never as an error to retry.

## A batch

Run `python3 '<HELPER>' status --wait 1500 --runcard '<CARD>'` from this
main conversation with `run_in_background: true` (Bash timeout 1,800,000
ms). It returns every unreported event since its last save, one line each
(`head`, `exit`, `status`, `landed`, `closed`), or `deadline`. Handle every
line before calling it again, in this order; lines for a stopped unit are
ignored except `landed`:

1. `landed` lines: the unit is done; its dependants become ready (`launch`
   sees them at step 5).
2. `closed` lines: a non-builder actor closed the PR unmerged or the issue
   → the owner has ruled; run
   `python3 '<HELPER>' decision rule --unit <U> --ruling 'stop the unit' --by <login> --posted closed:<n> --runcard '<CARD>'`.
   The builder account closed it → Decision point 3 (source `closed <n>`).
3. `exit` and `status` lines, one folded decision per unit. First record the
   exit: `python3 '<HELPER>' record-launch --unit <U> --exit <code> --runcard '<CARD>'`.
   Then: `DONE` and `DONE_WITH_CONCERNS` need nothing (the head is reviewed
   at step 4); `BLOCKED` or `NEEDS_CONTEXT`, an exit with no PR
   (`pr=none`), or an interrupted launch → Decision point 3.
4. `superegm foreman dispatch` for every active unit with a head, `deadline`
   included: `python3 '<HELPER>' foreman dispatch --unit <U> --runcard '<CARD>'`.
   It prints `<dispatch-id> <child-card>` when section 11's predicate holds
   (CI concluded, the latest launch terminal, no round posted since it, no
   decision pending, the review not stalled) and refuses otherwise: skip a
   refused unit, except exit 1 `recovered <word>`, which is the foreman's
   word for a round the PR already carries. Dispatch every accepted unit's
   foreman **in one message**, each through the `superegm:foreman` adapter,
   named `foreman-<U>-<dispatch-id>`, in the foreground, with the brief of
   `references/foreman_brief.md` filled in. Then `word_action` per returned
   word (the table below).
5. `superegm launch`:
   `python3 '<HELPER>' launch --idle <the report's idle list> --runcard '<CARD>'`
   (omit `--idle` when the list is `none`) marks the ready units up to the
   free slots and prints `in flight:` and `marked:`. Per marked unit:
   `python3 '<HELPER>' launch-builder --unit <U> --round <n> --runcard '<CARD>'`
   (`<n>` is the launch count; its last line is the command: run it with
   `run_in_background: true`), then
   `python3 '<HELPER>' record-launch --unit <U> --runcard '<CARD>'`. A
   `launch-builder` refusal makes the unit idle for this invocation:
   `python3 '<HELPER>' report --idle '<U>=launch-builder: <reason>' --runcard '<CARD>'`.
6. `superegm report`: `python3 '<HELPER>' report --runcard '<CARD>'`. If a
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
- `revise` → `launch-builder` and `record-launch` for the next round (the
  prompt carries the review).
- `contested: <ids>` → Decision point 1.
- `cap-reached` → Decision point 2.
- `error`, `target-moved`, or a return that is none of the six words →
  redispatch: nothing runs now; the head is reviewed again at the next
  batch's step 4, unless `review status` exits 5 (stalled) →
  `python3 '<HELPER>' report --idle '<U>=review stalled' --runcard '<CARD>'`.
- `blocked` (step 2's builder close, step 3's cases) → Decision point 3.
- `recovered <word>` from `foreman dispatch` → the row of `<word>`.

### Decision point 1

The builder contested findings. Write them (ids, claims, the builder's
reasons from the round's `comments.md`) to a question file and run
`python3 '<HELPER>' decision open --unit <U> --point 1 --question '<file>' --source 'review <head-review-id> round <n>' --runcard '<CARD>'`
(options `finding upheld; finding overruled`). In normal mode ask the owner,
one question per finding, the builder's reason verbatim as the overrule
option's text. Apply each ruling: per overruled finding
`python3 '<HELPER>' review settle --review <head-review-id> --finding <fid> --disposition contested --owner --runcard '<CARD>'`,
then `review status`; record it with
`python3 '<HELPER>' decision rule --unit <U> --decision <qid> --ruling '<fid> finding upheld' --by <login> --runcard '<CARD>'`
or `--ruling '<fid> finding overruled — <reason>'`, which posts the
`**Ruling:**` comment on the issue. Then by `review status`: 0 → the unit
awaits merge; 2 → Decision point 2; else `launch-builder`.
A third ruling, on a head, is `redesign — <one sentence why>` (the sentence the owner's, typed after the dash; a bare `redesign` is refused):
`python3 '<HELPER>' decision rule --unit <U> --decision <qid> --ruling 'redesign — <one sentence why>' --by <login> --runcard '<CARD>'`.
It stops the unit by `stop`'s own path (the issue labelled `superegm:stopped`, never relaunched) and writes the
store-only brainstorm brief `foreman/<U>-<qid>.brainstorm.md`; the `**Ruling:**` comment says the unit is
stopped for redesign and names the brief, and asks the owner to close the issue by hand once the re-planned unit is filed.
A redesign ruled by hand with `--posted` (a `<comment-id>`) posts nothing: the brief is written and the unit stopped,
but no comment names the brief, so the owner closes the issue by hand all the same.
The road back is typed phases only: `/superegm:brainstorming` from the brief, the amended spec, `plan`, `review-plan`, `file`, then the wave again.
Leavemealone-mode: U11 wires §13.2 here.

### Decision point 2

The head review is at its cap. Cap: 5 rounds, then PAUSE for the owner.
Write the `review status` trend line to a question file and run
`python3 '<HELPER>' decision open --unit <U> --point 2 --question '<file>' --source 'review <head-review-id> cap' --runcard '<CARD>'`
(options `one more round; stop`, and on a head `redesign — <one sentence why>`; once `one more round` is spent,
`judges question --review <head-review-id> --cap` asks `stop` and `redesign` alone). `one more round` (once per unit):
`python3 '<HELPER>' review rule --review <head-review-id> --ruling continue --owner --runcard '<CARD>'`,
then `decision rule … --ruling 'one more round'`, then `launch-builder`.
`stop`: `review rule … --ruling stop --owner`, then
`decision rule … --ruling stop`, which labels and stops the unit.
`redesign — <one sentence why>`: `review rule … --ruling stop --owner`, then
`decision rule … --ruling 'redesign — <one sentence why>' --by <login>`: the unit is stopped for redesign with its
brainstorm brief, the comment names it, and the road back is Decision point 1's.
Leavemealone-mode: U11 wires §13.2 here.

### Decision point 3

A builder is blocked, or its launch ended without a head. Write the
builder's comment (or the exit, interrupt or close facts) to a question file
and run
`python3 '<HELPER>' decision open --unit <U> --point 3 --question '<file>' --source '<comment <id> | launch <n> | closed <n>>' --runcard '<CARD>'`.
Its second line is the options: the comment's own `- (a)` lines plus
`stop the unit`; `relaunch; stop the unit` for an exit with no PR, an
interrupted launch, a builder's close, or a third blocked comment on one
head; or `ruled: stop the unit (relaunch already used)`, already applied.
Ask the owner, then
`python3 '<HELPER>' decision rule --unit <U> --decision <qid> --ruling '(<letter>) — <reason>' --by <login> --runcard '<CARD>'`
(it posts `**Ruling:** (<comment-id>) <option> — <reason>` quoting the
question; the next launch's prompt carries it). `relaunch` →
`launch-builder` now; `stop the unit` → the unit is labelled and never
relaunched.
Leavemealone-mode: U11 wires §13.2 here.

## Stops and by-hand rulings

- The owner's close (step 2) is `stop` without a question:
  `decision rule --posted closed:<n>` records nothing but the stop.
- A `**Ruling:**` the owner posted by hand on the issue, naming the BLOCKED
  comment's id as `(<comment-id>)`, rules that pending decision. When
  raising a pending point-3 decision, read the comments with
  `GH_HOST=github.com gh api repos/O/R/issues/<n>/comments --paginate` and,
  for such a comment, run
  `python3 '<HELPER>' decision rule --unit <U> --decision <qid> --ruling '<its option>' --by <author> --posted <comment-id> --runcard '<CARD>'`:
  nothing is posted; a comment by the builder account, one naming another
  id, or an author other than `--by` is refused and nothing is recorded.
- A stopped unit keeps its branch and its open issue, is never dispatched or
  launched again, and is listed in the report with its unlanded dependants
  for the owner (design section 12).

## Retries

- `error` and `target-moved`: the next batch's `foreman dispatch` for every
  active unit with a head, `deadline` included, until `review status` exits
  5, which makes the unit idle. A foreman that returns no word is `error`.
- A `launch-builder` refusal is idle for the invocation; no retry.
- `status --wait` exiting non-zero: run it once more; if it fails again, run
  `report`, say so in chat, and end this invocation.
- A `decision rule` whose post fails records nothing: run it again.
- Never evaluate the dispatch predicate yourself: `foreman dispatch` is its
  one place, and the batch order above is how a refusal is handled.

## The end

`loop: ended` → run `python3 '<HELPER>' runcard close '<CARD>'`. Then
report in chat from `wave_<n>_report.md`: per unit its state, head and
rounds; the non-terminal launches (builders still running report to the
next `wave`); the heads with pending or absent CI; the idle units and why;
the ready units without a slot; the pending decisions; the stopped units
with their unlanded dependants. That is what stayed open, for the owner to
merge, close, or re-type `/superegm:wave`.

## Leavemealone-mode

In leavemealone-mode (`--leavemealone` on the invocation, or `config.mode`,
recorded on the card at Entry step 1) the three `Leavemealone-mode: U11 wires
§13.2 here.` lines above are the entry points (`<card>` below is `<CARD>`): at
each decision point, after
`python3 '<HELPER>' decision open --unit <U> --point <1|2|3> --question <path> --source <source> --runcard <card>`
has recorded the pending decision, the judge panel rules instead of the owner,
and what each converged answer applies is the one routing table
`${CLAUDE_PLUGIN_ROOT}/skills/judges/references/leavemealone.md` (this skill
carries none of its own). Render the question from the record:

- point 1: `python3 '<HELPER>' judges question --review <id> --round <n> --runcard <card>`
  (`<id>` the head review; every `builder_contested[]` entry of the round
  renders itself, the builder's reason verbatim as the overrule option's text);
- point 2: `python3 '<HELPER>' judges question --review <id> --cap --runcard <card>`;
- point 3: `python3 '<HELPER>' judges question --unit <U> --blocked <comment-id> --runcard <card>`
  for a BLOCKED or NEEDS_CONTEXT comment,
  `python3 '<HELPER>' judges question --unit <U> --blocked launch <n> --runcard <card>`
  for an exit with no PR or an interrupted launch, and
  `python3 '<HELPER>' judges question --unit <U> --blocked closed <n> --runcard <card>`
  for a close by the builder account. Its second line, `consumers: #<n> …`,
  appears for an `interface` deviation: the ruling is also posted as the same
  `**Ruling:**` comment on every `consumers:` issue, with
  `GH_HOST=github.com gh issue comment <n> -R OWNER/NAME --body-file '<file>'`.
  A refusal (`relaunch` already used) means `stop the unit` was applied by
  `decision open` already.

Then the panel sequence of the reference:
`python3 '<HELPER>' judges open --question <path> --evidence <paths> --parent <card>`
(the round's `comments.md` and diff, or the builder's comment, are the
evidence; the panel's child card hangs under `<CARD>`), the dispatch of the
`judges` skill (Astra through the runner, the Claude judges through
`superegm:judge`, `judges record`, `judges diff`, round by round, from this
main conversation: a foreman never convenes the judges), and
`python3 '<HELPER>' judges verdict --panel <id> --runcard <card>`. Apply each
converged answer through its row as it converges (`decision rule … --by judges:<panel>`
posts the `**Ruling:**` comment; `review settle … --judges`; `review rule … --judges`).
An unconverged question leaves its decision pending: the batch ends as step 6
says, `report` lists it, and the owner rules by hand with `judges/<id>/verdict.json`
in front of them. Nothing here changes who updates `<base>`: the owner alone.
