# Australian MBS and PBS public archive reconciliation

The 13 November 2026 readback matched all **1,759 frozen paths** to the
approved Hugging Face revisions by Git blob ID and length, and by LFS SHA-256
where the Hub supplied it. The frozen admission ledger remains at **14 raw
admissions and reader checks**, with **1,745 objects awaiting admission**.
The six July 2025 MBS Silver tables have their own admission and reader record.

[Revision pins, object identities and ZIP member list](../../quality/qualifications/australian-public-archive-reconciliation-20261113.json) ·
[Raw admission ledger](../../quality/qualifications/australian-m112-effective-raw-delivery-reconciliation-20261028.json)

## Schedule and utilisation

| Collection | Verified public contents | Remaining work |
| --- | --- | --- |
| September 2025 PBS schedule API | The official reference ZIP is held under a SHA-256 filename in Reimbursement Atlas. An anonymous download matched its recorded SHA-256 and contained all **33 CSV members** listed in the reconciliation record. | Extract any needed member from the pinned ZIP. The record links the publisher URL through its acquisition receipt. |
| Historical MBS utilisation | Five original demographics ZIPs span **1993–2015**, starting with 1993–1997. Each source SHA-256 matches the corresponding build input. The public archive also carries the December 1993 age-label reconciliation. | The 91 generated workbook Parquets were absent by digest and output ID in the seven checked public trees. Their build and restore receipt is retained. Hosted publication of those derived outputs is a separate decision. |
| PBS ATC2 utilisation | The **1991–2008 teaching CSV** and the AIHW **May 2002–January 2015** historical workbook are archived. The teaching CSV retains its licence notices, attribution and gap-filled-zero caveat. | The recovered AIHW monthly ZIP covers January 2015–September 2026 and did not match the checked archive trees. Its [publication contract](aihw-pbs-atc2-monthly-20261113.md) is prepared. The September 2025 edition remains unidentified. |

[September PBS API ZIP](https://huggingface.co/datasets/edithatogo/reimbursement-atlas/resolve/8c75366a5d5fbf72cdde1d9f83e6f1cbaef7a338/raw/pbs/payloads/au_pbs_structured_28ef7f6eefc6309f/60ade25f04a6451239587ac546c34390099b231036349b3a4eaf28409eefdf59.zip) ·
[MBS utilisation](https://huggingface.co/datasets/edithatogo/australian-mbs-utilisation-archive/tree/05342df7dd2f92fe6e85e28e8add9bf3f43d0389) ·
[PBS utilisation](https://huggingface.co/datasets/edithatogo/australian-pbs-utilisation-archive/tree/e7d39f34e48adba2aaef601281887503baaf3354)

The December 1993 reconciliation matches three aggregate cells and preserves
the two source labels. The original documentation needed to interpret the
workbook's `>85` cutoff remains unresolved.

[Age-band reconciliation](../../quality/qualifications/mbs-dec1993-age-band-reconciliation.json)

## Derived schedule products

- **April 2026 PBS Silver.** Use the reproduced output at
  `3995deb3e2a82f09472d6a78020fb13bbbc96056`. Its exact bytes have a successful
  hosted publication and independent anonymous digest receipt. The remaining
  work is product-specific field and v4 role binding, trusted admission and
  revision-bound consumer checks. The older field-state receipt identifies a
  different output and retains its original scope.
  [Publication receipt](../../quality/qualifications/pbs-reproduced-publication-20261102-41395493749/publication.json) ·
  [Role evidence](../../quality/qualifications/pbs-reproduced-v4-evidence-readiness-20261029.json)
- **July 2025 MBS Silver.** All six admitted tables match the digest and size
  in the existing consumer receipt at the current public archive revision.
  [Consumer reconciliation](../../quality/qualifications/platinum-actual-consumer-reconciliation-20261028.json)
- **August 2026 MBS Bronze.** The four Parquets outside the frozen M-112 scope
  match their recorded SHA-256s and lengths. M-108 still requires a product
  card, typed v4 evidence and independent replica proof for the accepted
  parser prefix, plus a disposition for the other prefix.
  [August obligations](../../quality/qualifications/phase4-mandatory-output-delivery-reconciliation-20261028-3.json)

This record is a bounded comparison of public archives at the listed revisions.
It carries forward existing rights and acceptance evidence. The Hugging Face
reconciliation is a catalogue README update. Participant and cohort-derived
data are outside its scope.
