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

	// if client, ok := clientMap[nodeID]; ok {
	// 	return client, nil
	// }

	switch dbName {
	case "MongoDB":
		if client, ok := mongoClients[nodeID]; ok {
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
		mongoClients[nodeID] = client
		return client, nil

	case "Postgres":
		if client, ok := postgresClients[nodeID]; ok {
			return client, nil
		}
		dsn := fmt.Sprintf("postgres://pguser:pgpass@%s:%d/pg_db?sslmode=disable", ip, port)
		client, err := sql.Open("postgres", dsn)
		if err != nil {
			return nil, fmt.Errorf("failed to connect to Postgres at %s:%d: %v", ip, port, err)
		}
		client.SetMaxOpenConns(25)
		client.SetMaxIdleConns(5)
		postgresClients[nodeID] = client

		// // Check if the table already exists
		// var exists bool
		// err = client.QueryRow(`
		// 	SELECT EXISTS (
		// 		SELECT FROM information_schema.tables
		// 		WHERE table_schema = 'public' AND table_name = 'mewbie_table'
		// 	);
		// `).Scan(&exists)

		// if err != nil {
		// 	return nil, fmt.Errorf("failed to check if mewbie_table exists: %v", err)
		// }

		// // Create table only if it doesn't exist
		// if !exists {
		// 	_, err = client.Exec(`
		// 		CREATE TABLE mewbie_table (
		// 			key TEXT PRIMARY KEY,
		// 			value TEXT
		// 		);
		// 	`)
		// 	if err != nil {
		// 		return nil, fmt.Errorf("failed to create table mewbie_table: %v", err)
		// 	}
		// }

		return client, nil

		// client.SetConnMaxLifetime(30 * time.Minute)
		// postgresClients[nodeID] = client
		// _, err = client.Exec(`
		// 	CREATE TABLE IF NOT EXISTS mewbie_table (
		// 		key TEXT PRIMARY KEY,
		// 		value TEXT
		// 	);
		// `)
		// if err != nil {
		// 	return nil, fmt.Errorf("failed to create table mewbie_table: %v", err)
		// }
		// // if _, err := client.Exec(`CREATE TABLE IF NOT EXISTS mewbie_table (id SERIAL PRIMARY KEY, key TEXT, value TEXT);`); err != nil {
		// // 	return nil, err
		// // }
		// return client, nil

	case "Redis":
		if client, ok := redisClients[nodeID]; ok {
			return client, nil
		}
		client := redis.NewClient(&redis.Options{
			Addr:         fmt.Sprintf("%s:%d", ip, port),
			DialTimeout:  30 * time.Second,
			ReadTimeout:  30 * time.Second,
			WriteTimeout: 30 * time.Second,
		})
		// client := redis.NewClient(&redis.Options{
		// 	Addr: fmt.Sprintf("%s:%d", ip, port),
		// })
		if _, err := client.Ping(context.Background()).Result(); err != nil {
			return nil, fmt.Errorf("failed to connect to Redis at %s:%d: %v", ip, port, err)
		}
		redisClients[nodeID] = client
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
	mongoClient, ok := client.(*mongo.Client)
	if !ok {
		return "", fmt.Errorf("unexpected client type: expected *mongo.Client, got %T for nodeID %s", client, nodeID)
	}
	collection := mongoClient.Database("mewbie_db").Collection("mycollection")

	switch opType {
	case "write":
		for k, v := range kv {
			// 🔧 Normalize the document shape for indexing
			doc := bson.M{"key": k, "value": v}
			result, err := collection.InsertOne(ctx, doc)
			if err != nil {
				return "", err
			}
			return fmt.Sprintf("Payload inserted with id %v", result.InsertedID), nil
		}
		return "", fmt.Errorf("no key-value pair provided for write")
		// result, err := collection.InsertOne(ctx, kv)
		// if err != nil {
		// 	return "", err
		// }
		// return fmt.Sprintf("Payload inserted with id %v", result.InsertedID), nil

	case "read":
		for k := range kv {
			// 🔧 Use normalized key field for indexed lookup
			filter := bson.M{"key": k}
			var result bson.M
			err := collection.FindOne(ctx, filter).Decode(&result)
			if err != nil {
				return "No entry matching the query", nil
			}
			return fmt.Sprintf("Document found: %v", result), nil
		}
		return "", fmt.Errorf("no key provided for read")
		// var result bson.M
		// err := collection.FindOne(ctx, kv).Decode(&result)
		// if err != nil {
		// 	return "No entry matching the query", nil
		// }
		// return fmt.Sprintf("Document found: %v", result), nil

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
