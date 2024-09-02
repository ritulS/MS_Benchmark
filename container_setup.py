# List of nodes for each service
cont_to_setup = {
    'Mongodb': [],
    'Redis': [],    
    'Postgres': [],
    'Python': []
}

dc_template = {
    'version': '3',
    'services': {}
}

for service in cont_to_setup:
    service_nodes = cont_to_setup[service]
    for i in range(1, len(service_nodes) + 1):
        if service == 'Python':
            cont_name = f'{service}{service_nodes[i - 1]}'
            dc_template['services'][cont_name] = {
                'image': f'{service}:latest',
                'container_name': cont_name,
                'ports': [f'{i}:{i}']
            }
        elif service == 'Mongodb':
            cont_name = f'{service}{service_nodes[i - 1]}'
            dc_template['services'][cont_name] = {
                'image': f'{service}:4.2',
                'container_name': cont_name,
                'ports': [f'{i}:{i}']
            }
        elif service == 'Redis':
            cont_name = f'{service}{service_nodes[i - 1]}'
            dc_template['services'][cont_name] = {
                'image': f'{service}:6.0',
                'container_name': cont_name,
                'ports': [f'{i}:{i}']
            }
        elif service == 'Postgres':
            cont_name = f'{service}{service_nodes[i - 1]}'
            dc_template['services'][cont_name] = {
                'image': f'{service}:12',
                'container_name': cont_name,
                'ports': [f'{i}:{i}']
            }

