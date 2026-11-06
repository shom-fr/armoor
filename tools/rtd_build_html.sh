#!/bin/bash
# Read the Docs html job (see .readthedocs.yaml).
#
# RTD keeps the output of a command only once it returns, and has been killing
# the Sphinx command on time out, without any log, although the same build
# passes on the CI and locally. So write everything to files, stop Sphinx well
# before RTD's limit, sample the machine state every minute, and print it all
# at the end.

cd "$(dirname "$0")/.." || exit 1

sphinx_log=$(mktemp)
monitor_log=$(mktemp)

echo "nproc=$(nproc) cpu_count=$(python -c 'import os; print(os.cpu_count())')"
for limit in /sys/fs/cgroup/memory.max /sys/fs/cgroup/cpu.max; do
    [ -r "$limit" ] && echo "$limit: $(cat "$limit")"
done
free -m
df -h .

(
    while sleep 60; do
        {
            echo "=== $(date +%T)"
            free -m | sed -n 2p
            [ -r /sys/fs/cgroup/memory.current ] && echo "cgroup memory: $(cat /sys/fs/cgroup/memory.current)"
            ps -eo pid,ppid,stat,etimes,rss,pcpu,args --sort=-rss | head -12 | cut -c1-150
            echo "sphinx: $(tail -c 200 "$sphinx_log" | tr '\r' '\n' | tail -1 | cut -c1-120)"
        } >> "$monitor_log" 2>&1
    done
) > /dev/null 2>&1 &  # its `sleep` outlives the kill: must not hold our stdout
monitor_pid=$!

# No core dump on SIGABRT: only the faulthandler stacks are wanted.
ulimit -c 0
timeout -k 30 -s ABRT 900 python -X faulthandler -m sphinx -T -b html \
    -d _build/doctrees -D language=en doc "$READTHEDOCS_OUTPUT/html" \
    > "$sphinx_log" 2>&1 < /dev/null
status=$?

kill "$monitor_pid"
cat "$sphinx_log"
echo "=== machine state during the build"
cat "$monitor_log"
echo "=== sphinx exit status: $status"
exit "$status"
