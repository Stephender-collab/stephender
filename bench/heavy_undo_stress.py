#!/usr/bin/env python3
"""Sustained heavy-edit undo stress test for Stephender (Fix 1 proof).

Drives Blender's memfile undo stack past 512 MB using repeated mesh edits on a
Subsurf-9 cube (~1.57M verts, ~40 MB per mesh-edit undo step).

Runs two scenarios by default:
  1. limit=512 MB (8 GB laptop default): verifies the cap engages and keeps
     undo memory bounded while Ctrl+Z / Ctrl+Shift+Z still work.
  2. limit=0 MB (unlimited): verifies the same workload naturally drives the
     undo stack past 512 MB, proving the cap is doing real work.

Run:
  blender --background --factory-startup --python bench/heavy_undo_stress.py
Optional args (after --):
  --steps N     Number of mesh-edit undo pushes per scenario (default: 75)
  --levels L    Subsurf levels (default: 9)
  --limits CSV  Comma-separated undo_memory_limit values in MB (default: 512,0)
"""
import argparse
import sys
import time
import bpy
import mathutils


def read_proc_mb(field):
    try:
        with open("/proc/self/status") as f:
            for line in f:
                if line.startswith(field):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        return -1.0
    return -1.0


def vm_hwm_mb():
    return read_proc_mb("VmHWM:")


def vm_rss_mb():
    return read_proc_mb("VmRSS:")


def mem_undo_mb():
    try:
        return bpy.app.memory_usage_undo() / (1024.0 * 1024.0)
    except Exception:
        return -1.0


def min_vert_x(ob):
    # Use foreach_get into a flat list or numpy if available for speed on 1.57M verts.
    try:
        import numpy as np
        n = len(ob.data.vertices)
        coords = np.empty(n * 3, dtype=np.float32)
        ob.data.vertices.foreach_get("co", coords)
        return float(coords[0::3].min())
    except Exception:
        return min(v.co.x for v in ob.data.vertices)


def run_scenario(limit_mb, num_edits, subsurf_levels):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.object
    bpy.context.preferences.edit.undo_memory_limit = limit_mb
    # Ensure step-count limit does not trigger before memory limit.
    bpy.context.preferences.edit.undo_steps = max(128, num_edits + 8)

    t0 = time.monotonic()
    ob.modifiers.new(name="Subsurf", type='SUBSURF').levels = subsurf_levels
    bpy.ops.object.modifier_apply(modifier="Subsurf")
    t_apply = time.monotonic() - t0
    verts = len(ob.data.vertices)
    print(
        f"[limit={limit_mb}] setup: subsurf={subsurf_levels} apply={t_apply:.2f}s "
        f"verts={verts} undo_mem={mem_undo_mb():.1f}MB "
        f"rss={vm_rss_mb():.0f}MB rss_peak={vm_hwm_mb():.0f}MB",
        flush=True,
    )

    t_edits = time.monotonic()
    bpy.ops.ed.undo_push()
    prev_undo_mb = mem_undo_mb()
    peak_undo_mb = prev_undo_mb
    peak_rss_mb = vm_rss_mb()
    purge_count = 0
    print(
        f"[limit={limit_mb}] step 00/{num_edits:02d} (init): "
        f"undo_mem={peak_undo_mb:.1f}MB rss={peak_rss_mb:.0f}MB rss_peak={vm_hwm_mb():.0f}MB",
        flush=True,
    )

    step_delta = 1.0
    for step in range(1, num_edits + 1):
        ob = bpy.data.objects["Cube"]
        ob.data.transform(mathutils.Matrix.Translation((step_delta, 0.0, 0.0)))
        bpy.ops.ed.undo_push()
        u_mb = mem_undo_mb()
        r_mb = vm_rss_mb()
        hwm_mb = vm_hwm_mb()
        purged = u_mb < prev_undo_mb
        if purged:
            purge_count += 1
        prev_undo_mb = u_mb
        if u_mb > peak_undo_mb:
            peak_undo_mb = u_mb
        if r_mb > peak_rss_mb:
            peak_rss_mb = r_mb
        tag = " [PURGED]" if purged else ""
        print(
            f"[limit={limit_mb}] step {step:02d}/{num_edits:02d}: "
            f"undo_mem={u_mb:.1f}MB rss={r_mb:.0f}MB rss_peak={hwm_mb:.0f}MB{tag}",
            flush=True,
        )

    elapsed = time.monotonic() - t_edits
    final_undo_mb = mem_undo_mb()

    # Verify undo & redo using vertex DELTA (Subsurf smoothing shifts absolute coords).
    x_before = min_vert_x(bpy.data.objects["Cube"])
    r_undo = bpy.ops.ed.undo()
    x_after_undo = min_vert_x(bpy.data.objects["Cube"])
    r_redo = bpy.ops.ed.redo()
    x_after_redo = min_vert_x(bpy.data.objects["Cube"])

    d_undo = x_after_undo - x_before
    d_redo = x_after_redo - x_after_undo
    undo_works = (
        r_undo == {'FINISHED'}
        and abs(d_undo - (-step_delta)) < 1e-3
        and r_redo == {'FINISHED'}
        and abs(d_redo - step_delta) < 1e-3
    )

    res = {
        "limit_mb": limit_mb,
        "steps": num_edits,
        "verts": verts,
        "elapsed_s": round(elapsed, 2),
        "peak_undo_mb": round(peak_undo_mb, 1),
        "final_undo_mb": round(final_undo_mb, 1),
        "purge_count": purge_count,
        "peak_rss_mb": round(peak_rss_mb, 1),
        "vm_hwm_mb": round(vm_hwm_mb(), 1),
        "d_undo": round(d_undo, 4),
        "d_redo": round(d_redo, 4),
        "undo_works": undo_works,
    }
    print(
        f"[limit={limit_mb}] RESULT: elapsed={res['elapsed_s']:.2f}s "
        f"peak_undo={res['peak_undo_mb']:.1f}MB final_undo={res['final_undo_mb']:.1f}MB "
        f"purges={purge_count} peak_rss={res['peak_rss_mb']:.0f}MB vm_hwm={res['vm_hwm_mb']:.0f}MB "
        f"d_undo={res['d_undo']:.2f} d_redo={res['d_redo']:.2f} "
        f"undo_ret={r_undo} redo_ret={r_redo} UNDO_WORKS={undo_works}",
        flush=True,
    )
    return res


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description="Sustained heavy-edit undo stress test")
    p.add_argument("--steps", type=int, default=75, help="Mesh edit pushes per scenario")
    p.add_argument("--levels", type=int, default=9, help="Subsurf levels (default: 9)")
    p.add_argument(
        "--limits",
        default="512,0",
        help="Comma-separated undo_memory_limit values in MB (default: 512,0)",
    )
    return p.parse_args(argv)


