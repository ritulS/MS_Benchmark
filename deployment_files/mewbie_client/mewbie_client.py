import json
import time
import os
import requests
import csv
import subprocess
import pickle
import queue
import logging
import threading
from concurrent.futures import ThreadPoolExecutor

def pkl_to_dict(pkl_file):
    with open(pkl_file, 'rb') as f:
        return pickle.load(f)

# Initialize logging 
logging.basicConfig(level=logging.INFO)
executor = ThreadPoolExecutor(max_workers=10)
log_queue = queue.Queue()
def log_to_csv_file(tid, this_nid, logged_time):
    log_directory = "./logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)  # Create the directory if it does not exist
    
    log_file = f"{log_directory}/{this_nid}_log.csv"  
    try:
        with open(log_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([tid, this_nid, logged_time])
            # logging.info(f"Log entry for tid={tid}, this_nid={this_nid} written successfully")
    except Exception as e:
        logging.error(f"Failed to write log entry: {e}")


def log_thread():
    while True:
        log_data = log_queue.get()
        if log_data is None:
            break
        tid, this_nid, logged_time = log_data
        log_to_csv_file(tid, this_nid, logged_time) 
        log_queue.task_done()

#Create a thread to log data
log_thread = threading.Thread(target=log_thread,daemon=True)
log_thread.start()

def log_in_background(tid, this_nid, logged_time):
    # logging.info(f"Submitting log task for tid={tid}, this_nid={this_nid}"
    #executor.submit(log_to_csv_file, tid, this_nid, logged_time)
    log_queue.put((tid, this_nid, logged_time))


# Read trace packets from file
trace_packets_dict = json.load(open("./all_trace_packets.json"))
session = requests.Session()

def send_data_to_container(container_name, data, cont_type, tid):
    log_in_background(tid, "mewbie_client", time.time())
    #log_queue.put((tid, "mewbie_client", time.time()))
    #log_to_csv_file(tid, "mewbie_client", time.time())
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
        with session.post(url, json=data, headers=headers) as response:
            # print("Done")
            response.raise_for_status()
        # print("Data sent to: ", container_name)
        # if response.status_code == 200:
        #     print(f"Successfully sent data to {container_name}")
        # else:
        #     print(f"Status code: {response.status_code}")
        #     print(f"Failed to send data to {container_name}: {response.text}: {response.content}")
        # print("Data sent successfully!")
    except Exception as e:
        print("Error sending data to container: ", e)


def send_data_in_background(container_name, data, cont_type, tid):
    executor.submit(send_data_to_container, container_name, data, cont_type, tid)


rps = 1000 # packets per second; USER DEFINED
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
        # print(t_ini_cont)
        t_ini_type = t_packet['initial_node_type']
        send_data_in_background(t_ini_cont, t_packet, t_ini_type, tid)
        total_packets_sent += 1
        # logging.info(f"Logging = {tid}:'mewbie_client':{time.time()}")
        elapsed_time = time.time() - st
        if elapsed_time < delay:
            #print(delay - elapsed_time)
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
    log_queue.put(None)
    log_thread.join()

    #Query all node for status by sending http request to sl_test.py service
    #nodes is a list of all containers running in my stack
    # nodes = os.environ["SL_NODES"].split(",")
    # print(nodes)
    # try:
    #     for i in nodes:
    #         while True:
    #             with session.get(f"http://{i}:5000/status") as response:
    #                 response.raise_for_status()
    #                 #Go to next iteration only if alive request count is 0
    #                 if response.text == "Alive request count: 0":
    #                     break
                    
    # except:
    #     pass

#Tester!!!!
if __name__ == "__main__":
    # print("Chumma!!")
    main()
