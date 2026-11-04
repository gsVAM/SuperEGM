# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the orient subcommand (spec section 9.3).

"""superegm orient: copy what the repository's own files say about a unit into the store.

An extractor, never a summarizer: the tracked tree at a ref is exported, its docstrings,
public signatures, tests and documentation sections are copied per Scope path, graphify's
`graph.json` is projected in when the CLI is on `PATH`, and each file is capped."""

import re
from pathlib import PurePosixPath


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
