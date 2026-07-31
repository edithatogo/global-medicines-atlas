# Stable v1 incident rehearsal

This deterministic offline exercise proves the required order for responding
to a synthetic compromised source. It does not contact a regulator, funder,
credential authority, publication service, or downstream consumer.

The fail-closed lifecycle is:

1. detect and quarantine the compromised source;
2. rehearse signing-credential revocation after simulated human and credential-authority gates;
3. rehearse dataset withdrawal after simulated human and publication gates;
4. prepare a corrected replacement with separate digest-bound regulatory and funding evidence; and
5. prepare downstream notification after a simulated human gate.

Every transition is ordered and hash-chained. The receipt is deterministic,
rejects missing gates or reordered actions, and records all external effects as
`false`. The `simulated_*_gate` fields exercise state-machine controls; they
are not approvals, authority identities, or evidence that an external gate was
passed. An exact adjacent retry is idempotent and creates no additional event.

Run the bounded exercise with Python 3.14:

```console
uv run --python 3.14 python scripts/stable_v1_incident_rehearsal.py build/stable_v1_incident_rehearsal.json
```

Validate the output against
`schemas/stable_v1_incident_rehearsal.schema.json`. The generated receipt is
local rehearsal evidence only. Runtime verification validates the full fixed
sequence, summary invariants, JSON Schema, hash chain, and receipt identity.
Real credential revocation, withdrawal, replacement publication, and
notification each remain subject to durable human, credential-authority, and
publication evidence that this receipt deliberately does not contain.
