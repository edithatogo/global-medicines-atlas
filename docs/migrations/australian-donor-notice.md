# Compatibility and successor notice

Active successor development is in
[Global Medicines Atlas](https://github.com/edithatogo/global-medicines-atlas).
This repository remains unarchived, with its history and existing links
preserved. New development and consolidation issues belong in
[GMA issue #339](https://github.com/edithatogo/global-medicines-atlas/issues/339).

The frozen donor baselines are `aus_mbs_pbs_graph` at
`64e764cebeb3826f98ce672cbb4affc65d06a92f` and `aus-health-data-scraper` at
`931da0b9b6ae3e3cec0743568abb71a50d62b7cf`. Their exact MBS XML, legacy P7
workbook and complete baseline Git histories are preserved at
[public MBS revision 4d1dae4](https://huggingface.co/datasets/edithatogo/australian-mbs-source-archive/tree/4d1dae488ac43522f20e8320a8b2a56bf9138341).
The separately acquired PBS schedule is at
[public PBS revision 31ec854](https://huggingface.co/datasets/edithatogo/australian-pbs-source-archive/tree/31ec854ef9fc82f30a0dbe743fdf50a2e5bd24a7).
These are exact historical evidence, not a claim of complete current coverage.
Changes after the frozen donor commits require their own preservation receipt.

GMA supplies source-faithful MBS XML/workbook and PBS v3 parsing, bounded PBS
inspection, typed historical HTML tables and native P7 filtering. It preserves
MBS service-benefit evidence separately from medicine regulatory approval,
PBS funding/formulary evidence and terminology. Historical scraper runs with
404s or empty output are not successful data acquisition.

Consolidation is still in progress: the hosted current-release scheduler and
integrated qualification have separate acceptance evidence. Graph, complete
terminology hierarchy, NLP and distributed-processing roadmap ideas are not
implemented donor features. See the
[capability map and remaining boundaries](https://github.com/edithatogo/global-medicines-atlas/blob/main/docs/migrations/australian-donor-successors.md).
Future archive publication must run from GitHub Actions to public Hugging Face,
with anonymous digest verification; never upload from a developer machine.

No clinical equivalence, general redistribution licence, public software
release, or donor archival is asserted by this notice. Repository archival
requires a separate exact maintainer approval after parity and preservation
checks. Existing local dirty work must remain untouched.
