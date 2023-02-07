import socket
import time

HOST = "127.0.0.1"  # The server's hostname or IP address
PORT = 5005  # The port used by the server

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
    s.connect((HOST, PORT))
    print("Connected")
    time.sleep(1)
    s.sendall(b"Hello, world")
    data = s.recv(1024)

print(f"Recieved {data!r}")