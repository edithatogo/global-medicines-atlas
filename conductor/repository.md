# Canonical Repository

## Identity

- **Project name:** Global Medicines Atlas
- **Repository slug:** `global-medicines-atlas`
- **Canonical GitHub repository:** `edithatogo/global-medicines-atlas`
- **URL:** https://github.com/edithatogo/global-medicines-atlas
- **GitHub repository ID:** `1315059642`
- **GitHub node ID:** `R_kgDOTmI3ug`
- **Local remote:** `origin`
- **Remote URL:** `https://github.com/edithatogo/global-medicines-atlas.git`
- **Visibility:** private
- **Issue tracking:** enabled
- **Reserved default branch:** `main`

## Role

This local workspace and its Git history are the canonical implementation
source for the global system. The GitHub repository is its canonical hosted
identity and collaboration surface.

`edithatogo/nzmedicines` is an upstream migration source and future
compatibility mirror for the New Zealand FHIR/NZMT adapter and fixture
package. It is not the canonical repository for the global product.

## Publication Boundary

The canonical repository was intentionally created empty. Connecting `origin`
does not authorize publishing the current branch or historical objects.

Before the first push:

1. verify tracked files and history against the NZ asset rights matrix;
2. exclude local-only, licensed, source, generated, and large payloads;
3. verify the preserved `nzmedicines` bundle strategy;
4. establish the intended clean `main` history and branch policy;
5. run secret, large-file, licence, provenance, and workflow checks.

The repository remains private until an explicit public-release review and
approval.

