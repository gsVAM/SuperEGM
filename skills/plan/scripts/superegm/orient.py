# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the orient subcommand (spec section 9.3); doctor's `graphify:` line as its DOCTOR_CHECKS (U32).

"""superegm orient: copy what the repository's own files say about a unit into the store.

An extractor, never a summarizer: the tracked tree at a ref is exported, its docstrings,
public signatures, tests and documentation sections are copied per Scope path, graphify's
`graph.json` is projected in when the CLI is on `PATH`, and each file is capped."""

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
import tarfile
from pathlib import Path, PurePosixPath

import superegm as core

WRITES = frozenset(["orient", "orient_unit"])  # the store kinds this subcommand writes
SKILLS = frozenset(["orient", "plan", "review-plan", "wave"])  # the skills whose card this subcommand accepts
CAP_UNIT, CAP_MAP, MAP_DEPTH = 16_384, 24_576, 4
GRAPHIFY = "graphify"  # the command looked up on PATH; tests point it at a fake
TIMEOUT = 600  # seconds for one graphify build
CONFIG_DEFAULTS, INIT_STEP = {}, ""


def DOCTOR_CHECKS(config, repo_root, token):  # noqa: N802 (the registration name, U32)
  """doctor's informational `graphify:` line: the CLI on PATH, or none."""
  path = shutil.which("graphify")
  return [("graphify", f"ok ({path})" if path else "not on PATH (informational)")]
DOCS = ("README.md", "AGENTS.md", "CLAUDE.md", "context.md")
SKIPPED = {"dist", "build", "vendor", "target", "scratchpad"}
TEST_RE = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]+$|[_.](test|spec)\.[^/.]+$|(^|/)conftest\.py$")  # a test file by name, wherever it lives
JS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
MAX_BYTES = 1 << 20
HEADING_RE = re.compile(r"^#{1,6} +(.*?)\s*$")
ENTRY_RE = re.compile(r"^(__init__\.py|__main__\.py|main\..+|index\..+|mod\.rs)$")


def tokens(path: str):
  """(path, basename, directory, dotted name) of a Scope path, empties where none: the dotted
  name of an `__init__.py` is its package name, a non-Python path has none."""
  p = PurePosixPath(path.rstrip("/"))
  directory = "" if p.parent.as_posix() == "." else p.parent.as_posix()
  dotted = ""
  if p.suffix == ".py":
    dotted = p.parent.name if p.name == "__init__.py" else ".".join(filter(None, [directory.replace("/", "."), p.stem]))
  return p.as_posix(), p.name, directory, dotted


def names(path: str) -> list[str]:
  """The tokens a text may name the path by, repeats dropped; a text names a path when any
  token matches as a whole word."""
  return list(dict.fromkeys(t for t in tokens(path) if t))


def named(text: str, tokens: list[str]) -> bool:
  return any(re.search(r"\b" + re.escape(t) + r"\b", text) for t in tokens)


# ---------------------------------------------------------------- the export


def export_tree(repo_root: Path, ref: str, store) -> str:
  """The tracked files at `ref` into the store's `orient/export/` (emptied first) through one
  `git archive`, regular files and directories only; returns the tree's sha."""
  tree = core.run_git(["rev-parse", "--verify", f"{ref}^{{tree}}"], repo_root, check=False).strip()
  if not tree:
    raise core.HandoffError(f"orient: ref {ref} is not in this repository")
  export, tar = store.path("orient", "export"), store.path("orient", "export.tar")
  shutil.rmtree(export, ignore_errors=True)
  export.mkdir(parents=True)
  core.run_git(["archive", "--format=tar", "-o", str(tar), ref], repo_root)
  with tarfile.open(tar) as archive:
    archive.extractall(export, members=[m for m in archive.getmembers() if m.isfile() or m.isdir()], filter="data")
  tar.unlink()
  return tree


def walk(root: Path, skip=False) -> list[str]:
  """Every regular file under `root`, posix paths relative to it, sorted; symlinks are not
  followed; `skip` leaves the map's skipped directories and everything under them out."""
  found = []
  for folder, dirs, files in os.walk(root):
    dirs[:] = [d for d in dirs if not (skip and d in SKIPPED) and not Path(folder, d).is_symlink()]
    rel = Path(folder).relative_to(root).as_posix()
    found += [f if rel == "." else f"{rel}/{f}" for f in files if Path(folder, f).is_file() and not Path(folder, f).is_symlink()]
  return sorted(found)


