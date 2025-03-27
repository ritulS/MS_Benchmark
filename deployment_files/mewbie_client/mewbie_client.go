package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io/ioutil"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"sync"
	"sync/atomic"
	"time"
)

var (
	rps               = 800                                              // packets per second
	logger            *log.Logger                                        // logger for rotating log file
	logFileName       = "./logs/client_log.csv"                          // log file path
	maxLogFileSize    = int64(25 * 1024 * 1024)                          // 10 MB in bytes
	numBackupFiles    = 5                                                // number of backup files
	statusCheckRegexp = regexp.MustCompile(`Alive request count: (\d+)`) // regex to check status
)

// Initializes logging with log rotation
func initLogger() {
	logDir := filepath.Dir(logFileName)
	if _, err := os.Stat(logDir); os.IsNotExist(err) {
		if err := os.MkdirAll(logDir, 0755); err != nil {
			log.Fatalf("Failed to create log directory: %v", err)
		}
	}
	file, err := os.OpenFile(logFileName, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
	if err != nil {
		log.Fatalf("Failed to open log file: %v", err)
	}
	logger = log.New(file, "", 0)

	go manageLogRotation(file)
}

// Rotates the log file if it exceeds the max size
func manageLogRotation(file *os.File) {
	for {
		fileStat, err := file.Stat()
		if err != nil {
			log.Printf("Failed to get log file stat: %v", err)
			continue
		}
		if fileStat.Size() >= maxLogFileSize {
			file.Close()
			for i := numBackupFiles - 1; i > 0; i-- {
				oldName := fmt.Sprintf("%s.%d", logFileName, i)
				newName := fmt.Sprintf("%s.%d", logFileName, i+1)
				os.Rename(oldName, newName)
			}
			os.Rename(logFileName, fmt.Sprintf("%s.1", logFileName))
			file, _ = os.OpenFile(logFileName, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
			logger.SetOutput(file)
		}
		time.Sleep(1 * time.Minute)
	}
}

// Log an entry to the CSV log file
func logEntry(tid, thisNid string, loggedTime string) {
	logger.Printf("%s,%s,%s\n", tid, thisNid, loggedTime)
}

// Load trace packets from JSON file
func loadTracePackets(fileName string) (map[string]map[string]interface{}, error) {
	data, err := ioutil.ReadFile(fileName)
	if err != nil {
		return nil, err
	}
	var packets map[string]map[string]interface{}
	if err := json.Unmarshal(data, &packets); err != nil {
		return nil, err
	}
	return packets, nil
}

var transport = &http.Transport{
	MaxIdleConns:        5000,
	MaxIdleConnsPerHost: 2000,
	IdleConnTimeout:     90 * time.Second,
	DisableKeepAlives:   false,
}
var client = &http.Client{
	Transport: transport,
	Timeout:   100 * time.Second,
}

// Send data to a container
func sendDataToContainer(containerName, contType, tid string, data map[string]interface{}) {
	logEntry(tid, "mewbie_client", fmt.Sprint(time.Now().UnixMicro()))
	// fmt.Printf("###### In sendDataToContainer: %s [%s] with TID: %s\n", containerName, contType, tid)
	// Set the port based on container type
	port := map[string]int{
		"Python":   5000,
		"Redis":    6379,
		"MongoDB":  27017,
		"Postgres": 5432,
	}[contType]
	if port == 0 {
		port = 5000 // default port
	}

	url := fmt.Sprintf("http://%s:%d/", containerName, port)

	// log.Printf("Sending data to %s [%s] with TID: %s\n", containerName, contType, tid)
	// Marshal the data to JSON
	jsonData, err := json.Marshal(data)
	if err != nil {
		log.Printf("Error marshaling JSON: %v", err)
		return
	}
	// fmt.Printf("Sending data: %s\n", string(jsonData))
	// Create the POST request with JSON data
	req, err := http.NewRequest("POST", url, bytes.NewBuffer(jsonData))
	if err != nil {
		log.Printf("Error creating request: %v", err)
		return
	}
	req.Header.Set("Content-Type", "application/json")

	// client := &http.Client{
	// 	Timeout: 10 * time.Second,
	// }
	resp, err := client.Do(req)
	if err != nil {
		log.Printf("Error sending data to container: %v", err)
		return
	}
	defer resp.Body.Close()
	// fmt.Printf("Received response from %s [%s]: %d\n", containerName, contType, resp.StatusCode)
	// if resp.StatusCode != http.StatusOK {
	// 	log.Printf("Received non-OK response: %d", resp.StatusCode)
	// }
	// Read the response body for debugging
	body, err := ioutil.ReadAll(resp.Body)
	if err != nil {
		log.Printf("Error reading response body: %v", err)
		return
	}

	if resp.StatusCode != http.StatusOK {
		log.Printf("Received non-OK response from %s [%s]: %d - %s", containerName, contType, resp.StatusCode, string(body))
	}
}

// Run sendDataToContainer in the background
func sendDataInBackground(containerName, contType, tid string, data map[string]interface{}) {
	// fmt.Printf("############## In sendDataInBackground: %s [%s] with TID: %s\n", containerName, contType, tid)
	go sendDataToContainer(containerName, contType, tid, data)
}

// Query nodes for their status
func checkNodeStatus(nodes []string) {
	client := &http.Client{}
	for _, node := range nodes {
		for {
			resp, err := client.Get(fmt.Sprintf("http://%s:5000/status", node))
			if err != nil {
				log.Printf("Error with node %s: %v", node, err)
				break
			}
			defer resp.Body.Close()
			body, _ := ioutil.ReadAll(resp.Body)
			matches := statusCheckRegexp.FindStringSubmatch(string(body))
			if len(matches) > 1 {
				aliveRequestCount, _ := strconv.Atoi(matches[1])
				if aliveRequestCount > 0 {
					fmt.Printf("Node %s has alive request count: %d\n", node, aliveRequestCount)
				} else {
					break
				}
			}
		}
	}
}

func main() {
	initLogger()
	tracePackets, err := loadTracePackets("./all_trace_packets.json")
	if err != nil {
		log.Fatalf("Failed to load trace packets: %v", err)
	}
	tracePacketsDict := tracePackets

	// Define the number of goroutines
	numGoroutines := 14
	// fmt.Printf("################Running with %d goroutines\n", numGoroutines)
	// Split tracePacketsDict into chunks for each goroutine
	chunks := make([]map[string]map[string]interface{}, 0, numGoroutines)
	for i := 0; i < numGoroutines; i++ {
		chunks = append(chunks, make(map[string]map[string]interface{}))
	}

	i := 0
	for tid, packet := range tracePacketsDict {
		// fmt.Printf("################Processing TID: %s\n", tid)
		chunkIndex := i / ((len(tracePacketsDict) + numGoroutines - 1) / numGoroutines)
		if chunkIndex >= numGoroutines {
			chunkIndex = numGoroutines - 1
		}
		chunks[chunkIndex][tid] = packet
		i++
	}

	// Calculate the per-goroutine RPS
	rpsPerGoroutine := rps / numGoroutines
	delay := time.Second / time.Duration(rpsPerGoroutine)
	fmt.Printf("Running with total RPS: %d\n", rps)
	fmt.Printf("Delay per goroutine for target RPS: %v\n", delay)

	var wg sync.WaitGroup
	var totalPacketsSent int64
	startTime := time.Now()

	// Start goroutines to send packets
	for _, chunk := range chunks {
		wg.Add(1)
		go func(chunk map[string]map[string]interface{}) {
			defer wg.Done()
			ticker := time.NewTicker(delay)
			defer ticker.Stop()

			for tid, packet := range chunk {
				<-ticker.C // Wait for the ticker to signal when to send the next packet
				initialNode, nodeTypeOk := packet["initial_node"].(string)
				initialNodeType, typeOk := packet["initial_node_type"].(string)
				if !nodeTypeOk || !typeOk {
					continue
				}
				// fmt.Printf("##########Sending packet with TID: %s\n", tid)
				sendDataInBackground(initialNode, initialNodeType, tid, packet)
				atomic.AddInt64(&totalPacketsSent, 1)
			}
		}(chunk)
	}

	wg.Wait()

	totalExpRuntime := time.Since(startTime).Seconds()
	avgReqPs := float64(totalPacketsSent) / totalExpRuntime

	fmt.Println("Finished sending all packets!")
	fmt.Printf("Total packets sent: %d\n", totalPacketsSent)
	fmt.Printf("Total experiment runtime: %.2f seconds\n", totalExpRuntime)
	fmt.Printf("Average requests per second: %.2f\n", avgReqPs)

	// Close executor and wait for tasks to complete
	// close(executor)
}
