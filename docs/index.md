# SuperEGM

<!-- Modified by SuperEGM (gsVAM), 2026: EGM's index rewritten for SuperEGM: the intent of design section 1 and the five documents; the Codex and Harnesses entries removed. -->

SuperEGM is one Claude Code plugin that is the owner's entire software workflow, from an idea to a
merged pull request, run as one skillset. It absorbs two toolkits that each owned half of that
workflow:

- **superpowers 7.0.0** (MIT) owns the unit of work: brainstorming that ends in a written design;
  plans made of red → green → commit steps with the actual test code; exact interfaces between
  units; global constraints copied verbatim; a review focus; no placeholders.
- **EGM 0.2.1** (Apache-2.0) owns orchestration and verification: goldfish isolation enforced by
  adapters; an adversarial gate before anything is written anywhere; a second vendor's model as
  reviewer; a dependency graph cut into waves; idempotent, crash-recoverable GitHub filing; a
  foreman per unit reviewing every PR head against the unit's definition of done with CI as
  evidence; convergence with regression marking and a pausing cap; a merge that stays human.

The one distinction EGM never had: **the spec is not the plan.** The spec is the design document,
frozen at a sha256 by its approval. The plan belongs to the GitHub issue, one per unit, and is
TDD-shaped from its first line. The owner types one skill per phase; a phase typed in
leavemealone-mode runs to its gate without the owner, the judge panel ruling where the owner
would have, and the owner wakes to merge-ready draft pull requests or to the short list of
questions the judges could not settle. Nothing is merged by a machine.

## Find the right document

| Document | Purpose |
| --- | --- |
| [Getting started](getting_started.md) | Install, the by-hand setup `superegm init` prints, the eight phases in order. |
| [Claude Code](claude.md) | The platform facts the plugin relies on: adapters, hooks, headless builders, tokens, worktrees. |
| [FAQ](faq.md) | Modes, the builder account, the judges, what stays human. |
| [Privacy](privacy.md) | What leaves the machine, to GitHub and to OpenAI, and the knobs that stop it. |
| [Releases](releases.md) | Versioning, `prepare_release.py`, the archive and its checksum. |
| [Shared runtime resources](../resources/README.md) | The review standards and execution rules the runtime reads. |

`docs/` explains the system to the owner. `resources/` and each skill's `references/` hold the
rules the runtime reads; link to them rather than restating them here.
