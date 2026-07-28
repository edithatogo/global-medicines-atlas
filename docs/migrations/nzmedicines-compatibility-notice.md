# Draft nzmedicines Compatibility-Mirror Notice

> **DRAFT — DO NOT PUBLISH**
>
> This text has not been posted to the upstream repository. Publishing it,
> changing repository settings, or archiving the upstream repository requires
> explicit maintainer approval.

## Proposed Notice

Development of `nzmedicines` has moved to
[`edithatogo/global-medicines-atlas`][canonical].

The global repository incorporates the relevant `nzmedicines` work as its New
Zealand NZULM/NZMT FHIR adapter and fixture source. It also extends that work
into a jurisdiction-neutral system that keeps regulatory approval and public
funding status as separate evidence dimensions.

This repository is retained as a compatibility and provenance mirror. Existing
links and historical commit identifiers remain valid. New development, issue
reports, pull requests, and releases should use the canonical repository.

The imported source is anchored to upstream commit:

`6a8ecfae67f15d635750d11d5f446b93d76c1865`

The migration preserves:

- the complete upstream Git history in separately governed preservation
  evidence;
- the captured source commit and original commit identifiers;
- an immutable source snapshot with file-level provenance; and
- compatibility and restoration guidance.

The preservation bundle is not distributed from the canonical repository.
Access to restricted or locally governed source material is not implied by
this notice.

## Proposed Repository State

If separately approved, the upstream repository may be:

1. retained as a read-only compatibility mirror; or
2. archived after the notice and canonical links are verified.

Neither action is authorized by this draft. Repository settings, topics,
descriptions, default branches, releases, and issue state must remain
unchanged until the maintainer gives explicit approval at action time.

## Publication Checklist

- [ ] Confirm the canonical repository and migration links resolve.
- [ ] Confirm the imported commit and provenance evidence.
- [ ] Confirm licensing and redistribution boundaries.
- [ ] Confirm compatibility guidance for existing users.
- [ ] Obtain explicit maintainer approval to publish this notice.
- [ ] Obtain separate explicit approval for mirror or archive settings.
- [ ] Record the published notice URL and repository-setting receipt.

These actions remain assigned in the canonical
[external gate register](nzmedicines-external-gates.md).

[canonical]: https://github.com/edithatogo/global-medicines-atlas
