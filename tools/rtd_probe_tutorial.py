"""Run one tutorial on its own and report its duration and memory (RTD probe).

Read the Docs kills the Sphinx command without any log (see
tools/rtd_build_html.sh). RTD keeps the output of each command that returns, so
.readthedocs.yaml runs every tutorial through this script as its own command
before Sphinx: if one of them stalls or kills the container, the logs of the
previous ones are kept, and the last command shown is the culprit.

Usage: python tools/rtd_probe_tutorial.py tutorials/02_cli/04_comp_config.py
"""

import os
import resource
import signal
import subprocess
import sys
import threading
import time

TIMEOUT = 420  # s, per tutorial
CGROUP = "/sys/fs/cgroup"


def read(path):
    try:
        with open(path) as f:
            return f.read()
    except OSError:
        return ""


def unreclaimable():
    """anon + shmem of the container's cgroup, in bytes (page cache excluded)."""
    total = 0
    for line in read(f"{CGROUP}/memory.stat").splitlines():
        key, _, value = line.partition(" ")
        if key in ("anon", "shmem"):
            total += int(value)
    return total


def main(script):
    script = os.path.abspath(script)
    env = dict(os.environ, MPLBACKEND="Agg")
    peak = [unreclaimable()]
    stop = threading.Event()

    def sample():
        while not stop.wait(1):
            peak[0] = max(peak[0], unreclaimable())

    threading.Thread(target=sample, daemon=True).start()
    print(f"=== {os.path.relpath(script)}: start, anon+shmem={peak[0] >> 20} MiB", flush=True)
    start = time.monotonic()
    # Same working directory as sphinx-gallery: the script's own directory.
    proc = subprocess.Popen(
        [sys.executable, script],
        cwd=os.path.dirname(script),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        start_new_session=True,
    )
    try:
        out, _ = proc.communicate(timeout=TIMEOUT)
        status = proc.returncode
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        out, _ = proc.communicate()
        status = f"killed after {TIMEOUT} s"
    elapsed = time.monotonic() - start
    stop.set()
    maxrss = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss >> 10  # KiB -> MiB

    print((out or "")[-4000:])
    print(
        f"=== {os.path.relpath(script)}: status={status} elapsed={elapsed:.0f} s "
        f"peak anon+shmem={peak[0] >> 20} MiB (container) "
        f"max RSS of one subprocess={maxrss} MiB"
    )
    events = read(f"{CGROUP}/memory.events").split()
    print("memory.events:", " ".join(events))
    # Always 0: RTD stops at the first failing command, and every tutorial
    # should be probed (a failure is visible in the log above).
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
