import time
import random
import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from concurrent.futures import ThreadPoolExecutor


# Node id should be initialized in the beginning
node_id = 0

class SLRequestHandler(BaseHTTPRequestHandler):

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
    
    def get_shim_call(db, op):
        if db == 'MongoDB':
            # get relevant call from mongo shim file
            pass
        elif db == 'Redis':
            # get relevant call from redis shim file
            pass
        elif db == 'Postgres':
            # get relevant call from postgres shim file
            pass

    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        payload = json.loads(post_data)
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
                # call the downstream node

            if random.random() < async_sync_ratio:
                self.async_handler(dm_node)
            else:
                self.sync_handler(dm_node)

    def sync_handler(self, dm_node):
        # sample a processing time and sleep
        time.sleep(random.uniform(0.1, 1.5)) # TODO Need to get alibaba values for this
        # make a call to the downstream node
        return 0
    
    def async_handler(self, payload):
        # make a call to the downstream node
        return 0



def run_server(port=5000):
    server_address = ('0.0.0.0', port)
    print(f'Starting server at port {port}')
    httpd = HTTPServer(server_address, SLRequestHandler)
    httpd.serve_forever()


if __name__ == '__main__':
    run_server()