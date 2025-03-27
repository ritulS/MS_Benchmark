import json
import yaml
import subprocess, os

# Read inputs
def load_dict_from_json(file_path):
    with open(file_path, 'r') as json_file:
        T_prime = json.load(json_file)
    return T_prime

def read_yaml(file):
    with open(file, 'r') as f:
        data = yaml.safe_load(f)
    return data

conts_to_setup = {
    'MongoDB': {'count': 0, 'nodes_list': []},
    'Redis': {'count': 0, 'nodes_list': []},    
    'Postgres': {'count': 0, 'nodes_list': []},
    'Python': {'count': 0, 'nodes_list': []}
}

config = read_yaml('enrichment_config.yaml')
workload_name = config['ExpWorkloadName']
# print(workload_name)

node_split = load_dict_from_json(f"./enrichment_runs/{workload_name}/node_split_output.json")
# unique_nodes = load_dict_from_json("./node_and_trace_details/500_100k_unique_nodes.json")
# unique_nodes_str = ",".join(unique_nodes)
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
    # Mewbie client
    path = "./deployment_files/mewbie_client/"
    subprocess.run(["docker", "build", "-t", "mewbieregistry.com:5000/mewbie_img", path], check=True)
    subprocess.run(["docker","push","mewbieregistry.com:5000/mewbie_img:latest"])
    # SL Python
    path = "./deployment_files/sl_python/"
    subprocess.run(["docker", "build", "-t", "mewbieregistry.com:5000/slp_img", path], check=True)
    subprocess.run(["docker","push","mewbieregistry.com:5000/slp_img:latest"])
    # Mongo Mewbie
    path = "./deployment_files/mongo_mewbie_img/"
    subprocess.run(["docker", "build", "-t", "mewbieregistry.com:5000/mongo_mewbie_img", path], check=True)
    subprocess.run(["docker","push","mewbieregistry.com:5000/mongo_mewbie_img:latest"])
    # # Redis Mewbie
    # path = "./deployment_files/redis_mewbie_img/"
    # subprocess.run(["docker", "build", "-t", "mewbieregistry.com:5000/redis_mewbie_img", path], check=True)
    # subprocess.run(["docker","push","mewbieregistry.com:5000/redis_mewbie_img:latest"])
    # # Postgres Mewbie
    # path = "./deployment_files/postgres_mewbie_img/"
    # subprocess.run(["docker", "build", "-t", "mewbieregistry.com:5000/postgres_mewbie_img", path], check=True)
    # subprocess.run(["docker","push","mewbieregistry.com:5000/postgres_mewbie_img:latest"])

