# patches/

Numbered Stephender patches, applied in order on top of Blender v5.2.4 by the
GitHub Actions workflows (`git apply`).

Phase 0's zero-patch baseline build passed on both platforms (Linux run
44698225478 and Windows run 44729012726, both artifacts downloaded and
SHA-256 verified), so Phase 1 patches now land here one at a time, each
with its own build-and-measure cycle.

Currently in:
- `0001-undo-hardening.patch` (Phase 1 Fix 1, undo cap + merge accounting;
  commit d04a64a, 2026-11-20)

Still staged in the parent project folder, one per cycle after Fix 1:
- `../phase1-fix2-ram-aware-cache.patch` (0002, cache limit + GPU GC)
- `../phase1-fix3-tbb-trim-thp-guard.patch` (0003, allocator trim + huge-pages guard)

Superseded and NOT included: `phase2-proposal1-undomemory-256.patch` (the
one-line default flip — not a hard cap, can leave zero usable undo steps).
It stays in the parent project folder for reference only.
