#!/bin/bash


DELAY_MS="100ms"            # Delay in milliseconds
JITTER_MS="10ms"            # Jitter in milliseconds
CORRELATION="25%"         # Correlation percentage
DISTRIBUTION="distribution normal"     # Distribution type (e.g., 'uniform', 'normal')


# if mongo --eval "rs.status().myState" | grep -q PRIMARY; then
#     # Primary container: No delay
#     echo "Starting MongoDB as primary (no delay)"
#     exec mongod
# else
#     # Replica container: Apply delay
#     echo "Starting MongoDB replica with delay"
#     /home/delay.sh $DELAY_MS $JITTER_MS $CORRELATION $DISTRIBUTION
#     exec mongod
# fi

# checkif replica dict file exists
    # sleep until you get the file

# Run the delay script with predefined arguments
/home/delay.sh $DELAY_MS $JITTER_MS $CORRELATION $DISTRIBUTION

# Start MongoDB as the main process
exec mongod
