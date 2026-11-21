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
  machines exactly upstream (ram/2 up to the 4096 MB default);
  commit dabc0ac, pushed 2026-11-20; both builds green — Linux
  smoke test printed undo_mem_limit 981, Windows 1023; factory
  defaults verified on the 0003 Linux binary on a 7.9 GB machine:
  memcachelimit 991, timeouts 30/15/30/15, undo 495)
- `0004-tbb-trim-thp-guard.patch` (Phase 1 Fix 3 v2, allocator trim
  after undo purge / file load / render + huge-pages guard on
  >8 GB machines only; v2 reworked + verified, full stack
  0001→0002→0003→0004 applies clean in scratch; both builds green —
  Linux 44886084975, Windows 44886085141; post-render RSS measured
  494.9 MB → 354.3 MB, output byte-identical)
- `0005-startup-ram-lazy-loading.patch` (Phase 2 Fix 4, startup RAM:
  Windows /DELAYLOAD for OpenImageDenoise, oslcomp, oslexec, oslquery,
  embree4 — PE audit on the real Windows binary confirms 0 data
  imports for all five (oslexec's only 3 data imports were the
  OSL::Strings::* tokens, replaced with literals in osl.cpp);
  usd_ms excluded — 31 data imports, LNK1194; openvdb excluded —
  eager at startup, 0 MB saved; deferred Python remote-library
  imports in bl_pkg — Linux startup RSS measured 270.2 → 247.7 MB,
  modules 577 → 313, zero ssl/requests modules; Linux --as-needed
  already default, no change. Muse verified the whole patch
  independently before landing: stack, PE audit, live RSS, function
  tests. Unverified until CI: MSVC link, Windows runtime RSS, full
  C++ compile of osl.cpp.)

- `0006-packaging-trim.patch` (Phase 2 Fix 5, packaging trim: CMake
  excludes both copies of libpython3.13.a (2 × 84,181,888 B) and Windows
  Python venv PDBs; Linux -ffunction-sections/-fdata-sections +
  -Wl,--gc-sections on the blender link; Windows /Gy for MSVC cl.exe;
  workflow strips an explicit 5-file ELF allow-list on Linux and ships
  blender.pdb as a separate debug asset on Windows, dropping top-level
  .pdb/.lib/.exp + 6 build-time host tools. GPU kernels untouched —
  strip never touches libcycles_kernel_oneapi_aot.so or
  cycles/lib/*. Expected: Linux ~890–910 MB installed (from 1,182 MB),
  Windows ~733 MB uncompressed (from 883 MB). Muse verified the staged
  patch independently before landing: full-stack apply 0001→0006 clean,
  every claimed file size matches the real fix4 artifacts byte-for-byte,
  PLATFORM_LINKFLAGS_RELEASE reaches the blender link, workflow diff
  applies on ec93a84 with the Windows startup-measurement step
  preserved. CI is the real test for the gc-sections / /Gy link.)

Phase 1 is complete (0001–0004, all green + measured). Phase 2 is
complete (0005 + 0006 landed) once the 0006 builds go green and the
packaged sizes are verified from the CI artifacts.

Superseded and NOT included: `phase2-proposal1-undomemory-256.patch` (the
one-line default flip — not a hard cap, can leave zero usable undo steps).
It stays in the parent project folder for reference only.

Note: commit 64c8e4a (2026-11-20) added CI regression tests — every build
now runs `bl_global_undo.py`, `undo_runtime_test.py`, and a 64-sample
BMW27 smoke render on both platforms.
