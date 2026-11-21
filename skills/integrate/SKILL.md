---
name: integrate
license: Apache-2.0
effects: external
effect_kinds: [state-store, start-session, github-write, destructive-local]
disable-model-invocation: true
description: Merges the landed units of a wave into the base branch and closes the handoff.
---

<!-- Added by SuperEGM (gsVAM), 2026: the integrate skill (spec section 12); close's issue closes, `--note` and `--close --patch` (U32); the follow-ups given as known and quoted (U51); the post-mortem run after `close` (U78); the respec refusals (U86); the one-time offer of `/superegm:retro` after the post-mortem (U87); the respec offered beside the void on a design finding (U91); `clean --auto` at Step 4, on every path (U93). -->

# Integrate (phase 7)

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

    /superegm:integrate <spec-path> [--handoff <id>] [--close [--patch]]

Runs after every unit has landed, has its PR merged with its issue still open, or been closed by the owner
(who closes a stopped unit's unlanded dependants with it): one round of the review `spec-<spec-slug>-integrate-c<n>` of the
frozen spec against everything the handoff merged, then `close`, which writes `closed_at` into the handoff's
`state.json` and `handoffs/<id>.json`. `--handoff <id>` names the handoff (by default the spec's latest
approval's; an older handoff integrates and closes too); pass `--handoff '<id>'` to `runcard open` and to every
call below. `--close` is the owner's typed close of a handoff they have given up on: it
runs `close` without a review round, journaling every unlanded unit. `--close --patch` is the owner's typed
statement that the handoff is a patch release: it runs `close --note "patch release"` without the integrate
round (no Step 2), the note the reason. No judge panel sits in this
skill, in any mode (design anti-goal 6); nothing here approves, merges or pushes. `superegm`
below stands for `python3 '${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py'`, one Bash call
per command, run from the target repository, absolute paths in single quotes, nothing chained;
every writing call carries `--runcard`.

## Step 1: card and the landed set

1. `superegm runcard open --skill integrate --artifact <spec-path>` prints `<card>`; a card still
   open on this spec is marked interrupted by it.
2. The landed set `close` starts from is the snapshot `status --wait` saves:
   `superegm status --wait 1 --runcard <card>` reads GitHub once and saves every unit's `landed`
   and `closed` facts; `close` adds each unlanded unit whose recorded PR it reads merged (Step 3).
3. Respecs (design section 7.6), with or without `--close`, before the landed list: item 2's `status --wait` output,
   after its event lines, refuses the integrate round and the close while it prints `open: respec R<n>` (print
   `integrate: respec R<n> is open`), `<U> held: respec R<n>` (print `integrate: <U> holds respec R<n>`) or
   `respec: read failed: <error>` (print `integrate: respec read failed: <error>`; an unread respec is never taken as
   none): say that the wave applies and relaunches it, and go to Step 4. A withdrawn respec or a stopped unit's mark
   is not printed and does not refuse. Otherwise go to item 4.
4. From `state.json`'s `status.units`, list every unit that is neither `landed` nor closed by a
   non-builder login (`closed`'s issue entry); a unit whose PR is merged, its issue still open, is
   not listed: `close` lands it and closes its issue. The saved snapshot has no merged field: a
   merged PR is a unit with `pr` set and `ci` null (`status` reads no CI of a merged PR). Without `--close`, one listed unit ends the
   invocation here: print the list, say that the owner merges, closes or re-types
   `/superegm:wave`, and go to Step 4; with none listed, go to Step 2. With `--close` (`--patch` or not), go to Step 3.
   Say that the owner merges in the inbox (`/superegm:inbox`); where the base ruleset restricts updates to config.owners, the inbox runs the admin bypass, `gh pr merge --admin`, once the owner says yes to it.

## Step 2: one integrate round

1. `superegm review open --kind integrate --artifact <spec-path> --reviewers <config.reviewers.integrate> --runcard <card>`
   prints `<id>` (`design` is first; the Astra lane joins when `config.astra.enabled` is true).
2. Write the diff outside the store: the handoff's own merged pull requests (`state.json`'s
   `units[<U>].pr.number` of every unit whose PR merged, its issue open or not), each `GH_HOST=github.com gh pr diff <n> -R OWNER/NAME` output
   concatenated in unit order, into
   `${TMPDIR:-/tmp}/superegm-integrate/<card>.diff`, the file every reviewer reads (another handoff's merges stay out of it).
   Read the handoff's triage follow-ups before the round: every unit's `foreman/<U>.json` `followups[]`
   (units in sorted order, rows in record order), one line each in the form
   `- <unit> <fid> (round <n>, pattern <k>): <claim>`. Give them to every reviewer's brief, the Astra brief
   included, as known: a reviewer reports one only where the integrated code makes it worse than its row says.
3. Dispatch every reviewer of the panel concurrently, in one message, each through its adapter
   `superegm:<id>` (`omitClaudeMd: true`, read-only tools), with the frozen spec's path and sha256
   (`approvals/<spec-slug>.json`), the diff file, the review id, round 1 and its own id, and the
   findings line of `${CLAUDE_PLUGIN_ROOT}/skills/review-spec/references/review_loop.md` section 2:
   `<reviewer>-1-<n> | high|medium|low | <location> | regression: no | <claim>`, written to
   `<artifacts_dir>/<handoff id>/reviews/<id>/round-1-<reviewer>.txt`, empty when it found nothing. The Astra
   lane runs through the runner from this conversation, as `resources/astra_lane.md` says.
   A repository reviewer or an overridden built-in (spec section 3.6) is dispatched through `superegm:repo-reviewer`, not its own adapter: run `superegm reviewers --brief <id> --handoff <handoff id> --runcard <card>` (an integrate review reads the copy frozen at the handoff's approval) and put its output, unedited, under `# Reviewer persona` in the brief, before the artifact. A reviewer is overridden when the last approval entry for the handoff's id (a re-approval after a void appends another with the same id) froze a file for its id (`reviewers: [{id, sha}]`), not by what the working tree holds; a plain built-in with no frozen file goes through its own adapter. Its model and effort are `SUPEREGM_GOLDFISH_MODEL` and `SUPEREGM_GOLDFISH_EFFORT` when set (read with `printenv`; `inherit` means pass nothing, and a value outside the allowed model and effort lists of `${CLAUDE_PLUGIN_ROOT}/skills/review-spec/references/review_loop.md` section 2 is refused, not passed), else the file's `model` and `effort` when set (the frontmatter of `source` in the frozen copy, the store's `reviewers/<sha>.json`), else `config.reviewers.model` and `config.reviewers.effort`.
4. Record each result as it arrives:
   `superegm review record --review <id> --round 1 --sha256 <spec sha256> --reviewer <reviewer> --findings <file> --isolation <clean|exposed:what> --model <requested>:<effective> --effort <requested>:<effective> --runcard <card>`
   (one re-dispatch on a failed or empty return, then `--not-run '<reason>'`).
5. `superegm review status --review <id> --runcard <card>`; act on the exit code alone:

| Exit | Then |
| --- | --- |
| 0 | nothing to escalate: Step 3 |
| 5 | stalled (the round did not complete under this card): end with the record, Step 4 |
| any other | every high or medium is escalated: Step 2a |

### Step 2a: escalate

A frozen handoff (an older one: a later approval opened another handoff of the spec) appends no row
and runs no `--amend-units`, both refused; its spec's rows are planned in the latest handoff. Settle every
high or medium of the round in one file, a line `<fid> | escalated | (to the latest handoff)` each:
`superegm review settle --review <id> --file <path> --runcard <card>` (`fix-design` is refused there), then Step 3.
Otherwise settle every high or medium finding of the round first, in id order, each one way:

1. A finding a new unit fixes: append one row to the spec's `## Units` table for that unit, with the note
   `(from integrate, review <id>)` in its scope cell (the spec changes nowhere else), then
   `superegm review settle --review <id> --finding <fid> --disposition escalated --runcard <card>`.
2. A finding whose fix is in the frozen spec's design, not a new unit: on a normal card only, ask the owner
   whether it is a design defect; on Yes,
   `superegm review settle --review <id> --finding <fid> --disposition fix-design --owner --runcard <card>` (no row
   for it); on No, or on a leavemealone card, settle it as item 1. Go on to the next finding: nothing is voided or
   opened inside this loop.

When every finding is settled and one or more is `fix-design`, ask the owner one question with two options (a
normal card only: a leavemealone run settled none `fix-design`). `Respec` (design section 7.6): one respec for
the round, `superegm respec open --review <id> --finding <fid> --runcard <card>` with `<fid>` its first `fix-design`
finding in id order (its approval closes the cycle, resolving every one of them; a second `R<n>` on the same review
would stay open after it, so name the others in the respec's text), which writes
`respec/R<n>.open.json`; this skill and `next` then wait on it (`open: respec R<n>`, `waiting respec R<n>`) until
`/superegm:review-spec` approves it with `approve-spec --respec R<n>`, which closes this review's cycle so the next
integrate opens a new one. `Void`, for a change too large to respec:
`superegm approve-spec --void --review <id> --spec <spec-path> --runcard <card>`. The respec is the owner's alone:
the helper refuses it under a leavemealone card or `SUPEREGM_ROLE`.

Then, when the loop appended any `## Units` row and the owner did not choose `Void`,
`superegm approve-spec --spec <spec-path> --amend-units --runcard <card>`: the approval is re-recorded at the new
bytes without a review round, the handoff id kept; it refuses when any line outside `## Units` changed. An open
respec does not refuse it: the rows are the escalated findings' units, and the respec's approval is a later entry.
After a `Void` it is not run: the voided approval carries no amendment, and the rows go back to
`/superegm:review-spec` with the spec. Tell the owner in one line what happened: the respecs opened or the void,
and, when the rows were approved, push the approval commit to `origin/<base>`, then type
`plan` → `review-plan` → `file` → `wave` for the new units only (`file` waits while a respec is open). The handoff stays open; Step 4.

## Step 3: close

`superegm close --runcard <card>` prints `closed <handoff-id>; unlanded: <ids | none>`, writes
`closed_at` into `state.json` and `handoffs/<id>.json` and journals `close: <U> unlanded` for every unlanded unit (with
`--close`, the units the owner gave up on; after a clean round, none). With `--close --patch` it is

    superegm close --note "patch release" --runcard <card>

and the note is journaled `close: note patch release`. An unlanded unit's PR is read once
(`gh api repos/<repo>/pulls/<n>`); merged, the unit lands for this close. Each landed unit's issue is read
once and, still open, closed as completed (`close: <U> #<n> closed completed`, or `already closed`); when
every unit landed, the tracking issue is closed the same way, last, then `closed_at` is written. With a
unit unlanded the tracking issue stays open to the owner. A second `close` is
refused (`close: already closed at <ts>`). One `gh api repos/<repo>/issues/<n>` read per unit stopped for
redesign (its `foreman/<U>.json` carries `stopped.brief`) comes first; while that issue is open `close` exits 1 with
`close: <U> is stopped for redesign and #<n> is open: close it by hand once the re-planned unit is filed`, one line per
such unit, each read journaled and `state.json` untouched: the owner closes it by hand, since the plugin edits no issue it did not file, and `close`
runs again. The skill never closes it; it prints the refusal and ends at Step 4. Other handoffs of the store
are untouched: each has its own directory.

After `close` succeeds, run the post-mortem (no card of its own, it writes only the derived file):

    superegm postmortem --handoff '<id>'

It prints the path of `<handoff dir>/postmortem.md`. Tell the owner that path and three lines read from its
tables: the total wall time (Header, total wall seconds: the earliest first launch to the latest merge), the unit with the most rounds
(Units, head rounds) and the reviewer with the most overruled findings (Reviewers, overrules, the overruled
and allowed columns together, an allowance being an overrule, summed across its rows: a reviewer has one row per kind; the Lessons row
"reviewer most overruled" names the same reviewer: a tie lists every tied reviewer, each on its own Lessons row in reviewer-id order (sorted by name); a reviewer whose every finding was overruled or allowed gets the row "reviewer kept nothing", not "reviewer most overruled"); the figures are the report's, the one sum aside. A refused `close` ends the skill without it.
Then offer the retrospective, once: `/superegm:retro --handoff '<id>'` walks the report's Lessons with the owner and lands
what they agree in one commit (design section 7.7). The skill runs nothing of it; the owner starts it in a session of their own when they want it.

## Step 4: the end

On every path to this step, a filing or none (Step 2a's units, Step 3's close, a respec refusal, units listed without `--close`, a stalled round), run `superegm clean --auto --runcard <card>`: it removes the worktrees of every landed, merged or stopped unit, prints one line per unit cleaned and never refuses, so it never stops the skill.

`superegm runcard close <card>` (`--note '<text>'` journals a note with it) is the last action of every path, including an error you cannot
recover from. In chat: the review id and its `review status` line, the escalated findings with
their new unit rows, or the `closed` line with `close`'s `Follow-ups:` block quoted beside it, and the handoff journal's `accepted before the cap` lines quoted
verbatim (the one source for the owner's by-hand release notes), skipping a review's line that a later
`review <id> R<n> accept lapsed` line of the same review names; never a report pasted.
