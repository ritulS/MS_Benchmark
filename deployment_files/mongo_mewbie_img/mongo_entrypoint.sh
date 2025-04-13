#!/bin/bash
set -e

############## PRIMARY CONFIGURATION ##############
if [ "$IS_REPLICA" = false ]; then
    echo "Configuring MongoDB as Primary"

    # Start MongoDB normally
    mongod --replSet rs0 --bind_ip_all --port 27017 --fork --logpath /var/log/mongodb.log

    # Wait for MongoDB to be fully up before running rs.initiate()
    echo "Waiting for MongoDB to start..."
    until mongosh --eval "db.adminCommand('ping')" &> /dev/null; do
        echo "MongoDB is not ready yet. Waiting..."
        sleep 2
    done

    echo "Initializing MongoDB replica set..."
    mongosh --eval "rs.initiate();"

    # Remove any existing replicas to ensure only one replica is allowed
    echo "Ensuring primary has no old replicas..."
    mongosh --eval "
        cfg = rs.conf();
        cfg.members = [cfg.members[0]]; // Keep only the primary
        rs.reconfig(cfg, {force: true});
    "

    # Apply Consistency Mode for the Primary
    if [ "$CONSISTENCY_MODE" = "strong" ]; then
        echo "Setting Strong Consistency Mode (w: majority, ReadPreference: primary)"
        mongosh --eval "db.adminCommand({ setDefaultRWConcern: 1, defaultWriteConcern: { w: 'majority' }, defaultReadConcern: { level: 'majority' } })"
    else
        echo "Setting Eventual Consistency Mode (w: 1, ReadPreference: nearest)"
        mongosh --eval "db.adminCommand({ setDefaultRWConcern: 1, defaultWriteConcern: { w: 1 }, defaultReadConcern: { level: 'local' } })"
    fi

    echo "Running MongoDB initialization logic: create index"
    mongosh <<EOF
db = db.getSiblingDB("mewbie_db")
db.mycollection.createIndex({ key: 1 })
EOF

    echo "MongoDB Primary setup complete."

    tail -f /dev/null  # Keep container running

############## REPLICA CONFIGURATION ##############
else
    echo "Configuring MongoDB as Replica"

    PRIMARY_HOST="$REPLICATE_FROM:27017"

    # Wait for primary to be available
    until mongosh --host "$PRIMARY_HOST" --eval "db.adminCommand('ping')" &> /dev/null; do
        echo "Waiting for MongoDB Primary ($PRIMARY_HOST) to be available..."
        sleep 5
    done

    echo "Checking if Replica is already added..."
    IS_ALREADY_ADDED=$(mongosh --host "$REPLICATE_FROM" --quiet --eval "
        rs.status().members.some(m => m.name.includes('$REPLICA_SERVICE_NAME'))
    ")

    if [ "$IS_ALREADY_ADDED" = "true" ]; then
        echo "Replica is already in the set, skipping rs.add()..."
    else
        echo "Adding MongoDB Replica to the Replica Set..."
        mongosh --host "$REPLICATE_FROM" --eval "rs.add('$REPLICA_SERVICE_NAME:27017')"
    fi

    # echo "Adding MongoDB Replica to the Replica Set..."
    # mongosh --host "$REPLICATE_FROM" --eval "rs.add('$REPLICA_SERVICE_NAME:27017')"
    # echo "Replica_from: $REPLICATE_FROM"
    # echo "Hostname: $HOSTNAME:27017"
    # echo "MongoDB Replica added successfully."

    # Apply network delay using pg_delay.sh
    echo "Applying network delay..."
    /home/mongo_delay.sh 100ms 50ms 25% normal

    echo "Starting MongoDB Replica..."
    mongod --replSet rs0 --bind_ip_all --port 27017 --logpath /var/log/mongodb.log

    # Apply Consistency Mode for the Replica
    if [ "$CONSISTENCY_MODE" = "strong" ]; then
        echo "Setting Strong Consistency Mode for Replica"
        mongosh --host "$REPLICA_SERVICE_NAME:27017" --eval "db.adminCommand({ setDefaultRWConcern: 1, defaultWriteConcern: { w: 'majority' }, defaultReadConcern: { level: 'majority' } })"
    else
        echo "Setting Eventual Consistency Mode for Replica"
        mongosh --host "$REPLICA_SERVICE_NAME:27017" --eval "db.adminCommand({ setDefaultRWConcern: 1, defaultWriteConcern: { w: 1 }, defaultReadConcern: { level: 'local' } })"
    fi


fi

tail -f /dev/null  # Keep container running
