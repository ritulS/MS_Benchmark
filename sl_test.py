import time
import logging
import asyncio
import asyncpg
import requests
import aiohttp
import os
import random
import base64
import motor.motor_asyncio
from aiohttp import web
from concurrent.futures import ThreadPoolExecutor

# Initialize these two 
async_sync_ratio = 0
logging.basicConfig(level=logging.INFO)

##################### Initialization #################################
client_map = {} # key: sf_node_id, value: db client. Used to avoid initing client everytime
def db_con_initializer(db_name, sf_node, dm_ip, dm_port, client_map):
    if sf_node in client_map:
        return client_map[sf_node]
    if db_name == "MongoDB":
        client = motor.motor_asyncio.AsyncIOMotorClient(dm_ip, dm_port)
        client_map[sf_node] = client
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
    return os.environ['CONTAINER_NAME']


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

async def mongo_shim_func(kv, op, node_id, dm_ip, dm_port=27017):
    '''
    db_name= mongo, collection name= mycollection.
    '''
    client = db_con_initializer("MongoDB", node_id, dm_ip, dm_port, client_map)
    db = client.mewbie_db # Name of db in container  
    collection = db.mycollection 
    if op == "write":
        result = await collection.insert_one(kv)
        logging.info(f"Document inserted with id {result.inserted_id}")
        return web.Response(text=f"Payload inserted with id\
                             {result.inserted_id}", status=200)
    elif op == "read":
        result = await collection.find_one(kv)
        if result:
            logging.info(f"Document found: {result}")
            return web.Response(text=f"Payload inserted with id\
                             {result}", status=200)
        else:
            return web.Response(text="No entry matching the query", status=404)

###################### HELPERS ################################
def generate_random_string(length):
    """Generates a random string of given byte length."""
    random_bytes = bytes(random.getrandbits(8) for _ in range(length))
    random_string = base64.b64encode(random_bytes).decode('ascii')
    return random_string

async def make_sl_call(sl_dm_nid, async_flag, trace_packet_data):
    try:
        if async_flag == 0: # Call is synchronous
            logging.info(f"Making Sync SL call to {sl_dm_nid}")
            response = requests.post(f"http://{sl_dm_nid}:5000/", json=trace_packet_data)
        else: # Call is Asynchronous
            logging.info(f"Making Async SL call to {sl_dm_nid}")
            async with aiohttp.ClientSession() as session:
                await session.post(f"http://{sl_dm_nid}:5000/", json=trace_packet_data) 
            response = web.Response(text="Async task created", status=200)
        return response
    except requests.exceptions.RequestException as e:
        logging.info(f"Error in Sync SL call: {e}")
        return web.Response(text="Error in Sync SL call", status=500)
    except aiohttp.ClientError as e:
        logging.info(f"Error in Async SL call: {e}")
        return web.Response(text="Error in Async SL call", status=500)


async def make_db_call(tid, dm_nid, db_name, kv, async_flag, op_type, this_nid):
    if db_name == "MongoDB":
        if async_flag == 0: # Call is synchronous
            logging.info(f"Making Sync call to Mongo")
            response = await mongo_shim_func(kv, op_type, this_nid,\
                                                dm_ip=dm_nid, dm_port=27017)
            logging.info(f"Logging = {tid}:{this_nid}:{time.time()}")
        else: # Call is Asynchronous (Fire and forget)
            logging.info(f"Making Async call to Mongo")
            async def async_db_task():
                response = await mongo_shim_func(kv, op_type, this_nid,\
                                                    dm_ip=dm_nid, dm_port=27017)
                logging.info(f"Logging = {tid}:{this_nid}:{time.time()}")
            asyncio.create_task(async_db_task())
            response = web.Response(text="Async task created!", status=200)
        return response
    
    elif db_name == "Redis":
        pass
        return web.Response(text="Unsupported database specified", status=400)

######################################################
async def call_handler(request):
    try:
        trace_packet_data = await request.json()
        # logging.info(f"Received payload: {trace_packet_data}\n")
        this_nid = get_container_name()
        tid = trace_packet_data.get('tid')
        node_calls_dict = trace_packet_data.get('node_calls_dict')
        data_ops_dict = trace_packet_data.get('data_ops_dict')
        logger_nodes = trace_packet_data.get('logger_nodes')
        
        logging.info(f"This nid: {this_nid}\n")
        # dm_nodes_to_call = node_calls_dict[this_nid]
        dm_nodes_to_call = node_calls_dict.get(this_nid)
        
        logging.info(f"Nodes to call for this_nid {this_nid}: {dm_nodes_to_call}\n")
        # Sleep to simulate processing time
        await asyncio.sleep(random.uniform(0.1, 1.5)) # TODO Need to get alibaba values for this

        if this_nid in logger_nodes: # If node is leaf SL, it logs and quits
            logging.info(f"Logging = {tid}:{this_nid}:{time.time()}")

        if not dm_nodes_to_call:
            logging.info(f"Leaf node, no nodes to call further.")
            return web.Response(text=f"No operations for {this_nid}.", status=200)
        
        sl_tasks = []
        for dm_node_call in dm_nodes_to_call:
            dm_nid = dm_node_call[0]
            data_op_id = dm_node_call[1]
            async_flag = dm_node_call[2] # 1 if async, 0 if sync

            if data_op_id != -1: # data op id is -1 for SF call
                try: 
                    op_pkt = data_ops_dict[str(data_op_id)]
                    logging.info(f"Operation packet!!: {op_pkt}")
                    op_type = op_pkt['op_type']
                    op_obj_id = op_pkt['op_obj_id']
                    db_name = op_pkt['db']
                    kv = {op_obj_id: generate_random_string(100)} 
                    logging.info(f"Making db call to {dm_nid}")
                    response = await make_db_call(tid, dm_nid, db_name, kv, async_flag, op_type, this_nid)
                except Exception as e:
                    logging.info(f"Error in make_db_call: {e}")
                    return web.Response(text=f"Error during data operation: {e}", status=500)

            else: # SL call
                try: 
                    task = make_sl_call(dm_nid, async_flag, trace_packet_data)
                    sl_tasks.append(task)
                except Exception as e:
                    logging.error(f"Error in make_sl_call: {e}")
                    return web.Response(text=f"Error during sl call: {e}", status=500)
        if sl_tasks:
            await asyncio.gather(*sl_tasks)
        return web.Response(text="All operations complete!", status=200)
    
    except Exception as e:
        logging.error(f"Error while handling request: {e}")
        return web.Response(text="Error occurred! status", status=500)

this_nid = get_container_name()

async def run_server(port=5000):
    app = web.Application()
    app.router.add_post('/', call_handler)
    app.router.add_get('/', call_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Server started on port {port}")
    try:
        await asyncio.Future()  # run forever
    except KeyboardInterrupt:
        print('Shutting down...')
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(run_server())
