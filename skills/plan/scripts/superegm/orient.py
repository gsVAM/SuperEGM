# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the orient subcommand (spec section 9.3).

"""superegm orient: copy what the repository's own files say about a unit into the store.

An extractor, never a summarizer: the tracked tree at a ref is exported, its docstrings,
public signatures, tests and documentation sections are copied per Scope path, graphify's
`graph.json` is projected in when the CLI is on `PATH`, and each file is capped."""

import ast
import os
import re
from pathlib import Path, PurePosixPath

CAP_UNIT, CAP_MAP, MAP_DEPTH = 16_384, 24_576, 4
DOCS = ("README.md", "AGENTS.md", "CLAUDE.md", "context.md")
SKIPPED = {"dist", "build", "vendor", "target", "scratchpad"}
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
  tests = {f: read(export / f) or "" for f in walk(export, skip=True) if f.startswith("tests/")}
  lines = [l for path, action in scope for l in path_section(export, path, action, tests)]
  lines += read_first(export, scope)
  return render(lines, tree, token, [], set())


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
  files = walk(export, skip=True)
  folders = sorted({".", *(str(a) for f in files for a in PurePosixPath(f).parents if str(a) != ".")})
  lines = []
  for folder in folders:
    if folder != "." and folder.count("/") + 1 > depth:
      continue
    under = files if folder == "." else [f for f in files if f.startswith(folder + "/")]
    exts = {}
    for f in under:
      exts[PurePosixPath(f).suffix] = exts.get(PurePosixPath(f).suffix, 0) + 1
    dominant = min(exts, key=lambda e: (-exts[e], e)) if exts else ""
    own = [PurePosixPath(f).name for f in under if str(PurePosixPath(f).parent) == folder]
    entries = [n for n in sorted(own) if ENTRY_RE.match(n)]
    docs = "; ".join(f"{n}: {doc_summary(read(export / folder / n) or '')}" for n in DOCS if n in own)[:160]
    lines.append(f"{folder} | {len(under)} files | {dominant or '-'} | {', '.join(entries) or '-'} | {docs or '-'}")
  return lines


def map_text(export: Path, graph, tree: str, token: str) -> str:
  """`orient/map.md`: the graph's summary when there is one, then the repository map."""
  export = Path(export)
  first = f"orient: tree {tree} · graphify: {token} · trimmed: nothing"
  return "\n".join([first, "## Map", *map_lines(export, MAP_DEPTH)]) + "\n"
