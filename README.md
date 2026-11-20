# Stephender

Optimized Blender 5.2.4 LTS — 100% of features, interface, tools, shortcuts and
workflows preserved, made light for old laptops. Built from open source, not
a recreation.

## How it works

This repo does **not** contain Blender's source. It contains only:

- `patches/` — numbered patches applied cleanly on top of Blender v5.2.4,
  one per build-and-measure cycle. A patch only stays if it measurably helps
  and breaks nothing.
- `bench/` — the benchmark harness (`bench.py`, fixed timing) and the
  memory/undo stress scripts.
- `.github/workflows/` — the build pipeline. GitHub Actions builds Linux
  (`ubuntu-24.04`) and Windows (`windows-2022`) and publishes finished builds
  to GitHub Releases. No tunnels, no Colab.

Each workflow run: shallow-clones Blender v5.2.4, fetches the official
prebuilt libraries (`make update`), applies `patches/*.patch`, builds
Release with ccache/sccache, smoke-tests the result, and uploads it.

## Fix order (Antigravity plan, `../ANTIGRAVITY-PLAN.md`)

- Fix 0 — benchmark harness (done: `bench.py` timing fix)
- Fix 1 — hardened undo memory cap (merge accounting, keep ≥2 steps, RAM-aware default)
- Fix 2 — RAM-aware cache limit + faster texture/VBO cleanup
- Fix 3 — return freed allocator memory to the OS + huge-pages guard
- Fix 4 — startup RAM (lazy library loading, deferred Python imports)
- Fix 5 — install size 1.2 GB → ~750–850 MB, nothing removed
- Fix 6 — profile-gated Cycles tile size (only if measured)

Dropped, with reasons: Proposal 2 chunk-splitting (Blender already chunks at
~32 KB — a complete no-op) and the one-line `undomemory = 256` default
(not a hard cap, can leave zero usable undo steps — superseded by Fix 1).

## Download

Releases carry `stephender-linux-x64.tar.xz` and
`stephender-windows-x64.zip` with SHA-256 files. Example:

```bash
gh release download v5.2.4-stephender-r1 -p "*linux-x64.tar.xz"
```
