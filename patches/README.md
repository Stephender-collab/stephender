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
  commit c7f8658, pushed 2026-11-20; both builds green — smoke test
  printed undo_mem_limit 1023 (Windows) and 998 (Linux) on the 16 GB
  runners, not 2048, proving the helper reads real RAM)
- `0003-ram-aware-cache.patch` (Phase 1 Fix 2, cache limit + GPU GC
  scaled from real physical RAM: <=8 GB machines get memcachelimit
  ram/8 clamped 256–1024 MB and 30s/15s cleanup timeouts; >8 GB
  machines exactly upstream (ram/2 up to the 4096 MB default))

Still staged in the parent project folder, one per cycle:
- `../phase1-fix3-tbb-trim-thp-guard-v2.patch` (0004, allocator trim +
  huge-pages guard — v2 reworked + verified; v1 superseded, it had an
  INC_SYS wipe bug that would break the Linux build)

Superseded and NOT included: `phase2-proposal1-undomemory-256.patch` (the
one-line default flip — not a hard cap, can leave zero usable undo steps).
It stays in the parent project folder for reference only.

Note: commit 64c8e4a (2026-11-20) added CI regression tests — every build
now runs `bl_global_undo.py`, `undo_runtime_test.py`, and a 64-sample
BMW27 smoke render on both platforms.
