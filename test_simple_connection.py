#!/usr/bin/env python3
"""Simple connection test"""

import zmq
import json
import time

# Test ZMQ connection directly
context = zmq.Context()

print("Testing ZMQ ROUTER connection...")

# REQ socket (client)
req = context.socket(zmq.REQ)
req.connect("tcp://localhost:5556")

print("Connected REQ socket to localhost:5556")

# Send test request
request = {
    'action': 'register',
    'agent_id': 'test_simple',
    'name': 'test_simple',
    'metadata': {}
}

print(f"Sending: {request}")
req.send_string(json.dumps(request))

print("Waiting for response...")

# Poll for response
if req.poll(5000):
    response = req.recv_string()
    print(f"Response: {response}")
else:
    print("Timeout waiting for response")

req.close()
context.term()
