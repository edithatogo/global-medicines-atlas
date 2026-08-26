# GitHub Test-Acceleration Audit — 2026-08-26

This owner-wide audit inspected the default-branch trees and test configuration
of all 171 repositories under `edithatogo`. It included archived and template
repositories without mutating them. The deeper pytest assessment covered 84
active Python, Jupyter, or template candidates; 65 contained Python test or
`conftest.py` files.

The relevance threshold was at least 20 Python test/configuration files, plus
Python/data templates. Global Medicines Atlas was implemented directly; 31
other repositories received repository-specific issues. The remaining
repositories were assessed as archived, non-Python, without Python tests, or
too small to justify dependency and workflow expansion now.

## Decisions

- Changed-test selection and slow-test filtering are local feedback only. Full
  clean-environment CI remains authoritative.
- Prefer pytest-testmon's dependency mapping over adding pytest-picked as a
  second overlapping selector.
- Record HTTP only for public, replay-safe interactions with redaction. Never
  record credentials, restricted payloads, or evidentiary source bytes.
- Prefer explicit clocks to Freezegun, in-memory databases to file-backed ones
  when persistence is not under test, and reusable immutable fixtures where
  isolation remains intact.
- Measure Coverage.py `sysmon` compatibility instead of forcing it across
  dynamic contexts, plugins, branch coverage, and concurrency settings.
- Use import-time measurements and Scalene evidence before refactoring imports.

## Created Issues

- [global-family-justice-data #88](https://github.com/edithatogo/global-family-justice-data/issues/88)
- [archive-govt-nz #204](https://github.com/edithatogo/archive-govt-nz/issues/204)
- [reimbursement-atlas #764](https://github.com/edithatogo/reimbursement-atlas/issues/764)
- [pelican-bench #168](https://github.com/edithatogo/pelican-bench/issues/168)
- [riopa-infrastructure #618](https://github.com/edithatogo/riopa-infrastructure/issues/618)
- [rareburden-commons #255](https://github.com/edithatogo/rareburden-commons/issues/255)
- [mars #209](https://github.com/edithatogo/mars/issues/209)
- [innovate #473](https://github.com/edithatogo/innovate/issues/473)
- [voiage #1028](https://github.com/edithatogo/voiage/issues/1028)
- [ginsim #27](https://github.com/edithatogo/ginsim/issues/27)
- [nlp-policy-nz #312](https://github.com/edithatogo/nlp-policy-nz/issues/312)
- [fyi-archive #402](https://github.com/edithatogo/fyi-archive/issues/402)
- [foi-o #140](https://github.com/edithatogo/foi-o/issues/140)
- [new-drug-reimbursement-game #89](https://github.com/edithatogo/new-drug-reimbursement-game/issues/89)
- [gtpcnz #160](https://github.com/edithatogo/gtpcnz/issues/160)
- [closer-to-whom #210](https://github.com/edithatogo/closer-to-whom/issues/210)
- [fyi-cli #322](https://github.com/edithatogo/fyi-cli/issues/322)
- [careops-process #62](https://github.com/edithatogo/careops-process/issues/62)
- [conductor-next #25](https://github.com/edithatogo/conductor-next/issues/25)
- [asreview #8](https://github.com/edithatogo/asreview/issues/8)
- [mchs #373](https://github.com/edithatogo/mchs/issues/373)
- [senseno-munchausen #128](https://github.com/edithatogo/senseno-munchausen/issues/128)
- [rac-conformance #189](https://github.com/edithatogo/rac-conformance/issues/189)
- [hermes-training #6](https://github.com/edithatogo/hermes-training/issues/6)
- [nztaxmicrosim #193](https://github.com/edithatogo/nztaxmicrosim/issues/193)
- [UOGTO #120](https://github.com/edithatogo/UOGTO/issues/120)
- [template-solo-data #3](https://github.com/edithatogo/template-solo-data/issues/3)
- [template-solo-python #1](https://github.com/edithatogo/template-solo-python/issues/1)
- [lifecourse #50](https://github.com/edithatogo/lifecourse/issues/50)
- [scimapping #12](https://github.com/edithatogo/scimapping/issues/12)
- [pybliometrics #12](https://github.com/edithatogo/pybliometrics/issues/12)
