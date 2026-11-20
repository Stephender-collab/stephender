# Runtime test for Proposal 1 (undomemory default 0 -> 256) on the PREBUILT binary.
# No build needed: sets bpy.context.preferences.edit.undo_memory_limit at runtime.
# Replicates Blender's own tests/performance/tests/undo.py Subsurf-9 scenario,
# with instrumentation: undo stack memory + peak RSS after each push, and a
# verification that undo still works (vertex positions + operator return value).
# Also probes the edge case the Antigravity review flagged: a single step bigger
# than the limit (simulated with limit=1MB) — does Ctrl+Z break?
# Run: blender --background --factory-startup --python undo_runtime_test.py
import bpy
import mathutils
import time


def vm_hwm_mb():
    try:
        with open('/proc/self/status') as f:
            for line in f:
                if line.startswith('VmHWM:'):
                    return int(line.split()[1]) / 1024.0
    except Exception:
        return -1.0
    return -1.0


def mem_undo_mb():
    try:
        return bpy.app.memory_usage_undo() / (1024.0 * 1024.0)
    except Exception:
        return -1.0


def min_vert_x(ob):
    return min(v.co.x for v in ob.data.vertices)


def run_scenario(limit):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.object
    bpy.context.preferences.edit.undo_memory_limit = limit

    t0 = time.time()
    ob.modifiers.new(name="Subsurf", type='SUBSURF').levels = 9
    bpy.ops.object.modifier_apply(modifier="Subsurf")
    t_apply = time.time() - t0
    print(f"[{limit}] subsurf9 apply: {t_apply:.1f}s verts={len(ob.data.vertices)} "
          f"undo_mem={mem_undo_mb():.1f}MB rss_peak={vm_hwm_mb():.0f}MB", flush=True)

    start = time.time()
    bpy.ops.ed.undo_push()
    print(f"[{limit}] after initial push: undo_mem={mem_undo_mb():.1f}MB rss_peak={vm_hwm_mb():.0f}MB", flush=True)

    # Empty undo step.
    bpy.ops.ed.undo_push()
    bpy.ops.ed.undo()
    bpy.ops.ed.redo()

    # Object-modified undo step.
    ob = bpy.data.objects["Cube"]
    ob.location.x += 1.0
    bpy.ops.ed.undo_push()
    print(f"[{limit}] after obj push: undo_mem={mem_undo_mb():.1f}MB rss_peak={vm_hwm_mb():.0f}MB",
          flush=True)
    bpy.ops.ed.undo()
    bpy.ops.ed.undo()
    bpy.ops.ed.redo()
    bpy.ops.ed.redo()

    # Mesh-modified undo step.
    ob = bpy.data.objects["Cube"]
    ob.data.transform(mathutils.Matrix.Translation((1, 0, 0)))
    bpy.ops.ed.undo_push()
    print(f"[{limit}] after mesh push: undo_mem={mem_undo_mb():.1f}MB rss_peak={vm_hwm_mb():.0f}MB",
          flush=True)
    bpy.ops.ed.undo()
    bpy.ops.ed.undo()
    bpy.ops.ed.undo()
    bpy.ops.ed.redo()
    bpy.ops.ed.redo()
    bpy.ops.ed.redo()
    elapsed = time.time() - start

    # Verify undo still works: mesh verts were shifted +1 in x.
    # NOTE: Subsurf-9 smoothing moves verts, so absolute min_x is not -1.0/0.0;
    # check the DELTAS instead: undo must shift min_x by -1.0, redo by +1.0.
    ob = bpy.data.objects["Cube"]
    x_after_seq = min_vert_x(ob)
    r_undo = bpy.ops.ed.undo()
    x_after_undo = min_vert_x(bpy.data.objects["Cube"])
    r_redo = bpy.ops.ed.redo()
    x_after_redo = min_vert_x(bpy.data.objects["Cube"])
    d_undo = x_after_undo - x_after_seq
    d_redo = x_after_redo - x_after_undo
    undo_works = (r_undo == {'FINISHED'} and abs(d_undo - (-1.0)) < 1e-3
                  and r_redo == {'FINISHED'} and abs(d_redo - 1.0) < 1e-3)
    print(f"[{limit}] RESULT time={elapsed:.2f}s undo_mem={mem_undo_mb():.1f}MB "
          f"rss_peak={vm_hwm_mb():.0f}MB min_x: seq={x_after_seq:.2f} undo={x_after_undo:.2f} "
          f"redo={x_after_redo:.2f} d_undo={d_undo:.2f} d_redo={d_redo:.2f} "
          f"undo_ret={r_undo} redo_ret={r_redo} "
          f"UNDO_WORKS={undo_works}", flush=True)
    return undo_works


def run_edge_probe():
    # Limit 1MB: the Subsurf-9 initial step (tens of MB) exceeds the limit.
    # Does undo survive, or is Ctrl+Z broken (review's prediction)?
    limit = 1
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.mesh.primitive_cube_add()
    ob = bpy.context.object
    bpy.context.preferences.edit.undo_memory_limit = limit
    ob.modifiers.new(name="Subsurf", type='SUBSURF').levels = 9
    bpy.ops.object.modifier_apply(modifier="Subsurf")
    bpy.ops.ed.undo_push()
    ob = bpy.data.objects["Cube"]
    ob.location.x += 1.0
    bpy.ops.ed.undo_push()
    print(f"[{limit}] edge probe: after pushes undo_mem={mem_undo_mb():.1f}MB "
          f"rss_peak={vm_hwm_mb():.0f}MB loc.x={ob.location.x}", flush=True)
    r_undo = bpy.ops.ed.undo()
    loc_after = bpy.data.objects["Cube"].location.x
    print(f"[{limit}] edge probe RESULT: undo_ret={r_undo} loc.x after undo={loc_after} "
          f"(expect 0.0 if undo works) UNDO_WORKS={r_undo == {'FINISHED'} and loc_after == 0.0}",
          flush=True)


print("=== Proposal 1 runtime test (prebuilt binary, no build) ===", flush=True)
results = {}
for limit in (0, 256, 512):
    results[limit] = run_scenario(limit)
run_edge_probe()
print(f"=== SUMMARY: {results} ===", flush=True)
