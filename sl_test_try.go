

///////////////////////////////////////////////////////////
// Without wait for downstream tasks
///////////////////////////////////////////////////////////

// package main

// import (
// 	"bytes"
// 	"context"
// 	"encoding/base64"
// 	"encoding/csv"
// 	"encoding/json"
// 	"fmt"
// 	"log"
// 	"math/rand"
// 	"net/http"
// 	"os"
// 	"path/filepath"
// 	"time"

// 	"github.com/gorilla/mux"
// 	_ "github.com/lib/pq"
// )

// var (
// 	rqCounter    = 0
// 	specialNodes = []string{"n1865", "n2127", "n5223", "n2977", "n6292"}
// 	procTimeDist []time.Duration
// )

// func generateRandomString(length int) string {
// 	bytes := make([]byte, length)
// 	for i := range bytes {
// 		bytes[i] = byte(rand.Intn(256))
// 	}
// 	return base64.StdEncoding.EncodeToString(bytes)
// }

// func logToCSVFile(tid, thisNid, loggedTime, entryType, message string) error {

// 	logDirectory := "./logs"
// 	logFile := filepath.Join(logDirectory, fmt.Sprintf("%s_log.csv", thisNid))

// 	// Ensure the log directory exists
// 	if _, err := os.Stat(logDirectory); os.IsNotExist(err) {
// 		err := os.MkdirAll(logDirectory, os.ModePerm)
// 		if err != nil {
// 			log.Printf("Failed to create log directory: %v", err)
// 			return err
// 		}
// 	}

// 	// Open the CSV file in append mode (or create if it doesn't exist)
// 	file, err := os.OpenFile(logFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
// 	if err != nil {
// 		log.Printf("Failed to open log file: %v", err)
// 		return err
// 	}
// 	defer file.Close()

// 	writer := csv.NewWriter(file)
// 	defer writer.Flush()

// 	// Write the log entry to the CSV file
// 	entry := []string{tid, thisNid, loggedTime, entryType, message}
// 	if err := writer.Write(entry); err != nil {
// 		log.Printf("Failed to write log entry: %v", err)
// 		return err
// 	}

// 	// log.Printf("Log entry for tid=%s, this_nid=%s written successfully", tid, thisNid)
// 	return nil
// }

// func makeDBCall(dmNID, dbName string, kv map[string]string, opType, thisNid string) (string, error) {
// 	switch dbName {
// 	case "MongoDB":
// 		result, err := MongoShimFunc(context.Background(), kv, opType, thisNid, dmNID, 27017)
// 		return result, err

// 	case "Redis":
// 		result, err := RedisShimFunc(context.Background(), kv, opType, thisNid, dmNID, 6379)
// 		return result, err

// 	case "Postgres":
// 		result, err := PostgresShimFunc(context.Background(), kv, opType, thisNid, dmNID, 5432)
// 		return result, err

// 	default:
// 		return "", fmt.Errorf("unsupported database: %s", dbName)
// 	}
// }

// var httpClient = &http.Client{
// 	Timeout: 20 * time.Second,
// }

// // Makes an HTTP call to a SL node
// func makeSLCall(slDmNID string, tracePacketData []byte) (string, error) {
// 	url := fmt.Sprintf("http://%s:5000/", slDmNID)
// 	req, err := http.NewRequestWithContext(context.Background(), "POST", url, bytes.NewBuffer(tracePacketData))
// 	if err != nil {
// 		return "", fmt.Errorf("failed to create request: %v", err)
// 	}
// 	req.Header.Set("Content-Type", "application/json")

// 	// client := &http.Client{}
// 	resp, err := httpClient.Do(req)
// 	if err != nil {
// 		return "", fmt.Errorf("failed to perform SL call to %s: %v", slDmNID, err)
// 	}
// 	defer resp.Body.Close()

// 	if resp.StatusCode != http.StatusOK {
// 		return "", fmt.Errorf("SL call failed with status: %d", resp.StatusCode)
// 	}
// 	return "SL call successful", nil
// }

// type TracePacketResult struct {
// 	Status string   `json:"status"`           // e.g. "Completed" or "Failed"
// 	Errors []string `json:"errors,omitempty"` // Optional error messages
// }

// func initProcessingTimes() {
// 	// times := []int{0, 0, 0, 0, 1, 1, 2, 2, 3, 5, 10, 15, 20, 25}

// 	times := []int{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
// 		1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2,
// 		2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7,
// 		7, 8, 8, 9, 9, 10, 11, 11, 12, 13, 15, 16, 18, 20, 22, 25,
// 		29, 33, 39, 45, 52, 62, 70, 78, 87, 97, 111, 126, 143, 164,
// 		188, 220, 254, 289, 331, 379, 846, 38921}
// 	for _, t := range times {
// 		procTimeDist = append(procTimeDist, time.Duration(t)*time.Millisecond)
// 	}
// }

// func processTracePacket(tracePacketData map[string]interface{}) {
// 	// Increment request counter
// 	// atomic.AddInt32(&rqCounter, 1)
// 	// defer atomic.AddInt32(&rqCounter, -1)

// 	thisNID := os.Getenv("CONTAINER_NAME")
// 	tid := tracePacketData["tid"].(string)
// 	nodeCallsDict, _ := tracePacketData["node_calls_dict"].(map[string]interface{})
// 	dataOpsDict, _ := tracePacketData["data_ops_dict"].(map[string]interface{})
// 	loggerNodes, _ := tracePacketData["logger_nodes"].([]interface{})

