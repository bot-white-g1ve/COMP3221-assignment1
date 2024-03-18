import socket
import threading
import sys
import time
import json

shut_signal = threading.Event()

def load_config(config_file_path):
    neighbors = {}
    current_time = time.time()
    with open(config_file_path, 'r') as file:
        num_neighbors = int(file.readline().strip())
        for _ in range(num_neighbors):
            line = file.readline().strip().split()
            node_id, link_cost, port_id = line[0], float(line[1]), int(line[2])
            neighbors[node_id] = {'link_cost': link_cost, 'port_id': port_id, 'last_received': current_time}

    return neighbors


def listening_to_neighbors(node_id, port_id, server_socket, global_state, config_file_path):
    print(f"[{node_id}] Node is listening on port {port_id}\n")

    while not shut_signal.is_set():    
        try:
            conn, addr = server_socket.accept()
            print(f"[{node_id}] Connection from {addr} established.\n")
            data = conn.recv(4096)
            if data:
                message = data.decode('utf-8')
                update_routing_table(message,global_state['global_table'])
                # print(message)


    
            conn.close()
        except socket.error:
            break

    print(f"[{node_id}] Node has stopped listening on port {port_id}\n")

def init_routing_table(node_id, neighbors):
    cost_table = {}
    time_table = {}

    # List of all nodes in the network
    nodes = ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J']
    current_time = time.time()

    for node in nodes:
        cost_table[node] = {dest: float('inf') for dest in nodes}
        time_table[node] = None
        
    time_table[node_id] = current_time

    for dest in nodes:
        # initialise the tables
        if dest == node_id:
            cost_table[node_id][dest] = 0
        elif dest in neighbors:
            cost_table[node_id][dest] =  neighbors[dest]['link_cost']

    table = {'cost': cost_table, 'time': time_table}
    # format_print_for_dict(table)
    return table

def format_print_for_dict(global_table):
    nodes = sorted(global_table['cost'].keys())
    max_width = max(len(str(item)) for row in global_table['cost'].values() for item in row.values()) + 1
    max_width = max(max_width, max(len(node) for node in nodes))
    
    # Header
    header = "Source/Dest" + ''.join(f"{node:>{max_width}}" for node in nodes)
    print(header)
    
    # Rows
    for src in nodes:
        row_data = [f"{src:>{max_width}}"]  # Align right
        for dest in nodes:
            cost = global_table['cost'][src][dest]
            if cost == float('inf'):
                row_data.append(f"{'∞':>{max_width}}")
            else:
                row_data.append(f"{cost:>{max_width}.1f}")
        print(''.join(row_data))

def update_routing_table(messages, global_table):
    update_message = json.loads(messages)
    recv_costs = update_message['cost']
    recv_times = update_message['time']

    local_costs = global_table['cost']
    local_times = global_table['time']

    for neighbor, recv_time in recv_times.items():
        # Skip if no update received from this neighbor
        if recv_time is None:
            continue

        # Check if received update is newer than the local timestamp for the neighbor
        if local_times[neighbor] is None or recv_time > local_times[neighbor]:
            local_times[neighbor] = recv_time
            local_costs[neighbor] = recv_costs[neighbor]
                

    format_print_for_dict(global_table)


def send_updates(node_id, global_state):
    while not shut_signal.is_set():
    
        table = global_state['global_table']
        neighbors = global_state['neighbors']
      
        message = json.dumps(table)

        for neighbor_id, info in neighbors.items():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect(('localhost', info['port_id']))
                    s.sendall(message.encode('utf-8'))
            except socket.error as e:
                #print(f"Error sending cost table to neighbor {neighbor_id}: {e}")
                pass
                
        time.sleep(10)

def reconstruct_path(source, destination, predecessors):
   
    current_node = destination
    path = []
    while current_node is not None:
        path.insert(0, current_node)  # Insert the node at the beginning of the path
        current_node = predecessors[current_node]
    # Path is reversed so it goes from source to destination
    return path


def dijkstra(node_id, global_state):
    # Retrieve the cost table from the global state
    cost_table = global_state['cost']
    
    # Initialize distances: Set the distance to all nodes as infinity, except for the start node
    distances = {node: float('inf') for node in cost_table}
    distances[node_id] = 0

    # Initialize predecessors: Used to reconstruct the shortest path
    predecessors = {node: None for node in cost_table}
    
    # Nodes to visit
    unvisited = set(cost_table.keys())
    
    current_node = node_id
    while unvisited:
        # Find the unvisited node with the smallest distance
        current_node = min(unvisited, key=lambda node: distances[node])
        unvisited.remove(current_node)
        
        # Consider all neighbors of the current node
        for neighbor, cost in cost_table[current_node].items():
            if neighbor in unvisited:
                new_cost = distances[current_node] + cost
                if new_cost < distances[neighbor]:
                    distances[neighbor] = round(new_cost,3)
                    predecessors[neighbor] = current_node

        if distances[current_node] == float('inf'):
            break  # Remaining nodes are unreachable from start node
    
    # Update the global state with the shortest distances and paths
    global_state['shortest_distances'] = distances
    global_state['predecessors'] = predecessors

    print(f"Shortest paths from node {node_id}:")
    for dest in global_state['cost'].keys():
        if dest != node_id:
            if distances[dest] == float('inf'):
                print(f"Node {node_id} to node {dest}: Unreachable")
            else:
                path = reconstruct_path(node_id, dest, predecessors)
                print(f"Node {node_id} to node {dest}: Distance = {distances[dest]}, Path = {''.join(path)}")
    


def start_server(node_id, port_id, config_file_path):
    global_state = {}
    neighbors = load_config(config_file_path)
    global_table = init_routing_table(node_id, neighbors)
    global_state['global_table'] = global_table
    global_state['neighbors'] = neighbors
    global_state['routing_print_allowed'] = False
    global_state['active'] = True

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', port_id))
    server_socket.listen()

    listening_thread = threading.Thread(target=listening_to_neighbors, args=(node_id, port_id, server_socket, global_state, config_file_path))
    sending_thread = threading.Thread(target= send_updates, args=(node_id, global_state))

    listening_thread.start()
    sending_thread.start()

    # Wait for 60 seconds to gather sufficient information
    print(f"Node {node_id} is gathering information. Waiting for 60 seconds before executing the routing algorithm.")
    time.sleep(30)

    print("executing routing algorithm")
    dijkstra(node_id,global_state['global_table'])



if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 COMP3221_A1_Routing.py <Node ID> <Port ID> <Config File Path>")
        sys.exit(1)

    node_id = sys.argv[1]
    port_id = int(sys.argv[2])
    config_file_path = sys.argv[3]

    start_server(node_id, port_id, config_file_path)
