#!/bin/bash

DELAY_MS=$1
JITTER_MS=$2
CORRELATION=$([ "$3" = "0%" ] && echo "" || echo "$3")
DISTRIBUTION=$4

ifconfig -a | grep -e '^eth' | cut -d ':' -f 1 | while read -r INTERFACE ; do
  echo ">> Handling $INTERFACE"
  # clean existing rules
  # echo "Removing old rules ..."
  # tc qdisc del dev $INTERFACE root
  # echo "Removed Old rules!"

  # echo "Adding new rules ..."
  # # apply to all eth* interfaces
  # tc qdisc add dev $INTERFACE root handle 1: prio

  ## apply rules for each docker IP - weird docker stack bs where containers have multiple ips
  # for IP in $(dig +short $1); do
  #   echo "  - Add rule for dst $IP"
  #   tc filter add dev $INTERFACE parent 1:0 protocol ip prio 1 u32 match ip dst $IP flowid 2:1
  # done;

  echo "  - Adding 'netem delay $DELAY_MS $JITTER_MS $CORRELATION $DISTRIBUTION'"
  echo "tc qdisc add dev $INTERFACE root netem delay $DELAY_MS $JITTER_MS $CORRELATION"
  if [ -n "$DISTRIBUTION" ]; then
    tc qdisc add dev $INTERFACE root netem delay $DELAY_MS $JITTER_MS $CORRELATION distribution $DISTRIBUTION
  else
    tc qdisc add dev $INTERFACE root netem delay $DELAY_MS $JITTER_MS $CORRELATION
  fi

  # tc qdisc add dev $INTERFACE parent 1:1 handle 2: netem delay $DELAY_MS $JITTER_MS $CORRELATION $DISTRIBUTION
  echo "Done!"
done;