// 	// Simulate random processing time based on specified distribution
// 	// procTimes := []int{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
// 	// 	1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2,
// 	// 	2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7,
// 	// 	7, 8, 8, 9, 9, 10, 11, 11, 12, 13, 15, 16, 18, 20, 22, 25,
// 	// 	29, 33, 39, 45, 52, 62, 70, 78, 87, 97, 111, 126, 143, 164,
// 	// 	188, 220, 254, 289, 331, 379, 846, 38921}

// 	// procTimes := []int{0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
// 	// 	1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2,
// 	// 	2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7,
// 	// 	7, 8, 8, 9, 9, 10}

// 	// flag := true
// 	// for _, node := range specialNodes {
// 	// 	if node == thisNID {
// 	// 		flag = false
// 	// 		break
// 	// 	}
// 	// }

// 	// if flag {
// 	// 	time.Sleep(time.Duration(procTimes[rand.Intn(len(procTimes))]) * time.Millisecond)
// 	// }
// 	isSpecialNode := false
// 	for _, node := range specialNodes {
// 		if node == thisNID {
// 			isSpecialNode = true
// 			break
// 		}
// 	}

// 	if !isSpecialNode {
// 		time.Sleep(procTimeDist[rand.Intn(len(procTimeDist))]) // Simulate processing time if not a special node
// 	}

// 	// Log entry if node is a logger node
// 	for _, node := range loggerNodes {
// 		if node == thisNID {
// 			logToCSVFile(tid, thisNID, fmt.Sprint(time.Now().UnixMicro()), "Leaf", "")
// 		}
// 	}

// 	// Get the list of downstream nodes to call
// 	dmNodesToCall, ok := nodeCallsDict[thisNID].([]interface{})
// 	if !ok || len(dmNodesToCall) == 0 {
// 		return
// 	}

// 	// Process each downstream node call
// 	for _, nodeCall := range dmNodesToCall {
// 		call := nodeCall.([]interface{})
// 		dmNID := call[0].(string)
// 		dataOpID := int(call[1].(float64))
// 		asyncFlag := 0

// 		if dataOpID != -1 {
// 			// Handle Sf call
// 			opPkt := dataOpsDict[fmt.Sprint(dataOpID)].(map[string]interface{})
// 			opType := opPkt["op_type"].(string)
// 			opObjID := opPkt["op_obj_id"].(string)
// 			dbName := opPkt["db"].(string)
// 			kv := map[string]string{opObjID: generateRandomString(500)}

// 			if asyncFlag == 1 { // Async SF call
// 				go func() {
// 					if _, err := makeDBCall(dmNID, dbName, kv, opType, thisNID); err != nil {
// 						log.Printf("Async DB call to %s failed: %v", dmNID, err)
// 					}
// 				}()
// 				logToCSVFile(tid, thisNID, fmt.Sprint(time.Now().UnixMicro()), "Async", dbName)
// 			} else { // Sync SF call
// 				if _, err := makeDBCall(dmNID, dbName, kv, opType, thisNID); err != nil {
// 					log.Printf("Sync DB call to %s failed: %v", dmNID, err)
// 				}
// 				logToCSVFile(tid, thisNID, fmt.Sprint(time.Now().UnixMicro()), "Sync", dbName)
// 			}
// 		} else {
// 			// Handle SL call
// 			tracePacketDataBytes, _ := json.Marshal(tracePacketData)
// 			if asyncFlag == 1 {
// 				go func() {
// 					if _, err := makeSLCall(dmNID, tracePacketDataBytes); err != nil {
// 						log.Printf("Async SL call to %s failed: %v", dmNID, err)
// 					}
// 				}()
// 			} else {
// 				if _, err := makeSLCall(dmNID, tracePacketDataBytes); err != nil {
// 					log.Printf("Sync SL call to %s failed: %v", dmNID, err)
// 				}
// 			}
// 		}
// 	}
// }

// // Call handler function
// func callHandler(w http.ResponseWriter, r *http.Request) {
// 	var tracePacketData map[string]interface{}
// 	if err := json.NewDecoder(r.Body).Decode(&tracePacketData); err != nil {
// 		http.Error(w, "invalid request", http.StatusBadRequest)
// 		return
// 	}
// 	// Process trace packet in the background
// 	go processTracePacket(tracePacketData)
// 	// fmt.Fprintln(w, "Trace packet processing started!")
// }

// // Status handler function
// func statusHandler(w http.ResponseWriter, r *http.Request) {
// 	fmt.Fprintf(w, "Alive request count: %d\n", rqCounter)
// }

// func main() {
// 	initProcessingTimes() // Initialize Precomputed Processing Times

// 	r := mux.NewRouter()
// 	r.HandleFunc("/", callHandler).Methods("POST", "GET")
// 	r.HandleFunc("/status", statusHandler).Methods("GET")

// 	srv := &http.Server{
// 		Handler:      r,
// 		Addr:         "0.0.0.0:5000",
// 		WriteTimeout: 20 * time.Second,
// 		ReadTimeout:  20 * time.Second,
// 	}

// 	fmt.Println("Server started on port 5000")
// 	if err := srv.ListenAndServe(); err != nil {
// 		log.Fatalf("Server failed to start: %v", err)
// 	}
// }
