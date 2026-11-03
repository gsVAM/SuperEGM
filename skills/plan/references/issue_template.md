<!-- Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0.
Added by the elephant-goldfish-model Astra fork (gsVAM), 2026. -->
<!-- Modified by SuperEGM (gsVAM), 2026: the section 9.1 body layout and markers replace EGM's template. -->

# The issue body

Every unit issue is rendered in this layout (the default built into
`scripts/superegm/graph.py`; a repository overrides it with `issue_template`
in `.superegm/config.json`, a file that must start with the marker line and
use every placeholder below). The plan's section 1 names the layout in use.
No run card, no model name and no reviewer name appears in any GitHub text;
those stay in the store.

## Default layout

```markdown
<!-- superegm:handoff={{handoff_id}} unit={{unit_id}} spec={{spec_sha256}} -->
# {{unit_id}} — {{title}}
Spec: `{{spec}}` @ {{sha7}} · `{{design}}`

## Objective
{{objective}}

## Interfaces
{{interfaces}}

## Definition of done
{{dod}}

## Global constraints
{{global_constraints}}

## Review focus (this unit)
{{review_focus}}

## Steps
{{steps}}

## Decide before build
{{decisions}}

## Scope, order and risk
Scope: {{scope}} · Blocked by: {{blocked_by}} · Shared files: {{shared}} · Risk: {{risk}} · Size: {{size}}
Branch: `{{branch}}` · Part of #{{tracking}}
```

The first three lines fit one phone screen; the first line is the
idempotency marker. It stays in the raw body, is invisible when rendered, and
lets a rerun of `apply` find the issue instead of creating it twice.

## Placeholders

| Placeholder | Value |
| --- | --- |
| `{{handoff_id}}`, `{{unit_id}}`, `{{spec_sha256}}` | The handoff id of the approval, the unit id, the approved spec's sha256 (`graph` refuses when no approval matches it). |
| `{{title}}` | The unit's title (the issue title is `<unit id>: <title>`). |
| `{{spec}}`, `{{sha7}}` | The spec's path relative to the repository root and the first seven hex of its sha256. |
| `{{design}}` | The unit's Design range, `path:start-end (heading)`. |
| `{{objective}}` | The objective sentence. |
| `{{interfaces}}` | The unit's `- Consumes: …` and `- Produces: …` lines, verbatim. |
| `{{dod}}` | The definition of done as a numbered list, `1. item`; numbered lists only, no checklists. |
| `{{global_constraints}}` | The plan's `## Global constraints` lines, verbatim, in every body. |
| `{{review_focus}}` | The unit's review-focus lines, verbatim. |
| `{{steps}}` | The unit's Steps text, verbatim, fences included. |
| `{{decisions}}` | The `Decide before build` lines, verbatim, with `; answer: (x)` once an unfiled unit's item is decided. |
| `{{scope}}` | The Scope paths cell, `` `path` (action) `` comma-separated. |
| `{{blocked_by}}` | `#<n>` of each blocker (a placeholder `#<U01>` until `apply` fills the number; blockers exist by then because issues are created in topological order), or `none`. |
| `{{shared}}` | The shared-file items, `after` references as `#<n>`, `before` references as the unit id and title (that issue does not exist yet when this body is posted), or `none`. |
| `{{risk}}`, `{{size}}` | From the unit. |
| `{{branch}}` | `superegm/<handoff id>/<unit id>`: the branch the builder pushes and `status` recognises. |
| `{{tracking}}` | The tracking issue's number (`<tracking>` until `apply`). |

`body_sha256` in `handoff_units.json` and `state.json` is the sha256 of this
rendered text with its `#<U01>` and `#<tracking>` placeholders, as EGM hashes
it: `apply` re-checks that hash and rewrites the placeholders as it creates
the issues; `verify` re-substitutes and compares normalised text.

## The tracking issue

The tracking issue (title from `tracking_issue_title`, default `Build:
<design title>`; labels `superegm:tracking` and the handoff label) carries
the marker `<!-- superegm:handoff=<id> unit=tracking spec=<spec sha256> -->`,
the design reference, the wave table (unit ids and titles, never numbers,
since the units do not exist yet), the critical path and the shared files.
Every unit issue is added as its sub-issue.

## Limits the scan enforces

A body over 49,152 bytes is refused with "split it". `scan` warns, without
blocking, when a body passes 32,768 bytes, twenty Steps or a fenced share of
0.40; the numbers go to `<6hex>/plan/scan/<unit>.json` for the proportion
reviewer. No checklist item, no placeholder line (`TBD`, `handle edge cases`,
`add appropriate validation`, `write tests for the above`), no Consumes no
sibling produces or whose producer is not a blocker, global constraints and
review focus present, every review-focus test in its unit's Steps, every Step
with both paths under the Scope paths and its one command, every blocking
decision answered. No banned term and no bare `@name` anywhere in the text,
code spans and fenced blocks included, because the scan is not code-aware;
no merge markers. A mention that legitimately belongs in a body is listed in
`allowed_mentions` in `.superegm/config.json` as the exact token GitHub would
resolve (for example `@types/node`; `@acme` does not cover the team
`@acme/release`). The configured `fix_request_mention` is allowed only on the
first line of a comment, never in a body.
