# PBS URI reference review packet

`scripts/reconcile_pbs_uri_reference_review_packet.py` derives a bounded,
value-free structural packet from the pinned 46-case PBS reference packet and a
single exact Actions URI-screen receipt. It verifies both canonical report
digests and the packet byte digest, the expected URI receipt byte digest,
run and commit identity, the pinned dataset revision and member path/digest/
size, URI-screen v2 status and operation, and a one-to-one case ID plus
occurrence-address digest binding.

The reconciler rejects URI-screen v1 receipts. The current exact-main URI-screen
v2 run is `40120162365`, on workflow commit
`7084ee19081b6c5ce1ce5e2b6941125a446e8ee0`, for the pinned PBS dataset revision
`31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7` and member
`sch-2026-04-01-r1.xml` (SHA-256
`73d34185fe6ae7fd9a788a68448e20934b38553d42361117faa96cdb07f54f43`,
313,437,585 bytes). The receipt file digest is
`4a296004773c57d7c0a6d73aacc6fd67b052fc3e1900a96badb0948193a7b411`; its
canonical report digest is
`475655fd08abf4681908452ec9e76c6654904d697d10d702c6283c2490afde59`.

For this pinned member, the full scan records 992,456 XLink fragment
references resolving to unique same-member `xml:id` definitions, 1,094,033 RDF
resource references resolving to unique same-member `rdf:about` definitions,
and 73,577 RDF resources with no same-member definition. These are structural
resolution outcomes under the scanner's declared URI and identifier rules.
They do not establish why a reference is present, what a target means, or
whether a relationship is suitable for a PBS domain claim. A no-definition
outcome is unresolved relative to this member, not evidence that a relationship
is false; no external target is fetched.

The value-free derived packet is
`quality/qualifications/pbs-native-reference-uri-review-reconciliation-20261025-40120162365.json`,
with file SHA-256
`3698d217957c4d3263fce010d8ed6441c2050866052e1308fa352c6cd22772bb` and
canonical report SHA-256
`31e22bbda75bb7da755af0d09ed29c93477a9da08a5c50ed499dc6bc23dcd4fa`. It
binds all 46 deterministic review cases to the v2 receipt and occurrence
identities: 17 same-member unique-ID cases, 18 unique same-member RDF-subject
cases, and 11 no-definition controls. It adds allowlisted source/target QNames,
structural attribute roles, and occurrence-address digests for the selected
cases. The cases remain unreviewed; their link roles and target meanings are
not established. The sample is not probability-based and cannot estimate
population precision, recall, or semantic correctness. No semantic edges are
emitted and no matcher performance claim is made.

Human semantic adjudication still needs adequate source context for the
reference role, target type, predicate meaning, and correctness. The packet
intentionally contains no source values and cannot by itself support that
judgment. Keep cases pending until a bounded review surface can present the
necessary context without retaining source values in repository files, logs,
or public artifacts.

Run the focused synthetic checks with:

```sh
uv run pytest tests/test_pbs_reference_review_packet.py
```
