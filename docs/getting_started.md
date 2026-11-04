# Getting started

<!-- Modified by SuperEGM (gsVAM), 2026: EGM's and the Astra fork's workflow guide replaced by SuperEGM's install, by-hand setup and eight phases (design section 5). -->

## Install

Disable the two plugins SuperEGM absorbs, then add the marketplace and install:

```sh
claude plugin disable egm@egm-astra
claude plugin disable superpowers@claude-plugins-official
claude plugin marketplace add gsVAM/superegm
claude plugin install superegm@superegm
```

Every command is `/superegm:<skill>`. The session hook reads `using-superegm` into every session;
a headless session SuperEGM starts itself (a builder, a goldfish) gets nothing from the hook.

## Before the first run

In the target repository, `python3 '<plugin root>/skills/plan/scripts/superegm.py' init` writes
`.superegm/config.json` with every key's default (`repo`, `base`, `artifacts_dir`, `mode`,
`max_in_flight`, `labels`, `reviewers`, `astra`, `judges`, `builder`, `ci_wait_minutes`,
`banned_terms`, …) and prints the owner's by-hand steps; the first typed skill runs it when the
file is missing. The steps:

1. Create the **builder account**: its own GitHub login with write access to the repository, and
   put a token for it in `SUPEREGM_BUILDER_TOKEN` (config key `builder.gh_token_env`). Builders
   push and open draft pull requests as that account and can never merge.
2. Create the builder's empty profile at `config.builder.profile_dir`: no hooks, no plugins, no
   `CLAUDE.md`, only the login. `launch-builder` refuses a profile with anything else in it.
3. Set the branch protection of design section 11 on `<base>`: updates restricted to the owner
   with no bypass for the builder account's role; `superegm/**` protected from force-push and
   deletion. `launch` reads the protection and refuses the first wave without it.
4. Add a workflow triggered on `pull_request`, so every builder head gets CI: CI is the
   foreman's evidence.
5. Commit `.superegm/config.json`; `approve-spec` commits it with the spec.
6. Run reviews from a profile without SubagentStart hooks: such hooks in the owner's own profile
   reach adapter subagents, and every dispatch record carries what the goldfish reported seeing.

The store (`artifacts_dir`, outside the working tree) is never committed.

## The eight phases

One typed skill per phase, nothing chains, and the owner pushes the approval commit to
`origin/<base>` between phases 1 and 5 (`launch` refuses the first wave until the spec there
hashes to the approval).

| # | Phase | Skill | Gate | Record |
| --- | --- | --- | --- | --- |
| 0 | Brainstorm | `/superegm:brainstorming` (auto-invoked; reads and drafts only) | the owner's opt-in | a spec under `docs/specs/` ending in `## Units` |
| 1 | Spec review | `/superegm:review-spec <spec>` | converged or ruled | the review record; the approval freezing the spec at a sha256 |
| 2 | Plan | `/superegm:plan <spec>` | `graph` and `scan` pass | the plan file, one TDD plan per unit; the rendered bodies and their hashes |
| 3 | Plan review | `/superegm:review-plan <spec>` | converged or ruled, per unit | a review record per unit over the exact bytes |
| 4 | File | `/superegm:file <spec>` | a dry run the owner confirms; `verify` reads back | the tracking issue, one issue per unit, blocked-by links, the filing receipt |
| 5 | Wave | `/superegm:wave <spec>` | per unit: a clean head with its contested findings ruled, no regressions | launches, foreman rounds, review comments on the PR, the wave report |
| 6 | Merge | the owner, by hand | the owner | the merged pull request |
| 7 | Integrate | `/superegm:integrate <spec>` (`--close` to give up) | nothing left to escalate | the integrate review record; `closed_at` |

Nothing is merged by a machine: after a wave the owner merges the draft pull requests (or closes
what they give up on) and types the next phase. Around the phases: `/superegm:judges <question>`
convenes the judge panel by hand (advisory), `/superegm:interrupt` pauses a running wave at the
next safe point, `/superegm:clean` removes what a wave left behind locally, and
`/superegm:drift-report` checks the code against the specs after integrate.

## Modes

Every decision point pauses for the owner in normal mode. With `--leavemealone` on the
invocation, or `"mode": "leavemealone"` in `.superegm/config.json`, the four skills that reach a
decision point (`review-spec`, `review-plan`, `plan`, `wave`) ask the judge panel instead: a
contested or declined high or medium finding, a review at its cap, a blocking decision, a blocked
builder. A converged answer is applied and journaled as `Ruling (judges <id>, leavemealone): …`;
an unconverged one waits for the owner with the record. The approval of a converged spec and
"Create" in `file` are mechanical in leavemealone-mode. Merge is excluded from every mode.
