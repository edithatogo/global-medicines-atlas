# Stable-v1 release-candidate verification

This procedure builds and verifies a local stable-v1 candidate from one clean,
content-identified Git commit. It produces one wheel, one source distribution,
a normalized CycloneDX SBOM, the exact dependency lock, content-bound
provenance references, a manifest, and `SHA256SUMS`.

The package is deliberately **unsigned, unapproved, and not published**. It is
not a stable release, provenance attestation, licence decision, Git tag, GitHub
release, or external publication. Stable promotion remains blocked until the
maintainer supplies explicit licence and release approval and the protected
publication workflow produces independently observable receipts.

The committed candidate receipt is bound to durable `main` commit
`3c2100168d003364f1ad71954e1a5adb7d3fa7c5` (the merge of PR #115). The
integration harness clones the canonical remote, checks out that exact commit,
rebuilds with the pinned release toolchain, and requires the rebuilt receipt to
match the committed bytes before it exercises the wheel and sdist consumers.
The archives use canonical wheel payload/RECORD data and deterministic stored
gzip blocks. This closes the prior shallow-checkout and cross-platform
provenance gaps without crossing any signing, approval, tagging, or publication
gate.

## Build the local candidate

Use CPython 3.14.6 from a clean checkout of the intended source commit:

```powershell
uv sync --locked --all-groups
uv run --python 3.14.6 python -m scripts.build_stable_v1_release_candidate build --root . --stage build/stable-v1/release-candidate --receipt quality/qualifications/stable-v1-release-candidate.json
```

The command builds twice with the source commit timestamp as
`SOURCE_DATE_EPOCH`. Repository text is canonical LF through `.gitattributes`,
including JavaScript, JSONL, and SHA-256 sidecars; the preserved imported
`vendor/nzmedicines` exception remains explicitly CRLF. The build fails if the
worktree is dirty; the wheel, sdist, or normalized SBOM differs between builds;
the runtime SBOM disagrees with `uv.lock`; any required provenance reference is
missing; or any package byte fails its manifest or checksum identity.

Independently exercise both LF-oriented and Windows `core.autocrlf=true`
checkout policies in clean detached worktrees:

```powershell
uv run --python 3.14.6 python -m scripts.build_stable_v1_release_candidate reproduce --root . --output build/stable-v1/clean-detached-reproducibility.json
```

The test is also executed by the Linux, macOS, and Windows consumer CI matrix.
It records the exact source commit/tree and wheel, sdist, SBOM, and representative
packaged-text identities. A local result establishes only the named host and
checkout policies; cross-platform qualification requires all hosted matrix
jobs.

## Verify exact bytes and provenance

Check out the `source_commit` recorded in the receipt, rebuild the candidate,
then run:

```powershell
uv run --python 3.14.6 python -m scripts.build_stable_v1_release_candidate verify --root . --stage build/stable-v1/release-candidate --receipt quality/qualifications/stable-v1-release-candidate.json
```

The verifier rejects missing, additional, altered, symlinked, structurally
invalid, or identity-mismatched files. It validates both distribution metadata,
the CycloneDX project identity, the exact checksum set, the receipt self-digest,
and every repository or Git-object provenance reference.

## Clean consumer probes

Run the sorted `verification_commands` recorded in the receipt. The wheel and
sdist consumer commands each create a separate environment under
`build/stable-v1`, using `uv venv --python 3.14.6`. The verifier discovers the
standard `bin/python` or `Scripts/python.exe` layout instead of embedding an
operating-system-specific path. Each exact artifact must independently pass
installation, import, package/runtime version agreement, OpenAPI construction,
CLI help, reinstall, and a repeated probe. The existing clean-consumer
qualification continues to run on Linux, macOS, and Windows.

Deleting the disposable environment and ignored `build/stable-v1` directory
does not alter repository evidence. Do not upload these bytes, create release
metadata, add a tag, or produce a signature without the separately recorded
maintainer decisions and protected workflow evidence.
