# TLS trust for historical build reproduction

`cacert.pem` is the unmodified trust bundle from `certifi==2026.10.19`. Its
content digest and source are recorded in `provenance.json`; the upstream
license is retained in `LICENSE`. It removes the compromised emSign ECC G3
trust root described by GHSA-6q48-6c7w-9gw2.

The existing historical release contract pins uv 0.11.29. Workflows that retain
that pin set `SSL_CERT_FILE` to this bundle, using the custom-certificate
mitigation explicitly supported by the upstream uv advisory GHSA-hq85-5cpj-mr62.
This preserves the recorded build tool identity and TLS verification. No
certificate verification is disabled. The independently locked uv package is
upgraded to 0.13.4. Edgetest currently declares an older uv upper bound; the
exact temporary dependency override must pass all three dependency-canary
environments and can be removed after upstream permits a patched uv version.

## NPPA missing intermediate

`nppa-intermediate.pem` is the Sectigo Public Server Authentication CA DV R36
intermediate advertised by NPPA. Its signature verified against the existing
root bundle. The batch runner supplies it only for `nppa.gov.in`, checks its
pinned digest, and disables partial-chain trust so verification must reach a
trusted root. Hostname verification and the existing public-IP binding remain
enabled. Certificate source and digest are in
`nppa-intermediate-provenance.json`. Five price PDFs were downloaded successfully;
metadata is in `quality/qualifications/nppa-transport-20261030.json`.