def read(path: Path):
  """Best effort: None when the path is not a regular file, "" over 1 MB, else its text."""
  if path.is_symlink() or not path.is_file():
    return None
  return "" if path.stat().st_size > MAX_BYTES else path.read_text(encoding="utf-8", errors="replace")


def signatures(rel: str, text: str) -> list[str]:
  """Public `def`/`class` lines for Python (none on a SyntaxError), `export ` lines for JS/TS,
  the first 40 lines otherwise."""
  suffix = PurePosixPath(rel).suffix
  if suffix == ".py":
    try:
      tree = ast.parse(text)
    except (SyntaxError, ValueError):
      return []
    source, out = text.splitlines(), []

    def visit(body):
      for node in body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
          out.append(source[node.lineno - 1])
          if isinstance(node, ast.ClassDef):
            visit(node.body)
    visit(tree.body)
    return out
  if suffix in JS:
    return [l for l in text.splitlines() if l.startswith("export ")]
  # A copied line never opens a section of the unit file: a leading space keeps `#` lines as text.
  return [" " + l if l.startswith("#") else l for l in text.splitlines()[:40]]


def docstring(rel: str, text: str) -> list[str]:
  """The first paragraph of a Python module's docstring, as lines."""
  if PurePosixPath(rel).suffix != ".py":
    return []
  try:
    doc = ast.get_docstring(ast.parse(text))
  except (SyntaxError, ValueError):
    doc = None
  return (doc or "").split("\n\n")[0].strip().splitlines()


def siblings(export: Path, rel: str) -> list[str]:
  """The files of the same extension in the path's own directory, sorted; none where the
  directory does not exist."""
  p = PurePosixPath(rel)
  folder = export / p.parent
  if not folder.is_dir():
    return []
  return sorted(f"{p.parent}/{f}" if str(p.parent) != "." else f
                for f in os.listdir(folder) if PurePosixPath(f).suffix == p.suffix and (folder / f).is_file() and not (folder / f).is_symlink())


# ---------------------------------------------------------------- graphify's graph.json


def build_graph(export: Path, out: Path):
  """graphify's headless `update` over the export with `GRAPHIFY_OUT` naming `out`, any
  earlier `graph.json` removed first (so its shrink check never trips and `--force` is not
  needed); (the graph, its sha256), or (None, `not installed` | `failed: <reason>`)."""
  out = Path(out)
  out.mkdir(parents=True, exist_ok=True)
  (out / "graph.json").unlink(missing_ok=True)
  exe = shutil.which(GRAPHIFY)
  if not exe:
    return None, "not installed"
  try:
    run = subprocess.run([exe, "update", str(Path(export).resolve())], cwd=export, env={**os.environ, "GRAPHIFY_OUT": str(out)},
                         capture_output=True, text=True, timeout=TIMEOUT)
  except subprocess.TimeoutExpired:
    return None, "failed: timeout"
  if run.returncode != 0:
    last = (run.stderr.strip().splitlines() or [""])[-1]
    return None, f"failed: {last or f'exit {run.returncode}'}"
  if not (out / "graph.json").is_file():
    return None, "failed: no graph.json written"
  try:
    graph = json.loads((out / "graph.json").read_text(encoding="utf-8", errors="replace"))
  except ValueError:
    return None, "failed: graph.json is not JSON"
  return graph, hashlib.sha256((out / "graph.json").read_bytes()).hexdigest()


def nodes_of(graph: dict, export: Path) -> dict:
  """id -> node with `source_file` relative to the export (graphify writes the path it walked)."""
  root = str(Path(export).resolve()) + "/"
  nodes = {}
  for node in graph.get("nodes") or []:
    file = str(node.get("source_file") or "")
    file = file[len(root):] if file.startswith(root) else file.removeprefix("./")
    nodes[node.get("id")] = {**node, "source_file": file}
  return nodes


def edges_of(graph: dict, nodes: dict) -> list:
  """`links` (`edges` when absent) in order, ends read from `source` and `target`; an edge
  whose end no node carries is dropped."""
  links = graph.get("links") if "links" in graph else graph.get("edges")
  return [e for e in links or [] if e.get("source") in nodes and e.get("target") in nodes]


