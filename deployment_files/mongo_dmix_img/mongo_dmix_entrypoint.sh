#!/bin/bash
set -e

# Start Mongo in the background
mongod --bind_ip_all --fork --logpath /var/log/mongod.log

# Wait for it to come up
until mongosh --eval 'db.runCommand({ ping: 1 })'; do
  echo "Waiting for MongoDB to be ready..."
  sleep 1
done

# Run init logic (e.g., create index)
mongosh <<EOF
db = db.getSiblingDB("mewbie_db")
db.mycollection.createIndex({ key: 1 })
EOF

# Keep the container alive by tailing the log
tail -f /var/log/mongod.log
