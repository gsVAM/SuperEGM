# Copyright 2026 gsVAM. SPDX-License-Identifier: Apache-2.0
# Added by SuperEGM (gsVAM), 2026: U74's tests: the `dir` entry of `instructions`, its freezing, the index and the Astra lane's pastes.

"""U74: reference documents, the helper."""

import pytest

from conftest import git
from test_review import approve, converged_spec
from test_u37 import RULES, configure

DIR = "docs/reference"
ROLES = ["builder", "foreman", "reviewers", "judges"]


def commit_files(world, files):
  """`files` ({path: text or bytes}) written and committed together."""
  for rel, data in files.items():
    path = world.repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))
  git(["add", "-A", "--", *files], world.repo)
  git(["commit", "-qm", "add reference documents"], world.repo)


@pytest.mark.parametrize("case, named", [
  ("51 files", "docs/reference/f51.md"), ("a 65,537-byte file", "docs/reference/big.md"),
  ("an absent folder", "docs/reference"), ("an empty folder", "docs/reference"),
  ("both file and dir", "instructions")])
def test_a_dir_entry_outside_the_limits_is_refused(world, case, named):
  """At most 50 files, each at most 65,536 bytes; the folder present and non-empty; exactly one of file and dir."""
  entry = {"dir": DIR, "to": ROLES}
  files = {
    "51 files": {f"{DIR}/f{n:02d}.md": "x\n" for n in range(1, 52)},
    "a 65,537-byte file": {f"{DIR}/big.md": "x" * 65537},
    "an absent folder": {},
    "an empty folder": {f"{DIR}/notes.txt": "no markdown here\n"},   # no *.md file in the folder
    "both file and dir": {f"{DIR}/a.md": "A first line.\n", RULES: "Run the suite.\n"},
  }[case]
  if case == "both file and dir":
    entry["file"] = RULES
  commit_files(world, {"README-seed.txt": "seed\n", **files})
  configure(world, [entry])
  spec, cid, rid = converged_spec(world)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 1 and named in out, out
  assert "must be a list of" not in out, out   # refused for its reason, not as a malformed shape
  if case == "both file and dir":
    assert "exactly one of file and dir" in out, out


def test_a_folder_freezes_each_document_with_its_raw_copy(world):
  """Each document frozen by its 12-hex blob sha, the raw bytes beside the .json."""
  from test_review import hstore
  from test_u37 import blob_sha, entries_of
  texts = {f"{DIR}/b.md": "B first line.\nmore\n", f"{DIR}/a.md": "A first line.\n", f"{DIR}/sub/c.md": "C é line.\n"}
  commit_files(world, {**texts, f"{DIR}/skip.txt": "not markdown\n"})
  configure(world, [{"dir": DIR, "to": ROLES}])
  spec, cid, rid = converged_spec(world)
  code, out = approve(world, spec, cid, "--yes")
  assert code == 0, out
  entry = entries_of(world)[-1]["instructions"][0]
  assert entry["dir"] == DIR and entry["to"] == ROLES
  assert [f["file"] for f in entry["files"]] == ["docs/reference/a.md", "docs/reference/b.md", "docs/reference/sub/c.md"]
  for f in entry["files"]:
    assert f["sha"] == blob_sha(texts[f["file"]].encode("utf-8")) and set(f) == {"file", "sha"}
    assert f"{f['file']} {f['sha']}" in out, out
  store_dir = hstore(world).path("instructions", entry["files"][0]["sha"]).parent
  assert sorted(p.name for p in store_dir.iterdir()) == sorted(
    [f"{f['sha']}.json" for f in entry["files"]] + [f"{f['sha']}.md" for f in entry["files"]])
  for f in entry["files"]:
    assert (store_dir / f"{f['sha']}.md").read_bytes() == texts[f["file"]].encode("utf-8")


