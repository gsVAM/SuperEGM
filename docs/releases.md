# Versioned releases

<!-- Modified by SuperEGM (gsVAM), 2026: one archive, one host, no release workflow; the verification-workflow text removed. -->

The canonical version is `plugin.json`'s `version`; `.claude-plugin/plugin.json` must carry the
same one, and `prepare_release.py` refuses a tag that matches neither. Release 1.0.0 is the
stable contract for skill names, helper subcommands, store paths and the findings line; use patch
bumps for compatible fixes and minor bumps for new behaviour. Do not change published artifacts
under the same tag.

## Prepare a candidate

1. Update `plugin.json` and `.claude-plugin/plugin.json` to the new version in a reviewed pull
   request; `pytest tests/unit` (what `.github/workflows/tests.yml` runs) must be green on it.
2. After merge, create and push an annotated `vMAJOR.MINOR.PATCH` tag on that commit. Never move
   an existing tag.
3. From the tagged checkout, build the candidate into a fresh directory:

```sh
python3 scripts/prepare_release.py --tag v1.1.3 --commit "$(git rev-parse HEAD)" --output /tmp/superegm-1.1.3-candidate
```

It checks both manifests against the tag, packs the runtime with `scripts/pack_plugin.py` (the
same packer the tests run) into `superegm-1.1.3.zip`, writes `SHA256SUMS` and a draft
`RELEASE_NOTES.md` naming the declared source commit and the install commands. It does not verify
the caller-supplied commit, tag ancestry or tests; an existing output directory is never replaced.

4. Review the archive and the notes, fill in the changes, and upload the ZIP, `SHA256SUMS` and the
   notes to a GitHub release by hand. Installation goes through the marketplace
   (`claude plugin marketplace add gsVAM/superegm`, then `claude plugin install superegm@superegm`);
   the archive is for a by-hand install or an audit.

## Verify a download

```sh
sha256sum -c SHA256SUMS
```

The checksum ties the archive to the notes' declared source; it does not establish host support
or prove the code is safe. Read the notes' verification section for what the build does and does
not check.
