import json
import time
import os
import requests
import csv
import subprocess
import pickle
import logging
from concurrent.futures import ThreadPoolExecutor

def pkl_to_dict(pkl_file):
    with open(pkl_file, 'rb') as f:
        return pickle.load(f)

# Initialize logging 
logging.basicConfig(level=logging.INFO)
executor = ThreadPoolExecutor(max_workers=5)
def log_to_csv_file(tid, this_nid, logged_time):
    log_directory = "./logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)  # Create the directory if it does not exist
    
    log_file = f"{log_directory}/{this_nid}_log.csv"  
    try:
        with open(log_file, mode='a', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([tid, this_nid, logged_time])
    except Exception as e:
        logging.error(f"Failed to write log entry: {e}")

def log_in_background(tid, this_nid, logged_time):
    executor.submit(log_to_csv_file, tid, this_nid, logged_time)
    
# Read trace packets from file
trace_packets_dict = json.load(open('./all_trace_packets.json'))
# Read trace initial node info from file
trace_details_data = pkl_to_dict('./new_trace_details_data.pkl')
session = requests.Session()

def send_data_to_container(container_name, data, cont_type, tid):
    log_in_background(tid, "mewbie_client", time.time())
    #logging.info(f"Logging = {tid}:'mewbie_client':{time.time()}")
    try:
        if cont_type == 'Python':
            port = 5000
        elif cont_type == 'Redis':
            port = 6379
        elif cont_type == 'MongoDB':
            port = 27017
        elif cont_type == 'Postgres':
            port = 5432

        url = f"http://{container_name}:{port}/"
        #print(url)
        headers = {'Content-Type': 'application/json', 'Connection': 'close'}

        with session.post(url, json=data, headers=headers) as response:
            response.raise_for_status()
        # if response.status_code == 200:
        #     print(f"Successfully sent data to {container_name}")
        # else:
        #     print(f"Status code: {response.status_code}")
        #     print(f"Failed to send data to {container_name}: {response.text}: {response.content}")
    except Exception as e:
        print("Error sending data to container: ", e)


def send_data_in_background(container_name, data, cont_type, tid):
    executor.submit(send_data_to_container, container_name, data, cont_type, tid)


rps = 10000 # packets per second; USER DEFINED
def main():
    total_num_packets = len(trace_packets_dict)
    delay = 1/rps

    total_packets_sent = 0
    start_time = time.time()
    for i in range(1000000):
        st = time.time()
        for tid, t_packet in trace_packets_dict.items():
            t_ini_cont = t_packet['initial_node']
            t_ini_type = t_packet['initial_node_type']
            
            send_data_in_background(t_ini_cont, t_packet, t_ini_type, tid)
            total_packets_sent += 1
            # logging.info(f"Logging = {tid}:'mewbie_client':{time.time()}")
        elapsed_time = time.time() - st
        "limit the loop to req_ps packets per second"
        if elapsed_time < delay:
            #print(delay - elapsed_time)
            time.sleep(delay - elapsed_time)
        #time.sleep(delay)
    end_time = time.time()
    total_exp_runtime = end_time - start_time
    avg_req_ps = total_packets_sent / total_exp_runtime
    print("Finished sending all packets!")
    print(f"Total packets sent: {total_packets_sent}")
    print(f"Total exp runtime: {total_exp_runtime}")
    print(f"Average requests per second: {avg_req_ps}")

if __name__ == "__main__":
    print("Chumma!!")
    # main()