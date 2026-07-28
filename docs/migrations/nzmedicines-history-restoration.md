# Restoring nzmedicines History

The preserved `nzmedicines` Git bundle is governed external evidence. It is not
committed to or redistributed by this repository.

The expected bundle identity is:

- SHA-256:
  `f4414798f1b35558c69472d86d29b0b83facb2e799c9a20692b62fc889847223`
- size: `37,832` bytes
- required source commit:
  `6a8ecfae67f15d635750d11d5f446b93d76c1865`

Restore into a caller-created empty location, or a nonexistent child of an
existing directory:

```powershell
uv run python scripts/verify_nzmedicines_history.py `
  --bundle "C:\governed\history\nzmedicines-all.bundle" `
  --destination "$env:TEMP\nzmedicines-restored"
```

The verifier hashes the source bundle, proves that the required commit is
available from it in an isolated temporary Git repository, and only then
qualifies a sibling temporary clone. It verifies the expected 37,832-byte size,
commit, tree, and vendor snapshot before atomically moving the qualified clone
into the destination. A failed post-clone check leaves no populated destination.
It rejects nonempty, symbolic-link, filesystem root, size-mismatched,
digest-mismatched, and commit-mismatched destinations or inputs.

The command reads but never alters the source bundle. A successful JSON receipt
identifies the verified digest, required commit, and restored destination.
