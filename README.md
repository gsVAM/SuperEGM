# SuperEGM

SuperEGM is one Claude Code plugin for the whole workflow, from an idea to a merged pull request: superpowers' unit of work (a brainstormed design, a TDD-shaped plan per unit) inside EGM's orchestration (isolated reviewers, an adversarial gate before anything is written, a dependency graph cut into waves, a foreman per unit reviewing every PR head with CI as evidence, a merge that stays human). The spec is not the plan: the spec is the design document, and the plan belongs to the GitHub issue, one per unit.

## Install

```
claude plugin marketplace add gsVAM/superegm
claude plugin install superegm@superegm
```

Disable `egm@egm-astra` and `superpowers@claude-plugins-official` first. The workflow is in [docs/getting_started.md](docs/getting_started.md).

## Before the first run

<!-- superegm:u11 -->

## Skills

- `/superegm:brainstorming` — turn an idea into a written design that ends in `## Units`
- `/superegm:draft` — draft a spec from a brief when brainstorming was skipped
- `/superegm:review-spec` — the adversarial spec review, run to convergence
- `/superegm:plan` — cut the approved spec into TDD-shaped build units
- `/superegm:review-plan` — review the plan against the spec before anything is filed
- `/superegm:file` — file the confirmed plan as GitHub issues
- `/superegm:wave` — launch, review and land a wave of units
- `/superegm:interrupt` — pause a running wave at the next safe point
- `/superegm:clean` — remove what a wave left behind locally
- `/superegm:finishing-a-development-branch` — finish a branch outside a wave, the PR as the owner
- `/superegm:integrate` — merge the landed units and close the handoff
- `/superegm:judges` — run the judge panel over a review round
- `/superegm:test-driven-development` — red, green, commit on a filed unit's branch
- `/superegm:systematic-debugging` — find the root cause before fixing
- `/superegm:verification-before-completion` — prove it works before calling it done
- `/superegm:writing-skills` — write and test a skill for this plugin
- `/superegm:using-superegm` — the dispatcher every session reads first
- `/superegm:drift-report` — check the code against the designs after `integrate`

## Licence

Apache-2.0 (`LICENSE`) for the EGM-derived files, MIT (`LICENSE-MIT`) for the superpowers-derived files; U11 lists every modified file here.
