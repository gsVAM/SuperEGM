<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by SuperEGM (gsVAM), 2026: the wave skill's stops and by-hand rulings, moved out of the wave skill's SKILL.md (the owner's ruling: a 24K skill body is context bloat); `decision rule` settling the point-1 finding it rules, its second line, the missing-fid, CI-finding and edited-comment refusals (U103, 1.3 design sections 3.6 and 3.7); U107's head proceed `<sha7>` forms, posted and typed, and the undo refused while a proceed's merge is offered (U107, 1.3 design section 3.9). -->


# Rulings by comment, and stops

Open this for a `ruling` line (a batch's step 4, or the entry's step 2), for an owner's `**Ruling:**`
already posted on an issue before a `pending:` item is asked (entry step 4), and for a stop. "That
point's section" below is the point's section of `references/decision_points.md`.

## Stops and by-hand rulings

- The owner's close (batch step 2) is `stop` without a question:
  `decision rule --posted closed:<n>` records nothing but the stop.
- `ruling` lines (`U<n> ruling by <login>: <kind> <subject> (comment <id>)`):
  an owner's `**Ruling:**` comment in one of the forms (a `config.owners`
  author, the form exact, else it is text). First run
  `python3 '<HELPER>' decision rule --unit <U> --ruling '<its option>' --by <login> --posted <comment-id> --runcard '<CARD>'`
  with no `--decision`: the comment names its decision (`redesign` every
  pending one), and a `--ruling` other than the comment's is refused.
  `--ruling` is the event's words as the point's form: `<fid> finding upheld`
  or `<fid> finding overruled`, `one more round`, `stop`, the option's letter
  `(<x>)`, `redesign` as `--ruling 'redesign'` (the reason is the comment's);
  an `allowed` ruling as for an open decision,
  `<fid> allowed` as `--ruling '<fid> finding overruled'`, though
  in leavemealone-mode an allowance naming an open decision is refused (its
  `review settle --posted` reads only `<fid> finding overruled — <reason>`,
  the form the journal's dropped line names for the owner), except on an
  `owner: <ids>` decision, whose options are `<fid> allowed`: there it is
  `--ruling '<fid> allowed'`, and `test-delta <file> allowed` is
  `--ruling 'test-delta <file> allowed'` (any other text is refused). `decision rule` settles the finding it rules, so
  no `review settle` follows a point-1 ruling (the separate `review settle --owner --posted` step still works):
  each id an allowance rules is settled `declined`, never `contested`, as the `owner: <ids>` row under
  `## The owner's findings` of `references/decision_points.md` says, and an overrule on a contest decision
  `contested`, by the owner or, as `--by judges:<panel>`, by the panel, once `review settle`'s own checks of the
  ruler have run, before anything is posted or recorded: a ruling they refuse is neither (a failed GitHub
  read is one `gh: <error>` line, nothing recorded, the same call rerun). The
  same `test-delta <file> allowed` also rules an open decision on a contest's
  copy (`contested <fid>: …`) of a `test-delta:` finding of that file, recorded
  there as `<copy fid> finding overruled` and settled `contested`. A point-1 ruling names its fid first: a ruling
  that opens with the verdict is refused `missing <fid>: write "<fid> finding overruled"`; an overrule of the CI
  finding is refused `the CI finding is settled by no one` (the owner's form on the CI finding, `<fid> finding upheld`,
  is the one that rules it); a posted ruling comment edited before its first record, a
  `review rule --ruling proceed --owner --posted` one too, is refused `ruling comment edited: post a new one`:
  the owner posts a new one. In leavemealone-mode a ruling typed in the session (no `--posted`) is recorded and
  settles nothing: only the owner's posted comment does. Only on
  exit 0 continue as that point's section does. Point 1: `decision rule`'s second line, when it prints one, is the
  round's rewritten word (`owner: <ids>`, `revise` or `cap-reached`), which routes as the word table does: the owner row,
  the `revise` row or Decision point 2; with none,
  then, for `finding upheld` too, by `review status`: 0 → the unit awaits
  merge; 2 → Decision point 2; in normal mode `acceptable: yes` → Decision point 5; else `launch-builder`. Point 2 (the head at
  its cap; a spent `one more round` is refused before anything is recorded):
  `one more round` → `review rule … --ruling continue --owner`, then
  `launch-builder`; `stop` or `redesign` → `review rule … --ruling stop --owner`
  (a `redesign` at point 1 runs no `review rule`). Point 3: `relaunch`, or an
  option on a `BLOCKED` comment → `launch-builder` now, as for any option on a
  `BLOCKED` or `NEEDS_CONTEXT` comment; `respec` → nothing until `approve-spec --respec R<n>` applies it;
  `stop the unit` stops it. Every `launch-builder` here, a `held: respec` unit: step 6's `launch`. An `allowed`
  ruling refused with `no open decision names it` needs nothing more: `collect` reads a prior round's
  `tdd-order` one, the owner's `dod-<n> allowed`, a `<fid> allowed` on a posted
  `test-delta:` fid and a `test-delta <file> allowed` itself.
  Nothing is posted; the journal says `ruling edited after record, ignored`
  for a recorded comment re-read, and `ruling dropped (<by>, comment <id>): …`
  for one naming no open decision or an already ruled one, or a refused allowance (not one refused with `no open decision names it`); take either as the fact it states, and
  run nothing else for it. For a run stopped between a record and its continuation, the
  journal's `Ruling (…)` line with no continuation after it is the step to finish.
  A point-1 `decision rule` stopped after its `Ruling (…)` line and before its settle leaves the finding it
  overruled or allowed unsettled, and its rerun is refused as already ruled: finish it with `review settle`
  on that finding, its disposition the one `decision rule` gives (`contested`, or `declined` on an `owner: <ids>`
  decision) and its ruler the ruling's (the owner, with the ruling comment's `--posted <comment-id>` in
  leavemealone-mode, or `--judges <panel>`), then route by the word it prints, as `decision rule`'s second line.
- The undo of triage (design section 5.2): `**Ruling:** <fid> finding upheld`
  naming a fid of the unit's `followups[]` (a medium triage took off the blocking list, the
  inbox's undo) is the same `decision rule --unit <U> --ruling '<fid> finding upheld' --by <login>
  --posted <comment id>` with no `--decision`, and no decision: it is checked as the undo
  before any point-1 decision is looked for, so it never binds to an older one. On exit 0
  (`recorded (comment <id>): undo <fid>`) nothing else runs: no dispatch, no `collect`, no
  `review settle`; the finding is unsettled again, the follow-up row is gone, the latest
  posted `clean` reads `revise` (`cap-reached` at the cap), an accept given on the round
  has lapsed, and triage is off for the unit's remaining rounds; the next wave session
  sends the unit to revision or to the cap decision. Refused (a fid of an earlier
  round, a stopped unit, a proceed whose merge is still offered, a merged or closed pull
  request), the follow-up row stays for the
  owner to file as follow-up work, and the comment never blocks a round.
- A proceed (design section 4.2): the owner's `**Ruling:** proceed <sha7> — <reason>` on a
  unit's issue, `<sha7>` the head the owner was shown, ends the unit's head review whatever its
  state. Run
  `python3 '<HELPER>' review rule --ruling proceed --owner --posted <cid> --review <rid> --runcard '<CARD>'`,
  `<cid>` the comment's id and `<rid>` the unit's head review, never `decision rule`; typed in
  a session, the same proceed is
  `python3 '<HELPER>' review rule --ruling proceed --head <sha7> --owner --reason <text> --review <rid> --runcard '<CARD>'`
  (a spec or plan review takes `--reason` alone). It checks the comment (an owner's, of the
  proceed form, on the unit's issue), pins the head `<sha7>` names, settles every unsettled
  finding of the cycle `declined` by the owner and records `foreman.proceeds[]`; replayed
  for the same comment, review and head it writes nothing (a proceed recorded before 1.3 in
  the bare form too: it keeps its pinned head). Refused (`--judges`, a stopped unit,
  `comment <cid> already ruled`: a later head needs a new comment; the unit's head moved since
  `<sha7>`: the owner proceeds again on the new head; no head at all:
  `proceed needs the head: write "proceed <sha7> — <reason>"`), it writes nothing.
- A stopped unit keeps its branch and its open issue, is never dispatched or
  launched again, and is listed in the report with its unlanded dependants
  for the owner (design section 12).
