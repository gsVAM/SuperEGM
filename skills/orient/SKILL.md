---
name: orient
license: Apache-2.0
effects: external
effect_kinds: [state-store]
disable-model-invocation: true
description: Copies what the repository's own files say about a unit into the store, an extractor that never summarizes.
---

<!-- Added by SuperEGM (gsVAM), 2026: the orient skill (spec section 9.3). -->

# orient

In Claude Code or Cowork, read `${CLAUDE_PLUGIN_ROOT}/docs/claude.md` first.

    /superegm:orient <spec-path> [--unit U<id>]... [--ref <ref>]

## What it does

An extractor, never a summarizer: a helper subcommand with no model call that copies what the repository's own files say and invents nothing. It exports the tracked files at `--ref` (default `HEAD`) with one `git archive` into the store's `orient/export/`, so an uncommitted edit, an untracked or an ignored file never reaches it, and writes:

- `orient/map.md`: one line per directory to depth 4 (path, file count, dominant extension, entry points, the first heading of any `README.md`, `AGENTS.md`, `CLAUDE.md` or `context.md`), after graphify's community summary when that CLI is installed; 24,576 bytes at most.
- `<6 hex>/orient/<unit>.md`, one per unit: for every Scope path its module docstring, public signatures and the tests under `tests/` that name it (a path to be created: its siblings' signatures), the `## Graph` projection of graphify's `graph.json` per path, then `## Read first`, every section of those four documentation files (at the root and up the Scope paths' directories) that names the unit, verbatim; 16,384 bytes at most, trimmed in the design's sequence.

Each file's first line records the tree, the graph and the cuts: `orient: tree <sha> · graphify: <graph.json sha256 | not installed | failed: <reason>> · trimmed: <what | nothing>`. Without `--unit` it writes the map and, when a handoff is open, every unfiled unit's file; with `--unit` the named units' files only, never the map. graphify is optional: `references/graphify.md` says how it is invoked and what is read from `graph.json`; absent, failing or timing out, the extractor alone writes the files minus `## Graph`.

The phases run it themselves (`plan` before drafting and after every `graph`, `review-plan` when it starts and per re-rendered unit, `launch-builder` in process for every builder prompt's `# Orient` section); typed by hand it is for your own reading, and every effect refuses without an open run card.

1. Open the card on the spec: `superegm runcard open --skill orient --artifact '<spec>'`; it prints `<id>`.
2. Run `superegm orient --spec '<spec>' [--unit U<id>]... [--ref <ref>] --runcard '<id>'` through the helper, `python3 '${CLAUDE_PLUGIN_ROOT}/skills/plan/scripts/superegm.py'`. It prints one line per file written, `<store path> <bytes>`, and exits 0, or 1 with `orient: <reason>`: a unit whose section is not in the store's `handoff_plan.md` (run `graph --plan` first), a ref the repository does not hold, or a card that is not an open `orient`, `plan`, `review-plan` or `wave` card on this spec.
3. Close the card: `superegm runcard close '<id>'`.

Every read is best-effort (`errors="replace"`), files over 1 MB are skipped, symlinks are not followed; the store's files are never under the working tree and never committed.
