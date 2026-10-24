# PBS URI reference review packet

`scripts/reconcile_pbs_uri_reference_review_packet.py` derives a bounded,
value-free structural packet from the pinned 46-case PBS reference packet and a
single exact Actions URI-screen receipt. It verifies both canonical report
digests and the packet byte digest, the expected URI receipt byte digest,
run and commit identity, the pinned dataset revision and member path/digest/
size, URI-screen v2 status and operation, and a one-to-one case ID plus
occurrence-address digest binding.

The reconciler rejects URI-screen v1 receipts. The currently retained run
`40110616327` uses schema v1, so it cannot produce a derived packet under this
contract. A v2 exact-main receipt is required. Successful reconciliation adds
only scanner-provided structural fields. All cases remain pending and
unreviewed, target meaning stays `not_established`, and the report emits no
edges or precision/recall claims. The sample is non-probability-based and does
not estimate matcher performance or qualify semantic relationships.

Run the focused synthetic checks with:

```sh
uv run pytest tests/test_pbs_uri_review_packet_reconciler.py
```
