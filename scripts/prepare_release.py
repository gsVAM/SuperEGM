# Copyright 2026 Google LLC. SPDX-License-Identifier: Apache-2.0
# Modified by SuperEGM (gsVAM), 2026: one archive named superegm; the notes name gsVAM/superegm and the two
# install commands, and lose the verification-workflow paragraph (the repository's one workflow is tests.yml).
"""Build the versioned runtime archive and a checksum manifest for a draft release."""

import argparse
import hashlib
import json
from pathlib import Path
import re

from pack_plugin import build


def version_for_tag(root: Path, tag: str) -> str:
    """Returns the tag version after validating both shipped manifests.

    Args:
        root: Repository root containing the portable and host manifests.
        tag: Release tag in vMAJOR.MINOR.PATCH format, without leading zeroes.

    Returns:
        The version without the leading v.

    Raises:
        ValueError: The tag is invalid or a manifest version does not match it.
    """
    if not re.fullmatch(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)", tag):
        raise ValueError("Tag must be vMAJOR.MINOR.PATCH without leading zeroes")
    version = tag[1:]
    for relative in ("plugin.json", ".claude-plugin/plugin.json"):
        manifest = json.loads((root / relative).read_text(encoding="utf-8"))
        if manifest.get("version") != version:
            raise ValueError(f"{relative}: version must match {tag}")
    return version


def prepare(root: Path, tag: str, output: Path, commit: str) -> None:
    """Builds the runtime archive, its checksum, and draft notes in a new directory.

    Args:
        root: Repository root containing the runtime sources and manifests.
        tag: Release tag matching every shipped manifest version.
        output: New destination directory; an existing candidate is never replaced.
        commit: Caller-declared source identity as 40 lowercase hexadecimal digits.
            This function does not verify that it identifies the source checkout.

    Raises:
        ValueError: The tag, manifest versions, commit, or runtime inputs are invalid.
        FileExistsError: The destination already exists.
        OSError: Reading sources, building the archive, or writing output fails.
    """
    version = version_for_tag(root, tag)
    if len(commit) != 40 or any(char not in "0123456789abcdef" for char in commit):
        raise ValueError("Source commit must be a full Git SHA")
    output.mkdir(parents=True, exist_ok=False)
    _, archive = build(root, output / "build")
    destination = output / f"superegm-{version}.zip"
    archive.rename(destination)
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    (output / "SHA256SUMS").write_text(f"{digest}  {destination.name}\n", encoding="utf-8")
    (output / "RELEASE_NOTES.md").write_text(
        f"# SuperEGM {version}\n\nDeclared source: `{commit}`\nTag: `{tag}`\n\n"
        "Local source identity is caller-supplied and is not verified by this script. "
        "Publish only after `pytest tests/unit` is green on the tagged commit.\n\n"
        "Runtime archive: Claude Code. Verify the download with "
        "`sha256sum -c SHA256SUMS`, then install from the marketplace:\n\n"
        "```sh\nclaude plugin marketplace add gsVAM/superegm\nclaude plugin install superegm@superegm\n```\n\n"
        "## Changes\n\nMaintainer: summarize changes and migration steps before publishing.\n\n"
        "## Verification\n\nOffline unit tests and runtime packaging are checked by CI "
        "(`.github/workflows/tests.yml`). Live installation, workflow execution, reviewer isolation "
        "and cloud-host support are not established by this build. "
        "Maintainer: attach exact-bundle host evidence and limitations before publishing.\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tag", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    prepare(Path(__file__).resolve().parents[1], args.tag, args.output, args.commit)
