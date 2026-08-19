# Bronze: Hugging Face archive boundary and regeneration evidence

Conductor: `conductor/tracks/bronze_medallion_completion_20260819/`

GitHub: parent [#167](https://github.com/edithatogo/global-medicines-atlas/issues/167),
phase [#171](https://github.com/edithatogo/global-medicines-atlas/issues/171)

Requirements: M-096, M-097, S-004, S-011, S-012

Write failing tests, then bind Hugging Face as a bronze archive/output boundary
(not an ingest origin), prove deterministic regeneration, and record completion
evidence. Reuse the sibling Hugging Face archival path when it lands; do not
duplicate it.
