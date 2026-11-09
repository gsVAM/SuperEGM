<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by SuperEGM (gsVAM), 2026: the `owner:` row of the word table and the three decision points, moved out of the wave skill's SKILL.md (the owner's ruling: a 24K skill body is context bloat); Decision point 5, a head's accept below the cap (U35). -->

# The decision points

Open this when a returned word (`owner:`, `contested:`, `cap-reached`, `blocked`), a batch step or a
`pending:` item names the owner's findings or a decision point. `<HELPER>`, `<CARD>`, `<U>` and
`<head-review-id>` are the wave skill's, a named row is a row of its word table, and `launch-builder` and
`review status` run as its batch does.
In leavemealone-mode each point's last line hands the question to the judge panel of
`references/leavemealone_mode.md`.

## The owner's findings

- `owner: <ids>` → `decision open` for the owner's findings: no relaunch, no slot; the inbox lists them. Write the findings (ids, claims) to a question file and run
  `python3 '<HELPER>' decision open --unit <U> --point 1 --question '<file>' --source 'review <head-review-id> round <n>' --runcard '<CARD>'`, the option the owner's `<fid> allowed — <reason>` (point 1's `<fid> finding overruled — <reason>` is read as the same).
  The owner rules it, no judge panel, in leavemealone-mode too. On `allowed` run
  `python3 '<HELPER>' review settle --review <head-review-id> --finding <fid> --disposition declined --owner --runcard '<CARD>'`; in leavemealone-mode only the owner's by-hand comment
  `**Ruling:** <fid> finding overruled — <reason>` on the issue settles it, with `--disposition declined --owner --posted <comment-id>`. Record it with `decision rule … --ruling '<fid> finding overruled — <reason>' --by <login>`,
  then by `review status` as Decision point 1 proceeds. `<fid> finding upheld` below the cap is the `revise` row;
  at the cap (`review status` exit 2) it is Decision point 2 (`cap-reached`), never a relaunch.

## The three points

### Decision point 1

The builder contested findings. Write them (ids, claims, the builder's
reasons from the round's `comments.md`) to a question file, each finding on a line of its own starting `<fid> |` or `## Q<n> <fid> (`
(the lines `decision rule` finds a fid's decision by), and run
`python3 '<HELPER>' decision open --unit <U> --point 1 --question '<file>' --source 'review <head-review-id> round <n>' --runcard '<CARD>'`
(options `finding upheld; finding overruled`). In normal mode ask the owner,
one question per finding, the builder's reason verbatim as the overrule
option's text. Apply each ruling: per overruled finding
`python3 '<HELPER>' review settle --review <head-review-id> --finding <fid> --disposition contested --owner --runcard '<CARD>'`,
then `review status`; record it with
`python3 '<HELPER>' decision rule --unit <U> --decision <qid> --ruling '<fid> finding upheld' --by <login> --runcard '<CARD>'`
or `--ruling '<fid> finding overruled — <reason>'`, which posts the
`**Ruling:**` comment on the issue. Then by `review status`: 0 → the unit
awaits merge; 2 → Decision point 2; in normal mode `acceptable: yes` → Decision point 5; else `launch-builder`.
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
`revise` is the round's own word: `launch-builder` as the `revise` row does; it spends no point-3 relaunch.
The owner's alone (`--by judges:<id>` is refused): in leavemealone-mode no point 5 opens and no head is accepted early.
