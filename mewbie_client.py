import docker
import json
import time
import requests
import re
import pickle


def pkl_to_dict(pkl_file):
    with open(pkl_file, 'rb') as f:
        return pickle.load(f)

# Read trace packets from file
trace_packets_dict = json.load(open('./all_trace_packets.json'))
# Read trace initial node info from file
trace_details_data = pkl_to_dict('./trace_details_data.pkl')

def send_data_to_container(container_name, data, cont_type):
    try:
        print(container_name)
        print(cont_type)
        if cont_type == 'Python':
            port = 5000
        elif cont_type == 'Redis':
            port = 6379
        elif cont_type == 'MongoDB':
            port = 27017
        elif cont_type == 'Postgres':
            port = 5432

        url = f"http://{container_name}:{port}"
        response = requests.post(url, data=data)
        if response.status_code == 200:
            print(f"Successfully sent data to {container_name}")
        else:
            print(f"Failed to send data to {container_name}: {response.text}")
    except Exception as e:
        print("Error sending data to container: ", e)


req_ps = 50 # packets per second; USER DEFINED
def main():
    total_num_packets = len(trace_packets_dict)
    delay = 1/req_ps
    print(trace_packets_dict)
    for tid, t_packet in trace_packets_dict.items():
        t_ini_cont = trace_details_data[tid][2]
        t_ini_type = t_packet['initial_node_type']
        # t_ini_cont = 'Python-1_8738f7b585302b876bff0dbb5723d7234341f9e6f523c7877f7cff67b48cf782'
        send_data_to_container(t_ini_cont, t_packet, t_ini_type)
        time.sleep(delay)
        break

if __name__ == "__main__":
    main()