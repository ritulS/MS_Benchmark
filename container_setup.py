import json
import yaml

# Read inputs
def load_dict_from_json(file_path):
    with open(file_path, 'r') as json_file:
        T_prime = json.load(json_file)
    return T_prime

conts_to_setup = {
    'MongoDB': {'count': 0, 'nodes_list': []},
    'Redis': {'count': 0, 'nodes_list': []},    
    'Postgres': {'count': 0, 'nodes_list': []},
    'Python': {'count': 0, 'nodes_list': []}
}

# node_split_output = {'sf_split': db_split_arr, 'sl_split': sl_type_split}
node_split = load_dict_from_json('node_split_output_test.json')

# extract sl node info: count, sl nodeids
total_sl_count = 0
total_sl_nodes_list = []
for sl_type in node_split['sl_split']:
    total_sl_count += node_split['sl_split'][sl_type]['count']
    total_sl_nodes_list.extend(node_split['sl_split'][sl_type]['nodes_list'])

conts_to_setup['Python'] = {'count': total_sl_count, 'nodes_list': total_sl_nodes_list}
conts_to_setup['MongoDB'] = node_split['sf_split']['MongoDB']
conts_to_setup['Redis'] = node_split['sf_split']['Redis']
conts_to_setup['Postgres'] = node_split['sf_split']['Postgres']

for service in conts_to_setup:
    print(service, "=> Conts to setup: ",conts_to_setup[service]['count'])

print(conts_to_setup.keys())
def gen_docker_compose_data(conts_to_setup):
    docker_compose_data = {
    "version": "3.8",
    "services": {}
    }
    for service in conts_to_setup:
        service_node_count = conts_to_setup[service]['count']
        nodes_for_service = conts_to_setup[service]['nodes_list']
        # print(f"{service}-{i}")
        if service == 'Python':
            for j in range(service_node_count):
                cont_name = f"Python-{j}_{nodes_for_service[j]}" # eg: Python-0_(nodeid)
                docker_compose_data['services'][cont_name] = {
                    'image': f"python:latest",
                    'container_name': cont_name,
                    'volumes':[
                        './sl_server.py:/app/sl_server.py'  
                    ],
                    'ports': [f""] # TBC
                }
        elif service == 'Redis':
            for j in range(service_node_count):
                cont_name = f"Redis-{j}_{nodes_for_service[j]}" # eg: Redis-0_(nodeid)
                docker_compose_data['services'][cont_name] = {
                    'image': f"redis:latest",
                    'container_name': cont_name,
                    'ports': [f""] # TBC
                }
        elif service == 'MongoDB':
            for j in range(service_node_count):
                cont_name = f"MongoDB-{j}_{nodes_for_service[j]}" # eg: MongoDB-0_(nodeid)
                docker_compose_data['services'][cont_name] = {
                    'image': f"mongo:latest",
                    'container_name': cont_name,
                    'ports': [f""] # TBC
                }
        elif service == 'Postgres':
            for j in range(service_node_count):
                cont_name = f"Postgres-{j}_{nodes_for_service[j]}" # eg: Postgres-0_(nodeid)
                docker_compose_data['services'][cont_name] = {
                    'image': f"postgres:latest",
                    'container_name': cont_name,
                    'ports': [f""] # TBC
                }   
    
    return yaml.dump(docker_compose_data)

docker_compose_content = gen_docker_compose_data(conts_to_setup)
with open('docker-compose.yml', 'w') as f:
    f.write(docker_compose_content)