# nzmedicines Consolidation

[`edithatogo/global-medicines-atlas`][canonical] is the canonical hosted
repository and this local workspace is its canonical implementation source.
The original [`edithatogo/nzmedicines`][upstream] repository is being
incorporated as the NZULM/NZMT FHIR adapter and fixture source.

## Preservation

- Upstream snapshot: `vendor/nzmedicines/`
- Preserved bundle name: `nzmedicines-all.bundle`
- Captured commit: `6a8ecfae67f15d635750d11d5f446b93d76c1865`
- Bundle SHA-256:
  `f4414798f1b35558c69472d86d29b0b83facb2e799c9a20692b62fc889847223`
- Canonical repository:
  `https://github.com/edithatogo/global-medicines-atlas`

The snapshot is immutable evidence. First-party implementation files are kept
outside the vendor directory and retain file-level provenance. The Git bundle
is local preservation evidence and is not redistributed by this repository.

See [History restoration](nzmedicines-history-restoration.md) for verification
and recovery instructions.

## Compatibility Plan

The proposed end state is a narrow compatibility mirror. It would direct new
development, issues, and releases to the canonical repository while retaining
the original repository, Git history, commit identifiers, and migration
context.

The draft upstream notice is in
[Compatibility-mirror notice](nzmedicines-compatibility-notice.md).

## Publication and Archive Gate

No compatibility notice has been published and no upstream archive or mirror
change has been executed. Those external actions require explicit maintainer
approval after:

1. every upstream artifact has a recorded disposition;
2. the NZ adapter and fixtures pass validation;
3. restoration from the Git bundle is verified;
4. migration links and compatibility guidance are published;
5. licensing and redistribution boundaries are confirmed; and
6. the maintainer explicitly approves each external change.

The current repository state is therefore **draft and unexecuted**.

The complete owner, evidence, status, and follow-up mapping is maintained in
the [external gate register](nzmedicines-external-gates.md).

[canonical]: https://github.com/edithatogo/global-medicines-atlas
[upstream]: https://github.com/edithatogo/nzmedicines
