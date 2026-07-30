# Parser, Archive, and Recovery Safety

Official medicine datasets are untrusted inputs even when they come from an
approved source. Acquisition approval does not waive parsing, extraction, or
recovery controls.

## Bounded parsing

`global_medicines_atlas.parser_safety` is the shared XML boundary used by the
PBS, Pharmac, Union Register, and NICE XML adapters. It:

- rejects DTD and entity declarations from parser grammar events, independent
  of UTF-8 or UTF-16 document encoding and declaration formatting;
- feeds the parser in bounded chunks;
- limits payload bytes, XML depth, element count, and aggregate text bytes;
- fails closed on malformed or structurally excessive input.

Adapters may select a lower source-specific byte limit. Raising a limit
requires a representative source receipt, a memory measurement, and hostile
input tests.

## ZIP extraction

`global_medicines_atlas.archive_safety.extract_zip` validates the complete ZIP
directory before writing files. It rejects absolute or traversing paths,
Windows drive and alternate-data-stream paths, reserved or ambiguous Windows
names, portable case-insensitive collisions, symlinks, encryption, excessive
nesting, entry counts, declared sizes, aggregate sizes, and decompression
ratios. Content is streamed into a sibling staging tree and that complete tree
is published to a previously absent destination with one directory rename only
after each member's declared size is confirmed.

The returned extraction receipt binds the archive digest to sorted member
paths, sizes, and SHA-256 digests. Archive extraction must use this boundary;
direct `ZipFile.extract` and `extractall` calls are prohibited for source data.

## Backup, restore, and rollback

`global_medicines_atlas.recovery` provides deterministic local recovery for
governed artifact directories:

1. `create_backup` rejects symlinks and non-regular files, copies content into
   a new bundle, and writes a content-addressed `receipt.json`.
2. `restore_backup` verifies the receipt and every payload digest before
   staging a replacement. Before moving an existing destination, it builds and
   verifies a same-filesystem predecessor safeguard copied only from files
   whose identity was already measured, then verifies every copied byte. The sibling
   rollback directory is the primary recovery path; the safeguard is a second
   publication path if replacement and primary rollback renames both fail.
   Canonical and rollback identities are digest-verified before success.
3. `rollback_restore` quarantines the restored tree and reinstates the retained
   predecessor.

Bundles are local recovery artifacts, not remote backups. Operators must copy
them to an approved independent storage location, apply retention controls,
and verify restoration there before making disaster-recovery claims.

## Operational limitations

- The current archive boundary supports ZIP only. TAR, 7z, nested archives,
  and source-specific container formats remain unsupported and must not be
  unpacked through ad hoc commands.
- Recovery operates on one local directory and deliberately retains rollback
  and failed-restore directories for inspection; lifecycle cleanup is an
  explicit operator action.
- The controls establish deterministic fixture and local-artifact behavior.
  Production-scale memory, time, and recovery-point objectives require
  separate measured qualification receipts.
- The protocol bounds synchronous operation failures. It cannot promise an
  atomic directory swap across a process crash, power loss,
  storage-controller failure, or filesystem corruption. Production claims
  require a crash-consistent filesystem, immutable remote backups, and an
  independently rehearsed recovery procedure.
