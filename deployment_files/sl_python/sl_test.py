import time
import logging
import asyncio
import asyncpg
import requests
import aiohttp
import os, csv
import random
import base64
import motor.motor_asyncio
import redis.asyncio as redis 
from aiohttp import web
from concurrent.futures import ThreadPoolExecutor

#Request sleep counter
rq_counter = 0
session = None
# Initialize logging 
logging.basicConfig(level=logging.INFO)
# Async logging
executor = ThreadPoolExecutor(max_workers=5)
def log_to_csv_file(tid, this_nid, logged_time, entry_type="INFO", message=""):
    log_directory = "./logs"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)  # Create the directory if it does not exist
    
    log_file = f"{log_directory}/{this_nid}_log.csv"  
    try:
        with open(log_file, mode='a+', newline='') as file:
            writer = csv.writer(file)
            writer.writerow([tid, this_nid, logged_time, entry_type, message])
            logging.info(f"Log entry for tid={tid}, this_nid={this_nid} written successfully")
    except Exception as e:
        logging.error(f"Failed to write log entry: {e}")

def log_in_background(tid, this_nid, logged_time, entry_type="INFO", message=""):
    # logging.info(f"Submitting log task for tid={tid}, this_nid={this_nid}")
    executor.submit(log_to_csv_file, tid, this_nid, logged_time, entry_type, message)


##################### Initialization #################################
client_map = {} # key: sf_node_id, value: db client. Used to avoid initing client everytime
async def db_con_initializer(db_name, sf_node, dm_ip, dm_port, client_map):
    if sf_node in client_map:
        return client_map[sf_node]
    if db_name == "MongoDB":
        client = motor.motor_asyncio.AsyncIOMotorClient(dm_ip, dm_port)
        client_map[sf_node] = client
    elif db_name == "Postgres":
        client = await asyncpg.connect(
            user = "pguser",
            password="pgpass",
            host=dm_ip,
            port=dm_port,
            database="pg_db"
        )
        client_map[sf_node] = client
        create_table_query = """
        CREATE TABLE IF NOT EXISTS mewbie_table (
            id SERIAL PRIMARY KEY,
            key TEXT,
            value TEXT
        );
        """
        try:
            await client.execute(create_table_query)
            # logging.info("Table 'mewbie_table' created or already exists.")
        except Exception as e:
            logging.error(f"Error creating table 'mewbie_table': {e}")
    elif db_name == "Redis":
        client = await redis.from_url(f"redis://{dm_ip}:{dm_port}")
        client_map[sf_node] = client

    return client

def get_container_id():
    with open("/proc/self/cgroup", 'r') as f:
        for line in f:
            if 'cpu' in line:
                return line.strip().split('/')[-1]

def get_container_name():
    return os.environ['CONTAINER_NAME']


##################### SHIM FUNCS #################################
async def postgres_shim_func(kv, op, node_id, dm_ip="localhost", dm_port=5432):
    '''table name= mewbie_table, cols = key, value'''
    pg_client = await db_con_initializer("Postgres", node_id, dm_ip, dm_port, client_map)
    table_name = "mewbie_table"

    if op == "write":
        key, value = list(kv.items())[0]
        query = f"INSERT INTO {table_name} (key, value) VALUES ($1, $2)"
        try:
            result = await pg_client.execute(query, key, value)
            # logging.info(f"KV pair {key}:{value} inserted!")
            return web.Response(text=f"KV pair {key}:{value} inserted", status=200)
        except Exception as e:
            logging.error(f"Error in write to postgres: {e}")
            return web.Response(text=f"Error in write to postgres: {e}", status=500)
    elif op == "read":
        try:
            key, value = list(kv.items())[0]
            query = f"SELECT * FROM {table_name} WHERE key = $1"
            result = await pg_client.fetchrow(query, key)
            # logging.info(f"KV pair {key}:{value} found!")
            return web.Response(text=f"KV pair {key}:{value} read successfully", status=200)
        except Exception as e:
            logging.error(f"Error in read from postgres: {e}")
            return web.Response(text=f"Error in read from postgres: {e}", status=500)


