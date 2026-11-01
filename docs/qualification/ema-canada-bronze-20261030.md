# EMA publication and two-file Canadian batch

The maintainer approved EMA publication on 30 October 2026. The exact prepared
29 October payload is retained in Actions artifact `12896777847` from run
`40873191471`. The live EMA URL has changed since capture; it is not substituted.
The publication plan binds three files and the target
`edithatogo/global-medicines-atlas-ema-bronze-20261029`. The dispatch-only
`ema-snapshot-publication.yml` restores that artifact, checks its payload hash,
uses the existing publication transport and anonymously verifies every remote
file at the returned commit. It refuses local publication and existing target
replacement. If creation/upload fails, inspect the target and retained intent
before recovery; never blindly redispatch. The original retrieval record retains
its capture-time `not_uploaded` state; the hosted receipt establishes publication.

The next batch is limited to `ca-dpd` marketed products and `ca-noc` notices:

```sh
.venv/bin/python scripts/source_download_batch.py \
  --batch quality/qualifications/canada-bronze-20261030/batch.json \
  --output build/canada-bronze-20261030 --execute
```

This command completed once. Both ZIPs passed complete member CRC validation:
DPD: 1,513,654 bytes, 12 members; NOC: 4,621,340 bytes, 7 members.
Receipts, checksums, member manifests, official dataset licence references and
fresh reuse observations are under `quality/qualifications/canada-bronze-20261030/`.
The official Open Government dataset records explicitly identify the
[Open Government Licence – Canada](https://open.canada.ca/en/open-government-licence-canada).
Attribution and exclusions are retained. This records unchanged local acquisition;
Canadian public publication remains a separate decision. DPD approved, inactive
and dormant releases and linked documents are outside this batch.

The reuse search examined nine declared GitHub repository trees and seven public
HF dataset listings at the recorded revisions. Canadian fixture hits were fetched
and compared byte-for-byte with synthetic fixtures (Samplecycline/Demonstradol),
then classified as related examples, not live bulk archives. No matching live
bulk payload was found. Rerunning requires fresh discovery and a fresh output
folder; do not reuse the dated decision after expiry.

## All-source archival status

The 176-row URL inventory is complete as an index, not as archival. The existing
landing queue reports 42 landed-and-evidenced, 91 manual-only, 27 rights-blocked,
15 credentialed/excluded and one temporarily unavailable. The 42 count includes
bounded fixtures and structural evidence; it does not mean 42 live public
archives. The separate live receipt cohort, qualified horizon and full-source
inventory have different denominators and are preserved. These two new local
receipts do not silently promote those existing qualification claims.

## Swiss and federation

Swiss's official current-resource API returned null file URLs and update dates
again on 30 October. A candidate FHIR download exists, but an exact authoritative
resource binding and dataset-specific retention/reuse basis remain unresolved.
The simple path is to qualify a corrected official resource URL and terms, then
use the existing downloader; no new adapter is needed for raw byte retention.
No Swiss source bytes were acquired by this batch.

Australian federation remains deferred. Existing reconciliation retains missing
pre-archive parity evidence (M-105), 315/316 unresolved PBS schedule-to-archive
links (M-107), an older MBS hosted retrieval failure, required source meanings,
per-output admission/consumer evidence and independent recovery authority.
Exact matching and existing batch machinery may reduce mechanical work; URLs
cannot recreate absent historical evidence or establish source meanings and
independent recovery. Preserve the 14 admitted raw objects and 1,745 deferred
objects in the frozen 1,759-object inventory, and the separately qualified
six-table MBS Silver cohort. This work does not reopen federation or claim
Stable v1 release readiness.

Stop after EMA's hosted publication result and these two local acquisitions.
No continuous harvesting, new source IDs, Silver/Gold work or federation work.
