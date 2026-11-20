#!/usr/bin/env python3
"""Post-render steady-state RSS retention test for Stephender (Fix 3 baseline).

Renders BMW27 (Cycles, CPU, 960x540, 64 samples, no denoising), then waits 30 s
and measures RSS to quantify how much render memory stays retained in the
process (e.g. TBB allocator pools) after render completion.

Run:
  blender --background --factory-startup --python bench/post_render_rss.py
Or with an explicit scene:
  blender --background --factory-startup path/to/BMW27.blend --python bench/post_render_rss.py
Optional args (after --):
  --scene PATH    Path to .blend file (default: BMW27.blend in project scenes/)
  --samples N     Cycles samples (default: 64)
  --wait S        Seconds to wait after render completion (default: 30)
  --frame F       Frame to render (default: 0)
  --output PATH   Output PNG path (default: temp file, deleted after check)
"""
import argparse
import os
import sys
import tempfile
import time
import bpy

DEFAULT_SCENE = "/home/hatch/workspace/projects/blender-optimize/scenes/BMW27.blend"


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


def parse_args():
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(description="Post-render RSS retention test")
    p.add_argument("--scene", default=None, help="Path to BMW27.blend")
    p.add_argument("--samples", type=int, default=64, help="Cycles samples (default: 64)")
    p.add_argument("--wait", type=int, default=30, help="Post-render wait in seconds")
    p.add_argument("--frame", type=int, default=0, help="Frame to render (default: 0)")
    p.add_argument("--output", default=None, help="Output PNG path")
    return p.parse_args(argv)


def main():
    args = parse_args()

    if args.scene:
        if not os.path.isfile(args.scene):
            print(f"FAIL: scene not found: {args.scene}", flush=True)
            sys.exit(1)
        bpy.ops.wm.open_mainfile(filepath=args.scene)
        scene_path = args.scene
    elif bpy.data.filepath:
        scene_path = bpy.data.filepath
    else:
        if not os.path.isfile(DEFAULT_SCENE):
            print(f"FAIL: default scene not found: {DEFAULT_SCENE}", flush=True)
            sys.exit(1)
        bpy.ops.wm.open_mainfile(filepath=DEFAULT_SCENE)
        scene_path = DEFAULT_SCENE

    scene = bpy.context.scene
    scene.render.engine = 'CYCLES'
    scene.cycles.device = 'CPU'
    scene.cycles.samples = args.samples
    scene.cycles.use_denoising = False
    scene.render.resolution_x = 1920
    scene.render.resolution_y = 1080
    scene.render.resolution_percentage = 50
    scene.render.image_settings.file_format = 'PNG'
    scene.frame_set(args.frame)

    cleanup_out = False
    if args.output:
        out_path = args.output
    else:
        fd, out_path = tempfile.mkstemp(prefix="stephender_bmw27_", suffix=".png")
        os.close(fd)
        cleanup_out = True
    scene.render.filepath = out_path

    rss_before = vm_rss_mb()
    hwm_before = vm_hwm_mb()
    print(
        f"=== post_render_rss: scene={scene_path} "
        f"res={scene.render.resolution_x * scene.render.resolution_percentage // 100}x"
        f"{scene.render.resolution_y * scene.render.resolution_percentage // 100} "
        f"samples={scene.cycles.samples} device={scene.cycles.device} "
        f"denoising={scene.cycles.use_denoising} ===",
        flush=True,
    )
    print(
        f"[pre-render] rss={rss_before:.1f}MB rss_peak={hwm_before:.1f}MB",
        flush=True,
    )

    t0 = time.monotonic()
    ret = bpy.ops.render.render(write_still=True)
    render_seconds = time.monotonic() - t0

    rss_after_0s = vm_rss_mb()
    peak_rss_during = vm_hwm_mb()

    out_bytes = os.path.getsize(out_path) if os.path.isfile(out_path) else 0
    if cleanup_out and os.path.isfile(out_path):
        os.remove(out_path)

    print(
        f"[post-render t=0s] render_s={render_seconds:.2f}s ret={ret} "
        f"out_bytes={out_bytes} rss={rss_after_0s:.1f}MB peak_rss={peak_rss_during:.1f}MB",
        flush=True,
    )

    if ret != {'FINISHED'} or out_bytes <= 0:
        print(f"FAIL: render failed (ret={ret}, out_bytes={out_bytes})", flush=True)
        sys.exit(1)

    waited = 0
    while waited < args.wait:
        step = min(5, args.wait - waited)
        time.sleep(step)
        waited += step
        print(
            f"[post-render t={waited}s] rss={vm_rss_mb():.1f}MB peak_rss={vm_hwm_mb():.1f}MB",
            flush=True,
        )

    rss_after_wait = vm_rss_mb()
    peak_final = vm_hwm_mb()
    retained_vs_before = rss_after_wait - rss_before
    released_during_wait = rss_after_0s - rss_after_wait
    released_vs_peak = peak_rss_during - rss_after_wait

    print(
        f"=== SUMMARY: render_seconds={render_seconds:.2f} "
        f"rss_before_mb={rss_before:.1f} "
        f"peak_rss_during_render_mb={peak_rss_during:.1f} "
        f"rss_after_0s_mb={rss_after_0s:.1f} "
        f"rss_after_{args.wait}s_mb={rss_after_wait:.1f} "
        f"retained_vs_before_mb={retained_vs_before:+.1f} "
        f"released_vs_peak_mb={released_vs_peak:.1f} "
        f"released_during_wait_mb={released_during_wait:+.1f} "
        f"output_bytes={out_bytes} PASS=True ===",
        flush=True,
    )
    sys.exit(0)


if __name__ == "__main__":
    main()
