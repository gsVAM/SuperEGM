<!-- From superpowers 7.0.0 (MIT); modified by SuperEGM (gsVAM), 2026: moved verbatim from SKILL.md's Triage section (U83). -->

# The Triage section

The fields of a `## Triage` pattern, and an example. Every field is one of:

- `reach` (`external`, `agent`, `config` or `forged`): can an HTTP caller,
  an agent action or a plausible configuration mistake trigger it, or only
  a hand-forged in-process object?
- `later` (`easy`, `migration` or `version`): easy to fix later, or does
  the fix need a migration or a new declaration version?
- `critical` (`yes` or `no`): on the critical path with serious
  ramifications?
- `verified` (`confirmed` or `refuted`): the triager found the defect, or
  found none.

```markdown
## Triage

Unblock:
- reach: forged, later: easy
- critical: no, later: easy, verified: confirmed
```