async def mongo_shim_func(kv, op, node_id, dm_ip, dm_port=27017):
    '''
    db_name= mongo, collection name= mycollection.
    '''
    client = await db_con_initializer("MongoDB", node_id, dm_ip, dm_port, client_map)
    db = client.mewbie_db # Name of db in container  
    collection = db.mycollection 
    if op == "write":
        result = await collection.insert_one(kv)
        # logging.info(f"Document inserted with id {result.inserted_id}")
        return web.Response(text=f"Payload inserted with id\
                             {result.inserted_id}", status=200)
    elif op == "read":
        result = await collection.find_one(kv)
        if result:
            # logging.info(f"Document found: {result}")
            return web.Response(text=f"Payload inserted with id\
                             {result}", status=200)
        else:
            return web.Response(text="No entry matching the query", status=404)


async def redis_shim_func(kv, op, node_id, dm_ip, dm_port=6379):
    red_client = await db_con_initializer("Redis", node_id, dm_ip, dm_port, client_map)
    key, value = list(kv.items())[0]
    
    if op == "write":
        try:
            await red_client.set(key, value)
            # logging.info(f"KV pair {key}:{value} inserted!")
            return web.Response(text=f"KV pair {key}:{value} inserted!", status=200)
        except Exception as e:
            logging.error(f"Error in write: {e}")
            return web.Response(text=f"Error in write: {e}", status=500)
    
    elif op == "read":
        try:
            value = await red_client.get(key)
            if value:
                # logging.info(f"KV pair {key}:{value} found!")
                return web.Response(text=f"KV pair {key}:{value} found!", status=200)
            else:
                return web.Response(text=f"No entry found for key {key}", status=404)
        except Exception as e:
            logging.error(f"Error in read: {e}")
            return web.Response(text=f"Error during Redis read: {e}", status=500)

###################### HELPERS ################################
def generate_random_string(length):
    """Generates a random string of given byte length."""
    random_bytes = bytes(random.getrandbits(8) for _ in range(length))
    random_string = base64.b64encode(random_bytes).decode('ascii')
    return random_string

async def make_sl_call(sl_dm_nid, async_flag, trace_packet_data):
    try:
        if async_flag == 0: # Call is synchronous
            # logging.info(f"Making Sync SL call to {sl_dm_nid}")
            # response = requests.post(f"http://{sl_dm_nid}:5000/", json=trace_packet_data)
            async with session.post(f"http://{sl_dm_nid}:5000/", json=trace_packet_data) as response:
                await response.text()
        else: # Call is Asynchronous
            # logging.info(f"Making Async SL call to {sl_dm_nid}")
            async with session.post(f"http://{sl_dm_nid}:5000/", json=trace_packet_data) as response:
                await response.text() 
            response = web.Response(text="Async task created", status=200)
        return response
    except requests.exceptions.RequestException as e:
        # logging.info(f"Error in Sync SL call: {e}")
        return web.Response(text="Error in Sync SL call", status=500)
    except aiohttp.ClientError as e:
        # logging.info(f"Error in Async SL call: {e}")
        return web.Response(text="Error in Async SL call", status=500)

async def execute_db_call(db_shim_func, kv, op_type, this_nid, dm_nid,\
                         dm_port, tid, db_name, async_flag):
    if async_flag == 0:  # Synchronous call
        # logging.info(f"Making Sync call to {db_name}")
        response = await db_shim_func(kv, op_type, this_nid, dm_ip=dm_nid, dm_port=dm_port)
        # logging.info(f"Logging = {tid}:{this_nid}:{time.time()}")
        # log_in_background(tid, this_nid, time.time(),message="Sync SF")
    else:  # Asynchronous call (Fire and forget)
        # logging.info(f"Making Async call to {db_name}")
        async def async_db_task():
            response = await db_shim_func(kv, op_type, this_nid, dm_ip=dm_nid, dm_port=dm_port)
            # logging.info(f"Logging = {tid}:{this_nid}:{time.time()}")
            # log_in_background(tid, this_nid, time.time(),message="Async SF")
        asyncio.create_task(async_db_task())
        response = web.Response(text="Async task created!", status=200)
    return response