def test_the_index_lists_each_document_after_the_pasted_files(world):
  """One heading, one line per document addressed to the role, then the verbatim sentence."""
  from superegm.instructions import render
  from test_review import hstore
  from test_u37 import blob_sha, commit_file, entries_of
  a_text = "\n  \n" + "z" * 130 + "\nrest\n"
  commit_file(world, RULES, "Run the suite.\n")
  commit_files(world, {f"{DIR}/a.md": a_text, f"{DIR}/b.md": "# B title\n"})
  configure(world, [{"file": RULES, "to": ["builder"]}, {"dir": DIR, "to": ["builder", "reviewers"]}])
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  hid = entries_of(world)[-1]["handoff_id"]
  st = hstore(world)
  sha, sha_b = blob_sha(a_text.encode()), blob_sha(b"# B title\n")
  store = st.path("instructions", sha).parent.parent   # the store root: instructions/<sha>.md under it
  manifest, text = render(st, "builder", handoff_id=hid)
  assert text.index("## Reference documents") > text.index("rules.md")
  assert text.count("## Reference documents") == 1
  assert f"- docs/reference/a.md ({sha}): {'z' * 120} — read {store}/instructions/{sha}.md\n" in text
  assert f"- docs/reference/b.md ({sha_b}): # B title — read {store}/instructions/{sha_b}.md\n" in text
  assert "z" * 121 not in text
  assert text.rstrip().endswith("Read a reference document when your task touches what its first line names; "
                                "cite it by file when a finding rests on it.")
  assert manifest == [{"file": RULES, "sha": blob_sha(b"Run the suite.\n")},
                      {"file": "docs/reference/a.md", "sha": sha}, {"file": "docs/reference/b.md", "sha": sha_b}]
  # a role the folder is not addressed to gets nothing of it; a role with only the folder gets its heading
  assert render(st, "judges", handoff_id=hid) == ([], "")
  only = render(st, "reviewers", handoff_id=hid)
  assert only[1].startswith("# Repository instructions\n") and "```" not in only[1]
  assert only[0] == manifest[1:]


A_TEXT = "A first line.\nA body marker.\n"
B_TEXT = "B first line.\nB body marker.\n"
NOT_PASTED = "(not pasted: over the 262,144-byte brief budget)"


def approved_docs(world, docs):
  """`docs` committed under the folder, an entry for all four roles, approved; `(spec, handoff id)`."""
  from test_u37 import entries_of
  commit_files(world, docs)
  configure(world, [{"dir": DIR, "to": ROLES}])
  spec, cid, rid = converged_spec(world)
  assert approve(world, spec, cid, "--yes")[0] == 0
  return spec, entries_of(world)[-1]["handoff_id"]


def unapproved_docs(world, docs):
  """The same committed, its config committed too, and no approval: a flat store as a spec review's; `(spec, store)`."""
  from test_review import hstore, seed_handoff, spec_file
  commit_files(world, docs)
  configure(world, [{"dir": DIR, "to": ROLES}])
  git(["commit", "-qam", "config", "--allow-empty"], world.repo)
  spec = spec_file(world)
  seed_handoff(world, spec)
  return spec, hstore(world)


