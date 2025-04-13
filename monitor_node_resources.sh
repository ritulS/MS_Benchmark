#!/bin/bash

# File: monitor_resource_exhaustion.sh
# Monitors file descriptors, TCP ports, and ulimits in real time

refresh_interval=2  # seconds

echo "Monitoring file descriptors, TCP ports, and limits. Press Ctrl+C to exit."
echo

while true; do
    clear
    echo "===== System Resource Monitor ($(date)) ====="
    
    # --- 1. Global File Descriptor Usage ---
    echo
    echo "🔎 File Descriptors:"
    lsof | wc -l | awk '{print "Total open file descriptors:", $1}'
    cat /proc/sys/fs/file-nr | awk '{print "Allocated:", $1, "| Unused:", $2, "| Max allowed:", $3}'

    # --- 2. Process with Most Open FDs ---
    echo
    echo "🔧 Top Processes by FD Count:"
    ls /proc/*/fd 2>/dev/null | awk -F/ '{print $3}' | sort | uniq -c | sort -nr | head -5 | while read count pid; do
        pname=$(ps -p $pid -o comm= 2>/dev/null)
        echo "PID: $pid ($pname) - Open FDs: $count"
    done

    # --- 3. TCP Socket Stats ---
    echo
    echo "🌐 TCP Socket State Summary:"
    ss -s

    # --- 4. Port usage ---
    echo
    echo "📦 Listening TCP Ports:"
    ss -tuln | grep LISTEN | awk '{print $5}' | sort | uniq -c | sort -nr | head -10

    # --- 5. Ulimit for current shell ---
    echo
    echo "⚙️  Shell ulimit -n (max FDs for this session):"
    ulimit -n

    # --- 6. Global system limits ---
    echo
    echo "🧱 Global system limit for file descriptors:"
    sysctl fs.file-max

    sleep "$refresh_interval"
done

