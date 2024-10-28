import json
import time
import os
import requests
import csv
import re
import subprocess
import pickle
import queue
import logging
from logging.handlers import RotatingFileHandler
import threading
from concurrent.futures import ThreadPoolExecutor

def pkl_to_dict(pkl_file):
    with open(pkl_file, 'rb') as f:
        return pickle.load(f)

log_directory = "./logs"
if not os.path.exists(log_directory):
    os.makedirs(log_directory)  # Create the directory if it does not exist

log_file = os.path.join(log_directory, "client_log.csv")
logger = logging.getLogger("ClientLogger")
logger.setLevel(logging.INFO)
handler = RotatingFileHandler(log_file, maxBytes=10*1024*1024, backupCount=5)
logger.addHandler(handler)

executor = ThreadPoolExecutor(max_workers=15)

# Log function that uses the logger
def log_entry(tid, this_nid, logged_time):
    logger.info(f"{tid},{this_nid},{logged_time}")


# Read trace packets from file
trace_packets_dict = json.load(open("./all_trace_packets.json"))
session = requests.Session()

def send_data_to_container(container_name, data, cont_type, tid):
    log_entry(tid, "mewbie_client", time.time())
    try:
        port = 5000
        if cont_type == 'Python':
            port = 5000
        elif cont_type == 'Redis':
            port = 6379
        elif cont_type == 'MongoDB':
            port = 27017
        elif cont_type == 'Postgres':
            port = 5432
        url = f"http://{container_name}:{port}/"
        headers = {'Content-Type': 'application/json', 'Connection': 'close'}
        # print("Sending data to container: ", container_name)
        with session.post(url, json=data, headers=headers, timeout=2.5) as response:
            # print("Done")
            response.raise_for_status()
    except Exception as e:
        print("Error sending data to container: ", e)

def send_data_in_background(container_name, data, cont_type, tid):
    executor.submit(send_data_to_container, container_name, data, cont_type, tid)


rps = 500 # packets per second; USER DEFINED
def main():
    print(f"Running with rps: {rps}")
    total_num_packets = len(trace_packets_dict)
    print("Total number of packets: ", total_num_packets)
    delay = 1/rps

    total_packets_sent = 0
    start_time = time.time()

    for tid, t_packet in trace_packets_dict.items():
        st = time.time()
        t_ini_cont = t_packet['initial_node']
        t_ini_type = t_packet['initial_node_type']
        send_data_in_background(t_ini_cont, t_packet, t_ini_type, tid)
        total_packets_sent += 1
        elapsed_time = time.time() - st
        if elapsed_time < delay:
            time.sleep(delay - elapsed_time)

    end_time = time.time()
    total_exp_runtime = end_time - start_time
    avg_req_ps = total_packets_sent / total_exp_runtime
    
    print("Finished sending all packets!")
    print(f"Total packets sent: {total_packets_sent}")
    print(f"Total exp runtime: {total_exp_runtime}")
    print(f"Average requests per second: {avg_req_ps}")
    #Wait for all tasks to complete
    executor.shutdown(wait=True)
    #Wait for log thread to complete
    time.sleep(5)
    # log_queue.put(None)
    # log_thread.join()

    # Query all node for status by sending http request to sl_test.py service
    # nodes is a list of all containers running in stack
    nodes = os.getenv('SL_NODES').split(',')
    try:
        for i in nodes:
            while True:
                try:
                    # Send a GET request to check the status of each node
                    with requests.get(f"http://{i}:5000/status") as response:
                        response.raise_for_status()
                        match = re.search(r"Alive request count: (\d+)", response.text)
                        if match:
                            alive_request_count = int(match.group(1))
                            # If the alive request count is greater than zero, print it
                            if alive_request_count > 0:
                                print(f"Node {i} has alive request count: {alive_request_count}")
                            else:
                                break  # Exit loop if count is zero and move to the next node
                except requests.exceptions.RequestException as e:
                    print(f"Error with node {i}: {e}")
                    break  

    except Exception as e:
        print("An error occurred:", e)

if __name__ == "__main__":
    main()
