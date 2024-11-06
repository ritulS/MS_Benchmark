#!/bin/bash
set -e

############## PRIMARY CONFIGURATION ##############
if [ "$IS_REPLICA" = false ]; then 
    echo "Configuring as primary pg container"

    USER=postgres
    # Initialize the database if not already initialized
    if [ ! -f "$PGDATA/PG_VERSION" ]; then
        echo "Initializing PostgreSQL data directory at $PGDATA"
        gosu $USER initdb -D "$PGDATA"
    else
        echo "PostgreSQL data directory already initialized"
    fi

    # Configure replication settings in postgresql.conf
    echo "Configuring replication settings..."
    cat >> "$PGDATA/postgresql.conf" <<EOF
# Replication settings for primary
wal_level = replica
max_wal_senders = 3
wal_keep_size = 64MB
EOF

    # Configure pg_hba.conf to allow replication connections from any IP
    echo "host replication replicator all md5" >> "$PGDATA/pg_hba.conf"
    # Start PostgreSQL to apply configurations and create the replication user
    # gosu $USER pg_ctl start -D "$PGDATA" -w

    # Start PostgreSQL temporarily to create superuser (POSTGRES_USER)
    echo "Starting PostgreSQL temporarily to create superuser..."
    gosu $USER pg_ctl start -D "$PGDATA" -w

    # Ensure the POSTGRES_USER (superuser) exists
    if ! gosu $USER psql -U "$POSTGRES_USER" -c '\du' | grep -qw "$POSTGRES_USER"; then
        echo "Creating superuser $POSTGRES_USER..."
        gosu $USER psql -U postgres -c "CREATE USER $POSTGRES_USER WITH SUPERUSER PASSWORD 'pgpass';"
    fi

    echo "Creating replication user..."
    gosu $USER psql -U "$POSTGRES_USER" -c "CREATE ROLE replicator WITH REPLICATION PASSWORD 'replicator_password' LOGIN;"

    gosu $USER pg_ctl stop -D "$PGDATA"

    exec postgres

############## REPLICA CONFIGURATION ##############
else 
    echo "Configuring as replica pg container"
    USER=postgres
    # Check if REPLICATE_FROM is set
    if [ -z "$REPLICATE_FROM" ]; then
        echo "Error: REPLICATE_FROM environment variable not set for replica configuration."
        exit 1
    fi

    # Stop PostgreSQL if it's already running
    gosu $USER pg_ctl stop -D "$PGDATA" || true

    # Clear existing data directory
    echo "Clearing existing data directory..."
    rm -rf "$PGDATA"/*

    # Perform base backup from primary to initialize replication
    echo "Running pg_basebackup to replicate data from primary at $REPLICATE_FROM..."
    pg_basebackup -h "$REPLICATE_FROM" -D "$PGDATA" -U replicator -Fp -Xs -P -R

    # Run delay script to simulate network delay
    ################  DELAY SIMULATION  ################################
    /home/delay.sh $DELAY_MS $JITTER_MS $CORRELATION $DISTRIBUTION

fi

exec postgres