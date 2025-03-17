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

    # Configure synchronous_standby_names based on consistency mode
    if [ "$CONSISTENCY_MODE" = "sync" ]; then
        echo "Setting up STRONG consistency (synchronous replication)"
        echo "synchronous_commit = on" >> "$PGDATA/postgresql.conf"
        echo "synchronous_standby_names = '*'" >> "$PGDATA/postgresql.conf"
    else
        echo "Setting up EVENTUAL consistency (asynchronous replication)"
        echo "synchronous_commit = off" >> "$PGDATA/postgresql.conf"
        echo "synchronous_standby_names = ''" >> "$PGDATA/postgresql.conf"
    fi

    # Configure pg_hba.conf to allow replication connections from any IP
    echo "host replication replicator all md5" >> "$PGDATA/pg_hba.conf"
    # Start PostgreSQL to apply configurations and create the replication user
    # gosu $USER pg_ctl start -D "$PGDATA" -w
    
    #Temporarily blocking to run the container forever
    #tail -f /dev/null
    
    # Start PostgreSQL temporarily to create superuser (POSTGRES_USER)
    echo "Starting PostgreSQL temporarily to create superuser..."
    gosu $USER pg_ctl start -D "$PGDATA" -w

    # Ensure the POSTGRES_USER (superuser) exists
    if ! gosu $USER psql -U postgres -c '\du' | grep -qw "$POSTGRES_USER"; then
        echo "Creating superuser $POSTGRES_USER..."
        gosu $USER psql -U postgres -c "CREATE USER $POSTGRES_USER WITH SUPERUSER PASSWORD 'pgpass';"
    fi

    # Ensure the POSTGRES_DB (database) exists
    if ! gosu $USER psql -U postgres -c '\l' | grep -qw "$POSTGRES_DB"; then
        echo "Creating database $POSTGRES_DB..."
        gosu $USER psql -U postgres -c "CREATE DATABASE $POSTGRES_DB;"
    fi

    #echo "Creating replication user..."
    gosu $USER psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "CREATE ROLE replicator WITH REPLICATION PASSWORD 'replicator_password' LOGIN;"

    #gosu $USER pg_ctl stop -D "$PGDATA"

    #Start PostgreSQL with the superuser
    #echo "Starting PostgreSQL with the superuser..."
    #exec postgres
    
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

    # tail -f /dev/null
    #Sleep for 10 seconds to allow postgres to shutdown
    sleep 5

    # Perform base backup from primary to initialize replication
    echo "Running pg_basebackup to replicate data from primary at $REPLICATE_FROM..."

    export PGPASSWORD='replicator_password'
    pg_basebackup -h "$REPLICATE_FROM" -D "$PGDATA" -U replicator -Fp -Xs -P -R
    echo "Fixing permissions for PGDATA..."
    chown -R postgres:postgres "$PGDATA"
    chmod 700 "$PGDATA"

    # Run delay script to simulate network delay
    ################  DELAY SIMULATION  ################################
    /home/pg_delay.sh 2000ms 1000ms 25% normal

    # Create standby.signal file for PostgreSQL 12+
    touch "$PGDATA/standby.signal"

    # Modify recovery configuration for consistency mode
    if [ "$CONSISTENCY_MODE" = "strong" ]; then
        echo "Configuring STRONG consistency (synchronous replica)"
        echo "primary_conninfo = 'host=$REPLICATE_FROM port=5432 user=replicator password=replicator_password application_name=replica'" >> "$PGDATA/postgresql.conf"
    else
        echo "Configuring EVENTUAL consistency (asynchronous replica)"
        echo "primary_conninfo = 'host=$REPLICATE_FROM port=5432 user=replicator password=replicator_password application_name=replica'" >> "$PGDATA/postgresql.conf"
    fi

    # Change ownership to postgres
    chown -R postgres:postgres "$PGDATA"

    #Start postgress
    gosu $USER pg_ctl start -D "$PGDATA" -w
fi

tail -f /dev/null