def main():
    args = parse_args()
    limits = [int(x.strip()) for x in args.limits.split(",") if x.strip()]
    factory_limit = bpy.context.preferences.edit.undo_memory_limit
    print(
        f"=== heavy_undo_stress (factory undo_memory_limit={factory_limit}MB, "
        f"steps={args.steps}, subsurf={args.levels}, limits={limits}) ===",
        flush=True,
    )

    results = {}
    ok = True
    for lim in limits:
        r = run_scenario(lim, args.steps, args.levels)
        results[lim] = r
        if not r["undo_works"]:
            print(f"FAIL: undo verification failed for limit={lim}", flush=True)
            ok = False
        if lim == 0 and r["peak_undo_mb"] <= 512.0:
            print(
                f"FAIL: unlimited run did not cross 512 MB "
                f"(peak_undo_mb={r['peak_undo_mb']:.1f}MB)",
                flush=True,
            )
            ok = False
        if lim > 0 and r["purge_count"] == 0 and r["peak_undo_mb"] > lim:
            print(
                f"FAIL: capped run limit={lim}MB exceeded cap without purging "
                f"(peak_undo_mb={r['peak_undo_mb']:.1f}MB)",
                flush=True,
            )
            ok = False

    if 0 in results and 512 in results:
        if results[512]["final_undo_mb"] >= results[0]["final_undo_mb"]:
            print(
                f"FAIL: limit=512 final_undo ({results[512]['final_undo_mb']:.1f}MB) "
                f"not lower than limit=0 ({results[0]['final_undo_mb']:.1f}MB)",
                flush=True,
            )
            ok = False
        saved_final = results[0]["final_undo_mb"] - results[512]["final_undo_mb"]
        saved_peak = results[0]["peak_undo_mb"] - results[512]["peak_undo_mb"]
        print(
            f"=== SUMMARY: uncapped_peak_undo={results[0]['peak_undo_mb']:.1f}MB "
            f"capped512_peak_undo={results[512]['peak_undo_mb']:.1f}MB "
            f"capped512_final_undo={results[512]['final_undo_mb']:.1f}MB "
            f"capped512_purges={results[512]['purge_count']} "
            f"undo_saved_peak={saved_peak:.1f}MB undo_saved_final={saved_final:.1f}MB "
            f"capped512_peak_rss={results[512]['peak_rss_mb']:.0f}MB "
            f"uncapped_peak_rss={results[0]['peak_rss_mb']:.0f}MB "
            f"PASS={ok} ===",
            flush=True,
        )
    else:
        print(f"=== SUMMARY: {results} PASS={ok} ===", flush=True)

    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
