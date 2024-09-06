import time
import asyncio
import aiohttp
import requests
import string
import random
import json
import motor.motor_asyncio
from aiohttp import web
from concurrent.futures import ThreadPoolExecutor


# Node id should be initialized in the beginning
node_id = 0
client_map = {} # key: sf_node_id, value: client
def db_con_initializer(db_name, sf_node, dm_ip, dm_port, client_map):
    
    if sf_node in client_map:
        client = client_map[sf_node]
        return client
    if db_name == "MongoDB":
        client = motor.motor_asyncio.AsyncIOMotorClient(dm_ip, dm_port)
    return client

def generate_random_string(length):
    """Generates a random string of given length."""
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for _ in range(length))

async def mongo_shim_func(kv, op, node_id, dm_ip="localhost", dm_port=27017):
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

def make_sl_call(sl_node, sync_flag):
    sl_port = 5000
    try:
        if sync_flag: # Call is synchronous
            response = requests.post(f"http://{sl_node}:5000/")
        else: # Call is Asynchronous
            asyncio.create_task(requests.post(f"http://{sl_node}:5000/"))
            response = web.Response(text="Async task created", status=200)
        return response
    except requests.exceptions.RequestException as e:
        print(f"Error: {e}")
        return -1

async def call_handler(request):
    try:
        print("Received payload:", request)
        node_calls_dict = {}
        data_ops_dict = {}
        this_node_id = 123
        async_sync_ratio = 0
        dm_nodes_to_call = node_calls_dict[this_node_id]
        # Sleep to simulate processing time
        time.sleep(random.uniform(0.1, 1.5)) # TODO Need to get alibaba values for this
        for dm_node in dm_nodes_to_call:
            if dm_node[1] != -1: # sf call
                op_pkt = data_ops_dict[dm_node[1]]
                op_type = op_pkt['op_type']
                op_obj_id = op_pkt['op_obj_id']
                op_obj_size = op_pkt['op_obj_size']
                db_name = op_pkt['db']
                op = "write"
                kv = {"key1": "value1"} # TODO: Replace with random values based op_obj_size
                sync_flag = random.random() < async_sync_ratio
        
                if db_name == "MongoDB":
                    if sync_flag: # Call is synchronous
                        response = await mongo_shim_func(kv, op, this_node_id, dm_ip="localhost", dm_port=27017)
                    else: # Call is Asynchronous
                        asyncio.create_task(mongo_shim_func(kv, op, this_node_id, dm_ip="localhost", dm_port=27017))
                        response = web.Response(text="Async task created", status=200)
                    # return response
                else:
                    return web.Response(text="Unsupported database specified", status=400)
            elif dm_node[1] == -1: # sl call
                sl_response = await make_sl_call(dm_node[0], sync_flag)
                # return sl_response
    
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
