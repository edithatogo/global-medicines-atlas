# Reproduced PBS Silver publication

This workflow is preparation for the already-qualified April 2026 PBS source. It does not add a source or turn structural rows into funding, clinical, or current-status claims. The candidate is output `8e8bacdc72ea81ecfbb84d161b3f546eee03bddeae32f82daa7231c3759d23fc`, SHA-256 `86d65b147dc95787c5e3f14b13abe2630562f050e2221a1340939dcc7776a88c`, with 637,012,122 bytes. Its rights attestation does not itself record approval to publish.

The hosted workflow refuses an append until the exact publication authority record exists on the reviewed main commit. It rechecks the public parent and destination, rebuilds the two identical candidates, retains a run-bound intent and append-attempt artifact, rehashes the staged bytes, and uses the parent revision as the Hub compare-and-swap condition. The acknowledgement only records a returned revision; the separate anonymous readback and preserved-file checks establish publication verification. Neither creates v4 admission or a consumer canary.

A failed or interrupted append may have changed the Hub even if no acknowledgement exists. Do not rerun the job or redispatch publication solely because an acknowledgement or receipt is missing. Preserve the retained intent, attempt, and outcome artifacts; inspect the exact destination head, path, revision and bytes through read-only routes and reconcile the result under the existing recovery contract. An Actions rerun is rejected. Never delete or overwrite an existing destination to recover. Clean temporary staged files only after the anonymous verification receipt is retained.

The only configured target is `edithatogo/australian-pbs-source-archive` at the observed parent revision `208f0b0f1db7768018b3c50929596d63d16e3392`. A changed parent requires fresh reviewed inventory and a revised transaction plan, not a blind retry. The current workflow and its synthetic tests are not evidence that a hosted publication, admission, or consumer read has occurred.

After a successful authorized hosted run, authenticate and retain its publication and preparation artifacts using the run's actual workflow commit, run ID, and artifact IDs:

```sh
uv run python -m scripts.qualify_pbs_reproduced_v4 \
  --workflow-commit "$WORKFLOW_COMMIT" --run-id "$RUN_ID" \
  --publication-artifact-id "$PUBLICATION_ARTIFACT_ID" \
  --preparation-artifact-id "$PREPARATION_ARTIFACT_ID" \
  --output-dir "$NEW_RECEIPT_DIRECTORY"
```

The output directory must not exist. This read-only operation authenticates the exact successful run and both artifact identities before retaining their bytes and hashes. It does not establish the remaining v4 roles, admit the product, or run consumer canaries. Keep the receipt directory with the eventual admission evidence.
