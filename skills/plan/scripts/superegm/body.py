# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by the elephant-goldfish-model Astra fork (gsVAM), 2026.
# Modified by SuperEGM (gsVAM), 2026: the issue-body parsers of spec section 9.1; EGM's `fill_numbers` and `normalise` moved here.

"""The unit issue body (spec section 9.1) read back: its marker, its DoD items,
its Steps' commands and paths, and the interfaces it consumes."""

import re

MARKER_RE = re.compile(r"^<!-- superegm:handoff=(\S+) unit=(\S+) spec=(\S+) -->")
DECISION_HEADING = "**Decision {id}:**"
ITEM_RE = re.compile(r"^(\d+)\. (.+?)\s*$")
STEP_RE = re.compile(r"^(\d+)\. Write the failing test\b")
RUN_RE = re.compile(r"^\s*Run `([^`]+)`")
SPAN_RE = re.compile(r"`([^`]+)`")
CONSUMES_RE = re.compile(r"^- Consumes: (.+) \((U\d{2,})\)\s*$")


def sections(body: str) -> dict:
  """`## <heading>` -> its lines (the text before the first heading is under "")."""
  found, heading = {"": []}, ""
  for line in body.splitlines():
    if line.startswith("## "):
      heading = line[3:].strip()
      found[heading] = []
    else:
      found[heading].append(line)
  return found


def steps(body: str) -> list:
  """Each Step's lines, from its `<n>. Write the failing test` line to the next."""
  groups = []
  for line in sections(body).get("Steps", []):
    match = STEP_RE.match(line)
    if match:
      groups.append((int(match.group(1)), [line]))
    elif groups:
      groups[-1][1].append(line)
  return groups


def run_commands(body: str) -> list:
  commands = [text for _, kind, text in dod_items(body) if kind == "run"]
  for _, lines in steps(body):
    first = next((RUN_RE.match(l) for l in lines if RUN_RE.match(l)), None)
    if first:
      commands.append(first.group(1))
  return commands


def step_paths(body: str) -> list:
  """(step, test path, implementation path): the second span of the Step's first
  line and the last span of its `Implement` line."""
  found = []
  for number, lines in steps(body):
    spans = SPAN_RE.findall(lines[0])
    implement = next((l for l in lines[1:] if l.strip().startswith("Implement ")), "")
    targets = SPAN_RE.findall(implement)
    found.append((number, spans[1] if len(spans) > 1 else None, targets[-1] if targets else None))
  return found


def dod_items(body: str) -> list:
  """Items 2.. of the Definition of done as (n, run|exists|ci|other, text)."""
  found = []
  for line in sections(body).get("Definition of done", []):
    match = ITEM_RE.match(line)
    if not match or int(match.group(1)) == 1:
      continue
    number, item = int(match.group(1)), match.group(2)
    if item.startswith("Run `"):
      found.append((number, "run", SPAN_RE.match(item[4:]).group(1)))
    elif item.startswith("Exists `"):
      found.append((number, "exists", SPAN_RE.match(item[7:]).group(1)))
    elif re.search(r"\bCI\b", item):
      found.append((number, "ci", item))
    else:
      found.append((number, "other", item))
  return found


def consumes(body: str) -> list:
  """(name, unit) per `- Consumes:` line; a Python name is cut at its `(`."""
  found = []
  for line in sections(body).get("Interfaces", []):
    match = CONSUMES_RE.match(line)
    if match:
      name = match.group(1)
      found.append((name.split("(", 1)[0].strip() if "(" in name else name.strip(), match.group(2)))
  return found


def fill_numbers(body: str, numbers: dict, tracking=None) -> str:
  def replace(match):
    key = match.group(1)
    if key == "tracking":
      return f"#{tracking}" if tracking else match.group(0)
    return f"#{numbers[key]}" if key in numbers else match.group(0)
  return re.sub(r"#<([A-Za-z0-9]+)>", replace, body)


def normalise(body: str) -> str:
  return "\n".join(line.rstrip() for line in body.replace("\r\n", "\n").split("\n")).strip("\n")
