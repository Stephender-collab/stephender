#!/usr/bin/env python3
"""VSE / ImBuf memory cache stress test for Stephender (Fix 2 baseline).

Procedurally generates 1920x1080 RGBA image frames inside Blender (no downloads),
loads them as an image sequence strip into the Video Sequencer, enables raw and
final caches, and scrubs/renders through all frames.

Runs two passes by default:
  1. Capped pass (memory_cache_limit=128 MB): verifies the cache limit engages
     and evicts frames to hold cache usage near the cap.
  2. Default pass (factory memory_cache_limit): measures uncapped cache and RSS
     growth on the same frames.

Run:
  blender --background --factory-startup --python bench/cache_stress.py
Optional args (after --):
  --frames N       Number of 1920x1080 frames to generate & scrub (default: 40)
  --cap-mb M       Low cap to prove eviction engages (default: 128)
"""
import argparse
import os
import shutil
import sys
import tempfile
import time
import bpy
import numpy as np


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


def generate_frames(out_dir, num_frames, width=1920, height=1080):
    """Generate distinct procedural 1920x1080 PNG frames using Blender."""
    t0 = time.monotonic()
    img = bpy.data.images.new("StephenderGen", width=width, height=height, alpha=True)
    img.file_format = 'PNG'
    # Precompute base gradient once; vary each frame cheaply so frames are unique.
    x = np.linspace(0.0, 1.0, width, dtype=np.float32)
    y = np.linspace(0.0, 1.0, height, dtype=np.float32)
    buf = np.empty((height, width, 4), dtype=np.float32)
    buf[:, :, 3] = 1.0

    paths = []
    for i in range(1, num_frames + 1):
        phase = (i / float(num_frames))
        buf[:, :, 0] = (x[None, :] + phase) % 1.0
        buf[:, :, 1] = (y[:, None] + phase * 0.7) % 1.0
        buf[:, :, 2] = ((i * 37) % 256) / 255.0
        img.pixels.foreach_set(buf.ravel())
        fname = f"frame_{i:04d}.png"
        fpath = os.path.join(out_dir, fname)
        img.filepath_raw = fpath
        img.save()
        paths.append(fname)

    bpy.data.images.remove(img)
    dt = time.monotonic() - t0
    total_disk_kb = sum(os.path.getsize(os.path.join(out_dir, p)) for p in paths) / 1024.0
    print(
        f"[gen] created {num_frames} frames ({width}x{height}) in {dt:.2f}s "
        f"(disk={total_disk_kb:.0f}KB)",
        flush=True,
    )
    return paths