def end(node: dict) -> str:
  """`label (file:loc)`; a node with no file (a symbol defined outside the export) is its label alone."""
  loc = node.get("source_location")
  if not node["source_file"]:
    return f"{node.get('label')}"
  return f"{node.get('label')} ({node['source_file']}:{loc})" if loc else f"{node.get('label')} ({node['source_file']})"


def under(file: str, path: str) -> bool:
  rel = path.rstrip("/")
  return file == rel or file.startswith(rel + "/")


def graph_section(path: str, scope, nodes: dict, edges: list) -> list:
  """`## Graph: <path>`: its nodes, then the EXTRACTED edges touching them, then the other
  edges with their confidence; edges whose `source` is in the section first, then `target`."""
  mine = {i: n for i, n in nodes.items() if under(n["source_file"], path)}
  order = sorted(mine, key=lambda i: (mine[i]["source_file"], int((re.search(r"\d+", str(mine[i].get("source_location") or "")) or [10**9])[0]) if mine[i].get("source_location") else 10**9, str(i)))
  lines = [(None, f"## Graph: {path}")]
  if not mine:
    return lines + [(None, "none")]
  lines += [("graph-nodes", f"node {end(mine[i])} community {mine[i].get('community')}") for i in order]
  for extracted in (True, False):
    for key in ("source", "target"):
      for e in edges:
        if ((e.get("confidence") or "EXTRACTED") == "EXTRACTED") != extracted or e[key] not in mine or (key == "target" and e["source"] in mine):
          continue
        src, tgt = nodes[e["source"]], nodes[e["target"]]
        inside = all(any(under(n["source_file"], p) for p, _ in scope) for n in (src, tgt))
        head = f"edge {e.get('relation')}" if extracted else f"other {e.get('confidence')} {e.get('confidence_score')} {e.get('relation')}"
        lines.append(("graph-inside" if inside else "graph-outside", f"{head} {end(src)} -> {end(tgt)}"))
  return lines


def graph_summary(nodes: dict, edges: list, limit: int) -> list[str]:
  """`## Graph`: the counts and the `limit` largest communities by node count (ties by id),
  each with up to five files holding most of its nodes (ties by path); a node with no file counts
  toward its community but names no file."""
  by_community = {}
  for node in nodes.values():
    if node.get("community") is not None:
      by_community.setdefault(node["community"], []).append(node["source_file"])
  extracted = sum((e.get("confidence") or "EXTRACTED") == "EXTRACTED" for e in edges)
  lines = [f"nodes {len(nodes)} · edges {len(edges)} · communities {len(by_community)} · extracted {extracted}/{len(edges)}"]
  for cid in sorted(by_community, key=lambda c: (-len(by_community[c]), str(c)))[:limit]:
    files = by_community[cid]
    top = sorted({f for f in files if f}, key=lambda f: (-files.count(f), f))[:5]
    lines.append(f"community {cid}: {len(files)} nodes · {', '.join(top)}")
  return lines


# ---------------------------------------------------------------- the unit file


def file_section(export: Path, rel: str, action: str, level: str, tests: dict) -> list:
  """`## <path> (<action>)`, then an existing file's docstring and signatures (trim level
  `level`), or an absent file's siblings' signatures, then the tests that name it."""
  lines = [(None, f"## {rel} ({action})")]
  text = read(export / rel)
  if text is None:
    sibs = siblings(export, rel)
    lines.append(("siblings", "siblings: " + (", ".join(sibs) or "none")))
    for s in sibs:
      lines.append(("siblings", f"### {s}"))
      lines += [("siblings", l) for l in signatures(s, read(export / s) or "")]
  else:
    lines += [(level, l) for l in docstring(rel, text) + signatures(rel, text)]
  path, base, _, dotted = tokens(rel)
  naming = [t for t, body in tests.items() if named(body, [t for t in (path, base, dotted) if t])]
  lines.append(("tests", "tests: " + (", ".join(naming) or "none")))
  return lines


def path_section(export: Path, path: str, action: str, tests: dict) -> list:
  """A directory path contributes each file under it; every file of one Scope path shares
  the trim level `signatures:<path>`."""
  rel, level = path.rstrip("/"), f"signatures:{path}"
  if (export / rel).is_dir():
    return [l for f in walk(export / rel) for l in file_section(export, f"{rel}/{f}", action, level, tests)]
  return file_section(export, rel, action, level, tests)


