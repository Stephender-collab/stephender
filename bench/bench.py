#!/usr/bin/env python3
"""Blender baseline benchmark harness (Phase 1, read-only benchmarking).

Runs a Blender command, measures wall time and peak RSS (VmHWM) by polling
/proc/<pid>/status. No GNU time on this machine, so we poll ourselves.
Usage: python3 bench.py <label> <logfile> -- <blender args...>
Prints a one-line JSON summary to stdout; full Blender output goes to logfile.
"""
import json
import os
import subprocess
import sys
import time


def read_vmhwm(pid):
    try:
        with open(f"/proc/{pid}/status") as f:
            for line in f:
                if line.startswith("VmHWM:"):
                    return int(line.split()[1])  # kB
    except (FileNotFoundError, ProcessLookupError):
        return None
    return None


def main():
    label = sys.argv[1]
    logfile = sys.argv[2]
    assert sys.argv[3] == "--"
    cmd = sys.argv[4:]
    t0 = time.monotonic()
    peak_kb = 0
    with open(logfile, "w") as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT)
        # NOTE (Antigravity review 2026-11-20): the old loop did proc.poll()
        # then time.sleep(0.1), adding up to +0.10 s of artificial latency to
        # short runs (~9% on ~1.1 s runs). proc.wait(timeout=0.1) returns the
        # moment the process exits, so wall time has no sleep overshoot.
        while True:
            try:
                proc.wait(timeout=0.1)
                break
            except subprocess.TimeoutExpired:
                pass
            hwm = read_vmhwm(proc.pid)
            if hwm is not None and hwm > peak_kb:
                peak_kb = hwm
        # final read (process may already be gone; VmHWM is gone with it,
        # so the polled peak is what we report)
    wall = time.monotonic() - t0
    # ru_maxrss of children (max RSS of the largest waited-for child, kB on Linux)
    import resource

    ru = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
    print(json.dumps({
        "label": label,
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "wall_seconds": round(wall, 2),
        "peak_rss_kb_polled": peak_kb,
        "peak_rss_mb_polled": round(peak_kb / 1024, 1),
        "ru_maxrss_mb_children": round(ru / 1024, 1),
        "log": logfile,
    }))


if __name__ == "__main__":
    main()
