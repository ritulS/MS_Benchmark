#!/bin/bash

DELAY_MS=$1
JITTER_MS=$2
CORRELATION=$([ "$3" = "0%" ] && echo "" || echo "$3")
DISTRIBUTION=$4

ifconfig -a | grep -e '^eth' | cut -d ':' -f 1 | while read -r INTERFACE ; do
  echo ">> Handling $INTERFACE"

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