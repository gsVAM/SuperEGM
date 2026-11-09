# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: the builder transcript reader
# `trace_directory` and `assert_child_probe` moved from tests/integration/test_claude.py (Copyright 2026 Google LLC,
# Apache-2.0); modified by SuperEGM (gsVAM), 2026: `trace_directory` takes the profile directory first.

"""The builder's session transcript under its profile (U27): the platform's default subagents a launch spawned
through the `Agent` tool, read at the exit onto the launch entry as `subagent_calls`; the transcript directory and
the native child probe the integration probe checks. Defines no subcommand."""

import json
from datetime import datetime
from pathlib import Path


def trace_directory(profile_dir: Path, workspace: Path) -> Path:
  """Locates native transcripts under Claude's configured directory."""
  config = Path(profile_dir)
  project = "".join(c if c.isalnum() else "-" for c in str(workspace.resolve()))
  return config / "projects" / project


def assert_child_probe(
    raw: str, persona: Path, markers: list[str], deny_persona: bool = False,
) -> None:
  """Check the native child's answer, tool restrictions, and completed read."""
  assert all(marker not in raw for marker in markers)
  answers = []
  child_reads = []
  read_results = []
  for line in raw.split("\n"):
    if not line.strip():
      continue
    event = json.loads(line)
    content = event.get("message", {}).get("content", [])
    for block in content if isinstance(content, list) else []:
      if event.get("type") == "assistant":
        if block["type"] == "tool_use":
          assert block["name"] == "Read"
          child_reads.append((block["id"], block["input"]["file_path"]))
        if block["type"] == "text":
          answers.append(block["text"])
      if event.get("type") == "user" and block["type"] == "tool_result":
        result = block.get("content", "")
        if isinstance(result, list):
          result = "".join(
              part["text"] for part in result
              if part.get("type") == "text" and isinstance(part.get("text"), str)
          )
        read_results.append((
            block["tool_use_id"], bool(block.get("is_error")),
            isinstance(result, str) and bool(result.strip()),
        ))
  # Preserve the native probe's allowance for an explanation before the sentinel.
  assert answers and answers[-1].strip().splitlines()[-1:] == [
      "RESOURCE_UNREADABLE" if deny_persona else "UNKNOWN"
  ]
  assert [path for _, path in child_reads] == [str(persona)]
  assert read_results == [(child_reads[0][0], deny_persona, True)], (
      "Persona read has no correlated native denial result" if deny_persona
      else "Persona read has no successful native tool result"
  )


def events(path: Path) -> list:
  """The JSON objects of one `.jsonl` file, a bad line skipped; `[]` for an absent or unreadable file."""
  try:
    lines = Path(path).read_text(encoding="utf-8").splitlines()
  except (OSError, UnicodeDecodeError):
    return []
  found = []
  for line in lines:
    try:
      event = json.loads(line)
    except ValueError:
      continue
    if isinstance(event, dict):
      found.append(event)
  return found


def stamp(event: dict):
  """An event's `timestamp` as a datetime, or None."""
  try:
    return datetime.fromisoformat(str(event["timestamp"]).replace("Z", "+00:00"))
  except (KeyError, ValueError):
    return None


def agent_calls(transcript: list) -> list:
  """The `input` of every assistant `tool_use` block named `Agent`, in the transcript's order."""
  calls = []
  for event in transcript:
    content = (event.get("message") or {}).get("content") if event.get("type") == "assistant" else None
    for block in content if isinstance(content, list) else []:
      if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("name") == "Agent":
        calls.append(block.get("input") if isinstance(block.get("input"), dict) else {})
  return calls


def subagent_calls(profile_dir: Path, session_id: str) -> dict:
  """`{"count", "calls"}` for the session `session_id` under `profile_dir`: the one `projects/*/<session id>.jsonl`
  (a uuid4 needs no slug), one call per `Agent` tool use with `role` (`general-purpose` when absent), `description`
  (`""` when absent), `model` (else the paired child's first `message.model`, else None) and `duration_s` (the
  paired child's last timestamp minus its first, to one decimal; `0.0` unpaired). The children are
  `<session id>/subagents/agent-*.jsonl` beside the transcript, paired with the calls in order of first timestamp.
  No transcript: no calls."""
  found = sorted(Path(profile_dir).glob(f"projects/*/{session_id}.jsonl"))
  if not found:
    return {"count": 0, "calls": []}
  transcript = found[0]
  children = []
  for path in (transcript.parent / session_id / "subagents").glob("agent-*.jsonl"):
    child = events(path)
    times = [t for t in map(stamp, child) if t is not None]
    children.append((min(times) if times else None, str(path), child, times))
  children.sort(key=lambda c: (c[0] is None, c[0] or datetime.min, c[1]))
  calls = []
  for n, given in enumerate(agent_calls(events(transcript))):
    child = children[n] if n < len(children) else None
    model = given.get("model")
    if not model and child:
      model = next((e["message"]["model"] for e in child[2] if isinstance(e.get("message"), dict) and e["message"].get("model")), None)
    times = child[3] if child else []
    duration = round((max(times) - min(times)).total_seconds(), 1) if times else 0.0
    calls.append({"role": given.get("subagent_type") or "general-purpose", "description": given.get("description") or "",
                  "model": model or None, "duration_s": duration})
  return {"count": len(calls), "calls": calls}
