# Offline preregistration rehearsal

This directory is generated without network access. It is an OSF-ready draft,
not a registration or publication receipt.

Build from the repository root:

```console
python -m scripts.build_academic_preregistration --output research/preregistration/submission
```

Validate every schema, attachment, checksum, and documented boundary:

```console
python -m scripts.validate_academic_preregistration --bundle research/preregistration/submission
```

External submission requires explicit maintainer approval and is intentionally
not implemented by either command.
