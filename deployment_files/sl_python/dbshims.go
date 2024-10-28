// dbshim/shim.go
package main

import (
	"context"
	"database/sql"
	"fmt"
	"sync"

	"github.com/go-redis/redis/v8"
	"go.mongodb.org/mongo-driver/bson"
	"go.mongodb.org/mongo-driver/mongo"
	"go.mongodb.org/mongo-driver/mongo/options"
)

var (
	clientMap = make(map[string]interface{})
	mu        sync.Mutex
)

// Initialize database connections
func dbConInitializer(dbName, nodeID, ip string, port int) (interface{}, error) {

	mu.Lock()
	defer mu.Unlock()

	if client, ok := clientMap[nodeID]; ok {
		return client, nil
	}

	switch dbName {
	case "MongoDB":
		client, err := mongo.Connect(context.Background(), options.Client().ApplyURI(fmt.Sprintf("mongodb://%s:%d", ip, port)))
		if err != nil {
			return nil, fmt.Errorf("failed to connect to MongoDB at %s:%d: %v", ip, port, err)
		}
		clientMap[nodeID] = client
		return client, nil

	case "Postgres":
		dsn := fmt.Sprintf("postgres://pguser:pgpass@%s:%d/pg_db?sslmode=disable", ip, port)
		client, err := sql.Open("postgres", dsn)
		if err != nil {
			return nil, fmt.Errorf("failed to connect to Postgres at %s:%d: %v", ip, port, err)
		}
		clientMap[nodeID] = client
		if _, err := client.Exec(`CREATE TABLE IF NOT EXISTS mewbie_table (id SERIAL PRIMARY KEY, key TEXT, value TEXT);`); err != nil {
			return nil, err
		}
		return client, nil

	case "Redis":
		client := redis.NewClient(&redis.Options{
			Addr: fmt.Sprintf("%s:%d", ip, port),
		})
		if _, err := client.Ping(context.Background()).Result(); err != nil {
			return nil, fmt.Errorf("failed to connect to Redis at %s:%d: %v", ip, port, err)
		}
		clientMap[nodeID] = client
		return client, nil

	default:
		return nil, fmt.Errorf("unsupported database: %s", dbName)
	}
}

func MongoShimFunc(ctx context.Context, kv map[string]string, opType, nodeID, dmNID string, port int) (string, error) {
	client, err := dbConInitializer("MongoDB", nodeID, dmNID, port)
	if err != nil {
		return "", err
	}
	mongoClient := client.(*mongo.Client)
	collection := mongoClient.Database("mewbie_db").Collection("mycollection")

	switch opType {
	case "write":
		result, err := collection.InsertOne(ctx, kv)
		if err != nil {
			return "", err
		}
		return fmt.Sprintf("Payload inserted with id %v", result.InsertedID), nil

	case "read":
		var result bson.M
		err := collection.FindOne(ctx, kv).Decode(&result)
		if err != nil {
			return "No entry matching the query", err
		}
		return fmt.Sprintf("Document found: %v", result), nil

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
	redisClient := client.(*redis.Client)

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
		return fmt.Sprintf("KV pair %s:%s inserted", key, value), nil

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
	db := client.(*sql.DB)

	key, value := "", ""
	for k, v := range kv {
		key, value = k, v
		break
	}

	switch op {
	case "write":
		_, err := db.ExecContext(ctx, "INSERT INTO mewbie_table (key, value) VALUES ($1, $2)", key, value)
		if err != nil {
			return "", err
		}
		return fmt.Sprintf("KV pair %s:%s inserted", key, value), nil

	case "read":
		row := db.QueryRowContext(ctx, "SELECT value FROM mewbie_table WHERE key = $1", key)
		err := row.Scan(&value)
		if err == sql.ErrNoRows {
			// No rows found, return a message without an error
			return fmt.Sprintf("No entry found for key %s", key), nil
		} else if err != nil {
			return "", fmt.Errorf("error reading KV pair %s: %v", key, err)
		}
		return fmt.Sprintf("KV pair %s:%s read successfully", key, value), nil

	default:
		return "", fmt.Errorf("unsupported operation: %s", op)
	}
}
