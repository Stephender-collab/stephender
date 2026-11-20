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
- `0002-physical-ram.patch` (Phase 1 Fix 1b, real physical-RAM helper
  `BLI_system_memory_physical_in_megabytes()` + undo default uses it;
  landed locally 2026-11-20, NOT yet pushed — waiting on the 64c8e4a
  regression-test builds to finish first)

Still staged in the parent project folder, one per cycle after Fix 1b:
- `../phase1-fix2-ram-aware-cache.patch` (0003, cache limit + GPU GC —
  REWORK NEEDED first: must use the new physical-RAM helper, same
  misleading function would make it a no-op on small laptops)
- `../phase1-fix3-tbb-trim-thp-guard-v2.patch` (0004, allocator trim +
  huge-pages guard — v2 reworked + verified; v1 superseded, it had an
  INC_SYS wipe bug that would break the Linux build)

Superseded and NOT included: `phase2-proposal1-undomemory-256.patch` (the
one-line default flip — not a hard cap, can leave zero usable undo steps).
It stays in the parent project folder for reference only.

Note: commit 64c8e4a (2026-11-20) added CI regression tests — every build
now runs `bl_global_undo.py`, `undo_runtime_test.py`, and a 64-sample
BMW27 smoke render on both platforms.
