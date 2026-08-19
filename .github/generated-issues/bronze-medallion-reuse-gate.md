# Bronze: pre-acquisition reuse gate

Conductor: `conductor/tracks/bronze_medallion_completion_20260819/`

GitHub: parent [#167](https://github.com/edithatogo/global-medicines-atlas/issues/167)

Requirements: M-048, M-069, M-098

Before any acquire/download, including Drugs@FDA, search local clones,
maintainer GitHub repositories, Hugging Face (including
`edithatogo/global-medicines-atlas-catalogue`), and the source registry.
Explicitly choose reuse | link | mirror | extend | fork | acquire-new.
acquire-new is last resort. Acquisition without the gate fails. Reuse
`docs/ECOSYSTEM_REUSE.md` and `.context/ecosystem.toml`.
