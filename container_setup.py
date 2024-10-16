import json
import yaml
import subprocess

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
node_split = load_dict_from_json('./enrichment_runs/dmix2_mongo_heavy/node_split_output.json')

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

def build_images():
    path = "./deployment_files/mewbie_client/"
    subprocess.run(["docker", "build", "-t", "mewbie_img", path], check=True)
    path = "./deployment_files/sl_python/"
    subprocess.run(["docker", "build", "-t", "slp_img", path], check=True)

def gen_docker_compose_data(conts_to_setup, python_cpc, db_cpc, workload_name):
    docker_compose_data = {
        "version": "3.3",
        "services": {},
        "networks": {
            "mewbie_network": {
                "driver": "bridge"
            }
        },
        "volumes": {}
    }

    
    # Add Portainer service
    docker_compose_data['services']['portainer'] = {
        'image': 'portainer/portainer-ce:latest',
        'container_name': 'portainer',
        'restart': 'always',
        'ports': [
            '8000:9000'
        ],
        'volumes': [
            '/var/run/docker.sock:/var/run/docker.sock',  # To manage Docker
            'portainer_data:/data'  # Persistent volume for Portainer data
        ],
        'networks': ['mewbie_network']
    }
    # Add a volume for Portainer
    docker_compose_data['volumes']['portainer_data'] = {
        'driver': 'local'
    }

    # Client container setup
    docker_compose_data['services']['MewbieClient'] = {
            # 'build': {
            #     'context': './deployment_files/mewbie_client',  # Directory where the Dockerfile is located
            #     'dockerfile': 'Dockerfile'  # Name of the Dockerfile
            # },
            'image': f"mewbie_img:latest",
            'container_name': 'mewbie_client',
            'volumes':[
                './enrichment_runs/{}/all_trace_packets.json:/app/all_trace_packets.json'.format(workload_name),
                # './deployment_files/mewbie_client/mewbie_client.py:/app/mewbie_client.py',
                # './deployment_files/mewbie_client/new_trace_details_data.pkl:/app/new_trace_details_data.pkl'
            ],
            'environment': [
                f'CONTAINER_NAME=mewbie_client'
            ],
            'command':
            'sh -c "tail -f /dev/null"',
            'networks': ['mewbie_network'],
    }

    def calc_cpus_per_container(cpc):
        return 1.0/cpc

    for service in conts_to_setup:
        service_node_count = conts_to_setup[service]['count']
        nodes_for_service = conts_to_setup[service]['nodes_list']
        if service == 'Python':
            cpus_per_cont = calc_cpus_per_container(python_cpc)
            for j in range(service_node_count):
                service_name = f"Python-{j}_{nodes_for_service[j]}"  # e.g., Python-0_(nodeid)
                cont_name = f"{nodes_for_service[j]}"
                docker_compose_data['services'][service_name] = {
                    # 'build': {
                    #     'context': './deployment_files/sl_python',  # Directory where the Dockerfile is located
                    #     'dockerfile': 'Dockerfile'  # Name of the Dockerfile
                    # },
                    'image': f"slp_img",
                    'container_name': cont_name,
                    'environment': [
                        f'CONTAINER_NAME={cont_name}'
                    ],
                    'networks': ['mewbie_network'],
                }
        
        elif service == 'Redis':
            for j in range(service_node_count):
                service_name = f"Redis-{j}_{nodes_for_service[j]}" # eg: Redis-0_(nodeid)
                cont_name = f"{nodes_for_service[j]}"
                docker_compose_data['services'][service_name] = {
                    'image': f"redis:latest",
                    'container_name': cont_name,
                    'networks': ['mewbie_network'] 
                }
        elif service == 'MongoDB':
            for j in range(service_node_count):
                service_name = f"MongoDB-{j}_{nodes_for_service[j]}" # eg: MongoDB-0_(nodeid)
                cont_name = f"{nodes_for_service[j]}"
                docker_compose_data['services'][service_name] = {
                    'image': f"mongo:latest",
                    'container_name': cont_name,
                    'networks': ['mewbie_network']
                }
        elif service == 'Postgres':
            cpus_per_container = calc_cpus_per_container(db_cpc)
            for j in range(service_node_count):
                service_name = f"Postgres-{j}_{nodes_for_service[j]}" # eg: Postgres-0_(nodeid)
                cont_name = f"{nodes_for_service[j]}"
                docker_compose_data['services'][service_name] = {
                    'image': f"postgres:latest",
                    'container_name': cont_name,80
                        'POSTGRES_DB=pg_db',
                        'POSTGRES_HOST_AUTH_METHOD=trust'
                    ]
                    # 'deploy': {
                    #     'resources': {
                    #         'limits': {
                    #             'cpus': str(cpus_per_container)
                    #         }
                    #     }
                    # }
                }   
    
    return yaml.dump(docker_compose_data, default_flow_style=False, sort_keys=False)

python_cpc = 2
db_cpc = 2
workload_name = "new_test_run"
build_images()
docker_compose_content = gen_docker_compose_data(conts_to_setup, python_cpc, db_cpc, workload_name)
with open('docker-compose.yml', 'w') as f:
    f.write(docker_compose_content)