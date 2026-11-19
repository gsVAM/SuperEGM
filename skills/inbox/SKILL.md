---
name: inbox
license: Apache-2.0
effects: external
effect_kinds: [github-write, state-store, start-session]
disable-model-invocation: true
description: Use when the owner asks what needs them - lists every open decision, cap ruling, contested finding, merge-ready PR, stalled unit, escalation, redesign, test-delta finding and owner-only finding across the store's open handoffs, then asks the owner each open question in words with a recommended pick and, on the owner's answer, posts the ruling, writes the wait record's answer, voids, merges or kicks the driver.
---

<!-- Added by SuperEGM (gsVAM), 2026: the inbox skill (spec section 11.2). -->

# inbox

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

    python3 '<HELPER>' inbox [--all] [--json] [--handoff <id>]

`<HELPER>` is `${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`. Run `superegm inbox` and show its lines to the owner as printed; then, for the items the owner answers here, run `superegm inbox --json --handoff <id>` per open handoff and work from its objects (each item's handoff is the one its run named).

No skill asks the owner to post a comment or to paste a command: the inbox asks in words and does the rest. A comment the owner posts on GitHub by hand still counts; the inbox is the way, not the only way.

## What it lists

Listing is read-only: no run card, no store write, no GitHub call (`superegm inbox withdrawn`, the merge step's withdraw, is the exception: it journals one line and opens and closes its own inbox card); `superegm inbox` typed alone prints and never notifies, and any session may run it. It reads the current repository's store, every open handoff of its `handoffs/` index unless `--handoff` names one; `--all` reads every store the registry lists (`registry: none`, and the one store, while nothing is registered; under `--json` that line is left out). `--json` prints one object per line with the keys `repo`, `subject`, `kind`, `action` and `fingerprint`, and a ruling's object adds `forms` (the `**Ruling:**` forms of the choices still open) and `on` (the issue URL the ruling is posted on). An empty store prints nothing.

One line per item:

    <repo> <unit or review> | <kind> | <action>

The action is `answer in the inbox` for a ruling this skill asks, `answer in your <skill> session` for a ruling a review's own interactive session asks in words, or the merge, machine or setup step the item names. The kinds:

- `decision`: an open point-3 or point-5 decision; its forms are `**Ruling:** (<comment id>) <option> — <reason>` when its source is a comment, else `**Ruling:** (<decision id>) <option> — <reason>`, one per option of the record's `options` (the menu `(<a> | <b>)` of 1.2), `<option>` when it has none.
- `cap`: a review at its cap with no `stop` ruled. A head's pending point-2 decision, or a head at its cap with no such decision yet, is answered in the inbox with the forms `**Ruling:** one more round | **Ruling:** stop | **Ruling:** redesign — <reason>` (one form per choice, the reason with `redesign` alone); the next `/superegm:wave <spec>` records the posted ruling. A spec, plan or integrate review's cap is `answer in your review-spec session`, `answer in your review-plan session` or `answer in your integrate session`, the session recording it with `superegm review rule --review <id> --ruling continue|accept|stop --owner`. A spent choice leaves the forms: `one more round` once ruled on the unit, `continue` once ruled on the review.
- `contested`: a point-1 decision's contested finding, the forms `**Ruling:** <fid> finding upheld | **Ruling:** <fid> finding overruled — <reason>` (the reason with `finding overruled` alone).
- `merge`: the latest round's `outcome: clean`, or a `proceed` on the head; the action is the PR's URL, or the merge on the proceed's pinned head, `await-merge after <units>` first while the merge order holds it.
- `stalled`: a head review that stalled (`review status` exit 5); answered in the inbox with the cap's forms.
- `proceed again`: a `proceed` whose pinned head a later launch moved; answered in the inbox with the form `**Ruling:** proceed — <reason>`.
- `escalated`: a pair of the approval record's `escalated[]` that neither the spec's `## Units` section nor a unit's decision names yet, or a plan's `blocking: yes` D<n> line not yet answered: `answer in your plan session` (`/superegm:plan <spec>`, which asks it); or an integrate round's escalated finding, `answer in your integrate session`, which settles it with `superegm review settle --review <id> --finding <fid> --disposition fixed | declined --owner`, in leavemealone-mode a high or medium one's `--owner --posted <comment id>`, the id of the owner's `**Ruling:** <fid> finding overruled — <reason>` comment.
- `redesign`: a unit a redesign ruling ended; `/superegm:brainstorming <brief>`, a typed step.
- `test-delta` and `owner`: the owner's own findings, the form `**Ruling:** <fid> allowed — <reason>` (in leavemealone-mode, for a finding an open point-1 decision asks about, `**Ruling:** <fid> finding overruled — <reason>`, the form `decision rule` takes there), until the finding is settled or ruled.
- `kill_failed`: a launch whose process could not be ended; not yet listed, until the launch records `kill_failed`; its `/superegm:interrupt` stays a typed machine step.
- `wave`: an open `wave` card with its age, information and never an action. The driver's `/superegm:driver reset`, `register` and `install` lines stay typed setup steps.

Never listed: builders running, rounds in progress, heads waiting on CI, lows, or the judges' converged rulings.

## Answering

The inbox runs in the owner's interactive session and writes only on an answer the owner gave in it.

1. **Who may answer.** Before acting on any answer, read `gh api user --jq .login` and refuse, acting on nothing, unless the login is in `config.owners` of the item's store. Every comment is posted with that login, so every ruling reader sees the owner's comment as if typed.
2. **The pick.** Open every question with one recommended option and a one-line reason ("I'd rule (b): the builder's test covers it. Rule (b)?"), picked from the question and its evidence: the round's `comments.md` and diff, the builder's comment, and `judges/<panel>/verdict.json`'s split where a panel ran. The owner's "yes" takes it; the owner may answer anything else in words instead.
3. **In leavemealone.** The judges settle each ruling and `decision rule … --by judges:<panel>` posts it, so ask nothing about those. Ask only what stays the owner's: a question the panel did not converge on, a `redesign`, an `owner:` or test-delta finding, a `kill_failed` unit, a merge and a wait before filing the frozen mode leaves to the owner, each with its pick.
4. **A ruling** (`answer in the inbox`: a decision, a contested finding, a head's cap or stall, a test-delta or owner finding). Show the question, its forms as options and the pick; map the owner's words to one form and read the mapped ruling back once ("rule (b) — <reason>?"). On yes write it to a file and post it with `gh issue comment <n> -R <repo> --body-file <file>`, `<n>` and `<repo>` the item's `on`; the next wave session records it with `--posted`. Answers that map to no form are asked again, never posted.
5. **`proceed again`.** Ask the owner for a one-line reason, read `**Ruling:** proceed — <reason>` back once and, on yes, post it on the item's `on` as above.
6. **A wait before filing** (a `waiting <phase>: …` line). Show the record's question; on the owner's answer run `superegm next answer --handoff <id> --answer <text>`, which reads the login itself and writes the answer into the wait record; the driven skill records it. For file's Create, show `handoff_dryrun.md` with the question first.
7. **Nothing left to plan** (`waiting plan: no unit left to plan`). Ask "void the approval?" and on yes run `superegm approve-spec --void --spec <spec>`, which opens and closes its own `approve-spec` card.
8. **A review's session** (`answer in your <skill> session`). Tell the owner which session asks it; ask nothing here.
9. **Merging.** For a merge item ask "merge <PR>?" naming its head `<sha>`. Merge only the pull requests the owner named in that answer: never one the owner did not name. Offer and merge in the shared-file merge order: a unit whose item `merges after` an unmerged unit (`await-merge after <units>`) is offered after it. `<repo>` is the item's store's repository, carried as `-R <repo>` on every `gh pr merge` and `gh repo view` here, `--admin` included. `<method>` is the first of `merge`, `squash` and `rebase` the repository allows, read with `gh repo view -R <repo> --json mergeCommitAllowed,squashMergeAllowed,rebaseMergeAllowed` (`gh pr merge` without a method fails outside a terminal). Right before each merge, the ordinary one and the `--admin` one alike, read the unit's state again (`superegm inbox --json --handoff <id>` and the unit's head): the unit not stopped, no respec mark, no pending decision, no live launch, and the head's review verdict clean or proceeded. When any of these changed since the question, merge nothing: withdraw the offer with `superegm inbox withdrawn --pr <n> --reason <text> --handoff <id>`, the item's handoff filled in, which journals `merge withdrawn <PR> <reason>`, and tell the owner why. Otherwise run `gh pr merge <n> -R <repo> --<method> --match-head-commit <sha>`; a head that moved since the question re-asks with the new head. When GitHub refuses because the base branch's rules block the merge, ask "merge with the admin bypass?" and add `--admin` only on yes, after reading the state again as above.
10. **The kick.** After each posted ruling, written answer, void or merge, run `superegm driver kick --root <root>`, `<root>` the item's store's registered root (the registry entry's `root`, the current repository's root for the current store).

The inbox opens no run card and runs no recorder, except `approve-spec --void`, `driver kick` and `superegm inbox withdrawn`, which, typed without `--runcard`, opens and closes its own inbox card around its journal line: the phase session that holds the card records what it posted or wrote.

## Notify

`wave` notifies, never this skill: after each batch's `report` it runs `superegm notify --runcard <card>`, which writes the card's handoff's lines new since `state.json.notified` to the owner's `~/.superegm/notify` hook (absent means no hook), bounded by `config.notify_timeout_seconds`.
