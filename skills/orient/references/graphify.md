<!-- Added by SuperEGM (gsVAM), 2026: how orient drives graphify (spec section 9.3). -->

# graphify as orient's optional engine

`orient` looks `graphify` up on `PATH` (`shutil.which`; the CLI installs with `pipx install graphifyy`, the package's name). Absent, the extractor alone writes the files, minus `## Graph`, and the first line says `graphify: not installed`.

## The invocation

Probed against graphify 0.9.6 and pinned by `tests/unit/test_orient.py` against a fake CLI (no test runs graphify):

    GRAPHIFY_OUT=<store>/orient/graphify-out graphify update <store>/orient/export

- `graphify update <path>` re-extracts the code files under `<path>` by AST, no model call and no prompt, and writes `graph.json` (with `GRAPH_REPORT.md` and `graph.html`) under the directory `GRAPHIFY_OUT` names, the output directory itself; the export's absolute path is the one argument, the working directory is the export, the environment the caller's plus `GRAPHIFY_OUT`.
- The timeout is 600 seconds (`TIMEOUT`); a build past it is killed and the first line says `graphify: failed: timeout`.
- A non-zero exit gives `graphify: failed: <the last line of its stderr>` (`failed: exit <code>` with no stderr); a build that writes no `graph.json` gives `failed: no graph.json written`; one that is not JSON gives `failed: graph.json is not JSON`. In every failed case `## Graph` is left out and `orient` exits 0: an optional tool never blocks a launch.
- `--force` is not passed: graphify refuses to overwrite a `graph.json` when the rebuild has fewer nodes (its shrink check, which `--force` or `GRAPHIFY_FORCE=1` overrides) and runs that check only against an existing file, so `orient` removes any earlier `graph.json` before the build; every build extracts the whole export afresh and no node of another tree survives.
- `--no-cluster` is not passed: the communities come from clustering; `update` never invokes graphify's optional model-backed community naming.

## What is read from graph.json

NetworkX node-link JSON: `"nodes"`, each with `id`, `label`, `source_file` (the path graphify walked; `orient` makes it relative to the export), `source_location` (`L<line>`, `null` for a file node) and `community` (an integer id); and `"links"` (`"edges"` in older files), each with `source` and `target` (node ids), `relation`, `confidence` (`EXTRACTED`, `INFERRED` or `AMBIGUOUS`) and `confidence_score` (1.0, 0.5, 0.2). An edge whose end no node carries is dropped. The map lists the counts, the EXTRACTED share and the 40 largest communities with the five files holding most of their nodes; a unit file lists per Scope path its nodes with their communities, the EXTRACTED edges touching them (`edge`) and the other edges with their confidence (`other`). The first line names the graph by its sha256, since graphify's own build is not pinned.
