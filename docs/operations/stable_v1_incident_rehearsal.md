# Stable v1 incident rehearsal

This deterministic offline exercise proves the required order for responding
to a synthetic compromised source. It does not contact a regulator, funder,
credential authority, publication service, or downstream consumer.

The fail-closed lifecycle is:

1. detect and quarantine the compromised source;
2. rehearse signing-credential revocation after explicit human and credential-authority gates;
3. rehearse dataset withdrawal after explicit human and publication gates;
4. prepare a corrected replacement with separate digest-bound regulatory and funding evidence; and
5. prepare downstream notification after an explicit human gate.

Every transition is ordered and hash-chained. The receipt is deterministic,
rejects missing gates or reordered actions, and records all external effects as
`false`. An exact adjacent retry is idempotent and creates no additional event.

Run the bounded exercise with Python 3.14:

```console
uv run --python 3.14 python scripts/stable_v1_incident_rehearsal.py build/stable_v1_incident_rehearsal.json
```

Validate the output against
`schemas/stable_v1_incident_rehearsal.schema.json`. The generated receipt is
local rehearsal evidence only. Real credential revocation, withdrawal,
replacement publication, and notification each remain subject to their named
human, credential, and publication gates.
