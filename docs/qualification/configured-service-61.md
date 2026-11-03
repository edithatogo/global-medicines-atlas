# #61 configured service qualification — 2 November 2026

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
