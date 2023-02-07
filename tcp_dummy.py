"""
tcp_dummy.py
Create and serve dummy data from LabJack over TCP

Andrew Bare
"""

import socket
import json
import random

HOST = "127.0.0.1"
PORT = 5005

def timestep_dummy_data(data):
    data["timeStep"] = data["timeStep"] + 1
    r = random.randint(0, 10)
    data["sensorValues"] = random.sample(range(0, 10), 5)
    return data

# Load json string
# String will be decoded at client
with open('dummy_data.json') as data_file:
    data_raw = data_file.read()

data = json.loads(data_raw)

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    # Bind and accept socket. Print that we're connected.
    s.bind((HOST, PORT))

    s.listen()
    conn, addr = s.accept()
    with conn:
        print(f"Connected on {addr[0]}:{addr[1]}")
        s.setblocking(False)

        while True:
            data = timestep_dummy_data(data)
            data_encoded = json.dumps(data).encode()
            # Determine how many bytes client should read from server
            conn.send(len(data_encoded).to_bytes(2, "big"))

            # Send data to client
            conn.send(data_encoded)

            # Check for any command from client
            # Only read 2 bytes, that's all we need
            command = conn.recv(2)
            print(command)
