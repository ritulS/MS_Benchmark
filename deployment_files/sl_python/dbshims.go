// dbshim/shim.go
package main

import (
	"context"
	"database/sql"
	"fmt"
	"sync"
	"time"

	"github.com/go-redis/redis/v8"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

var (
	clientMap       = make(map[string]interface{})
	mongoClients    = make(map[string]*mongo.Client)
	postgresClients = make(map[string]*sql.DB)
	redisClients    = make(map[string]*redis.Client)
	mu              sync.Mutex
)

// Initialize database connections
func dbConInitializer(dbName, nodeID, ip string, port int) (interface{}, error) {

	mu.Lock()
	defer mu.Unlock()

	switch dbName {
	case "MongoDB":
		if client, ok := mongoClients[ip]; ok {
			return client, nil
		}
		// client, err := mongo.Connect(context.Background(), options.Client().ApplyURI(fmt.Sprintf("mongodb://%s:%d", ip, port)))
		client, err := mongo.Connect(context.Background(),
			options.Client().ApplyURI(fmt.Sprintf("mongodb://%s:%d", ip, port)).
				SetConnectTimeout(30*time.Second).
				SetServerSelectionTimeout(30*time.Second).
				SetSocketTimeout(60*time.Second))
		if err != nil {
			return nil, fmt.Errorf("failed to connect to MongoDB at %s:%d: %v", ip, port, err)
		}
		mongoClients[ip] = client
		return client, nil

	case "Postgres":
		if client, ok := postgresClients[ip]; ok {
			return client, nil
		}
		dsn := fmt.Sprintf("postgres://pguser:pgpass@%s:%d/pg_db?sslmode=disable", ip, port)
		client, err := sql.Open("postgres", dsn)
		if err != nil {
			return nil, fmt.Errorf("failed to connect to Postgres at %s:%d: %v", ip, port, err)
		}
		client.SetMaxOpenConns(25)
		client.SetMaxIdleConns(25)
		postgresClients[ip] = client

		return client, nil

	case "Redis":
		if client, ok := redisClients[ip]; ok {
			return client, nil
		}
		client := redis.NewClient(&redis.Options{
			Addr:         fmt.Sprintf("%s:%d", ip, port),
			DialTimeout:  30 * time.Second,
			ReadTimeout:  30 * time.Second,
			WriteTimeout: 30 * time.Second,
		})

		if _, err := client.Ping(context.Background()).Result(); err != nil {
			return nil, fmt.Errorf("failed to connect to Redis at %s:%d: %v", ip, port, err)
		}
		redisClients[ip] = client
		return client, nil

	default:
		return nil, fmt.Errorf("unsupported database: %s", dbName)
	}
}

func MongoShimFunc(ctx context.Context, kv map[string]string, opType, nodeID, dmNID string, port int) (string, error) {
	client, err := dbConInitializer("MongoDB", dmNID, dmNID, port) // cache key = dmNID
	if err != nil {
		return "", err
	}

	mongoClient, ok := client.(*mongo.Client)
	if !ok {
		return "", fmt.Errorf("unexpected client type: expected *mongo.Client, got %T for nodeID %s", client, nodeID)
	}

	collection := mongoClient.Database("mewbie_db").Collection("mycollection")

	var key, value string
	for k, v := range kv {
		key, value = k, v
		break
	}

	switch opType {
	case "write":
		// Upsert: insert if not exists, else update
		filter := bson.M{"key": key}
		update := bson.M{"$set": bson.M{"value": value}}
		opts := options.Update().SetUpsert(true)

		_, err := collection.UpdateOne(ctx, filter, update, opts)
		if err != nil {
			return "", fmt.Errorf("failed to upsert key '%s': %v", key, err)
		}

		// Read-after-write verification
		var result bson.M
		err = collection.FindOne(ctx, filter).Decode(&result)
		if err != nil {
			return "", fmt.Errorf("read-after-write failed for key '%s': %v", key, err)
		}
		return fmt.Sprintf("KV pair %s:%s inserted or updated", key, value), nil

	case "read":
		filter := bson.M{"key": key}
		var result bson.M
		err := collection.FindOne(ctx, filter).Decode(&result)
		if err == mongo.ErrNoDocuments {
			return "", nil
		} else if err != nil {
			return "", fmt.Errorf("error reading key '%s': %v", key, err)
		}
		val := result["value"]
		return fmt.Sprintf("KV pair %s:%v read successfully", key, val), nil

	default:
		return "", fmt.Errorf("unsupported operation: %s", opType)
	}
}

// Redis shim function
func RedisShimFunc(ctx context.Context, kv map[string]string, op, nodeID, ip string, port int) (string, error) {
	client, err := dbConInitializer("Redis", nodeID, ip, port)
	if err != nil {
		return "", err
	}
	redisClient, ok := client.(*redis.Client)
	if !ok {
		return "", fmt.Errorf("unexpected client type: expected *redis.Client, got %T for nodeID %s", client, nodeID)
	}

	key, value := "", ""
	for k, v := range kv {
		key, value = k, v
		break
	}

	switch op {
	case "write":
		if err := redisClient.Set(ctx, key, value, 0).Err(); err != nil {
			return "", err
		}
		// Read-after-write
		readVal, err := redisClient.Get(ctx, key).Result()
		if err == redis.Nil {
			return "", fmt.Errorf("read-after-write failed, key '%s' not found", key)
		} else if err != nil {
			return "", fmt.Errorf("read-after-write failed for key '%s': %v", key, err)
		}
		return fmt.Sprintf("KV pair %s:%s inserted or updated", key, readVal), nil

	case "read":
		value, err := redisClient.Get(ctx, key).Result()
		if err == redis.Nil {
			return "No entry found", nil
		} else if err != nil {
			return "", err
		}
		return fmt.Sprintf("KV pair %s:%s found", key, value), nil

	default:
		return "", fmt.Errorf("unsupported operation: %s", op)
	}
}

// PostgreSQL shim function
func PostgresShimFunc(ctx context.Context, kv map[string]string, op, nodeID, ip string, port int) (string, error) {
	client, err := dbConInitializer("Postgres", nodeID, ip, port)
	if err != nil {
		return "", err
	}

	db, ok := client.(*sql.DB)
	if !ok {
		return "", fmt.Errorf("unexpected client type: expected *sql.DB, got %T for nodeID %s", client, nodeID)
	}

	var key, value string
	for k, v := range kv {
		key, value = k, v
		break // Only one key-value pair expected
	}

	switch op {
	case "write":
		query := `
			INSERT INTO mewbie_table (key, value)
			VALUES ($1, $2)
			ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
		`
		_, err := db.ExecContext(ctx, query, key, value)
		if err != nil {
			return "", fmt.Errorf("failed to write key '%s': %v", key, err)
		}
		// Read-after-write
		readQuery := `SELECT value FROM mewbie_table WHERE key = $1`
		var dummy string
		err = db.QueryRowContext(ctx, readQuery, key).Scan(&dummy)
		if err != nil && err != sql.ErrNoRows {
			return "", fmt.Errorf("read-after-write failed for key '%s': %v", key, err)
		}
		return fmt.Sprintf("KV pair %s:%s inserted or updated", key, value), nil

	case "read":
		query := `SELECT value FROM mewbie_table WHERE key = $1`
		err := db.QueryRowContext(ctx, query, key).Scan(&value)
		if err == sql.ErrNoRows {
			return "", nil // Key not found — not an error
		} else if err != nil {
			return "", fmt.Errorf("error reading key '%s': %v", key, err)
		}
		return fmt.Sprintf("KV pair %s:%s read successfully", key, value), nil

	default:
		return "", fmt.Errorf("unsupported operation: %s", op)
	}
}