def sections(text: str):
  """(heading text or None, body lines) per heading-delimited section; the text before the
  first heading comes first with no heading."""
  heading, body = None, []
  for line in text.splitlines():
    match = HEADING_RE.match(line)
    if match:
      yield heading, body
      heading, body = match.group(1), []
    else:
      body.append(line)
  yield heading, body


def read_first(export: Path, scope) -> list:
  """Every section of the four documentation files at the root and in the Scope paths' own
  directories (walking up to, excluding, the root) that names a Scope path, verbatim, each
  file once."""
  toks = list(dict.fromkeys(t for path, _ in scope for t in names(path)))
  folders = [""]
  for path, _ in scope:
    rel = path.rstrip("/")
    own = PurePosixPath(rel) if (export / rel).is_dir() else PurePosixPath(rel).parent
    while str(own) != "." and own.as_posix() not in folders:
      folders.append(own.as_posix())
      own = own.parent
  files = [f"{d}/{n}" if d else n for d in folders for n in DOCS if (export / d / n).is_file()]
  lines = []
  for rel in files:
    for heading, body in sections(read(export / rel) or ""):
      while body and not body[0].strip():
        body.pop(0)
      while body and not body[-1].strip():
        body.pop()
      if named("\n".join([heading or "", *body]), toks):
        lines.append(("read-first", f"### {rel} · {heading}" if heading else f"### {rel}"))
        lines += [("read-first", l) for l in body]
  return [("read-first", "## Read first"), *lines] if lines else []


def render(lines, tree: str, token: str, trimmed: list[str], dropped) -> str:
  first = f"orient: tree {tree} · graphify: {token} · trimmed: {', '.join(trimmed) or 'nothing'}"
  return "\n".join([first, *[text for level, text in lines if level not in dropped]]) + "\n"


def unit_text(export: Path, scope: list[tuple[str, str]], graph, tree: str, token: str) -> str:
  """`<6 hex>/orient/<unit>.md`: one section per Scope path, the graph's projection per
  path, then `## Read first`; a function of the export, the graph and the scope."""
  export = Path(export)
  tests = {f: read(export / f) or "" for f in walk(export, skip=True) if TEST_RE.search(f)}
  lines = [l for path, action in scope for l in path_section(export, path, action, tests)]
  if graph is not None:
    nodes = nodes_of(graph, export)
    edges = edges_of(graph, nodes)
    lines += [l for path, _ in scope for l in graph_section(path, scope, nodes, edges)]
  lines += read_first(export, scope)
  levels = ["tests", "siblings", "read-first", "graph-outside", "graph-inside", "graph-nodes", *(f"signatures:{p}" for p, _ in scope)]
  present, dropped = {level for level, _ in lines}, []
  text = render(lines, tree, token, dropped, set())
  for level in levels:  # the trimming sequence, a level recorded only when it removed something
    if len(text.encode("utf-8")) <= CAP_UNIT:
      break
    if level in present:
      dropped.append(level)
      text = render(lines, tree, token, dropped, set(dropped))
  return text


# ---------------------------------------------------------------- the map


def doc_summary(text: str) -> str:
  """The first heading text, else the first non-blank line up to its first `. `, or the whole line."""
  for line in text.splitlines():
    match = HEADING_RE.match(line)
    if match:
      return match.group(1)
  return next((l.strip().split(". ")[0] for l in text.splitlines() if l.strip()), "")


def map_lines(export: Path, depth: int) -> list[str]:
  """One line per directory to `depth` over the tracked files: path, file count, dominant
  extension (ties by name), entry points, the documentation files' summaries (≤ 160 chars)."""
  stats = {".": {"count": 0, "exts": {}, "own": []}}
  for f in walk(export, skip=True):
    p = PurePosixPath(f)
    for folder in (".", *(a.as_posix() for a in reversed(p.parents) if a.as_posix() != ".")):
      if folder != "." and folder.count("/") + 1 > depth:
        break
      st = stats.setdefault(folder, {"count": 0, "exts": {}, "own": []})
      st["count"] += 1
      st["exts"][p.suffix] = st["exts"].get(p.suffix, 0) + 1
      if folder == str(p.parent):
        st["own"].append(p.name)
  lines = []
  for folder, st in sorted(stats.items()):
    dominant = min(st["exts"], key=lambda e: (-st["exts"][e], e)) if st["exts"] else ""
    entries = [n for n in sorted(st["own"]) if ENTRY_RE.match(n)]
    docs = "; ".join(f"{n}: {doc_summary(read(export / folder / n) or '')}" for n in DOCS if n in st["own"])[:160]
    lines.append(f"{folder} | {st['count']} files | {dominant or '-'} | {', '.join(entries) or '-'} | {docs or '-'}")
  return lines


