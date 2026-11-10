<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by SuperEGM (gsVAM), 2026: the wave skill's leavemealone-mode wiring, moved out of the wave skill's SKILL.md (the owner's ruling: a 24K skill body is context bloat); the owner's-alone sentence (U23); the driver role's no-ask clauses (U24); the `launch <n>` question after its decision, a stalled launch's (U31). -->

# Leavemealone-mode

In leavemealone-mode (`--leavemealone` on the invocation, or `config.mode`,
recorded on the card at Entry step 1) the three `Leavemealone-mode: U11 wires
§13.2 here.` lines of `references/decision_points.md` are the entry points (`<card>` below is `<CARD>`): at
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
  for an exit with no PR, an interrupted or a stalled launch (after `decision open`: it renders that decision's options), and
  `python3 '<HELPER>' judges question --unit <U> --blocked closed <n> --runcard <card>`
  for a close by the builder account. Its second line, `consumers: #<n> …`,
  appears for an `interface` deviation: the ruling is also posted as the same
  `**Ruling:**` comment on every `consumers:` issue, with
  `GH_HOST=github.com gh issue comment <n> -R OWNER/NAME --body-file '<file>'`.
  A `ruled: stop the unit (…)` from `decision open` needs no panel: it is applied already.

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
An unconverged question leaves its decision pending: the batch ends as its step 7
says (under SUPEREGM_ROLE=driver it goes on, the unit `pending a decision`), `report` lists it, and the owner rules by hand with `judges/<id>/verdict.json`
in front of them. A judges' `redesign` refused, a pending decision whose panel answered is the owner's alone
(`judges/<panel>/verdict.json` converged on it): ask the owner (under SUPEREGM_ROLE=driver an inbox line, never a question), never the panel again. Nothing here changes who updates `<base>`: the owner alone.
