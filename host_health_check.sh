#!/bin/bash

# Color codes
RED=$(tput setaf 1)
YELLOW=$(tput setaf 3)
GREEN=$(tput setaf 2)
BOLD=$(tput bold)
RESET=$(tput sgr0)

TARGET_PORT=${1:-5000}
HOSTNAME=$(hostname)

divider() {
  echo -e "${BOLD}------------------------------------------------------${RESET}"
}

section() {
  echo -e "\n${BOLD}$1${RESET}"
  divider
}

header() {
  echo -e "\n${BOLD}🖥️  System Health Check: $HOSTNAME${RESET}"
  divider
}

metric() {
  printf "%-35s %s\n" "$1" "$2"
}

warn_if_high() {
  local label=$1
  local used=$2
  local total=$3
  local threshold=${4:-90}
  local percent=$((100 * used / total))

  local color=$GREEN
  if (( percent > threshold )); then
    color=$RED
  elif (( percent > threshold - 10 )); then
    color=$YELLOW
  fi

  metric "$label" "${color}$used / $total (${percent}%)${RESET}"
}

header

# File Descriptors
section "📂 File Descriptors"
read used unused max < /proc/sys/fs/file-nr
warn_if_high "Open File Descriptors" "$used" "$max"

# TCP Sockets
section "🔌 TCP Connections"
total_tcp=$(ss -s | awk '/TCP:/ {print $2}')
metric "Total TCP Connections" "$total_tcp"

tcp_on_port=$(netstat -ant | grep ":$TARGET_PORT" | wc -l)
metric "Connections on Port $TARGET_PORT" "$tcp_on_port"

# Ephemeral Ports
read port_start port_end < /proc/sys/net/ipv4/ip_local_port_range
ephemeral_used=$(netstat -ant | awk '{print $5}' | grep -oE '[0-9]+$' | sort -n | uniq | wc -l)
warn_if_high "Unique Ephemeral Ports" "$ephemeral_used" "$((port_end - port_start))"

# Conntrack
if [[ -f /proc/sys/net/netfilter/nf_conntrack_count ]]; then
  section "🌐 Conntrack (NAT Table)"
  ct_count=$(cat /proc/sys/net/netfilter/nf_conntrack_count)
  ct_max=$(cat /proc/sys/net/netfilter/nf_conntrack_max)
  warn_if_high "Active Conntrack Entries" "$ct_count" "$ct_max"
fi

# CPU and Memory
section "🧠 CPU and Memory (Top 3 Processes)"
top -b -n1 | head -n 12 | tail -n 3

divider