async def make_db_call(tid, dm_nid, db_name, kv, async_flag, op_type, this_nid):
    if db_name == "MongoDB":
        db_shim_func = mongo_shim_func
        dm_port = 27017
    elif db_name == "Redis":
        db_shim_func = redis_shim_func
        dm_port = 6379
    elif db_name == "Postgres":
        db_shim_func = postgres_shim_func
        dm_port = 5432
    else:
        return web.Response(text="Unsupported database specified", status=400)

    return await execute_db_call(db_shim_func, kv, op_type, this_nid, dm_nid,\
                                 dm_port, tid, db_name, async_flag)

async def status_handler(request):
    return web.Response(text=f"Alive request count: {rq_counter}\n", status=200)

######################################################
async def process_trace_packet(trace_packet_data):
    try:
        this_nid = get_container_name()
        tid = trace_packet_data.get('tid')
        node_calls_dict = trace_packet_data.get('node_calls_dict')
        data_ops_dict = trace_packet_data.get('data_ops_dict')
        logger_nodes = trace_packet_data.get('logger_nodes')

        # Status Ctr
        global rq_counter
        rq_counter += 1

        dm_nodes_to_call = node_calls_dict.get(this_nid)
        
        # logging.info(f"Nodes to call for this_nid {this_nid}: {dm_nodes_to_call}\n")
        proc_times = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,\
                       1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 2, 2, 2, 2,\
                        2, 2, 2, 2, 2, 3, 3, 3, 3, 3, 4, 4, 4, 5, 5, 5, 6, 6, 6, 7,\
                        7, 8, 8, 9, 9, 10, 11, 11, 12, 13, 15, 16, 18, 20, 22, 25,\
                        29, 33, 39, 45, 52, 62, 70, 78, 87, 97, 111, 126, 143, 164,\
                        188, 220, 254, 289, 331, 379, 446, 3892] #38928
        if this_nid in ['n1765', 'n2134', 'n4376', 'n2977', 'n942', 'n4202', 'n5015', 'n2436', 'n6952', 'n6286']:
            await asyncio.sleep(0.01)
        else:
            await asyncio.sleep(random.choice(proc_times)/1000)  # Simulating processing time
        
        if this_nid in logger_nodes:  # If node is leaf SL, it logs and quits
            # log_in_background(tid, this_nid, time.time())
            pass

        if not dm_nodes_to_call: # leaf node, no further nodes to call.
            rq_counter -= 1
            return

        for dm_node_call in dm_nodes_to_call:
            dm_nid = dm_node_call[0]
            data_op_id = dm_node_call[1]
            async_flag = dm_node_call[2]  # 1 if async, 0 if sync

            if data_op_id != -1:  # data op id is -1 for SF call
                try: 
                    op_pkt = data_ops_dict[str(data_op_id)]
                    op_type = op_pkt['op_type']
                    op_obj_id = op_pkt['op_obj_id']
                    db_name = op_pkt['db']
                    kv = {op_obj_id: generate_random_string(100)} 
                    await make_db_call(tid, dm_nid, db_name, kv, async_flag, op_type, this_nid)
                except Exception as e:
                    logging.info(f"Error in make_db_call: {e}")

            else:  # SL call
                try: 
                    task = await make_sl_call(dm_nid, async_flag, trace_packet_data)
                except Exception as e:
            #         log_in_background("Error in make_sl_call!", this_nid, logged_time=time.time()\
            # , entry_type="ERROR", message=str(e))
                    logging.error(f"Error in make_sl_call: {e}")
        rq_counter -= 1

    except Exception as e:
        logging.error(f"Error in async processing: {e}")

async def call_handler(request):
    try:
        trace_packet_data = await request.json()
        # logging.info(f"Received payload: {trace_packet_data}\n")
        asyncio.create_task(process_trace_packet(trace_packet_data))
        return web.Response(text="Trace packet processing started!", status=200)
    except Exception as e:
        logging.error(f"Error while handling request: {e}")
        # log_in_background("Request Handler Error!", this_nid, logged_time=time.time()\
        #     , entry_type="ERROR", message=str(e))
        return web.Response(text="Error occurred! status:", status=500)
        

this_nid = get_container_name()

async def run_server(port=5000):
    global session
    session = aiohttp.ClientSession()
    app = web.Application()
    app.router.add_post('/', call_handler)
    app.router.add_get('/', call_handler)
    app.router.add_get('/status', status_handler)

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
    finally:
        await session.close()
        await runner.cleanup()

if __name__ == '__main__':
    asyncio.run(run_server())
