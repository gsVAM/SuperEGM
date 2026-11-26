<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by SuperEGM (gsVAM), 2026: the `owner:` row of the word table and the three decision points, moved out of the wave skill's SKILL.md (the owner's ruling: a 24K skill body is context bloat); the `owner: <ids>` decision's allowed options, one per id, and its leavemealone sentence (U25); Decision point 5, a head's accept below the cap (U35); a stalled launch at point 3 and the carve-out (U31); a failed resume excluded from point 3 (U63); the `held: respec` routes to `launch` and point 3's `respec` route (U86); `decision rule` settling the point-1 finding it rules, its second line routed by the word, the refused round and the refused `redesign` (U103, 1.3 design sections 3.6 and 3.10); the foreman spec finding's row beside the `owner: <ids>` row, its one decision for the round opened at once in both modes (U104's owner-only spec findings, 1.3 design section 3.8). -->

# The decision points

Open this when a returned word (`owner:`, `contested:`, `cap-reached`, `blocked`), a batch step or a
`pending:` item names the owner's findings or a decision point. `<HELPER>`, `<CARD>`, `<U>` and
`<head-review-id>` are the wave skill's, a named row is a row of its word table, and `launch-builder` and
`review status` run as its batch does.
In leavemealone-mode each point's last line hands the question to the judge panel of
`references/leavemealone_mode.md`.

## The owner's findings

- `owner: <ids>` → `decision open` for the owner's findings: no relaunch, no slot; the inbox lists them. Write the findings (ids, claims) to a question file, each on a line of its own in the full finding-line shape `<fid> | <severity> | <location> | regression: <yes|no> | test-delta: <file>:<line> <kind>`, as the review posted it (`decision open` offers `<fid> allowed` only for an id of the word standing in the question as its own word: an id written only as `<fid>:`, `(<fid>)` or `<fid>,` gets no option, and `decision rule` refuses its `<fid> allowed` as none of the options; only when no id of the word stands as its own word do the options fall back to `finding upheld; finding overruled`; the owner's posted `<fid> allowed` finds its decision by any line starting `<fid> |` or a `## Q<n> <fid> (` heading, as Decision point 1's; only the file form below needs the full shape), and run
  `python3 '<HELPER>' decision open --unit <U> --point 1 --question '<file>' --source 'review <head-review-id> round <n>' --runcard '<CARD>'`, the option the owner's `<fid> allowed — <reason>` (point 1's `<fid> finding overruled — <reason>` is read as the same).
  The owner rules it, no judge panel, in leavemealone-mode too. `decision rule` settles the finding it rules: on `allowed` it settles it `declined` as the owner (`--disposition declined --owner`); in leavemealone-mode only the owner's comment, posted by the inbox or by hand,
  `**Ruling:** <fid> allowed — <reason>` (or `**Ruling:** <fid> finding overruled — <reason>`, read as the same) on the issue settles it, as `--disposition declined --owner --posted <comment-id>` (`decision rule` reads that comment as the settle does, before it records anything), and an allowance typed in the session there is recorded and settles nothing. Record it with `decision rule --unit <U> --decision <qid> --ruling '<fid> allowed — <reason>' --by <login> --runcard '<CARD>'`, which posts the comment
  when the owner rules in the session; on a comment the inbox posted, or one by hand, add `--posted <comment-id>` (`--decision` may then be left out). The owner's
  `**Ruling:** test-delta <file> allowed — <reason>` rules every id of that file at once: record it with `--ruling 'test-delta <file> allowed' --posted <comment-id>`; `decision rule` settles each id of that file the same way, the same file comment's id for every one.
  Record it (the separate `review settle --owner --posted` step is no longer needed, though it still works; `decision rule`'s second line, when it prints one, is the word to route by, below), then by `review status` as Decision point 1 proceeds. The owner may instead rule `<fid> finding upheld`, recorded the same way and the owner's alone; `<fid> finding upheld` below the cap is the `revise` row, the builder restoring it;
  at the cap (`review status` exit 2) it is Decision point 2 (`cap-reached`), never a relaunch.
  `decision open` prints the options `<fid> allowed`, one per id; the owner answers each id in the inbox, which posts one `**Ruling:** <fid> allowed — <reason>` comment per id (a comment written by hand on the issue still counts), or the one file comment above for every id of its file, and the decision stays pending until each id is ruled.
  A `review settle` made outside this row (the round's word not yet `owner: <ids>`) that leaves a posted round's remainder owner-only prints `owner: <ids>` and rewrites the round's outcome to it: go to this row, not by `review status`; `decision rule`'s second line is that word too, and routes the same way: `owner: <ids>` → this row, `revise` → the `revise` row, `cap-reached` → Decision point 2.
  A settle on this row's own ids keeps the word and prints none while the decision is open on the ids left; when every id left is one the owner upheld, it prints `revise` (or `cap-reached` at the cap) and rewrites the outcome to it: the `revise` row, or Decision point 2.
  In leavemealone-mode an `owner: <ids>` decision convenes no panel: the owner rules it in the inbox, which lists it until then.
- A foreman spec finding (`collect --spec`, its claim `deviation (spec) unruled: …`) is the owner's alone, never the judges', in both modes, contested or not: whenever the round holds one, whatever else blocks, the round's word is `owner: <spec fid>[, <test-delta fid>…]` (never `revise`, never `contested:`), and the round has one decision for the round, opened at once, in both modes, by this row's `decision open --point 1`; its question carries the spec finding, the round's test-delta findings and its other contests, each on a line of its own (`<fid> |` or `## Q<n> <fid> (`), and offers `finding upheld`, `finding overruled` and `<fid> respec` (one per spec fid, beside each test-delta fid's `<fid> allowed`); the owner rules each spec fid `<fid> finding upheld`, `<fid> finding overruled — <reason>` (settled `declined` as the owner) or `<fid> respec — <reason>` (the open respec file, keyed by unit, head cycle and fid; settles nothing), and the decision stays pending until each spec and test-delta fid is ruled. The builder's contest of the spec finding is never asked of the judges and is closed by the owner's ruling on the spec finding (a ruling on the contest copy settles the spec finding too); the round's other contests are still asked of the judges first, by `superegm judges question --review <head-review-id> --round <n>` (which leaves the spec finding and its contest copy out), and ruled on this one decision as Decision point 1 rules them, the decision open until each contest its question names is ruled. `review settle --judges` on a spec finding is refused (`--owner required`), and `<fid> allowed` on a spec fid is none of the options.

## The three points

### Decision point 1

The builder contested findings. Write them (ids, claims, the builder's
reasons from the round's `comments.md`) to a question file, each finding on a line of its own starting `<fid> |` or `## Q<n> <fid> (`
(the lines `decision rule` finds a fid's decision by), and run
`python3 '<HELPER>' decision open --unit <U> --point 1 --question '<file>' --source 'review <head-review-id> round <n>' --runcard '<CARD>'`
(options `finding upheld; finding overruled`). A contested or declined high or medium finding goes to the
judges first in both modes (`superegm judges question --review <head-review-id> --round <n>`, then the panel sequence of
`skills/judges/references/leavemealone.md`; its evidence the round's `comments.md`, the diff, the unit's body,
`r<n>/spec_range.md` and `r<n>/amendments.md`); a converged ruling follows `leavemealone.md`:
only `finding overruled` settles through `review settle --judges <panel>` (journalled `Ruling (judges <panel>, contest)` in normal mode); on a normal-mode card `decision rule --by judges:<panel>` settles it the same way, as `judges:<panel>`, but in leavemealone-mode it settles nothing (a ruling typed in the session is recorded alone): there the `review settle --judges <panel>` call of `leavemealone.md` is the settle; `finding upheld` and `redesign` go through `decision rule --by judges:<panel>` alone. Only a panel that does not
converge goes to the owner, as does a round `judges question` refuses (the refused round: a low or the CI finding stands beside the contest, so no panel rules it) and a `redesign` the panel converged on that `decision rule` refuses (the refused `redesign`: one with no high finding behind it): ask point 1's question, one question per finding, the builder's reason verbatim as the overrule
option's text, with the line naming `judges/<panel>/verdict.json` and each judge's last choice (the panel's
`owner-question.md`). The owner alone rules `<fid> allowed`, `amend`, `respec` and the CI finding, in both modes: the
judges never settle them (the owner's form on the CI finding is `<fid> finding upheld`: an overrule of it is refused `the CI finding is settled by no one`), and a spec, plan or integrate review's contest is the owner's, asked as before. Record each ruling with
`python3 '<HELPER>' decision rule --unit <U> --decision <qid> --ruling '<fid> finding upheld' --by <login> --runcard '<CARD>'`
or `--ruling '<fid> finding overruled — <reason>'` (the fid first, else `missing <fid>: write "<fid> finding overruled"`), which posts the
`**Ruling:**` comment on the issue. `decision rule` settles the finding it rules: an overrule is settled `contested`, as the owner (typed, or `--posted`; in leavemealone-mode only by `--posted`) or, on a normal-mode card, as `judges:<panel>` for the panel's own, once `review settle`'s own checks of the ruler have run (a ruling they refuse is neither posted nor recorded), so no `review settle` follows (the separate `review settle --owner --posted` step still works); in leavemealone-mode the panel's overrule is settled by `review settle --judges <panel>` alone, and a `decision rule` typed there settles nothing; an uphold is recorded and leaves the finding for the builder to fix. `decision rule`'s second line, when it prints one, is the round's rewritten word: `owner: <ids>` → the owner row, `revise` → the `revise` row, `cap-reached` → Decision point 2; with none, by `review status`: 0 → the unit
awaits merge; 2 → Decision point 2; in normal mode `acceptable: yes` → Decision point 5; else `launch-builder`. For a `held: respec` unit, step 6's `launch`.
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

The head review is at its cap. The cap is `review.rounds` (default 3; the approval froze the spec's `Rounds:` line, else the live value, for this handoff), then PAUSE for the owner.
Write the `review status` trend line to a question file and run
`python3 '<HELPER>' decision open --unit <U> --point 2 --question '<file>' --source 'review <head-review-id> cap' --runcard '<CARD>'`
(options `one more round; stop`, and on a head `redesign — <one sentence why>`; once `one more round` is spent,
`judges question --review <head-review-id> --cap` asks `stop` and `redesign` alone). `one more round` (once per unit):
`python3 '<HELPER>' review rule --review <head-review-id> --ruling continue --owner --runcard '<CARD>'`,
then `decision rule … --ruling 'one more round'`, then `launch-builder` (a `held: respec` unit: step 6's `launch`).
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
`stop the unit`; `relaunch; stop the unit` for an exit with no PR, an interrupted or a stalled launch, a builder's close, or a third blocked comment on one
head; or `ruled: stop the unit (relaunch already used)` or `ruled: stop the unit (second launch with no commit of its own)`, already applied.
A stalled launch's question carries the stall facts (the event line `U<n> stalled (<minutes> min; last commit <time | none>)`, source `launch <n>`); leavemealone's panel renders it `<U> launch <n> stalled (last commit <time | none>)`.
A stopped unit's stall is recorded and asks nothing: the kill is the one thing left to do.
A launch with no commit of its own (an `exited …` entry whose `last_commit_at` is absent or none, a launch recorded before U31 included) spends no `relaunch`; a second such launch on the unit is `stop the unit`, with no question.
A failed resume (`record-launch` printed `failed resume`, the entry `failed_resume: true`) is not a launch without a commit and opens no question here: the batch's step 3 relaunches it at once, fresh.
Ask the owner, then
`python3 '<HELPER>' decision rule --unit <U> --decision <qid> --ruling '(<letter>) — <reason>' --by <login> --runcard '<CARD>'`
(it posts `**Ruling:** (<comment-id>) <option> — <reason>` quoting the
question; the next launch's prompt carries it). `relaunch` →
`launch-builder` now (a `held: respec` unit: step 6's `launch`; `respec` → nothing until its approval); `stop the unit` → the unit is labelled and never
relaunched.
Leavemealone-mode: U11 wires §13.2 here.

### Decision point 5

A head's round below the cap that the owner may accept: the foreman returned `revise` and `review status`
printed `acceptable: yes (<n> medium, <m> low)` (unsettled mediums and lows alone). Write that line and the
findings to a question file and run
`python3 '<HELPER>' decision open --point 5 --unit <U> --question '<file>' --source 'review <head-review-id> round <n>' --runcard '<CARD>'`
(options `accept; revise`). The unit is pending, so no launch follows; the inbox and the board list it by its `point`.
Ask the owner, then
`python3 '<HELPER>' decision rule --unit <U> --decision <qid> --ruling 'accept — <reason>' --by <login> --runcard '<CARD>'`
or `--ruling 'revise — <reason>'` (it posts `**Ruling:** (<qid>) <option> — <reason>`; an owner's comment in that
form rules it with `--posted <comment-id>`). `accept` converges the head review by ruling: the round is `clean` and the
unit awaits merge. A refused accept (`review rule: accept refused: <blockers>`) records nothing: ask again with `revise`.
An accept on a pull request whose head moved since the round is refused `review rule: the reviewed head moved: revise`;
on a rerun after a failed post it first withdraws the accept it gave (journaled `review <id> R<n> accept lapsed`, the
round's word `revise`), the decision staying pending: rule it `revise`.
`revise` is the round's own word: `launch-builder` as the `revise` row does (a `held: respec` unit: step 6's `launch`); it spends no point-3 relaunch.
The owner's alone (`--by judges:<id>` is refused): in leavemealone-mode no point 5 opens and no head is accepted early.
