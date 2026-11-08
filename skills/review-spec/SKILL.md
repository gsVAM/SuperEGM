---
name: review-spec
license: Apache-2.0
effects: external
effect_kinds: [state-store, start-session, github-write, remote-branch]
disable-model-invocation: true
description: >-
  Orchestrates the EGM Goldfish Review Protocol. Used as part of the EGM
  process to perform design document reviews. Executes five review phases:
  Initial Zoom Out Review, Comprehension Review, Design Critique, Intermediate
  Zoom Out Review, and Implementation Readiness.
---

<!-- Modified by SuperEGM (gsVAM), 2026: renamed to review-spec; the body is spec section 8's one review loop over the helper (the stages, presets, semantic split, checkpoint gates and report files are gone); persona path agents/zoom-out.md; the amendment scope, the branch sentence and the batch settle (U19); the spec PR, the pushes and the PR's ingest (U26). -->

<!-- Modified by the elephant-goldfish-model Astra fork (gsVAM), 2026: run card, panel presets, Astra lane. -->

# Spec review (phase 1)

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

    /superegm:review-spec <spec-path> [--reviewers design,zoom-out,…] [--astra on|off] [--leavemealone] [--scope auto|whole|<sections>]

Reviews a spec through fresh-context goldfish reviewers until it converges, then records the
owner's approval, which freezes the spec at its sha256 for the plan. One loop, one convergence
rule, one cap: the helper judges, you dispatch. The helper is
`python3 '${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py'`, run from the target
repository; every writing subcommand takes `--runcard <id>`.

## Delegation

A goldfish runs in a fresh context with no conversation history. Dispatch each reviewer with
the Agent tool through its own adapter, `superegm:<id>` (`.claude-plugin/agents/<id>.md`, which
sets `omitClaudeMd: true` and the read-only tools; the persona is `agents/<id>.md`, for example
`agents/design.md` and `agents/zoom-out.md`). Pass the brief verbatim and wait for the report.
A reviewer spawned any other way is not a goldfish. If your harness has no subagent tool, stop
and tell the owner: a review in the same context is not a goldfish review.

## Constraints

1. **Artifact-first.** Findings live in the store, dispositions in the round files. Do not
   paste reports into chat; name the review id and the `superegm review status` line.
2. **One question per turn.** Every gate (a structured question tool when the harness has one,
   else plain chat) carries exactly one question, is the sole tool call of its turn, and offers
   plain options without a `(Recommended)` prefix.
3. **Plain English, no flattery, no apologies.** Lead with what is wrong. The owner's spec is
   under test; agreement is earned by a clean round, not given.
4. **Never dispatch the goldfish yourself as reviewers of your own fixes in the same turn** you
   made them: record, settle, ask `review status`, then the next round.

## Workflow

### 1. Preflight

First: start on the branch you want the commits on. Your fixes and `approve-spec`'s approval
commit land on the checkout's current branch; this skill never switches branches or adds a
worktree in the owner's checkout.

1. `TargetFile` is `<spec-path>`, a committed or uncommitted spec under `docs/specs/` whose
   last H2 (after any numeric prefix) is `Units`. If it is missing, ask for the path in plain
   chat (an open-ended input, not a choice) and end the turn.
2. If `.superegm/config.json` is missing, run `superegm init` first: it writes the config with
   every key and prints the owner's by-hand steps (the builder account and profile, the branch
   protection). Do them later; the review does not need them.

   Then the spec PR, the elephant's own (spec section 8): refuse on `<base>` (`config.base`; start on a branch) before any commit, push or PR, and end the turn. Otherwise, with `<spec-path>` relative to the repository root:

       git add -- <spec-path>
       git commit --allow-empty -m "superegm: review <spec-slug>" -- <spec-path>
       git push -u origin <branch>
       gh pr list --head <branch> --state open --json number

   When the list is empty, open the PR ready for review, never `--draft` (a bot may skip drafts):
   `gh pr create --head <branch> --base <base> --title "<the spec's H1>" --body "<spec-path>"`.
   `<branch>` is the current branch; `<n>` below is the number of the PR the list found or the one just created.
3. Open the run card: `superegm runcard open --skill review-spec --artifact <spec-path>`, with
   `--mode leavemealone` when the invocation said `--leavemealone`. The id goes on every helper
   call below; a card of an earlier invocation on the same spec is marked interrupted.
