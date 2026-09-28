# Draft request: supported OpenPrescribing API access

**Status:** prepared, not sent. The acquisition/publication authority for
OpenPrescribing is already recorded in
`quality/qualifications/openprescribing-acquisition-authorization.json`. This
draft requests a provider-supported transport route only; it does not expand
source or rights scope.

**Suggested contact:** OpenPrescribing's [official contact page](https://openprescribing.net/contact/).

**To:** `feedback@openprescribing.net` (the address published on the official contact page).

**Subject:** Supported automated access to OpenPrescribing API v1

Hello OpenPrescribing team,

We maintain Global Medicines Atlas, a research project that preserves public
medicine-source records with source identity, period, provenance and reuse
terms. We have maintainer approval for bounded, receipt-bound partitions from
the six documented OpenPrescribing API v1 endpoints under the recorded
attribution and Open Government Licence conditions.

Our latest metadata-only checks receive HTTP 403 responses with a Cloudflare
challenge indication from both our local route and a GitHub Actions runner.
The hosted check sent one `HEAD` request per documented endpoint for the
2026-06-01 partition where applicable, did not follow redirects, and did not
read response bodies. The checks retained only status and response metadata.

Could you please confirm whether the API is intended to support automated
retrieval and identify a documented, provider-supported route that works from
these environments? In particular, please clarify whether there are supported
request headers or rate limits, an approved allow-list or token-based route, or
an agency-controlled mirror. Please also confirm the current status of API v1
and any applicable reuse or attribution changes since the documentation
snapshot we recorded.

We will follow your supported access controls and will not attempt to solve the
challenge or substitute NHSBSA source files for the OpenPrescribing API
products. If a proposed route requires credentials, a new host, or different
rights, we will stop and obtain the required authority before using it.

Thank you.

## Source references

- [OpenPrescribing API documentation](https://openprescribing.net/api/)
- [OpenPrescribing About page](https://openprescribing.net/about/)
- [OpenPrescribing contact page](https://openprescribing.net/contact/)
- Current access receipt: `quality/qualifications/openprescribing-head-availability-20260927.json`
- Acquisition scope: `quality/qualifications/openprescribing-acquisition-authorization.json`
