import socket
import threading
import sys
import time
import re

shut_signal = threading.Event()

def load_config(config_file_path):
    neighbors = {}
    with open(config_file_path, 'r') as file:
        num_neighbors = int(file.readline().strip())
        for _ in range(num_neighbors):
            line = file.readline().strip().split()
            node_id, distance, port_id = line[0], float(line[1]), int(line[2])
            neighbors[node_id] = {'distance': distance, 'port_id': port_id}
    return neighbors

def listening_to_neighbors(node_id, port_id, server_socket):
    print(f"[{node_id}] Node is listening on port {port_id}")

    while not shut_signal.is_set():
        try:
            conn, addr = server_socket.accept()
            print(f"[{node_id}] Connection from {addr} established.")
            conn.close()
        except socket.error:
            break

    print(f"[{node_id}] Node has stopped listening on port {port_id}")

def command_line_interface(node_id, neighbors, server_socket):
    while not shut_signal.is_set():
        cmd = input()
        if cmd == "config":
            for neighbor, info in neighbors.items():
                print(f"{neighbor} {info['distance']} {info['port_id']}")
        elif cmd == "shutdown":
            shut_signal.set()
            server_socket.close()
        elif re.match(r'shutdown -n \d+', cmd):
            wait_time = int(re.findall(r'\d+', cmd)[0])
            print(f"Shutdown scheduled in {wait_time} seconds.")
            time.sleep(wait_time)
            shut_signal.set()
            server_socket.close()

def format_routing_table_for_sending(routing_table):
    lines = [f"{node_id} {info['distance']} {info['port_id']}" for node_id, info in neighbors.items()]
    routing_table_str = "\n".join(lines)
    return routing_table_str

def init_routing_table(node_id, neighbors):
    routing_table = {}
    for neighbor_id, info in neighbors.items():
        path = node_id + neighbor_id
        routing_table[neighbor_id] = {'distance': info['distance'], 'path': path}
    return routing_table

def format_routing_table_for_sending(routing_table):
    lines = [f"{node_id} {info['distance']} {info['path']}" for node_id, info in routing_table.items()]
    routing_table_str = "\n".join(lines)
    return routing_table_str

def sending_routing_table(node_id, neighbors, routing_table):
    routing_table_str = format_routing_table_for_sending(neighbors)
    message = f"{len(neighbors)}\n{routing_table_str}"

    for neighbor_id, info in neighbors.items():
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.connect(('localhost', info['port_id']))
                s.sendall(message.encode('utf-8'))
        except socket.error as e:
            print(f"Error sending routing table to neighbor {neighbor_id}: {e}")
        time.sleep(10)

def start_server(node_id, port_id, config_file_path):
    neighbors = load_config(config_file_path)
    rrouting_table = init_routing_table(node_id, neighbors)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', port_id))
    server_socket.listen()

    listening_thread = threading.Thread(target=listening_to_neighbors, args=(node_id, port_id, server_socket))
    cli_thread = threading.Thread(target=command_line_interface, args=(node_id, neighbors, server_socket))
    

    listening_thread.start()
    cli_thread.start()

    cli_thread.join()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 COMP3221_A1_Routing.py <Node ID> <Port ID> <Config File Path>")
        sys.exit(1)

    node_id = sys.argv[1]
    port_id = int(sys.argv[2])
    config_file_path = sys.argv[3]

    start_server(node_id, port_id, config_file_path)
