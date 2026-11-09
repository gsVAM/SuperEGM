<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by SuperEGM (gsVAM), 2026: the wave skill's stops and by-hand rulings, moved out of the wave skill's SKILL.md (the owner's ruling: a 24K skill body is context bloat). -->

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
  `--ruling 'test-delta <file> allowed'` (any other text is refused); each id
  it allows is then settled `review settle … --disposition declined --owner
  --posted <comment id>`, never `contested`, as the `owner: <ids>` row under
  `## The owner's findings` of `references/decision_points.md` says. The
  same `test-delta <file> allowed` also rules an open decision on a contest's
  copy (`contested <fid>: …`) of a `test-delta:` finding of that file, recorded
  there as `<copy fid> finding overruled` and settled as `finding overruled`
  is below. Only on
  exit 0 continue as that point's section does. Point 1: `finding overruled`
  → `review settle … --disposition contested --owner --posted <comment id>`;
  then, for `finding upheld` too, by `review status`: 0 → the unit awaits
  merge; 2 → Decision point 2; else `launch-builder`. Point 2 (the head at
  its cap; a spent `one more round` is refused before anything is recorded):
  `one more round` → `review rule … --ruling continue --owner`, then
  `launch-builder`; `stop` or `redesign` → `review rule … --ruling stop --owner`
  (a `redesign` at point 1 runs no `review rule`). Point 3: `relaunch`, or an
  option on a `BLOCKED` comment → `launch-builder` now, as for any option on a
  `BLOCKED` or `NEEDS_CONTEXT` comment; `stop the unit` stops it. An `allowed`
  ruling refused with `no open decision names it` needs nothing more: `collect` reads a prior round's
  `tdd-order` one, the owner's `dod-<n> allowed`, a `<fid> allowed` on a posted
  `test-delta:` fid and a `test-delta <file> allowed` itself.
  Nothing is posted; the journal says `ruling edited after record, ignored`
  for a recorded comment re-read, and `ruling dropped (<by>, comment <id>): …`
  for one naming no open decision or an already ruled one, or a refused allowance (not one refused with `no open decision names it`); take either as the fact it states, and
  run nothing else for it. For a run stopped between a record and its continuation, the
  journal's `Ruling (…)` line with no continuation after it is the step to finish.
- A stopped unit keeps its branch and its open issue, is never dispatched or
  launched again, and is listed in the report with its unlanded dependants
  for the owner (design section 12).
