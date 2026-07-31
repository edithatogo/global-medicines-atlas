# Protected CI, security and publication evidence

The stable-v1 protected-evidence verifier keeps local Git observations separate
from hosted GitHub truth. A clean local commit is useful corroboration, but it
cannot prove that a pull request or hosted check passed.

The policy pins the repository, pull-request number, exact 40-character commit
and every required CI and security check, including its producer and optional
workflow name. The normalized hosted snapshot records the corresponding pull
request, check-run and workflow-run identifiers. Verification fails closed on
missing or duplicate checks, pending or unsuccessful conclusions, dirty or
mismatched local state, and any repository, commit, pull-request, app, check or
workflow identity mismatch.

Offline verification is the default and requires no GitHub credentials:

```console
python scripts/verify_protected_evidence.py \
  --policy build/stable-v1/protected/policy.json \
  --snapshot build/stable-v1/protected/hosted.json \
  --output build/stable-v1/protected/receipt.json
```

The optional acquisition helper invokes authenticated `gh api` read calls and
does not publish, approve or mutate anything:

```console
python scripts/acquire_github_protected_evidence.py \
  --policy build/stable-v1/protected/policy.json \
  --output build/stable-v1/protected/hosted.json
```

Acquisition never invents publication evidence. It records publication as
`not_attempted`, or as `blocked` when `--publication-blocker` is supplied. Only
an explicitly supplied durable publication receipt bound to the exact commit
can produce `verified` publication. Evidence verification and release
eligibility remain separate, so successful protected checks cannot silently
promote or publish a release.
