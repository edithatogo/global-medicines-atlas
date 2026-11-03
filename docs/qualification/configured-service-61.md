# #61 configured service qualification — 2 November 2026

## Accessibility testing excluded — 3 November 2026

The maintainer explicitly removed accessibility testing from project scope.
Manual and automated accessibility audits, screen-reader/assistive-technology
qualification, WCAG conformance testing and accessibility-specific acceptance
are excluded from every current Conductor track and from the roadmap. They
are not deferred work or a pending completion gate. Do not schedule further
accessibility testing without new explicit maintainer direction. Historical
results and unverified assessments remain evidence, not conformance claims.
Existing working UI features and tests are retained; this scope change does
not delete regressions, weaken protected CI, or mark unperformed tests passed.
All other source, temporal-data, rights, production and release gates remain.

[#61](https://github.com/edithatogo/global-medicines-atlas/issues/61) is the
smallest finite remaining issue: clean artifact startup, live deployment,
production-data qualification and deployed browser accessibility. #491 is a
standing dependency dashboard; the other open issues span larger source,
federation or release prerequisites. This follow-up implements the unblocked
configured-service and clean-artifact gate, without changing the remaining
external acceptance requirements.

## Installed service

The built package now provides the ASGI factory
`global_medicines_atlas.serving:create_app`. Install the selected verified wheel
with its `server` extra, or install that extra from a qualified source archive.
It reuses the already-locked Uvicorn and Atlas JSON-schema dependencies; no
dependency version is upgraded.

Configure `GMA_DATABASE_PATH` to the absolute path of an existing compatible
canonical DuckDB database, and supply the operator-owned `GMA_CURSOR_SECRET`
through the deployment's existing private secret mechanism. It must contain at
least 16 bytes and cannot be blank. Do not put real secrets in shell history,
repository files or public receipts. The factory generates no credentials,
creates no database and selects no source data implicitly.

Start the installed application with:

```sh
python -m uvicorn global_medicines_atlas.serving:create_app --factory --host 127.0.0.1 --port 8765
```

The v1 API, including `/api/v1/health`, `/api/v1/readiness`,
`/api/v1/openapi.json` and `/api/v1/docs`, and the Atlas at `/` use the same
read-only query service. API paths remain reserved so unsupported methods keep
API error semantics rather than falling through to Atlas. Readiness verifies
the database at request time; liveness is separate. Invalid configuration stops
startup without echoing the private database path or cursor-secret value.
The operator remains responsible for the approved source, rights, provenance,
coverage, deployment target, HTTPS and access configuration. This command does
not deploy to a public endpoint or make clinical claims.

## Executed qualification boundary

The existing clean-consumer harness now starts this installed factory as a real
Uvicorn process on an ephemeral loopback socket after building and installing
both the wheel and source distribution with the `server` extra alone. It requests health, readiness, Atlas and
a packaged stylesheet over HTTP, then stops only its owned child process.
The synthetic database remains explicitly labelled in the resulting receipt.
Core-only installation and the existing v2 CLI/compatibility checks remain in
place. The three protected platform consumer lanes execute the same check.

Focused regressions cover missing and invalid configuration, private-error
redaction, API routing/method handling, unchanged source bytes, and readiness
failure without database recreation after the source disappears. The original
root-mount composition failed the 405 regression and was replaced by explicit
API/Atlas dispatch. A mounted ASGI root-path regression also failed before
root-path-aware dispatch was added. Review caught a missing Atlas validator in
the initial server extra; it is now explicit, and the consumer no longer masks
that dependency with a concurrent federation-extra install. An offline lock attempt lacked cached metadata; the supported
online lock refresh succeeded, changing only the project's new extra metadata.

The [executed clean-artifact receipt](../../quality/qualifications/external-product-clean-start-20261102.json)
binds the tested source commit/tree, Python/uv versions and both distribution
hashes. Server-only installation, real loopback startup and HTTP checks passed
for the wheel and sdist. This satisfies the first #61 gate for that candidate;
all three external gates remain false. Required final-head CI independently
builds and exercises the integrated candidate on Linux, macOS and Windows.

## Remaining external gates

#61 stays open until these observations exist for the actual product deployment:

- A recorded live deployment endpoint and successful health/readiness receipt.
- The approved canonical production query database, with exact provenance,
  coverage and source qualifications. A public raw archive or synthetic query
  database is not this evidence.
- Browser accessibility, keyboard and responsive checks against that endpoint.

No GMA GitHub Pages site was configured at the readback, and the inspected
owned Hugging Face Spaces listed only the separate static reimbursement atlas.
No deployment target or production query database is recorded for this packet.
These bounded checks do not prove no deployment exists elsewhere. Existing
fixture browser tests remain fixture evidence. No cloud resource, public
release, credential, data acquisition or native deployment is created here.

## Ownership and evidence

Chat `01a19600-56dd-73a2-9ff5-4a2484a54493` owns this lane in
`/Volumes/PortableSSD/GitHub/global-medicines-atlas`, branch
`codex/61-configured-service`, based on `f6716b5eb8ac5331574d569ede82000aeb4f9fb5`.
Owned scope is the serving factory, server extra and lock metadata, focused
regressions, existing consumer harness, scoped scheduling and qualification
records. Prior ownership remains history. No other writer or native operation
is moved. Reuse unchanged product/consumer receipts; run focused checks and the
clean-artifact harness, then merge only after protected CI passes.

## Hosted implementation — 3 November 2026

The selected target is the Docker Space `edithatogo/global-medicines-atlas`.
The new `hf-space-service.yml` workflow builds the existing package, exports
only locked runtime/server dependencies and builds the container on Actions.
Its disposable container checks startup, restart, HTTP, keyboard, landmarks and
360/1280-pixel layouts. No source payload, database, secret or local environment
is included in the code-only candidate artifact.

At startup the installed `hosted_service` anonymously verifies the exact B1
admission digest and the permitted FDA payload at revision
`9476e7894ed60a603ec9542d7f438d12c5eca726`. The original admitted denominator is
100 applications. The cache preserves explicit application/product identities
and names, with no invented temporal assertions or effective dates. The scope
banner and `/deployment.json` expose that this is an historical catalogue
candidate, not qualified production regulatory/funding evidence. The immutable
archive and original terms remain authoritative. No new source is acquired.

Space deployment is dispatch-only from exact current main in the existing
production environment. It uses only the existing HF_TOKEN, verifies the native
account and target ownership, creates only this exact Space, and uploads six
code/package/licence/trust files against the observed parent. Creation and commit
POSTs are never retried. Native denial is recorded in the mutation journal.
No subscription or hardware upgrade occurs. Public file digests are checked
anonymously before live endpoint verification. The service uses the existing
platform-provided SPACE_SIGNING_SECRET; no account token enters the container.

This closes implementation gaps only where observable hosted receipts pass.
#61 remains open until a qualified production query dataset and the complete
deployed accessibility criteria pass. Bounded browser checks do not claim a
full WCAG audit; a Docker candidate is not a running public endpoint.

Review fixes bind the installed application commit into the image and wait for
that exact identity at the live endpoint; an old healthy deployment cannot pass
for a new build. The hosted catalogue uses the existing Atlas US jurisdiction
convention, and default-page discovery is exercised. Factory configuration is
passed directly rather than written into process-global environment variables;
the scope banner survives split streaming body chunks.

The existing Hub SDK 1.19.0 has a CLI Typer ceiling incompatible with the app's
locked Typer 0.27.3. Its native deployment process therefore uses a separate
Python 3.15.1 environment, installed from the generated, fully hashed
`sdk-requirements.txt`. The app's pyproject/uv/PEP751 lock bytes are unchanged.
The container does not include this SDK environment or the account credential.

## Current selection: free-only hosting — 3 November 2026

The maintainer requires free options. The native Docker Space request in run
`41576482688` returned HTTP 402 requiring a paid account plan. That publisher is
now retired before credential loading; the current workflow has no HF token or
Space-create job. The previous results above are retained as history.

The root Render Blueprint selects exactly one Free Python service for both
API and Atlas. See [the activation contract](../../deployment/render/README.md).
It preserves Python 3.15.1, uv 0.13.6, the existing application lock, archive and
rebuildable cache. Render supplies source identity and a private generated
cursor key. Native authentication and a verified no-payment-method workspace
are required before activation, so quota exhaustion cannot silently bill.
No credentials, account plan or billing state are changed by this PR.

HF's free ZeroGPU route currently lists only Python 3.10.13/3.12.12; it is not a
qualified replacement for this runtime. Static HF Spaces cannot run the existing
Python API. Render Free sleeps after idle periods and remains a candidate, not
a production-availability claim. A prepared Blueprint does not establish a
live endpoint or production temporal medicine-data qualification.

## Live audit follow-up — 3 November 2026

Chat `01a19600-56dd-73a2-9ff5-4a2484a54493` owns the follow-up in
`/Volumes/PortableSSD/GitHub/global-medicines-atlas`, branch
`codex/61-accessibility-temporal`. Scope is a free hosted accessibility audit
and assessment of the existing admitted FDA source, without new acquisition.
The live Render service is `srv-dbkn0h7b9u1s73fsnth0`, free plan, no card on
file, automatic deploy off. Exact deployed merge is
`31aba40b1bd2888965cf99e94d7e509ae382c820` and initial HTTP/provenance and
Chromium verification passed in Actions run `41583895484`.

The new audit uses locked axe-core and captures violations and incomplete
findings across default, search and empty states at 320/360/1280 pixels.
Automated results are not full WCAG conformance. Screen-reader task traversal
and review of applicable manual criteria remain explicit obligations.
The FDA archive assessment counts native submission date/type/status fields
on the hosted runner without writing source bytes locally. Application action
dates must not be propagated as product-level approval validity intervals.
Source reference: https://open.fda.gov/fields/drugsfda_reference.pdf .

Hosted source assessment in Actions run `41585112103` confirmed 633 dated
submission actions across the admitted 100 applications: 544 SUPPL, 89 ORIG;
630 AP and three TA. Thus dates are present; the blocker is not missing dates.
The catalogue projects 183 products, while these action dates belong to
application submissions. There is no reviewed product-action mapping or
validity-end/continued-approval evidence in this projection. Treating every
AP action as approval of every associated product would invent evidence; TA
must remain distinct. Existing sources require that bounded mapping and
qualification before the production temporal gate can pass.

The [direct manual assessment and source mapping disposition](atlas-manual-assessment-61.md)
records the follow-up keyboard findings and FDA's actual table keys. Membership
is supported; submission-to-product temporal applicability remains unresolved.
Keep full conformance and production-data gates unverified.

## Orange Book approval-event reconciliation — 3 November 2026

Chat `01a19600-56dd-73a2-9ff5-4a2484a54493` owns branch
`codex/61-orange-book-temporal` in the existing integration checkout.
The historical admission's restricted rights label is superseded by the
already maintainer-approved `us-fda-orange-book` entry in
`source-rights-review-ledger.json`: redistribution, transformation and public
source use are permitted subject to its exclusions. FDA's current website
policy and Orange Book field definitions were inspected again. Earlier #61
notes treating that historical label as a present restriction were incomplete;
this additive reconciliation preserves those receipts rather than rewriting
immutable history. See `orange-book-reuse-reconciliation-20261103.json`.

The hosted runtime now binds the existing Orange Book ZIP to its admitted
revision, byte count and digest, and reads only Products.txt fields. Exact
application type/number/product keys yield native product approval events at
`/approval-events.json`. FDA explicitly defines Approval Date as the product's
approval-letter date. Dates before 1982 expressed only as a bound, invalid
dates, conflicting dates and unmatched products remain explicit. An event
never establishes continued approval, withdrawal time, funding or a validity
interval. The comparison status tables remain empty and unqualified.

Native VoiceOver Utility was reachable through its verified application path;
its caption panel was already enabled. VoiceOver itself returned a launch/read
timeout, and computer control explicitly denied access to the Codex host.
No external browser, scripted accessibility permission, host bypass or synthetic
speech substitute was used. Screen-reader speech traversal remains unverified;
keyboard/tree/axe evidence is retained separately. This is the specific current
screen-reader route limitation, not proof of full accessibility conformance.

## Production query follow-up — 3 November 2026

The maintainer requested qualification of the production query database using
existing sources, with free deployment and accessibility testing excluded.
This follow-up materializes each pinned Orange Book approval-event disposition
inside the same read-only query database as the 183-product FDA catalogue.
The bootstrap rejects duplicate, missing, extra or unrecognised identities;
the endpoint reads the resulting rows from DuckDB. A per-disposition count
accounts for the full catalogue and is checked against the served events,
source revisions, digests and rights evidence. The qualification is limited to
source-native approval events, including explicit unmatched, conflicting and
non-exact dates. It does not infer continued regulatory approval or funding.

The canonical status-comparison tables still contain no qualified temporal
intervals. Until source-supported status intervals and the required production
comparison coverage are qualified, `production_data_qualified` remains false
and #61 remains open. This work adds no source acquisition, dataset publication,
paid resource, inferred absence or release qualification.

For the already deployed bounded snapshot, anonymous product-event readback
found 148 exact dates, 28 source entries saying approval was prior to
1 January 1982, and seven unmatched products. The prior-to date is preserved
as an exclusive source-supported upper bound, not an invented exact date.
FDA defines the wording in its Orange Book product data description:
https://www.fda.gov/drugs/drug-approvals-and-databases/orange-book-data-files .
Neither a historical approval date nor snapshot absence establishes present
regulatory status or an end date.

### Application-submission source events

Follow-up ownership: chat `01a19600-56dd-73a2-9ff5-4a2484a54493`,
checkout `/Volumes/PortableSSD/GitHub/global-medicines-atlas`, branch
`codex/61-application-events`. The next operation is protected integration and
free-service verification. The same pinned FDA payload contains 100 source
applications and, in the existing audit, 633 dated submission records. The
query database now preserves each native submission and its exact source path,
including missing or invalid dates, with bounded pagination and source digest
provenance. These are application-level historical records; neither product
approval nor continuing status is inferred. Hosted readback must independently
confirm the counts against the pinned source. This adds no source acquisition or
archive publication and does not satisfy the outstanding status-interval gate.

### Product-specific FDA action letters — 3 November 2026

Chat `01a19600-56dd-73a2-9ff5-4a2484a54493` owns checkout
`/Volumes/PortableSSD/GitHub/global-medicines-atlas`, branch
`codex/61-fda-action-evidence`. A bounded acquisition of 30 FDA letters is
recorded in [the content-digest receipt](fda-action-letter-acquisition-20261103.json).
The exact PDF bytes remain in the local recovery directory named by digest;
the public FDA URLs and SHA-256 digests are references, not an archive upload.
Candidate links in that receipt do not establish which products an action
covers. The approved FDA source-rights ledger applies its stated exclusions.

Four letters have been reviewed against the FDA action date, application,
product identity, dosage form, route and strength in the pinned catalogue.
The ANDA 207984 letter supports the 18 December 2020 tentative action for
three capsule strengths; it expressly does not grant final approval. The BLA
761385 letter supports the 27 March 2026 approval action for the one identified
product. The PERIOSTAT letter supports one further product action. Two DAKLINZA strengths are also reviewed. These seven action-to-product mappings are exposed as events,
with source PDF byte lengths and SHA-256 digests. Hosted qualification reconciles the deployed records against the committed
source-digest receipts; it does not re-download the FDA PDFs. Neither document proves a continuing status
interval or a withdrawal date, and the remaining acquired letters have not
been promoted merely by date matching. The production comparison-data gate and
#61 remain open until source-supported intervals and required coverage exist.

The FDA notice in official Federal Register document 05-9624 identifies the
withdrawal of NDA 50-744 for PERIOSTAT 20 mg capsules effective 15 June 2005.
Its [official PDF receipt](fda-withdrawal-05-9624-receipt.json) binds the exact
bytes by SHA-256. The notice summary also contains an inconsistent NDA number;
the DATES section and section I identify 50-744 and the corresponding product.
That inconsistency is retained as evidence. The earlier reviewed action is
30 September 1998. Both endpoints are source-supported, but an uninterrupted
status between them is not established by those two documents, so no canonical
validity interval is inferred. This is a bounded historical example, not proof
of complete coverage or current status.

A second [official withdrawal notice receipt](fda-withdrawal-2021-23729-receipt.json)
records withdrawal of NDA 206843 effective 1 December 2021. Its notice
identifies DAKLINZA strengths including both reviewed products; the later 90 mg
product is not assigned the earlier original approval event. The Federal
Register API did not populate its effective date, so the date was checked in
the official PDF. Intervening status continuity remains unverified.

#### FDA runner access and verification scope

GitHub-hosted verification run 41623701184 received an FDA HTTP 302 to
`/apology_objects/abuse-detection-apology.html`. No redirect or access control
was bypassed. The six PDFs underlying the four reviewed letters and two
withdrawal notices were acquired anonymously from the official sources and
rehashed against their byte counts and SHA-256 digests in the local recovery
directory. The hosted verifier independently checks the running service's
exact commit, product mappings and withdrawal references against the
Git-tracked acquisition receipts. It does not claim a hosted PDF rehash. The
locally retained PDFs remain in place; no new dataset archive was published.

### Additional reviewed product-action anchors — 3 November 2026

Chat `01a19600-56dd-73a2-9ff5-4a2484a54493` owns checkout
`/Volumes/PortableSSD/GitHub/global-medicines-atlas`, branch
`codex/61-reviewed-action-starts`. Five already-acquired FDA letters were
reviewed against the pinned product identities, strengths, routes, action
statuses and dates, and their retained bytes were rehashed against the
existing acquisition receipts. They add ten product-specific original
approval events: two isosorbide mononitrate strengths (ANDA 075037), one
diclofenac sodium strength (ANDA 074723), three SUTENT strengths (NDA 021938),
two zolmitriptan strengths (ANDA 202956), and two ertugliflozin strengths
(ANDA 216947). The later 37.5 mg SUTENT product is not assigned the original
approval. Source PDFs stay in the existing local recovery directory; their
content-digest references are included in the action events.

These are additional historical action anchors, not continuing status
intervals. A source-qualified end and intervening status history remain
necessary; unknown coverage remains unknown and #61 stays open.

The FDA's official 25 June 2021 notice records withdrawal of ANDA 074723,
covering the reviewed 50 mg diclofenac product, effective 26 July 2021.
The [notice receipt](fda-withdrawal-2021-13593-receipt.json) binds its PDF and
the official correction by SHA-256. The correction removed ANDA 065152 from
the withdrawal list; it did not remove ANDA 074723. Neither notice establishes
uninterrupted status between the 1999 approval and the 2021 withdrawal.
