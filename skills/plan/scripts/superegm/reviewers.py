# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the reviewers module: `.superegm/reviewers/*.md` loaded and checked (spec 1.2.1 section 3.6, U76).

"""superegm reviewers: the repository's custom review goldfish, `.superegm/reviewers/<id>.md` (spec 1.2.1 section 3.6)."""

from pathlib import Path
import re
import subprocess

import superegm as core

WRITES = frozenset()  # the store kinds this subcommand writes
CONFIG_DEFAULTS = {}  # no config key of its own: a file under `.superegm/reviewers/` is the setting
INIT_STEP, DOCTOR_CHECKS = "", None  # no init line of its own; its doctor line is `doctor`'s
DIR = ".superegm/reviewers"
KINDS = ("spec", "plan", "head", "integrate")
LIMIT = 8192  # the most bytes of persona a file may hold
ID_RE = re.compile(r"^[a-z][a-z0-9-]{1,31}$")
NOT_REVIEWERS = ("foreman", "judge", "cartographer", "triage")  # roles that are not reviewers: no file may take their id


def blob_sha(data: bytes) -> str:
  """git's blob sha of `data`, 12 hex."""
  from superegm import instructions
  return instructions.blob_sha(data)


def refuse(rel: str, reason: str) -> core.HandoffError:
  """The refusal for the file `rel`, naming it."""
  return core.HandoffError(f"reviewers: {rel}: {reason}")


def frontmatter(rel: str, text: str) -> tuple[dict, str]:
  """`text`'s frontmatter as `{key: value}` (a `[a, b]` value a list) and the body after it; refused when it does not open with one."""
  lines = text.split("\n")
  if not lines or lines[0].rstrip() != "---":
    raise refuse(rel, "does not open with a frontmatter block")
  try:
    end = next(i for i in range(1, len(lines)) if lines[i].rstrip() == "---")
  except StopIteration:
    raise refuse(rel, "the frontmatter is not closed by ---") from None
  fields = {}
  for line in lines[1:end]:
    if not line.strip():
      continue
    key, sep, value = line.partition(":")
    if not sep or not key.strip():
      raise refuse(rel, f"the frontmatter line {line!r} is not `key: value`")
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
      fields[key.strip()] = [v.strip().strip("'\"") for v in value[1:-1].split(",") if v.strip()]
    else:
      fields[key.strip()] = value.strip("'\"")
  return fields, "\n".join(lines[end + 1:])


def parse(rel: str, data: bytes) -> dict:
  """The reviewer the file `rel` holds, `{id, name, kinds, model, effort, text, sha}`; refused naming `rel` and the reason."""
  stem = Path(rel).stem
  if not ID_RE.match(stem):
    raise refuse(rel, f"the id {stem!r} does not match [a-z][a-z0-9-]{{1,31}}")
  if stem in NOT_REVIEWERS:
    raise refuse(rel, f"{stem} is not a reviewer and cannot be overridden")
  try:
    text = data.decode("utf-8")
  except UnicodeDecodeError:
    raise refuse(rel, "is not UTF-8") from None
  fields, body = frontmatter(rel, text)
  name = fields.get("name")
  if not isinstance(name, str) or not name:
    raise refuse(rel, "name is required")
  kinds = fields.get("kinds")
  if not isinstance(kinds, list) or not kinds or not set(kinds) <= set(KINDS):
    raise refuse(rel, f"kinds must be a non-empty list from {', '.join(KINDS)}")
  model, effort = fields.get("model"), fields.get("effort")
  if model is not None and (not isinstance(model, str) or not core.MODEL_RE.match(model)):
    raise refuse(rel, f"model {model!r} is not a model alias")
  if effort is not None and effort not in core.EFFORTS:
    raise refuse(rel, f"effort {effort!r} is not one of {', '.join(core.EFFORTS)}")
  size = len(body.encode("utf-8"))
  if size > LIMIT:
    raise refuse(rel, f"the persona is {size} bytes, over {LIMIT}")
  return {"id": stem, "name": name, "kinds": kinds, "model": model, "effort": effort, "text": body, "sha": blob_sha(data)}


def load(root: Path, ref: str | None = None) -> dict[str, dict]:
  """`{id: {name, kinds, model, effort, text, sha}}` from `.superegm/reviewers/*.md` under `root`, or at `ref` when given;
  the first bad file is refused, naming it and the reason."""
  found = {}
  if ref is None:
    for path in sorted((root / DIR).glob("*.md")):
      rel = f"{DIR}/{path.name}"
      if path.is_file():
        found[Path(rel).stem] = {k: v for k, v in parse(rel, path.read_bytes()).items() if k != "id"}
    return found
  with core.hook_free() as pairs:
    listed = subprocess.run(["git", *pairs, "ls-tree", "-z", "--name-only", ref, f"{DIR}/"], cwd=str(root), capture_output=True)
  from superegm import instructions
  for rel in sorted(n for n in listed.stdout.decode("utf-8", "replace").split("\0") if n.endswith(".md")):
    data = instructions.blob(root, ref, rel)
    if data is not None:
      found[Path(rel).stem] = {k: v for k, v in parse(rel, data).items() if k != "id"}
  return found
