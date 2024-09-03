import json

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
node_split = load_dict_from_json('enrichment_runs/test_run/node_split_output.json')
conts_to_setup['MongoDB'] = node_split['sf_split']['MongoDB']
conts_to_setup['Redis'] = node_split['sf_split']['Redis']
conts_to_setup['Postgres'] = node_split['sf_split']['Postgres']

total_sl_count = 0
total_sl_nodes_list = []
for sl_type in node_split['sl_split']:
    total_sl_count += node_split['sl_split'][sl_type]['count']
    total_sl_nodes_list.extend(node_split['sl_split'][sl_type]['nodes_list'])

conts_to_setup['Python'] = {'count': total_sl_count, 'nodes_list': total_sl_nodes_list}
for service in conts_to_setup:
    print(service, "=> Conts to setup: ",conts_to_setup[service]['count'])

# dc_template = {
#     'version': '3',
#     'services': {}
# }

# for service in cont_to_setup:
#     service_nodes = cont_to_setup[service]
#     for i in range(1, len(service_nodes) + 1):
#         if service == 'Python':
#             cont_name = f'{service}{service_nodes[i - 1]}'
#             dc_template['services'][cont_name] = {
#                 'image': f'{service}:latest',
#                 'container_name': cont_name,
#                 'ports': [f'{i}:{i}']
#             }
#         elif service == 'Mongodb':
#             cont_name = f'{service}{service_nodes[i - 1]}'
#             dc_template['services'][cont_name] = {
#                 'image': f'{service}:4.2',
#                 'container_name': cont_name,
#                 'ports': [f'{i}:{i}']
#             }
#         elif service == 'Redis':
#             cont_name = f'{service}{service_nodes[i - 1]}'
#             dc_template['services'][cont_name] = {
#                 'image': f'{service}:6.0',
#                 'container_name': cont_name,
#                 'ports': [f'{i}:{i}']
#             }
#         elif service == 'Postgres':
#             cont_name = f'{service}{service_nodes[i - 1]}'
#             dc_template['services'][cont_name] = {
#                 'image': f'{service}:12',
#                 'container_name': cont_name,
#                 'ports': [f'{i}:{i}']
#             }