4. The panel is `config.reviewers.spec` unless the invocation gave `--reviewers`;
   `design` is first, one to six ids. The Astra lane runs when `config.astra.enabled` is true (or
   `--astra on`) and the preflight of `resources/astra_lane.md` section 1 passes; otherwise
   `--astra off`, said in one line.
5. Show the run card (`references/review_loop.md` section 7): model and effort per role,
   requested and effective, the panel, and whether the Astra lane runs. In normal mode, ask the
   owner once whether to start; in leavemealone-mode, start.

### 2. Open

    superegm review open --kind spec --artifact <spec-path> --reviewers <panel> [--astra on|off] [--scope auto|whole|<sections>] --runcard <id>

The id is `spec-<spec-slug>-c<n>`. A cycle still open from an earlier invocation is resumed
with its stored panel and scope form; a closed one (`accept`, `stop`, or a spec edited after the
approval that names it) starts the next cycle with a fresh cap.

`--scope` is the invocation's, default `auto`: an amendment is reviewed in scope, the sections
changed since the last approval and their neighbours, re-derived every round; with no approval
the whole spec. `whole` forces a full review. A list names headings verbatim, separated by `;`,
added to `auto`'s scope without neighbours (`(preamble)` names the text above the first `##`),
and is refused with no approval (`--scope <list>: no approval: use whole`) or when a heading is
not one of the spec's `##` or `###` headings now (`--scope: <heading> is not in the spec`).

### 3. The loop

Run the loop exactly as `references/review_loop.md` says. Before each round's dispatch, ask the
helper for the round's scope:

    superegm review scope --review <id> --runcard <id>

and put the lines it prints in every goldfish's brief with the scope sentence of
`references/review_loop.md` section 2. Then the whole panel concurrently through the adapters,
the Astra lane alongside when it is on, every reviewer recorded with `superegm review record`
(an empty file is a record; one retry, then `--not-run`). A finding citing a line outside the
scope is out of scope: the helper refuses it, keeps it in the round's `out_of_scope[]`, and you
neither fix nor settle it. Between rounds, `references/resolve.md`: fix the spec, write the
round's dispositions in one call (one `<fid> | <disposition> | <note>` per line; a refused line
writes nothing and is named),

    superegm review settle --review <id> --file <dispositions> [--owner | --judges <judges-id>] --runcard <id>

and put every high or medium you contest or decline to the owner in one question (normal mode)
or to the judges (leavemealone-mode). After the dispositions, commit the fix by path and push it, so a PR reviewer reads every round's bytes, then ingest the PR:

    git add -- <spec-path>
    git commit --allow-empty -m "superegm: fix <spec-slug> round <round>" -- <spec-path>
    git push origin <branch>
    superegm review ingest --pr <n> --runcard <id>

The ingest records the PR's new threads as `external:<login>` findings into the latest round, carries an unsettled external high or medium of an earlier round, of this cycle or an earlier one, forward, and posts `**Reply <fid>:** fixed` on each thread settled `fixed`. Settle them like any finding: `fixed` by an edit alone (the next round reviews it); a thread's GitHub "resolved" state settles nothing. Then:

    superegm review status --review <id> --runcard <id>

Act on the exit code and nothing else:

