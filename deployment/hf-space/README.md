---
title: Global Medicines Atlas
emoji: 🌐
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
license: apache-2.0
---

<!-- GMA_DEPLOYMENT_OWNER=edithatogo/global-medicines-atlas -->

# Global Medicines Atlas — bounded historical catalogue candidate

[Source and citation](https://github.com/edithatogo/global-medicines-atlas) ·
[Data archive](https://huggingface.co/datasets/edithatogo/global-medicines-atlas-fda-public) ·
[Deployment provenance](/deployment.json)

This Space rebuilds a disposable read-only discovery database from the exact
accepted public FDA snapshot pinned in the installed application. The source
is a bounded August 2026 acquisition, not a current or complete population.
Native application/product identities and names are preserved. No regulatory,
funding or formulary status is inferred; reviewed source-effective dates and
temporal assertions remain unavailable. This is not clinical advice.

The API and Atlas share the existing installed service. `/deployment.json`
records exact source revision/digest, observed denominators and qualification
limits. A successful build or health check does not qualify production medicine
evidence, full federation, independent recovery or Stable v1.

The immutable archive remains authoritative. The Space downloads only the
already-public, permitted member and admission metadata anonymously. It stores
no Hub token and uses `SPACE_SIGNING_SECRET`, supplied by Hugging Face, for
cursor integrity. Temporary files are rebuildable cache, not a durable lake.

Project-owned code is Apache-2.0; source data retains the archive's FDA/openFDA
terms, exclusions and attribution. Deployment is performed only by the exact
reviewed main workflow, using a parent-bound commit and anonymous file checks.
