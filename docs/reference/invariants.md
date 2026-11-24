<!-- Added by SuperEGM (gsVAM), 2026: the 1.3 brainstorm's reference document, the rules every agent of a SuperEGM build carries (1.3 design sections 2, 3.1, 3.7, 6). -->

# Invariants

These rules hold for every change to this repository. A builder follows them, the foreman checks
them, and reviewers and judges treat a break of one as a finding. Where a spec and this file
differ, the spec wins and this file is out of date: say so in a finding.

## Every changed file says so

- Every file a unit creates or changes carries a provenance header at its top, tests included.
- A new file gets `Added by SuperEGM (gsVAM), 2026: <what>`.
- A changed file gets its `<what>` appended to its existing `Modified by SuperEGM (gsVAM), 2026: …`
  line, or gets that line if it has none.
- `<what>` names the unit and the spec section: for example `U104's owner-only spec findings
  (1.3 design section 3.8)`.
- Python and YAML use a `#` comment, Markdown an HTML comment, as the files around it do.
- The header keeps the file's existing copyright and `From …` lines unchanged.

## The store

- The helper (`skills/plan/scripts/superegm/`) is the only writer of the store. A skill or an
  agent never writes a file under `artifacts_dir` itself.
- A subcommand writes only the store kinds it declares in its `WRITES`.
- A command that reads a store file, changes it and writes it back does so within one short
  step: it never holds a loaded copy across a wait and writes it back afterwards.
- A store written by 1.2.1 opens unchanged. A new key or file reads as absent when missing; no
  migration step is needed.

## Builders

- One command per Bash call. No pipes, `;`, `&&`, `||` or heredocs.
- Comments and PR bodies are written to a file with Write, then posted with one
  `gh … --body-file <file>` call.
- The check for an existing PR is `gh pr view <branch>`.
- A Step whose test passes before any change is a deviation the builder posts. It is never
  committed as an empty `feat` commit.
- Nothing outside the unit's Scope is changed. A stale neighbouring file is reported, not fixed.

## Security

- No change widens what an unattended builder may run: no new allow-list entry with a broader
  prefix, no unrestricted `Bash`, no bare `Skill`.
- Text from a GitHub comment or review reaches a builder's prompt only from the authors its form
  allows: the builder's identity for Seam, the builder or `config.owners` for Deviation, and
  `config.owners` for Decision, Ruling, Note and pull-request reviews. An edited comment or review
  never reaches it.
- Nothing the helper sends off the machine (the Astra lane, the Codex judge) goes unlisted in
  `docs/privacy.md` and `resources/astra_lane.md`.
- No secret, token or key value is ever printed, journaled or written to the store. Name the
  variable, never its value.

## Tests

- Standard library only in the helper. No new dependency in the helper or its tests.
- A test never calls GitHub or a model. It uses the test world's fakes, as the existing tests do.
- A behaviour the spec fixes is pinned with the spec's exact values.
