# Four existing August 2026 MBS projection dossiers

These dossiers describe four already-public Bronze projections of the August
2026 MBS **schedule**. They do not describe patient-level claims, utilisation
or a study cohort. The [machine-readable report](../../quality/qualifications/australian-mbs-four-projection-dossiers-20261115.json)
binds each path, full SHA-256, byte count, source receipt, product manifest,
historical publication receipt and producer code revision. No source XML or
Parquet payload was read to make this report.

| Product | Projection | SHA-256 prefix | Producer-reported records | Dossier disposition |
| --- | --- | --- | ---: | --- |
| `d78170f1…` | `source.parquet` | `02693aaa7d1a…` | 6,046 | Complete; output gates blocked |
| `d78170f1…` | `p7.parquet` | `c4aa29f9d4bd…` | 165 | Complete; output gates blocked |
| `f9f9af5a…` | `source.parquet` | `553399aa0683…` | 6,046 | Complete; output gates blocked |
| `f9f9af5a…` | `p7.parquet` | `50ce02b89698…` | 165 | Complete; output gates blocked |

The record counts come from the producer manifests; this assessment did not
measure the Parquet rows. The two source projections have equal byte counts,
as do the two P7 projections, but their digests differ and they remain four
distinct objects. Their latest retained tree readback is the pinned 28 October
2026 revision, not a claim about the current Hub head.

## What the evidence establishes

Both product manifests name the same public schedule XML content digest and
each lists the corresponding two projection digests. Their exact source
receipts classify that XML as non-sensitive and containing no personal data.
The previously recorded maintainer attestation covers public release of the
four exact output identities; it did not authorize v4 admission or consumer
canaries, and this assessment makes no new licensing conclusion.

The original [d781 producer run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/37066153375)
and [f9f9 producer run](https://github.com/edithatogo/global-medicines-atlas/actions/runs/37163925043)
succeeded. Their retained publication receipts bind the exact manifest
digests, report anonymous digest verification of every staged object at the
published primary revision, and record cleanup of temporary source material.
Their manifests and receipts are preserved as public metadata alongside this
report. A read-only review of 12 exact historical code blobs found that the
recorded producer stages the receipt-bound schedule XML, parses its native
fields, writes all records or the native `Group=P7` subset to Parquet, and
checks staged and anonymous object digests. Code and receipt references are
included in the report. The source-receipt transformation itself describes
raw acquisition, not Parquet production.

This establishes the producer's declared source-to-output path and historical
primary digest verification. It does **not** provide an independent replay,
an output-specific privacy clearance, or proof of current availability. The
source's privacy classification is not silently inherited by the outputs.

## Admission and remaining work

The `d781` product has an accepted, unreviewed Bronze sidecar; its retained
record does not contain a landed predecessor. It is not a federation-v4
admission. The `f9f9` manifest reports an accepted parser profile, but the
product prefix had no Bronze admission sidecar at the pinned readback. Its
separately accepted raw B1/B2 lifecycle applies to the source, not to either
projection.

For **each** projection, the remaining prerequisites are output-specific
privacy and source-to-output evidence, an applicable v4 product contract and
separate admission decision, authorized consumer checks, and independent
recovery evidence. A bounded review may use existing evidence or existing
public objects once their privacy and access gates permit it; no new dataset
is inherently required. Missing independent replica evidence may still need
an independently controlled copy and a restore test. Do not treat the primary
Hub's historical digest verification as that replica.

The four outputs are outside the frozen 1,759-object M-112 inventory. This
packet changes neither that inventory nor the established admission counts,
and does not accept the wider Australian federation.

## Reproduction

With the repository's qualified Python 3.15.1 interpreter, run:

```sh
python -m scripts.qualify_mbs_four_projection_dossiers --check quality/qualifications/australian-mbs-four-projection-dossiers-20261115.json
python -m scripts.qualify_mbs_four_projection_dossiers --check-producer-code
```

The first command reads only digest-bound repository JSON metadata. The second
checks the twelve historical code hashes against local Git objects and needs
the corresponding Git history; it does not download data. Neither command
publishes, admits, or accesses source or projection payloads.
