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

## Build the local candidate

Use CPython 3.14.6 from a clean checkout of the intended source commit:

```powershell
uv sync --locked --all-groups
uv run --python 3.14.6 python -m scripts.build_stable_v1_release_candidate build --root . --stage build/stable-v1/release-candidate --receipt quality/qualifications/stable-v1-release-candidate.json
```

The command builds twice with the source commit timestamp as
`SOURCE_DATE_EPOCH`. It fails if the worktree is dirty; the wheel, sdist, or
normalized SBOM differs between builds; the runtime SBOM disagrees with
`uv.lock`; any required provenance reference is missing; or any package byte
fails its manifest or checksum identity.

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

Create a disposable environment and run the `verification_commands` recorded
in the receipt. The wheel and sdist are tested separately. Confirm that the
installed `global_medicines_atlas.__version__` equals `package_version` and that
the existing clean-consumer qualification continues to pass on Linux, macOS,
and Windows.

Deleting the disposable environment and ignored `build/stable-v1` directory
does not alter repository evidence. Do not upload these bytes, create release
metadata, add a tag, or produce a signature without the separately recorded
maintainer decisions and protected workflow evidence.
