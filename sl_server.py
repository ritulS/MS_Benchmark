import time
import asyncio
import aiohttp
import requests
import string
import random
import json
from aiohttp import web
from concurrent.futures import ThreadPoolExecutor


# Node id should be initialized in the beginning
node_id = 0

def generate_random_string(length):
    """Generates a random string of given length."""
    letters = string.ascii_lowercase
    return ''.join(random.choice(letters) for _ in range(length))

class SLRequestHandler():
    '''
    payload: {node_call_dict, data_ops_dict}
    '''
    def _set_response(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers() 

    def extract_payload(payload):
        '''
        Extract dm_nodes_ops & ops_dict 
        '''
        dm_and_ops = payload['node_call_dict'][node_id] # change this to match trace packet format
        ops_dict = payload['data_ops_dict']
        return dm_and_ops, ops_dict
    
    def get_shim_call(db, op_type):
        if db == 'MongoDB':
            if op_type == 'write':
                w_op = ""
            if op_type == 'read':
                r_op = ""

    async def do_POST(self, request):
        payload = await request.json()
        # randomly generate 1 0r 0 with ratio 
        dm_and_ops, ops_dict = self.extract_payload(payload) # downstream nodes
        async_sync_ratio = 1
        for dm_and_op in dm_and_ops:
            dm_node = dm_and_op[0]
            dm_op_id = dm_and_op[1]
            if dm_op_id != -1: # sf call
                op_pkt = ops_dict[dm_op_id]
                op_type = op_pkt['op_type']
                op_obj_id = op_pkt['op_obj_id']
                op_obj_size = op_pkt['op_obj_size']
                db = op_pkt['db']
                db_op = self.get_shim_call(db, op_type)
                # call the downstream node
            port = 0 # TODO: fix ports
            url = f"http://{dm_node}:{port}/"
            if random.random() < async_sync_ratio:
                self.make_async_post(url, payload)
            else:
                self.make_sync_post(url, payload)

    def make_sync_post(self, url, payload):
        # sample a processing time and sleep
        time.sleep(random.uniform(0.1, 1.5)) # TODO Need to get alibaba values for this
        # make a call to the downstream node
        try:
            response = requests.post(url, json=payload)
            print(f"Response: {response.status}, {response.reason}")
            return 0
        except requests.exceptions.RequestException as e:
            print(f"Error: {e}")
            return -1
    
    async def make_async_post(self, url, payload):
        # make a post request to the downstream node
        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload) as response:
                    print(f"Response: {response.status}, {response.reason}")
                    # print(f"Response: {response.text}")
                    return 0
            except aiohttp.ClientError as e:
                print(f"Error: {e}")
                return -1


async def run_server(port=5000):
    app = web.Application()
    app.router.add_post('/', SLRequestHandler)
    app.router.add_get('/', SLRequestHandler)
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