def gen_docker_compose_data(conts_to_setup, python_cpc, db_cpc, workload_name):
    docker_compose_data = {
        "version": "3.3",
        "services": {},
        "networks": {
            "mewbie_network": {
                "driver": "overlay",
                "ipam": {
                    "config": [
                        {
                            "subnet": "10.20.0.0/16"
                        }
                    ]
                }
            }
        },
        "volumes": {
            "ritul_logs":{},
            "prometheus_data":{},
            "grafana_data":{}
        }
    }

    # # ADD PROMETHEUS SERVICE
    # docker_compose_data['services']['prometheus'] = {
    #     'image': 'prom/prometheus:latest',
    #     'container_name': 'prometheus',
    #     'volumes': [
    #         './monitoring/prometheus.yml:/etc/prometheus/prometheus.yml',
    #         'prometheus_data:/prometheus'
    #     ],
    #     'ports': [
    #         '9091:9090'
    #     ],
    #     'networks': ['mewbie_network'],
    #     'command': [
    #         "--config.file=/etc/prometheus/prometheus.yml",
    #         "--storage.tsdb.path=/prometheus",
    #         "--web.enable-lifecycle"
    #     ],
    #     'deploy': {
    #         'placement': {
    #             'constraints': [
    #                 'node.role == manager'
    #             ]
    #         }
    #     }
    # }

    # # ADD GRAFANA SERVICE
    # docker_compose_data['services']['grafana'] = {
    #     'image': 'grafana/grafana:latest',
    #     'container_name': 'grafana',
    #     'volumes': [
    #         'grafana_data:/var/lib/grafana'
    #     ],
    #     'ports': [
    #         '3000:3000'
    #     ],
    #     'networks': ['mewbie_network'],
    #     'environment': [
    #         'GF_SECURITY_ADMIN_USER=admin',
    #         'GF_SECURITY_ADMIN_PASSWORD=admin',
    #         'GF_USERS_ALLOW_SIGN_UP=false'
    #     ],
    #     'deploy': {
    #         'placement': {
    #             'constraints': [
    #                 'node.role == manager'
    #             ]
    #         }
    #     }
    # }

    # # ADD CADVISOR SERVICE
    # docker_compose_data['services']['cadvisor'] = {
    #     'image': 'gcr.io/cadvisor/cadvisor:latest',
    #     'container_name': 'cadvisor',
    #     'volumes': [
    #         '/var/run/docker.sock:/var/run/docker.sock',
    #         '/sys:/sys',
    #         '/var/lib/docker/:/var/lib/docker',
    #         '/etc/machine-id:/etc/machine-id:ro',
    #         '/var/lib/dbus/machine-id:/var/lib/dbus/machine-id:ro'
    #     ],
    #     'ports': [
    #         '8080:8080'  # Access cAdvisor on port 8080
    #     ],
    #     'networks': ['mewbie_network'],
    #     'deploy': {
    #         'mode': 'global'  # Runs on all nodes in the Swarm
    #     }
    # }



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
        'networks': ['mewbie_network'],
        'deploy': {
                'placement': {
                    'constraints': [
                        'node.role == manager'
                    ]
                }
            }
    }
    # Add a volume for Portainer
    docker_compose_data['volumes']['portainer_data'] = {
        'driver': 'local'
    }
    docker_compose_data['services']['MewbieClient'] = {
            'image': "mewbieregistry.com:5000/mewbie_img:latest",
            'container_name': 'mewbie_client',
            'volumes':[
                './enrichment_runs/{}/all_trace_packets.json:/app/all_trace_packets.json'.format(workload_name),
                './deployment_files/mewbie_client/mewbie_client.go:/app/mewbie_client.go',
                './deployment_files/mewbie_client/go.mod:/app/go.mod',
                './deployment_files/mewbie_client/go.sum:/app/go.sum',
                'ritul_logs:/app/logs/'
            ],
            'environment': [
                'CONTAINER_NAME=mewbie_client',
                f'WORKLOAD_NAME={workload_name}'
                # f'SL_NODES={unique_nodes_str}'
            ],
            'command':
            'sh -c "tail -f /dev/null"',
            'networks': ['mewbie_network'],
            'deploy': {
                'placement': {
                    'constraints': [
                        'node.role == manager'
                    ]
                }
            },
            'sysctls': [  # Added sysctls for port range
                'net.ipv4.ip_local_port_range=1024 65000',
                'net.core.somaxconn=65535',  # Increase TCP backlog
                'net.ipv4.tcp_tw_reuse=1'  # Enable TCP port reuse
                ]
    }
    
    def calc_cpus_per_container(cpc):
        return 1.0/cpc

    special_nodes = ["n1865", "n5223", "n2127", "n530", "n4210", "n6292"]
    sf_hot_nodes = ["n4037", "n7049", "n3882", "n2127", "n6572", "n2405", "n7709"]
    
    for service in conts_to_setup:
        service_node_count = conts_to_setup[service]['count']
        nodes_for_service = conts_to_setup[service]['nodes_list']
        if service == 'Python':
            cpus_per_cont = calc_cpus_per_container(python_cpc)
            for j in range(service_node_count):
                service_name = f"Python-{j}_{nodes_for_service[j]}"  # e.g., Python-0_(nodeid)
                cont_name = f"{nodes_for_service[j]}"
               
                docker_compose_data['services'][service_name] = {
                        'image': f"mewbieregistry.com:5000/slp_img:latest",
                    'container_name': cont_name,
                    'volumes':[
                        'ritul_logs:/app/logs/' 
                    ],
                    'environment': [
                        f'CONTAINER_NAME={cont_name}'
                    ],
                    'networks': {
                        'mewbie_network': {
                            'aliases': [cont_name]  
                        }
                    },
                    'deploy': {

                        'resources': {
                            'limits': {
                                'cpus': '15',  # CPU limit
                                'memory': '15G'  # Memory limit, adjust as needed
                            }
                        }
                    },
                    'sysctls': [  # Added sysctls for port range
                    'net.ipv4.ip_local_port_range=1024 65000',
                    'net.core.somaxconn=65535',  # Increase TCP backlog
                    'net.ipv4.tcp_tw_reuse=1'  # Enable TCP port reuse
                    ]
                }
                if cont_name in special_nodes:
                    docker_compose_data['services'][service_name]['deploy'] = {
                            'resources': {
                                'limits': {
                                    'cpus': '15',  # CPU limit
                                    'memory': '15G'  # Memory limit, adjust as needed
                                }
                            }  
                    }
        
        elif service == 'Redis':
            for j in range(service_node_count):
                db_cpu = 3
                service_name = f"Redis-{j}_{nodes_for_service[j]}" # eg: Redis-0_(nodeid)
                cont_name = f"{nodes_for_service[j]}"
                # if cont_name in sf_hot_nodes:
                #     db_cpu = 1
                docker_compose_data['services'][service_name] = {
                    'image': f"redis:latest",
                    'container_name': cont_name,
                    'networks': {
                        'mewbie_network': {
                            'aliases': [cont_name]  
                        }
                    },
                    'sysctls': [
                        'net.core.somaxconn=65535',
                        'net.ipv4.tcp_max_syn_backlog=65535',
                        'net.ipv4.tcp_tw_reuse=1',
                        'net.ipv4.ip_local_port_range=1024 65000'
                    ],
                    'deploy': {
                        # 'replicas': 2,
                        'resources': {
                            'limits': {
                                'cpus': f'{db_cpu}',
                                'memory': '4G'  
                            }
                        }
                    } 
                }           
        elif service == 'MongoDB':
            for j in range(service_node_count):
                db_cpu = 3
                service_name = f"MongoDB-{j}_{nodes_for_service[j]}" # eg: MongoDB-0_(nodeid)
                cont_name = f"{nodes_for_service[j]}"
                # if cont_name in sf_hot_nodes:
                #     db_cpu = 1
                docker_compose_data['services'][service_name] = {
                    'image': f"mongo:latest",
                    'container_name': cont_name,
                    'networks': {
                        'mewbie_network': {
                            'aliases': [cont_name] 
                        }
                    },
                    'cap_add': ['NET_ADMIN'],
                    'sysctls': [
                        'net.core.somaxconn=65535',
                        'net.ipv4.tcp_max_syn_backlog=65535',
                        'net.ipv4.tcp_tw_reuse=1',
                        'net.ipv4.ip_local_port_range=1024 65000'
                        # 'vm.max_map_count=16777216', ######### Temp fix by running on host
                        # 'vm.swappiness=10'
                    ],
                    'volumes': [
                        './deployment_files/mongo-init/mongo-init.js:/docker-entrypoint-initdb.d/mongo-init.js'
                    ],
                    'deploy': {
                        # 'replicas': 2,  # Number of replicas set to 2
                        'resources': {
                            'limits': {
                                'cpus': f'{db_cpu}',
                                'memory': '16G' 
                            }
                        }
                    }
                    # 'cap_add': ['SYS_ADMIN']
                }
        elif service == 'Postgres':
            cpus_per_container = calc_cpus_per_container(db_cpc)
            for j in range(service_node_count):
                db_cpu = 3
                service_name = f"Postgres-{j}_{nodes_for_service[j]}" # eg: Postgres-0_(nodeid)
                cont_name = f"{nodes_for_service[j]}"
                # if cont_name in sf_hot_nodes:
                #     db_cpu = 1
                docker_compose_data['services'][service_name] = {
                    'image': f"postgres:latest",
                    'container_name': cont_name,
                    'networks': {
                        'mewbie_network': {
                            'aliases': [cont_name]  
                        }
                    },
                    'environment': [
                        'POSTGRES_USER=pguser',
                        'POSTGRES_PASSWORD=pgpass',
                        'POSTGRES_DB=pg_db',
                        'POSTGRES_HOST_AUTH_METHOD=trust',
                        'PG_SHARED_BUFFERS=2GB',  # Increased shared buffers
                        'PG_WORK_MEM=16MB',  # More memory per query
                        'PG_EFFECTIVE_CACHE_SIZE=6GB',  # Optimize cache size
                    ],
                    'sysctls': [
                        'net.core.somaxconn=65535',
                        'net.ipv4.tcp_max_syn_backlog=65535',
                        'net.ipv4.tcp_tw_reuse=1',
                        'net.ipv4.ip_local_port_range=1024 65000'
                    ],
                    'volumes': [
                        './deployment_files/pg-init/init.sql:/docker-entrypoint-initdb.d/init.sql'
                    ],
                    'command': ["postgres", 
                                "-c", "max_connections=500",
                                "-c", "shared_buffers=500MB"
                                ],
                    'deploy': {
                        'resources': {
                            'limits': {
                                'cpus': f'{db_cpu}',
                                'memory': '4G'  
                            }
                        }
                    }
                }  

    return yaml.dump(docker_compose_data, default_flow_style=False, sort_keys=False)


python_cpc = 2
db_cpc = 2
build_images()
docker_compose_content = gen_docker_compose_data(conts_to_setup, python_cpc, db_cpc, workload_name)
with open('docker-compose.yml', 'w') as f:
    f.write(docker_compose_content)


