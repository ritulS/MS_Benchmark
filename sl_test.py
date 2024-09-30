import time
import docker
import asyncio
import asyncpg
import requests
import string
import random
import json
import motor.motor_asyncio
from aiohttp import web
from concurrent.futures import ThreadPoolExecutor

# Initialize these two 
async_sync_ratio = 0

##################### Initialization #################################
client_map = {} # key: sf_node_id, value: db client. Used to avoid initing client everytime
def db_con_initializer(db_name, sf_node, dm_ip, dm_port, client_map):
    if sf_node in client_map:
        client = client_map[sf_node]
        return client
    if db_name == "MongoDB":
        client = motor.motor_asyncio.AsyncIOMotorClient(dm_ip, dm_port)
    elif db_name == "Postgres":
        client = asyncpg.connect(
            user = "pguser",
            password="pgpass",
            host=dm_ip,
            port=dm_port,
            database="pg_db"
        )
    return client

def get_container_id():
    with open("/proc/self/cgroup", 'r') as f:
        for line in f:
            if 'cpu' in line:
                return line.strip().split('/')[-1]

def get_container_name():
    client = docker.DockerClient(base_url='unix://var/run/docker.sock')
    container_id = get_container_id()
    container = client.containers.get(container_id)
    return container.name
this_nid = get_container_name()

##################### SHIM FUNCS #################################
async def pg_shim_func(kv, op, node_id, dm_ip="localhost", dm_port=27017):
    '''
    table name= ms_table, cols = key, value
    '''
    pg_client = db_con_initializer("Postgres", node_id, dm_ip, dm_port, client_map)
    if op == "write":
        result = await pg_client.execute("INSERT INTO ms_table (key, value) VALUES ($1, $2)", kv[1], kv[2])
        return web.Response(text=f"Payload inserted with id\
                                {result.rows[0]['id']}", status=200)
    elif op == "read":
        pass

async def mongo_shim_func(kv, op, node_id, dm_ip="localhost", dm_port=27017):
    '''
    db_name= mongo, collection name= mycollection.
    '''
    client = db_con_initializer("MongoDB", node_id, dm_ip, dm_port, client_map)
    db = client.mongo  
    collection = db.mycollection 
    if op == "write":
        result = await collection.insert_one(kv)
        return web.Response(text=f"Payload inserted with id\
                             {result.inserted_id}", status=200)
    elif op == "read":
        result = await collection.find_one(kv)
        return web.Response(text=f"Payload inserted with id\
                             {result.inserted_id}", status=200)

###################### HELPERS ################################
def generate_random_string(length):
    """Generates a random string of given length."""
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for _ in range(length))

def make_sl_call(sl_dm_nid, sync_flag):
    sl_port = 5000
    try:
        if sync_flag: # Call is synchronous
            response = requests.post(f"http://{sl_dm_nid}:5000/")
        else: # Call is Asynchronous
            asyncio.create_task(requests.post(f"http://{sl_dm_nid}:5000/"))
            response = web.Response(text="Async task created", status=200)
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return -1
    
async def make_db_call(db_name, kv, sync_flag, op_type, this_nid):
    if db_name == "MongoDB":
        if sync_flag: # Call is synchronous
            response = await mongo_shim_func(kv, op_type, this_nid,\
                                                dm_ip="localhost", dm_port=27017)
        else: # Call is Asynchronous (Fire and forget)
            asyncio.create_task(mongo_shim_func(kv, op_type, this_nid,\
                                                    dm_ip="localhost", dm_port=27017))
            response = web.Response(text="Async task created", status=200)
        return response
    elif db_name == "Redis":
        pass
    else:
        return web.Response(text="Unsupported database specified", status=400)

######################################################
async def call_handler(request):
    try:
        data = await request.json()
        # print(data)
        print("Received payload:", request)
        node_calls_dict = data.get('node_call_dict')
        data_ops_dict = data.get('data_ops_dict')

        this_nid = '0'
        async_sync_ratio = 0
        dm_nodes_to_call = node_calls_dict[this_nid]
        print(dm_nodes_to_call)
        print(data_ops_dict)
        # Sleep to simulate processing time
        time.sleep(random.uniform(0.1, 1.5)) # TODO Need to get alibaba values for this

        for dm_nid, data_op_id in dm_nodes_to_call:
            
            if data_op_id != str(-1): # data op id is -1 for SF call
                
                try: 
                    print("herey")
                    op_pkt = data_ops_dict[str(data_op_id)]
                    print(op_pkt)
                    op_type = op_pkt['op_type']
                    op_obj_id = op_pkt['op_obj_id']
                    op_obj_size = op_pkt['op_obj_size']
                    db_name = op_pkt['db']
                    op_type = "write"
                    kv = {"key1": "value1"} # TODO: Replace with random values based op_obj_size
                    sync_flag = random.random() < async_sync_ratio
                    print(sync_flag)
                    
                    response = make_db_call(db_name, kv, sync_flag, op_type, this_nid)
                except Exception as e:
                    print(f"Error in make_db_call: {e}")
                    return web.Response(text=f"Error during data operation: {e}", status=500)

            else: # SL call
                try: 
                    response = await make_sl_call(dm_nid, sync_flag)
                except Exception as e:
                    print(f"Error in make_sl_call: {e}")
                    return web.Response(text=f"Error during sl call: {e}", status=500)
    
    except Exception as e:
        print(f"Error while handling request: {e}")
        return web.Response(text="Error occurred!", status=500)


async def run_server(port=5000):
    app = web.Application()
    app.router.add_post('/', call_handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', port)
    await site.start()
    print(f"Server started on port {port}")
    try:
        await asyncio.Future()  # run forever
    except KeyboardInterrupt:
        print('Shutting down...')
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(run_server())
