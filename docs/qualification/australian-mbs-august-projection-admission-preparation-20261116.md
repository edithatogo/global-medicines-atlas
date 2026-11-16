# August MBS projection admission preparation

The [preparation packet](../../quality/qualifications/australian-mbs-august-projection-admission-preparation-20261116.json)
assembles value-free draft components for the eight existing August 2026 MBS
Bronze projections. Every row binds the dataset, revision, path, digest and
byte count to retained source-event, B2 reference, source receipt, producer,
rights, privacy, exact hosted digest, field-lineage and replay evidence. Four
objects are in the frozen M-112 inventory at revision `243f9ff…`; four are
outside it at revision `b925a8a…`. This work does not change inventory.

The retained hosted digest receipt covers all eight exact identities. The
privacy record is a non-sensitive **source-profile** assessment, not an
exhaustive screening or a new output-specific clearance. Rights evidence is
the maintainer's exact-object public-release attestation; the instruments were
not independently reviewed and the attestation does not authorize admission or
consumer canaries. For the four outside-frozen objects it names an earlier
revision, joined to the selected revision by the same path, digest and size.

Each output has 85 existing structural field-lineage records. Their replay
evidence rebuilds registration metadata twice; it is not a replay of the
Parquet payload. The four frozen objects have prior-revision exact-byte
reproduction; the four outside objects have footer-adjusted reproduction, not
an execution of their historical PyArrow 25 writer. The draft preserves these
limits and distinguishes two later reconstructed source metadata pairs from
the source retrieval dates.

The packet is **not a v4 contract, receipt closure, admission, or payload
consumer check**. For each object, the remaining work is to assess the limited
privacy and reproduction evidence for the intended use; resolve the applicable
v1, v2 and v3 contract references; bind the other real v4 roles and independently
trusted receipt closure; and obtain a separate admission decision. The existing
v1 raw-source helper emits Bronze B2 raw artifacts and cannot simply be reused
as proof that a Parquet projection is raw evidence. The two `f9f9` objects
also retain their explicit independently verifiable replica prerequisite
**before** admission. Independent recovery remains unproved for all eight.
Any subsequent bounded payload canary is a separate step and requires the
appropriate authorization; the synthetic checks only prove refusal without
an admission.

With the repository-local Python 3.15.1 interpreter, regenerate or verify the
packet with `python -m scripts.prepare_mbs_august_projection_admission` or the
same command with `--check`. The affected tests exercise mismatched object
identities, privacy, rights chronology, replica requirements and field lineage,
and run the preparation with network access disabled. This work reads only
digest-pinned repository metadata. It does not access participant or
cohort-derived data, acquire or publish datasets, or change rights, privacy,
admission or federation decisions.
