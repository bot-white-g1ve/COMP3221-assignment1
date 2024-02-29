import socket
import threading
import sys

def load_config(config_file_path):
    neighbors = {}
    with open(config_file_path, 'r') as file:
        num_neighbors = int(file.readline().strip())
        for _ in range(num_neighbors):
            line = file.readline().strip().split()
            node_id, distance, port_id = line[0], float(line[1]), int(line[2])
            neighbors[node_id] = {'distance': distance, 'port_id': port_id}
    return neighbors

def handle_client(conn, addr, node_id, neighbors):
    print(f"[{node_id}] Connection from {addr} established.")
    # 添加与客户端通信的代码
    conn.close()

def start_server(node_id, port_id, config_file_path):
    neighbors = load_config(config_file_path)
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', port_id))
    server_socket.listen()
    print(f"[{node_id}] Node is listening on port {port_id}")

    try:
        while True:
            conn, addr = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(conn, addr, node_id, neighbors))
            thread.start()
            print(f"[{node_id}] Active connections: {threading.activeCount() - 1}")
    except KeyboardInterrupt:
        print(f"[{node_id}] Shutting down node.")
        server_socket.close()

if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: script.py <Node ID> <Port ID> <Config File Path>")
        sys.exit(1)

    node_id = sys.argv[1]
    port_id = int(sys.argv[2])
    config_file_path = sys.argv[3]

    start_server(node_id, port_id, config_file_path)
