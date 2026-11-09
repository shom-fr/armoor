#!/bin/bash
# Read the Docs html job (see .readthedocs.yaml).
#
# Since 2026-10-30, RTD kills the Sphinx command at its build time limit
# without any log. A previous attempt (db4a1d0) wrapped Sphinx in
# `timeout 900` with its output in a file, and even that timeout never fired:
# the whole container stalls, which is what a cgroup at its memory limit does
# (every process, `timeout` included, is throttled until RTD kills the build).
#
# So watch the memory ourselves and stop Sphinx well before the limit (or
# after MAX_SECONDS), while the container still responds, then print the
# Sphinx log and the memory samples: they show which tutorial was running and
# which processes held the memory. RTD keeps a command's output only once the
# command returns.

cd "$(dirname "$0")/.." || exit 1

MAX_SECONDS=${MAX_SECONDS:-1200}  # RTD kills the whole build at ~1800 s
MEM_FRACTION=${MEM_FRACTION:-80}  # % of the memory limit that stops Sphinx
POLL=5

log_dir=$(mktemp -d)
sphinx_log=$log_dir/sphinx.log
monitor_log=$log_dir/monitor.log

# Memory limit and usage: cgroup v2 when bounded, else /proc/meminfo.
# Not memory.current: it includes the page cache (~6.8 GiB left by the conda
# install on RTD), which the kernel reclaims. Count what it cannot reclaim:
# anonymous memory and shmem (/dev/shm, used by multiprocessing).
if [ -r /sys/fs/cgroup/memory.max ] && [ "$(cat /sys/fs/cgroup/memory.max)" != max ]; then
    mem_limit=$(cat /sys/fs/cgroup/memory.max)
    mem_used() { awk '$1 == "anon" || $1 == "shmem" {s += $2} END {print s}' /sys/fs/cgroup/memory.stat; }
else
    mem_limit=$(($(awk '/^MemTotal:/ {print $2}' /proc/meminfo) * 1024))
    mem_used() { echo $((mem_limit - $(awk '/^MemAvailable:/ {print $2}' /proc/meminfo) * 1024)); }
fi
mem_stop=$((mem_limit / 100 * MEM_FRACTION))

echo "nproc=$(nproc)"
for f in /sys/fs/cgroup/memory.max /sys/fs/cgroup/memory.high /sys/fs/cgroup/memory.swap.max /sys/fs/cgroup/cpu.max; do
    [ -r "$f" ] && echo "$f: $(cat "$f")"
done
free -m
echo "memory limit: $((mem_limit >> 20)) MiB, Sphinx stopped above $((mem_stop >> 20)) MiB or after $MAX_SECONDS s"

# No core dump on SIGABRT: only the faulthandler stacks are wanted.
ulimit -c 0
# Own session/process group, so the tutorials' subprocesses can be killed too.
# Serial build (no -j), same as the CI. Extra arguments go to Sphinx.
setsid python -X faulthandler -m sphinx -T -b html \
    -d _build/doctrees -D language=en "$@" doc "$READTHEDOCS_OUTPUT/html" \
    > "$sphinx_log" 2>&1 < /dev/null &
sphinx_pid=$!

start=$SECONDS
peak=0
reason=
last_sample=-60
while kill -0 "$sphinx_pid" 2> /dev/null; do
    used=$(mem_used)
    ((used > peak)) && peak=$used
    elapsed=$((SECONDS - start))
    if ((elapsed - last_sample >= 30)); then
        last_sample=$elapsed
        {
            echo "=== t=${elapsed}s used=$((used >> 20)) MiB peak=$((peak >> 20)) MiB"
            [ -r /sys/fs/cgroup/memory.current ] && echo "cgroup memory.current (with cache): $(($(cat /sys/fs/cgroup/memory.current) >> 20)) MiB"
            [ -r /sys/fs/cgroup/memory.pressure ] && sed 's/^/memory.pressure /' /sys/fs/cgroup/memory.pressure
            ps -eo pid,ppid,etimes,rss,pcpu,args --sort=-rss | head -8 | cut -c1-160
            echo "sphinx: $(tail -c 300 "$sphinx_log" | tr '\r' '\n' | grep -v '^$' | tail -1 | cut -c1-150)"
        } >> "$monitor_log" 2>&1
    fi
    if ((used > mem_stop)); then
        reason="memory $((used >> 20)) MiB > $((mem_stop >> 20)) MiB at t=${elapsed}s"
    elif ((elapsed > MAX_SECONDS)); then
        reason="time limit ${MAX_SECONDS}s reached"
    fi
    if [ -n "$reason" ]; then
        {
            echo "=== STOPPING SPHINX: $reason"
            ps -eo pid,ppid,etimes,rss,pcpu,args --sort=-rss | head -15 | cut -c1-200
        } >> "$monitor_log" 2>&1
        # SIGABRT: faulthandler dumps the Python stacks of every process
        # that has it enabled (Sphinx itself), then kill the whole group.
        kill -ABRT -- "-$sphinx_pid" 2> /dev/null
        sleep 10
        kill -KILL -- "-$sphinx_pid" 2> /dev/null
        break
    fi
    sleep "$POLL"
done
wait "$sphinx_pid"
status=$?

cat "$sphinx_log"
echo "=== memory samples (peak $((peak >> 20)) MiB of $((mem_limit >> 20)) MiB)"
cat "$monitor_log"
for f in /sys/fs/cgroup/memory.events /sys/fs/cgroup/memory.pressure; do
    [ -r "$f" ] && { echo "=== $f"; cat "$f"; }
done
echo "=== sphinx exit status: $status${reason:+ (stopped: $reason)}"
[ -n "$reason" ] && exit 1
exit "$status"
