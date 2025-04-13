#!/bin/sh

echo "🧩 Container Health Check: $(hostname)"
echo "------------------------------------------------------"

# Open file descriptors
OPEN_FD=$(ls /proc/1/fd 2>/dev/null | wc -l)
FD_LIMIT=$(ulimit -n 2>/dev/null)

echo "📂 File Descriptors"
echo "------------------------------------------------------"
echo "Open FDs                             : $OPEN_FD / $FD_LIMIT"

# Socket count (via file descriptors pointing to sockets)
SOCKETS=$(ls -l /proc/1/fd 2>/dev/null | grep socket | wc -l)

echo ""
echo "🔌 Socket Usage"
echo "------------------------------------------------------"
echo "Open Socket FDs                      : $SOCKETS"

# Memory usage (RSS from /proc/1/status)
RSS_KB=$(grep VmRSS /proc/1/status 2>/dev/null | awk '{print $2}')
RSS_MB=$(( ${RSS_KB:-0} / 1024 ))

echo ""
echo "🧠 Memory (Process 1)"
echo "------------------------------------------------------"
echo "Resident Memory                      : ${RSS_MB} MB"

# CPU time used by PID 1 (utime + stime)
CPU_TICKS=$(awk '{print $14 + $15}' /proc/1/stat 2>/dev/null)
CLK_TCK=$(getconf CLK_TCK)
CPU_SECS=$(( ${CPU_TICKS:-0} / ${CLK_TCK:-100} ))

echo ""
echo "⚙️  CPU (Process 1)"
echo "------------------------------------------------------"
echo "CPU Time Used                        : ${CPU_SECS}s"

echo ""
echo "✅ Lightweight check complete."

