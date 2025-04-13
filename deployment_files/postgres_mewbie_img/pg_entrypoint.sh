#!/bin/bash
set -e


PG_PORT=5433
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

    # Configure pg_hba.conf to allow replication and connections
    # Open up all DBs for the "pguser" and "replicator" roles
    echo "host replication replicator 0.0.0.0/0 trust" >> "$PGDATA/pg_hba.conf"
    echo "host replication replicator ::/0 trust" >> "$PGDATA/pg_hba.conf"
    echo "host all pguser 0.0.0.0/0 trust" >> "$PGDATA/pg_hba.conf"
    echo "host all replicator 0.0.0.0/0 trust" >> "$PGDATA/pg_hba.conf"


    cat >> "$PGDATA/postgresql.conf" <<EOF
wal_level = replica
max_wal_senders = 3
wal_keep_size = 64MB
max_connections = 700
port = 5433
EOF

    # Start PostgreSQL temporarily to create users and configure
    echo "Starting PostgreSQL temporarily to create superuser..."
    gosu $USER pg_ctl start -D "$PGDATA" -w

    # Ensure the POSTGRES_USER (superuser) exists
    if ! gosu $USER psql -U postgres -p $PG_PORT -tc "SELECT 1 FROM pg_roles WHERE rolname='$POSTGRES_USER'" | grep -q 1; then
        echo "Creating superuser $POSTGRES_USER..."
        gosu $USER psql -U postgres -p $PG_PORT -c "CREATE USER $POSTGRES_USER WITH SUPERUSER PASSWORD 'pgpass';"
    fi

    # Ensure the POSTGRES_DB (database) exists
    if ! gosu $USER psql -U postgres -p $PG_PORT -tc "SELECT 1 FROM pg_database WHERE datname='$POSTGRES_DB'" | grep -q 1; then
        echo "Creating database $POSTGRES_DB..."
        gosu $USER psql -U postgres -p $PG_PORT -c "CREATE DATABASE $POSTGRES_DB;"
    fi

    # replicator role creation 
    echo "Creating replication user..."
    gosu $USER psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -p $PG_PORT -tc "SELECT 1 FROM pg_roles WHERE rolname='replicator'" | grep -q 1 || \
    gosu $USER psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -p $PG_PORT -c "CREATE ROLE replicator WITH REPLICATION PASSWORD 'replicator_password' LOGIN;"

    # Configure settings using ALTER SYSTEM
    echo "Applying config via ALTER SYSTEM..."
    # gosu $USER psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "ALTER SYSTEM SET wal_level = 'replica';"
    # gosu $USER psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "ALTER SYSTEM SET max_wal_senders = 3;"
    # gosu $USER psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "ALTER SYSTEM SET wal_keep_size = '64MB';"

    if [ "$CONSISTENCY_MODE" = "strong" ]; then
        echo "Setting up STRONG consistency (synchronous replication)"
        gosu $USER psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -p $PG_PORT -c "ALTER SYSTEM SET synchronous_commit = 'remote_write';"
        gosu $USER psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -p $PG_PORT -c "ALTER SYSTEM SET synchronous_standby_names = 'ANY 1 (replica)';"
    else
        echo "Setting up EVENTUAL consistency (asynchronous replication)"
        gosu $USER psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -p $PG_PORT -c "ALTER SYSTEM SET synchronous_commit = 'off';"
        gosu $USER psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -p $PG_PORT -c "ALTER SYSTEM SET synchronous_standby_names = '';"
    fi

    # Reload config
    gosu $USER pg_ctl reload -D "$PGDATA"

    # Run init script
    if [ -f /docker-entrypoint-initdb.d/pg-init.sql ]; then
        echo "Running pg-init.sql to create initial schema..."
        gosu $USER psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -p $PG_PORT -f /docker-entrypoint-initdb.d/pg-init.sql
    fi

    until pg_isready -h 127.0.0.1 -p $PG_PORT -U "$POSTGRES_USER"; do
    echo "Waiting for PostgreSQL to be ready before launching PgBouncer..."
        sleep 1
    done

    echo "Starting PgBouncer..."
    echo "PgBouncer config being used:"
    cat /etc/pgbouncer/pgbouncer.ini

    # pgbouncer /etc/pgbouncer/pgbouncer.ini &
    gosu postgres pgbouncer /etc/pgbouncer/pgbouncer.ini &

    echo "PgBouncer pool mode:"
    psql -U pguser -h 127.0.0.1 -p 5432 -d pgbouncer -c "SHOW CONFIG;" | grep pool_mode

    echo "Primary configuration complete!"


############## REPLICA CONFIGURATION ##############
else 
    echo "Configuring as replica pg container"
    USER=postgres

    if [ -z "$REPLICATE_FROM" ]; then
        echo "Error: REPLICATE_FROM environment variable not set for replica configuration."
        exit 1
    fi

    # Stop PostgreSQL if it's already running
    gosu $USER pg_ctl stop -D "$PGDATA" || true

    # Clear existing data directory
    echo "Clearing existing data directory..."
    rm -rf "$PGDATA"/*
    sleep 5

    # Perform base backup from primary to initialize replication
    echo "Running pg_basebackup to replicate data from primary at $REPLICATE_FROM..."
    export PGPASSWORD='replicator_password'

    # Wait for PostgreSQL to accept connections and for 'replicator' role to be ready
    until pg_isready -h "$REPLICATE_FROM" -p $PG_PORT -U replicator -d postgres && \
        pg_basebackup -h "$REPLICATE_FROM" -U replicator -p $PG_PORT -D /tmp/test -Fp -Xs -R -Xf -l test_conn --no-password &>/dev/null; do
        echo "Primary not ready or replicator user not available yet at $REPLICATE_FROM. Retrying..."
        sleep 2
    done
    rm -rf /tmp/test

    pg_basebackup -h "$REPLICATE_FROM" -D "$PGDATA" -U replicator -p $PG_PORT -Fp -Xs -P -R

    # echo "max_wal_senders = 3" >> "$PGDATA/postgresql.auto.conf"

    # Override primary_conninfo with application_name=replica
    #### CHANGE TO 5432 is removing pgbouncer
    echo "primary_conninfo = 'host=$REPLICATE_FROM port=$PG_PORT user=replicator password=replicator_password application_name=replica'" >> "$PGDATA/postgresql.auto.conf"  ### <-- CHANGED

    echo "Fixing permissions for PGDATA..."
    chown -R postgres:postgres "$PGDATA"
    chmod 700 "$PGDATA"

    # Run delay script to simulate network delay
    /home/pg_delay.sh 50ms 15ms 25% normal

    # Create standby.signal file (usually already created by -R, but safe)
    touch "$PGDATA/standby.signal"

    echo "Replica setup complete. Now streaming from $REPLICATE_FROM."

    # Start replica
    gosu $USER pg_ctl start -D "$PGDATA" -w

    until pg_isready -h 127.0.0.1 -p $PG_PORT -U "$POSTGRES_USER"; do
    echo "Waiting for PostgreSQL to be ready before launching PgBouncer..."
        sleep 1
    done

    echo "Starting PgBouncer..."
    # pgbouncer /etc/pgbouncer/pgbouncer.ini &
    gosu postgres pgbouncer /etc/pgbouncer/pgbouncer.ini &

fi

# Keep container alive
tail -f /dev/null
