# PBS independent whole-pipeline build qualification

The existing exact PBS native candidate has two byte-identical serialization
outputs and complete source/restore checks. Both writers consume one producer
batch stream, so its retained report correctly says
`independent_pipeline_builds=false`.

The dispatch-only workflow
`.github/workflows/pbs-independent-pipeline-qualification.yml` reuses the
qualified `qualify_historical_pbs_public.py --projection value-package` route in
two separate fresh GitHub-hosted jobs. Both jobs independently fetch and verify
the same pinned source archive, extract/reparse its XML member, execute the
complete producer and source oracle, restore the Parquet output and remove
transient derivatives. Only dependency setup is cached; no parsed rows,
source payload, Parquet file or producer output is passed between jobs.
Both jobs run on the same exact merged main commit with Python 3.15.1.

This is independent execution of the existing pipeline, not an independent
algorithmic implementation. The two serialization files inside each worker
retain their original shared-batch classification. Workflow configuration and
synthetic tests do not establish actual build independence.

## Evidence required after a native run

Retain both aggregate worker reports and native run/job/artifact readbacks.
Require two distinct completed successful matrix jobs, exact producer commit,
matching source archive/member/receipt identities, complete source reparse and
restore, and removal of temporary derivatives. Independently validate each
worker's report-envelope digest before comparing it.

Compare the complete native-core digest, field/entity denominators, package
manifest, Parquet SHA-256 and byte count across workers. To qualify the
already-attested exact candidate, also require the existing identities:

- Output ID: `842f4130a14574f9fe1395a284d54e759ac87726132cc4693288eff971107503`.
- Parquet: `e122b50a37e51f9df06fe1251f8d867283e2fc280bd00ef226f922c2693bb1b2`,
  637,012,122 bytes.
- Native core: `890c607f0e8c9de95c37770610fdc51fd241ea97210ef5ea61d7ad22fd228a25`.
- Native fields: 18,208,758; native entities: 7,730,684.

If the two current builds agree but differ from the earlier exact output,
record reproducibility and the identity difference separately. Do not transfer
the earlier output's exact rights attestation or admission to new bytes, and
do not label the earlier candidate independently reproduced.

The workflow retains aggregate JSON only. It performs no publication or
admission and selects no new date profile. Domain meanings, current status,
payable benefit, patient cost, vocabulary membership, clinical eligibility,
source-era equivalence and independent recovery remain separate. The existing
rights attestation is not expanded by this technical qualification.

## Actual isolated builds, 29 October 2026

[Run 40700877242](https://github.com/edithatogo/global-medicines-atlas/actions/runs/40700877242)
completed successfully on exact main
`c0f17f86f5d4f9a21efc28181786201005c369da`. Jobs 122860031714 and
122860032201 independently completed the full producer/oracle/restore path.
Their two native artifacts were checked by archive digest, exact one-file
inventory and receipt-envelope digest. Aggregate worker receipts and native
job/run evidence are retained in
`quality/qualifications/pbs-independent-pipeline-builds-20261029/`.

The complete package manifests agree across workers. Both retain the same
18,208,758 fields, 7,730,684 entities and native-core digest
`890c607f0e8c9de95c37770610fdc51fd241ea97210ef5ea61d7ad22fd228a25`.
However, the current Parquet digest is
`86d65b147dc95787c5e3f14b13abe2630562f050e2221a1340939dcc7776a88c`
(637,012,122 bytes), and output ID is
`8e8bacdc72ea81ecfbb84d161b3f546eee03bddeae32f82daa7231c3759d23fc`.
These differ from the older exact candidate. Only the package's `parquet` and
`output_id` entries differ; the source, coverage, serialization declaration and
other package identities agree. Producer source files are unchanged between
the old and new workflow commits; locked PyArrow changed from 25.0.0 to 26.0.0.
This comparison does not establish the byte-level cause of the change.

Independent pipeline execution is now observed for the current candidate.
Independent algorithmic implementation is not claimed, and the older exact
candidate is not independently reproduced. Its exact-output rights attestation
is preserved without automatically applying it to the new bytes. No derived
publication, admission, consumer canary or domain-semantic promotion occurred.

An isolated local compatibility probe attempted the historical PyArrow 25
writer with the verified repository Python 3.15.1. The old lock and the
official PyPI release list contain no CPython 3.15 wheel for PyArrow 25. The
source build stopped because the local Arrow C++ SDK was not configured.
`historical-writer-compatibility.json` records the bounded attempt. This is a
local build limitation, not proof that another supported build environment
cannot reproduce the old bytes. The working environment remains on Python
3.15.1 and PyArrow 26; neither was replaced or downgraded.
