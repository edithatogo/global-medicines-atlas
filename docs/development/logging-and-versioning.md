# Logging and Dynamic Versioning

## Logging

Library modules use child loggers under `global_medicines_atlas` and never
configure the process root logger. Applications opt in with:

```python
from global_medicines_atlas.logging import configure_logging, get_logger

configure_logging(level="INFO")
logger = get_logger(
    "ingestion",
    component="country-adapter",
    jurisdiction="NZL",
    source_id="nzulm",
)
logger.info("Ingestion started")
```

JSON is the default output. Stable context fields are `component`,
`jurisdiction`, `source_id`, and `track_id`; unknown fields fail closed.
Configuration is idempotent and propagation is disabled at the package
boundary.

## Dynamic versioning

PEP 621 declares `version` as dynamic. Hatchling and Hatch-VCS derive package
versions from Git tags and commit distance, then generate `_version.py` only
during builds. The generated file is ignored by Git and coverage.

Release tags use PEP 440-compatible `vMAJOR.MINOR.PATCH` names. Untagged builds
include commit and date provenance. Source archives without VCS metadata use
the explicit `0+unknown` fallback rather than claiming a release.

Runtime consumers use:

```python
from global_medicines_atlas import __version__
```

The `package` Test-Goblin profile builds both the wheel and source
distribution, verifying the dynamic metadata path without publishing either
artifact.
