<!-- Copyright 2026 Google LLC. SPDX-License-Identifier: Apache-2.0. -->
<!-- Modified by the elephant-goldfish-model Astra fork (gsVAM), 2026: run card on the report, persisted dispositions per stage and round. -->
<!-- Modified by SuperEGM (gsVAM), 2026: EGM's resolve skill rewritten as the settle step of the one review loop: the four categories are the five dispositions, written with `superegm review settle`; the report files are gone, the store is the record (spec section 8). -->

# Resolve: settle a round's findings

Run between rounds, in the conversation that produced the artifact (the elephant), on every
finding of the round just recorded. The round file,
`<artifacts_dir>/reviews/<id>/round-<n>.json`, holds every reviewer's findings with their ids;
nothing is written anywhere else: no report file, no dispositions file. The store is the
record, and `superegm review status` reads it.

## 1. Read

Read the artifact and the round file. For each finding, the id, severity, location,
`regression: yes|no` and claim are the goldfish's; you decide the disposition and nothing
else.

## 2. Decide

Give each finding exactly one disposition:

- **fixed**: the critique is valid. Change the artifact: a precise replacement, a deletion, a
  narrowed contract. The next round reviews the new bytes; a later goldfish that raises the same
  defect at the same scope marks it `regression: yes`, so a fix that moved the defect does not
  converge.
- **contested**: the critique is inaccurate or rests on a misunderstanding. Cite evidence the
  reviewer could read: a file and symbol, or a decision recorded in the artifact. For a high or
  medium this is a decision point (section 4).
- **declined**: a low you will not fix (record it; fix it anyway when the fix is worth it), or a
  high or medium the owner or the judges decline (section 4).
- **escalated**: the critique may be right but the evidence is outside every file the reviewer
  could read (a team convention, a verbal decision), or it belongs to someone else: a new unit, or
  a decision point of the plan. State the fact, do not fix it here, and name where it went. It
  is settled.
- **fix-design**: the defect is in the frozen spec, not in this artifact (a plan or integrate
  review). Never worked around; refused on a head. `review status` exits 4 and the skill runs
  `superegm approve-spec --spec <path> --void --review <id>`: the spec returns to spec review.

Apply these rules:

- **A contest must be checkable.** "This was intentional" is not evidence. If you cannot cite
  evidence the reviewer could read, settle it `escalated` or fix it.
- **Do not add context only to satisfy a reviewer.** Add context when a human reader of the
  document needs it. If only a zero-context subagent needs it, settle it `escalated`.
- **Do not contest a comprehension gap.** If a fresh reader could not follow the document, the
  document is missing context.
- **Do not change a severity.** If you think a high is a low, contest it and state the reason.
- You wrote the artifact under review. A wish to contest is not evidence that the reviewer is
  wrong.
- The `foreman` finding that records CI not green on a head is settled by no one: `collect`
  records it afresh each round from the CI file and omits it when CI is green; `superegm review
  settle` refuses it.

## 3. Write

Apply the fixes to the artifact first, then write every disposition:

    superegm review settle --review <id> --finding <fid> --disposition fixed|contested|declined|escalated|fix-design --runcard <id> [--owner | --judges <judges-id>]

The helper prints `<fid> <disposition>`, stores it on the finding with who ruled (`owner`,
`judges:<id>`, or nothing), and re-derives the review's convergence. A finding in any recorded
round settles, whether or not its round was `completed`; a finding settled once stays settled
when a later goldfish raises it again at the same scope, unless it was `fixed` (then it is a
regression, section 2).

## 4. The one gate: a high or medium contested or declined

A high or medium finding is overruled by nobody but the owner or the judges (spec section
13.2, point 1). The helper refuses `contested` and `declined` on such a finding without
`--owner` in normal mode and without `--judges <id>` in leavemealone-mode; a low needs neither.

- **Normal mode**: after the fixes, put every high and medium you want to contest or decline to
  the owner in one question, one per round: the finding line, your reason, and the options
  `finding upheld` and `finding overruled` (your reason verbatim as the overrule option's
  text). Then write each answer: overruled, `--disposition contested --owner` (or `declined
  --owner`); upheld, leave it unsettled and fix it in this round, or settle it `escalated` when
  it is not yours to fix.
- **Leavemealone-mode** (`--leavemealone` or `config.mode`): render the same question from the
  record with `superegm judges question --review <id> --round <n> --reason <fid>=<your
  reason>…`, open the panel with `superegm judges open --parent <your run card>`, dispatch the
  judges as the `judges` skill says, and apply each converged answer with `--disposition
  contested --judges <panel-id>` (or `declined`); an unconverged question pauses the owner with
  the record. A ruling that overrules a finding settles it `contested`; one that upholds it
  leaves it unsettled for you to fix.
- On a head, a builder's `contested` reply reaches the same gate through `collect`'s
  `builder_contested[]`; `collect` carries an upheld finding forward as a `foreman` high until a
  later builder reply marks it `fixed`.

## 5. Then

`superegm review status --review <id> --runcard <id>`: the exit code says whether the artifact
converged, needs another round, is at its cap, voids the approval or stalled
(`references/review_loop.md` section 5). Converging at round 2 is the normal case. When counts
stop falling, change the thing, not the round.
