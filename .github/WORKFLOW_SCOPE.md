# Executable workflow scope

Only workflow definitions directly under `.github/workflows/` are executable
for this repository and are included in action-pin, runner, toolchain,
Actionlint and Zizmor validation.

Files below `vendor/nzmedicines/.github/workflows/` are preserved, inert
migration-history artifacts. They are not copied, linked or generated into the
active workflow directory and must not be treated as repository automation.
Any future reuse requires a new reviewed root workflow with immutable action
pins and the current repository's permission and toolchain contracts.
