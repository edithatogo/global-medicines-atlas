#!/usr/bin/env python3
"""Project a hosted CMS Part D payload without publication capability."""

from global_medicines_atlas import cms_partd_records  # pragma: no cover

if __name__ == "__main__":  # pragma: no cover
    cms_partd_records.projection_cli()
