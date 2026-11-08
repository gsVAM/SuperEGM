---
name: inbox
license: Apache-2.0
effects: none
description: Use when the owner asks what needs them - lists, read-only, every open decision, cap ruling, contested finding, merge-ready PR, stalled unit, escalation, redesign, test-delta finding and owner-only finding across the store's open handoffs, one line each with the comment, command or PR URL that moves it, and each open wave card as information.
---

<!-- Added by SuperEGM (gsVAM), 2026: the inbox skill (spec section 11.2). -->

# inbox

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

    python3 '<HELPER>' inbox [--all] [--json] [--handoff <id>]

`<HELPER>` is `${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py`. Run `superegm inbox` and show its lines to the owner as printed.

## What it does

Read-only: no run card, no store write, no GitHub call; typed alone it prints and never notifies. It reads the current repository's store, every open handoff of its `handoffs/` index unless `--handoff` names one; `--all` reads every store the registry lists (`registry: none`, and the one store, while nothing is registered). `--json` prints one object per line with the keys `repo`, `subject`, `kind`, `action` and `fingerprint`. An empty store prints nothing.

One line per item:

    <repo> <unit or review> | <kind> | <action>

The action is the exact comment to post (a `**Ruling:**` form with the issue's URL, copyable from a phone), the command to type, or the PR's URL to merge. The kinds:

- `decision`: an open point-3 or point-5 decision, `**Ruling:** (<comment id>) <option> — <reason>` when its source is a comment, else `**Ruling:** (<decision id>) <option> — <reason>`, followed by the menu of the record's `options`, `(<a> | <b>)`, when it has some.
- `cap`: a review at its cap with no `stop` ruled; a head's pending point-2 decision is `**Ruling:** one more round | stop | redesign — <reason>`, a head at its cap with no such decision is `/superegm:wave <spec>` (the wave opens it), and a spec, plan or integrate review's cap is `superegm review rule --review <id> --ruling continue|accept|stop --owner --runcard <card>`.
- `contested`: a point-1 decision's contested finding, `**Ruling:** <fid> finding upheld | finding overruled — <reason>`.
- `merge`: the latest round's `outcome: clean`; the action is the PR's URL.
- `stalled`: a head review that stalled (`review status` exit 5); re-type `/superegm:wave <spec>`.
- `escalated`: a pair of the approval record's `escalated[]` that neither the spec's `## Units` section nor a unit's decision names yet, `/superegm:plan <spec>`, or, when a plan's `blocking: yes` D<n> line names it, `superegm decide --unit <U> --decision <D> --answer <option> --runcard <card>` until `decide` answers it; or an integrate round's escalated finding, `superegm review settle --review <id> --finding <fid> --disposition fixed | declined --owner --runcard <card>`.
- `redesign`: a unit stopped for redesign; `/superegm:brainstorming <brief>`.
- `test-delta` and `owner`: the owner's own findings, `**Ruling:** <fid> allowed — <reason>` (in leavemealone-mode, for a finding an open point-1 decision asks about, `**Ruling:** <fid> finding overruled — <reason>`, the form `decision rule` takes there), until the finding is settled or ruled.
- `kill_failed`: a launch whose process could not be ended; not yet listed, until the launch records `kill_failed`.
- `wave`: an open `wave` card with its age, information and never an action.

Never listed: builders running, rounds in progress, heads waiting on CI, lows, or the judges' converged rulings.

## Notify

`wave` notifies, never this skill: after each batch's `report` it runs `superegm notify --runcard <card>`, which writes the card's handoff's lines new since `state.json.notified` to the owner's `~/.superegm/notify` hook (absent means no hook), bounded by `config.notify_timeout_seconds`.