@pytest.mark.parametrize("case, expect", [
  ("working tree changed", "the store copy's bytes"),
  ("store copy sha differs", "refused naming docs/reference/a.md"),
  ("over 262,144 bytes", "(not pasted: over the 262,144-byte brief budget) and pasted: false"),
  ("spec review before first approval", "the HEAD copy pasted and {file, sha} recorded"),
  ("a panel's Astra and local members", "the Astra member pasted, the local member indexed"),
  ("a head review's prepare.astra_brief", "the documents pasted"),
])
def test_the_astra_lane_pastes_checked_store_copies(world, tmp_path, monkeypatch, case, expect):
  """The Astra lane cannot read the store: each copy pasted under its index line after its sha check."""
  import superegm
  from superegm.instructions import render
  from test_review import hstore
  from test_u37 import blob_sha
  files = {f"{DIR}/a.md": A_TEXT, f"{DIR}/b.md": B_TEXT}
  sha_a, sha_b = blob_sha(A_TEXT.encode()), blob_sha(B_TEXT.encode())
  both = [{"file": f"{DIR}/a.md", "sha": sha_a}, {"file": f"{DIR}/b.md", "sha": sha_b}]
  pasted_a = f"- {DIR}/a.md ({sha_a}): A first line.\n```\n{A_TEXT}```\n"
  if case == "working tree changed":
    spec, hid = approved_docs(world, files)
    st = hstore(world)
    commit_files(world, {f"{DIR}/a.md": "A first line.\nEdited after the approval.\n"})
    manifest, text = render(st, "reviewers", handoff_id=hid, lane="astra")
    assert pasted_a in text and "Edited after the approval." not in text and "— read" not in text
    assert manifest == both
    local_manifest, local_text = render(st, "reviewers", handoff_id=hid, lane="local")   # the other lane of the round
    assert local_manifest == both and "A body marker." not in local_text and "— read" in local_text
  elif case == "store copy sha differs":
    spec, hid = approved_docs(world, files)
    st = hstore(world)
    st.path("instructions", sha_a).with_suffix(".md").write_bytes(b"A first line.\nTampered.\n")
    with pytest.raises(superegm.HandoffError, match=f"{DIR}/a.md"):
      render(st, "reviewers", handoff_id=hid, lane="astra")
  elif case == "over 262,144 bytes":
    big = {f"{DIR}/d{n}.md": f"Doc {n}\n" + "x" * (65536 - len(f"Doc {n}\n")) for n in range(1, 6)}
    spec, hid = approved_docs(world, big)
    st = hstore(world)
    manifest, text = render(st, "reviewers", handoff_id=hid, lane="astra")
    shas = [blob_sha(data.encode()) for data in big.values()]
    assert manifest == [{"file": f, "sha": s} for f, s in zip(big, shas)][:4] + [{"file": f"{DIR}/d5.md", "sha": shas[4], "pasted": False}]
    assert text.count(NOT_PASTED) == 1 and f"- {DIR}/d5.md ({shas[4]}): Doc 5 {NOT_PASTED}\n" in text
    assert text.count("x" * 65000) == 4          # the first four fit the budget exactly, the fifth is not pasted
    assert all("pasted" not in item for item in render(st, "reviewers", handoff_id=hid, lane="local")[0])
  elif case == "spec review before first approval":
    spec, st = unapproved_docs(world, files)
    manifest, text = render(st, "reviewers", root=world.repo, lane="astra")
    assert manifest == both and pasted_a in text and "— read" not in text
    assert st.path("instructions", sha_a).with_suffix(".md").read_bytes() == A_TEXT.encode()   # the review wrote the copy
  elif case == "a panel's Astra and local members":
    from test_review import card
    from test_u38 import open_judges
    spec, st = unapproved_docs(world, files)
    pid, record_card, panel = open_judges(world, parent=card(world, spec, "review-spec"))
    astra, local = panel["instructions"]["astra"], panel["instructions"]["local"]
    assert astra["manifest"] == both and local["manifest"] == both
    assert pasted_a in astra["text"] and "A body marker." not in local["text"] and "— read" in local["text"]
  else:   # a head review's prepare.astra_brief
    import json
    import test_foreman as tf
    from superegm import approve_spec, foreman as foreman_mod
    monkeypatch.setattr(foreman_mod, "runner_path", lambda: None)
    target, base, head, g = tf.pr_repo(world, tmp_path, monkeypatch)
    st, wave, child, did, _ = tf.dispatched(world, head=head, astra={"enabled": True})
    for name, text, sha in (("a.md", A_TEXT, sha_a), ("b.md", B_TEXT, sha_b)):
      approve_spec.write_copy(st, {"file": f"{DIR}/{name}", "sha": sha, "text": text}, raw=True)
    path = st.path("approvals", "sample")
    record = json.loads(path.read_text(encoding="utf-8"))
    superegm.atomic_write(path, {**record, "instructions": [{"dir": DIR, "to": ["reviewers"], "files": both}]})
    code, out = world.run("prepare", "--unit", tf.UNIT, "--dispatch", did, "--runcard", child)
    assert code == 0, out
    stored = json.loads(st.path("runcards", child).read_text(encoding="utf-8"))["instructions"]["reviewers"]["astra"]
    assert stored["manifest"] == both and pasted_a in stored["text"]
    brief = (st.path("review", tf.UNIT, f"pr{tf.PR}") / "r1" / "astra_brief.md").read_text(encoding="utf-8")
    assert brief.rstrip().endswith(stored["text"].rstrip())


