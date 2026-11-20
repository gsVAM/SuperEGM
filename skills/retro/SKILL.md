---
name: retro
license: Apache-2.0
effects: external
effect_kinds: [state-store]
disable-model-invocation: true
description: Walks a closed handoff's post-mortem Lessons with the owner, lands the agreed edits in one commit and records the retrospective.
---

<!-- Added by SuperEGM (gsVAM), 2026: the retro skill (spec section 7.7) (U87). -->

# Retro

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

    /superegm:retro [--handoff <id>]

The retrospective of a handoff that has closed: the post-mortem says what happened, this skill turns what the owner
agrees into edits. `--handoff <id>` names the handoff; by default it is the latest closed handoff: the one whose `handoffs/<id>.json`
(`{"id", "spec", "opened_at", "closed_at"}`) holds the latest non-null `closed_at`, skipping a voided close (a handoff whose
`journal.md` records `closed <id> at <closed_at>` followed by `(closed: voided)` filed no unit and has no Lessons). Integrate offers the
retrospective once, after the post-mortem; typed later, it runs the same way. `superegm` below stands for
`python3 '${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py'`, one Bash call per command, run from the target
repository, absolute paths in single quotes, nothing chained.

The store is `artifacts_dir` in `.superegm/config.json`; the handoff's directory, `<handoff dir>` below, is
`<artifacts_dir>/<handoff id>/`, and `handoffs/<id>.json` and `approvals/<spec-slug>.json` sit directly in `<artifacts_dir>`.

## Step 1: read the Lessons

1. Read `<handoff dir>/postmortem.md`; when it is missing, `superegm postmortem --handoff <id>` writes it first
   (`postmortem.md` is the helper's write, not this skill's).
2. Its Lessons table is the agenda: one fact row per respec, `fix-design` finding, interface amendment, silent or most
   overruled reviewer, escalated or capped unit and decision answered by default, each naming its source record. The
   rows are facts and propose nothing; the proposals are this skill's, and the owner's to accept.

## Step 2: the Q&A

Work through the Lessons **one question at a time**, in the brainstorm's manner: for each lesson, what caused it and what
would have prevented it. Every question is led by its **suggested answer**, the cause and the prevention the records
point to, so the owner may agree in a word. Ask only where the cause is not plain from the records; a row whose fix is
obvious gets a proposed edit and no question. The owner may stop at any point; what was agreed so far still lands.

## Step 3: the edits

Each agreed cause becomes one proposed edit to one of four targets:

- a **reference document** under the configured `dir`: an invariant, an architecture fact, a rule specs must state
  (for example a `lessons.md` of spec patterns that needed a respec);
- a **reviewer file**: a new custom reviewer, or a reworded prompt for one that missed or over-raised;
- `.superegm/config.json`: `review.rounds`, `units.*`, `reviewers.<kind>`, `mode`, `driver.chain`;
- `.superegm/brainstorm.md`, committed: questions to ask in every brainstorm, which the brainstorm reads at its start
  (not the per-decision brief the brief lookup reads).

Show each edit as a diff. The owner accepts, changes or drops it; nothing is applied without the owner's yes, one yes per
edit. A respec's root cause in the spec text itself is for the next spec: this skill never edits the approved spec of
any handoff, and a finished spec is not edited by the retrospective.

**Live and frozen keys.** A config key is either live or frozen, and the skill says which before it asks for the yes:

- a live key (`driver.chain`, `units.*` read by `graph`, `reviewers.<kind>` for a review not yet opened): name
  every open handoff (each `handoffs/<id>.json` whose `closed_at` is null; a legacy flat-store handoff, the one `state.json`
  at the root of `<artifacts_dir>` holds, has no such file until it closes and counts while that `state.json` has no
  `closed_at`) and say the edit applies to it at once;
- a frozen key (`mode`, `review.rounds`, which an approval freezes): read each open handoff's approval, the entries of
  `approvals/<spec-slug>.json` that carry its `handoff_id`, fields `mode` and `rounds`. One whose
  approval froze the key keeps it; one whose approval has no frozen value (an approval before 1.2.1, which falls back to
  the live `config.mode`) is named as changed at once.

Reference documents, reviewer files and `.superegm/brainstorm.md` are frozen by the next spec's approval and read by the
next brainstorm: say so.

## Step 4: one commit and `retro.md`

1. Land the accepted edits in one commit `retro: <handoff>` on the current branch: stage the edited files by name and
   commit them together; with no accepted edit there is no commit.
2. Write `retro.md` to a scratch file, listing each lesson, its cause and what was done (`dropped` for an edit the
   owner declined, `no edit` for a lesson with none), then copy it into the store:

        superegm postmortem --handoff <id> --retro <file>

   which writes `<handoff dir>/retro.md` and needs no run card.
3. Tell the owner the commit and the path of `retro.md`.

## What it never does

It applies nothing without the owner's yes, writes nothing to the store but `retro.md`, never pushes, and never edits
the approved spec of any handoff.
