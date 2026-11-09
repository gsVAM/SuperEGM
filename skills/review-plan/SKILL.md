---
name: review-plan
license: Apache-2.0
effects: external
effect_kinds: [state-store, start-session]
disable-model-invocation: true
description: Reviews a handoff plan against its design through the judge panel before any issue is filed.
---

<!-- Modified by SuperEGM (gsVAM), 2026: the body: plan review over the helper's review-plan and review subcommands (U06); `[--handoff <id>]`, `filed_elsewhere` and the handoff's directory (U20); the accept below the cap's one question per round (U35). -->

# Plan review (phase 3)

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

    /superegm:review-plan <spec-path> [--handoff <id>] [--units U01,U02] [--reviewers readiness,proportion,set,…] [--leavemealone]

## What it does

One review per unfiled unit, id `plan-<unit>-c<n>` (in the handoff's directory of the store), kind
`plan`, over the unit's current rendered body, the fenced text of `unit_<id>.md`. The panel is
`readiness,proportion,set` unless the invocation says otherwise: `readiness` first, `proportion`
the zoom-out persona with its plan brief, and `set` the readiness persona dispatched
once per round over the whole set of unfiled units. Every unfiled unit runs through the one loop of
`${CLAUDE_PLUGIN_ROOT}/skills/review-spec/references/review_loop.md` (retry, decision points,
doctrine, model and effort, consumed unchanged) against the eleven questions of
`${CLAUDE_PLUGIN_ROOT}/resources/document_standards/handoff-standard.md`. Nothing is filed
here; the next phase is `/superegm:file`.

`<HELPER>` is `${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`. Every helper command is
one Bash call, `python3 '<HELPER>' <subcommand> …`, run from the target repository, absolute
paths in single quotes, nothing chained. The helper judges: `review status` holds the only cap
and stall predicates, and `review-plan due` derives the round's dispatch set from it. You
dispatch.

## Step 0: card and panel

1. When `.superegm/config.json` is missing, run `python3 '<HELPER>' init`, then continue; the
   owner's by-hand steps it prints are not needed for this review.
2. `python3 '<HELPER>' runcard open --skill review-plan --artifact '<spec>' --mode '<normal|leavemealone>'`
   prints `<card>`; it goes on every writing helper call below. `<spec>` is the approved spec
   the plan names (`state.json`'s `design.path`). With `[--handoff <id>]` on the invocation, pass `--handoff '<id>'` to this `runcard open` and to every helper call below; an older handoff is frozen and refuses.
3. The panel is `--reviewers` when the invocation gave it, else `config.reviewers.plan`;
   `readiness` is first, one to six ids.
4. Each decision point (a high or medium you contest or decline, a review at its cap)
   pauses the owner with one question, the sole tool call of its turn, options without a
   `(Recommended)` prefix; in leavemealone-mode the routing of design section 13.2 replaces the
   pause.
5. Show the run card line of review_loop.md section 7 once; in normal mode ask the owner once
   whether to start, in leavemealone-mode start.
6. Run `superegm orient --spec '<spec>' --runcard '<card>'` through the helper (the `orient`
   subcommand of the same `python3 '<HELPER>'` Bash call as every command below) when the skill
   starts, and `superegm orient --spec '<spec>' --unit U<id> --runcard '<card>'` for each unit
   after every `graph` it runs that re-rendered that unit's body, so the next round's
   `readiness` goldfish reads a fresh unit file (the map is `plan`'s, written without `--unit`);
   stop on its exit 1 with its line.

## Step 1: the dispatch set

    python3 '<HELPER>' review-plan due --runcard '<card>'

One line per unfiled unit: `<unit> <due|converged|stalled|cap|fix-design> <review-id|-> <next
round|-> <body_sha256>`. Keep only the rows `--units` names when the invocation gave it (the
command carries no flag), and drop the units this invocation already ended. Then, per row:

- `due - 1`: `python3 '<HELPER>' review open --kind plan --artifact '<unit>' --reviewers '<panel>' --runcard '<card>'`
  prints `<id>` (a cycle still open from an earlier invocation is resumed with its stored
  panel); round 1.
- `due <id> <n>`: round `n` of `<id>`. A body re-rendered since its last round, or a converged
  unit a set finding reopened, is a new round of the same review.
- `converged`: nothing; the body is reviewed at the printed sha.
- `stalled`: the loop ends the invocation for that unit, the others continue; the closing
  record names the reviewer and the reason from
  `python3 '<HELPER>' review status --review '<id>' --runcard '<card>'` and the round file's
  `not run (<reviewer>: <reason>)`. A re-typed `/superegm:review-plan` opens a new card and
  resumes the same cycle.
- `cap`: decision point 2 as one question (continue one bounded round, once per cycle; accept
  the remainder, not while the body moved since the round; stop, alone and ruled by no one once
  continue is spent and the body moved), recorded with
  `python3 '<HELPER>' review rule --review '<id>' --ruling '<continue|accept|stop>' --owner --runcard '<card>'`
  (`--judges '<id>'` in leavemealone-mode). `continue` raises the cap by one and the next round
  follows; `accept` converges the unit; `stop` ends the invocation for that unit. When the
  helper answers `review rule: cycle stopped`, a stop was ruled earlier: run `review open` as
  for `due - 1`; it starts the next cycle with a fresh cap.
- Below the cap, before the `due <id> <n>` rows run, run `python3 '<HELPER>' review status --review '<id>' --runcard '<card>'` per
  such row and read its `acceptable:` line. In normal mode ask the owner one question, once per round, naming every acceptable unit
  with its counts (`acceptable: yes (<n> medium, <m> low)`); the owner names the units accepted, recorded with
  `review rule --review '<id>' --ruling accept --owner --runcard '<card>'` (the unit converges by ruling), and the rest are fixed.
  The judges never accept below the cap: in leavemealone-mode nothing is asked.
- `fix-design`: Step 4.

No `due` row left after this: Step 5. Otherwise Step 2 with the due units.

## Step 2: dispatch

Everything a round dispatches goes in one message so it runs concurrently: every due unit's
goldfish and the one set read, each through its adapter `superegm:<id>` with the Agent tool
(`.claude-plugin/agents/<id>.md`; a reviewer spawned any other way is not a goldfish). `k` is
this invocation's round count, 1 at its first Step 2.

1. Once per round, `python3 '<HELPER>' review-plan set-input --spec '<spec>'` prints the set
   text: the spec's `## Units`, then per unfiled unit `## <id>` with its Interfaces block and
   Scope line. Save it to `${TMPDIR:-/tmp}/superegm-review-plan/<card>_set_r<k>.md`, outside
   the store.
2. Per due unit, each panel reviewer except `set` and `proportion` receives, by absolute path:
   the body; the spec path with the approval's sha256 (`approvals/<spec-slug>.json`);
   `${CLAUDE_PLUGIN_ROOT}/resources/document_standards/handoff-standard.md`; the set text, as
   every sibling's Interfaces block; from round 2 the prior round's findings with their
   dispositions, rendered from `round-<n-1>.json` as review_loop.md section 2 says, the fixes
   marked `-> fixed`; the round number and its own reviewer id; the findings line
   `<reviewer>-<round>-<n> | high|medium|low | <location> | regression: yes|no | <claim>`, one
   per finding, written to `<artifacts_dir>/<handoff id>/reviews/<id>/round-<n>-<reviewer>.txt`, an empty
   file when it found nothing. The `readiness` goldfish also receives the standard's readiness
   sentence: a question a builder would have to ask before building is a finding, a blocking
   one is `high`; and, by absolute path, the unit's `orient/<unit>.md` in the handoff's directory when the store
   holds it (the brief says `no orient file` when it is absent); that dispatch is recorded with
   `--isolation 'exposed:orient <tree sha>'`, the tree its first line names, joined with
   whatever else the goldfish reports.
3. Per due unit, one `proportion` dispatch through `superegm:zoom-out` with
   `${CLAUDE_PLUGIN_ROOT}/skills/review-plan/references/proportion.md` and, in place of the set
   text, the text `python3 '<HELPER>' review-plan proportion-input --unit '<unit>' --spec '<spec>'`
   prints (the body, its `plan/scan/<unit>.json`, the spec lines of its Design range), saved
   beside the set text as `<card>_proportion_<unit>_r<k>.md`. When the scan files are missing
   or older than the bodies, run `python3 '<HELPER>' scan --plan '<plan>'` first. It answers question 11 only;
   its findings are `medium` at most and name the Step and the bytes they would remove.
4. One `set` dispatch through `superegm:readiness` with the set text and the standard;
   questions 1 to 4 and 8 are its lens (coverage of the spec's `## Units`, contradictions,
   blockers, shared-file order, interfaces; a row the section's `Landed:` line names counts as covered).
   So does a row `handoff_units.json`'s `filed_elsewhere` lists: a unit filed in another handoff of the spec, planned there.
   Its ids are `set-<k>-<n>`; each location names the
   unit or units it concerns, or none; its one findings file is `<card>_set_r<k>.txt` beside the
   set text.
5. The Astra lane per due unit as review_loop.md section 2 says, when the review opened with it.

Model and effort per dispatch: review_loop.md section 2, with the run card line's pairs.

## Step 3: record and judge

Per due unit per panel reviewer, as each result arrives:

    python3 '<HELPER>' review record --review '<id>' --round <n> --reviewer '<reviewer>' --findings '<file>' --isolation '<clean|exposed:what>' --model '<requested>:<effective>' --effort '<requested>:<effective>' --runcard '<card>'

A dispatch that times out, fails or returns no file is re-dispatched once within the round;
when it fails again, `--not-run '<reason>'` replaces `--findings`. The set file goes to every
due unit with `--reviewer set` (the helper keeps the lines whose location names that unit or no
unit, and takes the set's own round in the ids), and to a converged unit a set finding names,
at that unit's latest round plus one: this reopens it, and `due` lists it next round.

Then per due unit `python3 '<HELPER>' review status --review '<id>' --runcard '<card>'`, and act
on the exit code alone:

| Exit | Then |
| --- | --- |
| 0 | converged at the printed sha: nothing more for this unit |
| 3 | open: fix and settle below, then Step 1; an acceptable unit (an `acceptable:` line) gets the Step 1 question before any fix moves its bytes, so it goes to Step 1 unfixed |
| 2 | at the cap: Step 1 lists it `cap` |
| 4 | a `fix-design` finding: Step 4 |
| 5 | stalled: Step 1 lists it `stalled` |

Fixing (exit 3): a finding against a body is fixed in the plan file `state.json` names as
`plan`, never in a body by hand; re-render with
`python3 '<HELPER>' graph --plan '<plan>' --runcard '<card>'`, then `python3 '<HELPER>' scan --plan '<plan>'`
(D1 (a): `graph` accepts this card; the re-render is the next round of the same review). Write
every disposition of the round with
`python3 '<HELPER>' review settle --review '<id>' --finding '<fid>' --disposition '<fixed|contested|declined|escalated|fix-design>' --runcard '<card>'`
as `${CLAUDE_PLUGIN_ROOT}/skills/review-spec/references/resolve.md` says; a high or medium you
contest or decline is decision point 1 (`--owner` in normal mode, `--judges '<id>'` in
leavemealone-mode; the helper refuses it without). Doctrine between rounds, review_loop.md
section 5: change the thing, not the round. Readiness and proportion are an adversarial pair: a
conflict between them is resolved in favour of the shorter form that keeps the test honest, and
you record that disposition. Never dispatch the goldfish as reviewers of your own fixes in the
turn you made them: record, settle, ask `review status`, then Step 1.

## Step 4: fix-design

`review status` exit 4: the defect is in the frozen spec, not in the units.
`python3 '<HELPER>' approve-spec --void --review '<id>' --spec '<spec>' --runcard '<card>'`
writes `voided_by` on the approval, and `graph` refuses the spec from then on. Tell the owner
in one line that the spec returns to `/superegm:review-spec` for that unit's Design range, then
`python3 '<HELPER>' runcard close '<card>'` and stop.

## Step 5: the end

One line per unit from the last `due` listing: converged at round n; stalled, with the reviewer
and reason; stopped at the cap. `python3 '<HELPER>' runcard close '<card>'` is the last action
of every path, including an error you cannot recover from. The next phase is `/superegm:file`.

## Rules

- No GitHub write in this skill; the helper writes the store alone, you write nothing in it by
  hand.
- Only a `completed` round counts: every panel reviewer recorded, an empty file included; the
  findings of any other round settle nothing and block nothing.
- The readiness goldfish reads one body, except as `set`, when it reads the set text alone and
  no body.
- Findings live in the store and dispositions in the round files: name the review id and the
  `review status` line in chat, never paste a report.

## Leavemealone-mode

In leavemealone-mode (`--leavemealone` on the invocation, or `config.mode`) the pause of Step 0
item 4 is replaced by the judge panel at decision points 1 and 2, and what each converged answer
applies is the one routing table `${CLAUDE_PLUGIN_ROOT}/skills/judges/references/leavemealone.md`
(this skill carries none of its own). At the point, render the question from the record:

- point 1, every high or medium you contest or decline in a unit's round (Step 3), one panel per
  round: `python3 '<HELPER>' judges question --review <id> --round <n> --reason <fid>=<text> --runcard <card>`,
  one `--reason` per finding, your reason verbatim as the overrule option's text;
- point 2, a `cap` row of Step 1: `python3 '<HELPER>' judges question --review <id> --cap --runcard <card>`.

Then the panel sequence of the reference: `python3 '<HELPER>' judges open --question <path> --evidence <paths> --parent <card>`
(the unit's body and the spec are the evidence; the panel's child card hangs under this card), the
dispatch of the `judges` skill (Astra through the runner, the Claude judges through
`superegm:judge`, `judges record`, `judges diff`, round by round), and
`python3 '<HELPER>' judges verdict --panel <id> --runcard <card>`. Apply each converged answer
through its row as it converges (`review settle … --judges '<panel>'`, `review rule … --judges '<panel>'`);
the verdict's `open[]` are the unconverged questions: end the invocation for that unit naming
them and `judges/<id>/verdict.json`, the other units continue, and the owner rules by hand.