def run_vse_pass(label, cache_limit_mb, frame_dir, frame_names, width=1920, height=1080):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.context.preferences.system.memory_cache_limit = cache_limit_mb

    scene = bpy.context.scene
    scene.render.resolution_x = width
    scene.render.resolution_y = height
    scene.render.resolution_percentage = 100
    scene.render.use_sequencer = True
    scene.frame_start = 1
    scene.frame_end = len(frame_names)

    scene.sequence_editor_create()
    se = scene.sequence_editor
    se.use_cache_raw = True
    se.use_cache_final = True

    first_path = os.path.join(frame_dir, frame_names[0])
    strip = se.strips.new_image(
        name="StressStrip",
        filepath=first_path,
        channel=1,
        frame_start=1,
    )
    for fname in frame_names[1:]:
        strip.elements.append(fname)

    rss_before = vm_rss_mb()
    hwm_before = vm_hwm_mb()
    peak_cache_total = 0
    peak_cache_raw = 0
    peak_cache_final = 0
    peak_rss = rss_before

    t0 = time.monotonic()
    for f in range(1, len(frame_names) + 1):
        scene.frame_set(f)
        bpy.ops.render.render(write_still=False)
        raw_mb = se.cache_raw_size
        fin_mb = se.cache_final_size
        tot_mb = raw_mb + fin_mb
        rss_now = vm_rss_mb()
        if tot_mb > peak_cache_total:
            peak_cache_total = tot_mb
        if raw_mb > peak_cache_raw:
            peak_cache_raw = raw_mb
        if fin_mb > peak_cache_final:
            peak_cache_final = fin_mb
        if rss_now > peak_rss:
            peak_rss = rss_now
        if f in (1, len(frame_names)) or (f % 10 == 0):
            print(
                f"[{label} limit={cache_limit_mb}MB] frame {f:03d}/{len(frame_names):03d}: "
                f"cache_raw={raw_mb}MB cache_final={fin_mb}MB cache_total={tot_mb}MB "
                f"rss={rss_now:.0f}MB rss_peak={vm_hwm_mb():.0f}MB",
                flush=True,
            )

    elapsed = time.monotonic() - t0
    rss_after = vm_rss_mb()
    final_cache_raw = se.cache_raw_size
    final_cache_final = se.cache_final_size
    final_cache_total = final_cache_raw + final_cache_final

    res = {
        "label": label,
        "limit_mb": cache_limit_mb,
        "frames": len(frame_names),
        "elapsed_s": round(elapsed, 2),
        "rss_before_mb": round(rss_before, 1),
        "rss_after_mb": round(rss_after, 1),
        "rss_growth_mb": round(rss_after - rss_before, 1),
        "peak_rss_mb": round(peak_rss, 1),
        "vm_hwm_mb": round(vm_hwm_mb(), 1),
        "peak_cache_raw_mb": peak_cache_raw,
        "peak_cache_final_mb": peak_cache_final,
        "peak_cache_total_mb": peak_cache_total,
        "final_cache_total_mb": final_cache_total,
    }
    print(
        f"[{label} limit={cache_limit_mb}MB] RESULT: elapsed={res['elapsed_s']:.2f}s "
        f"rss_before={res['rss_before_mb']:.0f}MB rss_after={res['rss_after_mb']:.0f}MB "
        f"rss_growth={res['rss_growth_mb']:+.0f}MB peak_rss={res['peak_rss_mb']:.0f}MB "
        f"vm_hwm={res['vm_hwm_mb']:.0f}MB peak_cache={peak_cache_total}MB "
        f"(raw={peak_cache_raw}MB final={peak_cache_final}MB)",
        flush=True,
    )
    return res


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description="VSE/ImBuf cache stress test")
    p.add_argument("--frames", type=int, default=40, help="Number of 1920x1080 frames")
    p.add_argument("--cap-mb", type=int, default=128, help="Low cache cap in MB")
    return p.parse_args(argv)


def main():
    args = parse_args()
    factory_limit = bpy.context.preferences.system.memory_cache_limit
    print(
        f"=== cache_stress (factory memory_cache_limit={factory_limit}MB, "
        f"frames={args.frames}, cap_mb={args.cap_mb}) ===",
        flush=True,
    )

    tmp_dir = tempfile.mkdtemp(prefix="stephender_vse_cache_")
    try:
        frame_names = generate_frames(tmp_dir, args.frames)
        # Run capped pass FIRST so VmHWM reflects the capped workload cleanly.
        r_cap = run_vse_pass("capped", args.cap_mb, tmp_dir, frame_names)
        r_def = run_vse_pass("default", factory_limit, tmp_dir, frame_names)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    cache_populated = r_def["peak_cache_total_mb"] > 0 and r_cap["peak_cache_total_mb"] > 0
    # Eviction engaged if capped pass stayed below default pass and near cap_mb
    # (allow up to +64 MB headroom for in-flight frame buffers before eviction).
    cache_limit_engaged = (
        cache_populated
        and r_cap["peak_cache_total_mb"] < r_def["peak_cache_total_mb"]
        and r_cap["peak_cache_total_mb"] <= args.cap_mb + 64
    )
    ok = cache_populated and cache_limit_engaged

    print(
        f"=== SUMMARY: factory_limit={factory_limit}MB "
        f"capped({args.cap_mb}MB)_peak_cache={r_cap['peak_cache_total_mb']}MB "
        f"capped_rss_growth={r_cap['rss_growth_mb']:+.0f}MB "
        f"default_peak_cache={r_def['peak_cache_total_mb']}MB "
        f"default_rss_growth={r_def['rss_growth_mb']:+.0f}MB "
        f"vm_hwm={r_def['vm_hwm_mb']:.0f}MB "
        f"CACHE_POPULATED={cache_populated} "
        f"CACHE_LIMIT_ENGAGED={cache_limit_engaged} PASS={ok} ===",
        flush=True,
    )
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