| Exit | Then |
| --- | --- |
| 0 | converged: step 4 |
| 3 | open: the next round (from round 2, each goldfish also receives the prior round's findings with their dispositions) |
| 2 | at the cap: step 5 |
| 4 | a `fix-design` finding: `superegm approve-spec --void --review <id> --spec <spec-path>` voids the earlier approval (when there is none the defect is this spec's own: settle it `fixed` instead); fix the spec, then the next round |
| 5 | stalled: step 6 |

Doctrine between rounds (`resources/review_panels.md` section 7): change the thing, not the
round. When two consecutive rounds regress on the same area, delete the capability, narrow the
contract or shrink the surface, and say in the journal what was removed.

### 4. Approve (exit 0)

    superegm approve-spec --spec <spec-path> --runcard <id>

The helper checks that the working-tree bytes hash to the converged round's sha256 and that the
last H2 is `Units`, then prints the one question. **Normal mode**: ask the owner that question
with the options `Approve | Stop` (one question, sole tool call); on `Approve`, run it again
with `--yes`; on `Stop`, go to step 7 with the record. **Leavemealone-mode**: run it with
`--leavemealone`; the converged record is the approval. The helper then adds and commits the
spec and `.superegm/config.json` by path on the owner's current branch, ignoring other changes
in the tree, with the message `superegm: approve <spec-slug> at review <id>` (`config.commit_trailer`
after a blank line), and writes `approvals/<spec-slug>.json` (`commit`, `sha256`, `handoff_id`,
`escalated[]`). Before its question the helper lists the pairs that record will carry as
`approve-spec: <n> escalated finding(s) await the owner: <ids>`: every `escalated` finding of the
cycles since the last approval that no `## Units` row names; each needs a row there or a
`blocking: yes` decision in the plan before `graph` accepts the plan.

The helper ingests the spec PR once before its refusals (never under `--amend-units`; with no open PR on the current branch, or no round in the cycle yet, it reads nothing); an unsettled external high or medium there refuses with `approve-spec: external:<login> <fid> unsettled on PR <n>`, ruled or not: settle it and go back to step 3 (the next round). When the cycle was closed by an `accept` and settling it edits the spec, the edit opens the next cycle with a fresh cap: run step 2's `review open` first, then back to step 3.
After the approval commit, `git push origin <branch>`, so the PR's head is the approved commit.

Tell the owner, in one line: push the approval commit to `origin/<base>` (only the owner updates
the base branch; `launch` refuses the first wave until the spec there hashes to the approval; GitHub records that push as the PR's merge),
then type `/superegm:plan <spec-path>`. Nothing chains.

### 5. At the cap (exit 2)

No further round starts. Request the ruling of spec section 13.2 point 2 as one question:
`continue one bounded round` (once per cycle), `accept the remainder` (not while the reviewed bytes moved),
or `stop`; in leavemealone-mode, `superegm judges question --review <id> --cap` and the `judges`
skill. Once `continue` is spent and the bytes moved, the question has `stop` alone, ruled with no `--owner` or `--judges`.
Record it:

    superegm review rule --review <id> --ruling continue|accept|stop (--owner | --judges <judges-id>) --runcard <id>

`continue` raises the cap by one: the next round. `accept` converges the spec: step 4. `stop`
ends the cycle at its cap: step 7 with the record; the next invocation opens cycle n+1.

### 6. Stalled (exit 5)

The two latest rounds did not complete under this run card. End this invocation with the
record: name the review id, the reviewer and the reason from the round file, and close the card
(step 7). A re-typed `/superegm:review-spec` opens a new run card and resumes the same cycle.

### 7. Close

`superegm runcard close <id>` is the last action of every path, including a stop or an error
you cannot recover from. State the review id, the last `review status` line and, after an
approval, the commit to push.

## A fix-design finding later

When plan review or integrate finds the defect to be in the frozen spec, that skill runs
`superegm approve-spec --void --review <id> --spec <spec-path>`: the approval is void, `graph`
refuses it, and the owner types `/superegm:review-spec <spec-path>` again. The review opens as
the next cycle; a re-approval while any unit is filed keeps the handoff id.

## Data notice

When the Astra lane runs, the whole spec, the brief (on a resumed round, with your dispositions
on Astra's own earlier findings) and any file your OS account can read that Astra opens go to
OpenAI under the account `codex login status` reports. Say so in one line the first time the
lane starts in a session; `skip astra` stops waiting for it in this review, and
`config.astra.enabled: false` turns it off.

## Leavemealone-mode

In leavemealone-mode (`--leavemealone` on the invocation, or `config.mode`) decision points 1 and 2
go to the judge panel instead of the owner, and what each converged answer applies is the one
routing table `${CLAUDE_PLUGIN_ROOT}/skills/judges/references/leavemealone.md` (this skill carries
none of its own). At the point, render the question from the record:

- point 1, every high or medium you contest or decline in a round (step 3), one panel per round:
  `superegm judges question --review <id> --round <n> --reason <fid>=<text> --runcard <card>`,
  one `--reason` per finding, your reason verbatim as the overrule option's text;
- point 2, the cap (step 5): `superegm judges question --review <id> --cap --runcard <card>`.

Then the panel sequence of the reference: `superegm judges open --question <path> --evidence <paths> --parent <card>`
(the spec is the evidence; the panel's child card hangs under this card), the dispatch of the
`judges` skill (Astra through the runner, the Claude judges through `superegm:judge`, `judges record`,
`judges diff`, round by round), and `superegm judges verdict --panel <id> --runcard <card>`. Apply
each converged answer through its row as it converges (`review settle … --judges <panel>`,
`review rule … --judges <panel>`); the verdict's `open[]` are the unconverged questions: end the
invocation naming them and `judges/<id>/verdict.json`, close the card, and the owner rules by hand.
Point 4 is mechanical here: `approve-spec --leavemealone` (step 4).
