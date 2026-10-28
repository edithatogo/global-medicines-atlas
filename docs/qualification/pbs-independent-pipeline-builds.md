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