def map_text(export: Path, graph, tree: str, token: str) -> str:
  """`orient/map.md`: the graph's summary when there is one, then the repository map; the
  community list is cut to what fits beside the map, then the depth is reduced until it fits."""
  export = Path(export)
  counts, communities = [], []
  if graph is not None:
    nodes = nodes_of(graph, export)
    counts, *communities = graph_summary(nodes, edges_of(graph, nodes), 40)
  kept, depth = len(communities), MAP_DEPTH

  def build():
    cut = ([f"communities {kept}"] if kept < len(communities) else []) + ([f"depth {depth}"] if depth < MAP_DEPTH or kept < len(communities) else [])
    first = f"orient: tree {tree} · graphify: {token} · trimmed: {', '.join(cut) or 'nothing'}"
    head = ["## Graph", counts, *communities[:kept]] if graph is not None else []
    return "\n".join([first, *head, "## Map", *rows]) + "\n"

  rows = map_lines(export, depth)
  text = build()
  while len(text.encode("utf-8")) > CAP_MAP and kept > 0:
    kept -= 1
    text = build()
  while len(text.encode("utf-8")) > CAP_MAP and depth > 0:
    depth -= 1
    rows = map_lines(export, depth)
    text = build()
  return text


# ---------------------------------------------------------------- the subcommand


def register(subparsers):
  p = core.add_parser(subparsers, "orient", "copy what the repository says about the units into the store")
  p.add_argument("--spec", dest="design", required=True, help="the approved spec whose handoff the units belong to")
  p.add_argument("--unit", dest="units", action="append", default=[], help="write this unit's file only (repeatable)")
  p.add_argument("--ref", default="HEAD", help="the tree to read (default HEAD)")
  p.set_defaults(run=run, writes=WRITES)


def stored_plan(store):
  """The store's `handoff_plan.md` parsed; None without a handoff or the file."""
  return core.parse_plan(store.path("plan")) if store.handoff_id and store.path("plan").is_file() else None


def scope_of(plan, unit: str):
  """The unit's Scope paths; the refusal when its section is not in the stored plan."""
  if plan is None or unit not in plan.units:
    raise core.HandoffError(f"orient: {unit} is not in the plan: run graph --plan first")
  return plan.units[unit].scope


def orient_unit(store, repo_root: Path, ref: str, unit: str) -> Path:
  """One unit's file, written in process for `launch-builder`: the plan check, then the export
  (its ref check first), then the graph build, so a refusal leaves no fresh export and runs no
  graphify; returns the file's path."""
  scope = scope_of(stored_plan(store), unit)
  tree = export_tree(repo_root, ref, store)
  export = store.path("orient", "export")
  graph, token = build_graph(export, store.path("orient", "graphify-out"))
  path = store.path("orient_unit", f"{unit}.md")
  core.atomic_write(path, unit_text(export, scope, graph, tree, token))
  return path


def run(args) -> int:
  core.require_runcard(args, SKILLS)
  repo_root = core.git_toplevel(Path.cwd())
  st = core.store(repo_root)
  state = core.load_state(st.root)
  plan = stored_plan(st)
  units = list(args.units)
  if not units and plan is not None and not state.get("closed_at"):
    units = [u for u in plan.order if not (state.get("units") or {}).get(u, {}).get("number")]
  scopes = {u: scope_of(plan, u) for u in units}  # every refusal before the export
  tree = export_tree(repo_root, args.ref, st)
  export = st.path("orient", "export")
  graph, token = build_graph(export, st.path("orient", "graphify-out"))
  written = [] if args.units else [st.path("orient", "map.md")]
  for path in written:
    core.atomic_write(path, map_text(export, graph, tree, token))
  for unit, scope in scopes.items():
    path = st.path("orient_unit", f"{unit}.md")
    core.atomic_write(path, unit_text(export, scope, graph, tree, token))
    written.append(path)
  core.journal(st, f"orient {args.ref} tree {tree} graphify {token}: {len(written)} files")
  for path in written:
    print(f"{path} {path.stat().st_size}")
  return 0