@pytest.mark.parametrize("round_no", [1, 2])
def test_the_astra_member_gets_a_brief_with_the_pastes(world, round_no):
  """Each round writes `brief.md` for the local members (the index) and `brief-astra.md` for the Astra member (the pastes)."""
  from test_judges import QUESTIONS, open_panel, record
  from test_review import card
  from test_u38 import panel_dir, panel_json
  spec, st = unapproved_docs(world, {f"{DIR}/a.md": A_TEXT})
  pid, cid, _ = open_panel(world, QUESTIONS, parent=card(world, spec, "review-spec"))
  if round_no == 2:
    for judge, answers in (("fable", {"Q1": "a", "Q2": "a"}), ("opus", {"Q1": "a", "Q2": "b"}), ("astra", {"Q1": "a", "Q2": "b"})):
      assert record(world, pid, cid, 1, judge, answers)[0] == 0
    code, out = world.run("judges", "diff", "--panel", pid, "--round", 1, "--runcard", cid)
    assert code == 0, out
  folder = panel_dir(world, pid) / f"round-{round_no}"
  local, astra = [(folder / name).read_text(encoding="utf-8") for name in ("brief.md", "brief-astra.md")]
  instructions = panel_json(world, pid)["instructions"]
  assert local.endswith(instructions["local"]["text"]) and astra.endswith(instructions["astra"]["text"])
  assert f"```\n{A_TEXT}```" in astra and "— read" not in astra and "A body marker." not in local and "— read" in local
  assert local.replace(instructions["local"]["text"], "") == astra.replace(instructions["astra"]["text"], "")   # one brief, two sections


def test_a_spec_review_renders_each_lane_apart(world):
  """`superegm instructions --spec --lane` stores and prints one rendering per lane: the Astra one pasted, the local one indexed."""
  import json
  from test_review import hstore, opened
  from test_u37 import blob_sha
  commit_files(world, {f"{DIR}/a.md": A_TEXT})
  configure(world, [{"dir": DIR, "to": ROLES}])
  git(["commit", "-qam", "config", "--allow-empty"], world.repo)
  spec, cid, rid = opened(world, astra="on")
  sha = blob_sha(A_TEXT.encode())
  outputs = {}
  for lane in ("local", "astra"):
    code, out = world.run("instructions", "--role", "reviewers", "--spec", spec, "--review", rid, "--round", 1, "--lane", lane,
                          "--runcard", cid, card=None)
    assert code == 0, out
    outputs[lane] = out
  assert f"```\n{A_TEXT}```" in outputs["astra"] and "— read" not in outputs["astra"]
  assert "A body marker." not in outputs["local"] and "— read" in outputs["local"]
  st = hstore(world)
  for lane in ("local", "astra"):
    stored = json.loads(st.path("reviews", rid, f"instructions-1-reviewers-{lane}.json").read_text(encoding="utf-8"))
    assert stored["manifest"] == [{"file": f"{DIR}/a.md", "sha": sha}] and stored["text"] == outputs[lane]
