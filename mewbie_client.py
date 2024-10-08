import json
import time
import requests
import re
import pickle
import logging

def pkl_to_dict(pkl_file):
    with open(pkl_file, 'rb') as f:
        return pickle.load(f)

# Read trace packets from file
trace_packets_dict = json.load(open('./all_trace_packets.json'))
# Read trace initial node info from file
trace_details_data = pkl_to_dict('./trace_details_data.pkl')

def send_data_to_container(container_name, data, cont_type):
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
        print(url)
        headers = {'Content-Type': 'application/json'}
        print(data)
        response = requests.post(url, json=data, headers=headers)
        if response.status_code == 200:
            print(f"Successfully sent data to {container_name}")
        else:
            print(f"Status code: {response.status_code}")
            print(f"Failed to send data to {container_name}: {response.text}: {response.content}")
    except Exception as e:
        print("Error sending data to container: ", e)


req_ps = 50 # packets per second; USER DEFINED
def main():
    total_num_packets = len(trace_packets_dict)
    delay = 1/req_ps
    for tid, t_packet in trace_packets_dict.items():
        t_ini_cont = t_packet['initial_node']
        t_ini_type = t_packet['initial_node_type']
        send_data_to_container(t_ini_cont, t_packet, t_ini_type)
        logging.info(f"Logging = {tid}:'mewbie_client':{time.time()}")
        time.sleep(delay)

if __name__ == "__main__":
    main()