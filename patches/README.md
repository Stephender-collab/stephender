# patches/

Numbered Stephender patches, applied in order on top of Blender v5.2.4 by the
GitHub Actions workflows (`git apply`).

Currently empty: Phase 0 runs a **zero-patch baseline build** first, to prove
the pipeline and to have a clean self-built baseline to measure against.

The first patches to land will be the Phase 1 memory fixes (from
`../ANTIGRAVITY-PLAN.md`). All three are drafted and verified to apply
cleanly in order against v5.2.4, STAGED in the parent project folder —
do not copy them here until Phase 0's zero-patch baseline build has
passed:
- `../phase1-fix1-undo-hardening.patch` (0001, undo cap + merge accounting)
- `../phase1-fix2-ram-aware-cache.patch` (0002, cache limit + GPU GC)
- `../phase1-fix3-tbb-trim-thp-guard.patch` (0003, allocator trim + huge-pages guard)

Superseded and NOT included: `phase2-proposal1-undomemory-256.patch` (the
one-line default flip — not a hard cap, can leave zero usable undo steps).
It stays in the parent project folder for reference only.
