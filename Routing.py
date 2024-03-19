import socket
import threading
import sys
import time
import json
import re

shut_signal = threading.Event()
calculation_signal = threading.Event()


def load_config(config_file_path):
    neighbors = {}
    with open(config_file_path, 'r') as file:
        num_neighbors = int(file.readline().strip())
        for _ in range(num_neighbors):
            line = file.readline().strip().split()
            node_id, link_cost, port_id = line[0], float(line[1]), int(line[2])
            neighbors[node_id] = {'link_cost': link_cost, 'port_id': port_id, 'last_received': None,'active': True}

    return neighbors


def listening_to_neighbors(port_id, server_socket, global_state, config_file_path,update_singal):
    node_id = global_state['node_id']
    print(f"[{node_id}] Node is listening on port {port_id}\n")

    while not shut_signal.is_set():

        if not global_state['active']:
            continue

        try:
            conn, addr = server_socket.accept()
            print(f"[{node_id}] Connection from {addr} established.\n")
            data = conn.recv(4096)

            if data:
                message = data.decode('utf-8')
                message = json.loads(message)
                sender = message['sender']
                updates = message['table']
        
                global_state['neighbors'][sender]['last_received'] = time.time()

                 # Check if the node has just been enable and should ignore checking
                if global_state['last_enable'] is not None and time.time() - global_state['last_enable'] < 5:
                    time_to_wait = 5 - (time.time() - global_state['last_enable'])
                    print(f"Ignoring listening for {time_to_wait} more seconds.")
                    time.sleep(time_to_wait) 
                    continue

                num_changes = update_routing_table(updates, global_state,config_file_path)
                if num_changes > 0:
                    print("update detected")
                    global_state['update'] = True

            conn.close()
        except socket.error:
            break

    print(f"[{node_id}] Node has stopped listening on port {port_id}\n")

def init_routing_table(node_id, neighbors):
    cost_table = {}
    time_table = {}

    # List of all nodes in the network
    nodes = ['A', 'B', 'C']
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

def update_routing_table(update_message, global_state,config_file_path):
    
    global_table = global_state['global_table']

    node_id = global_state['node_id']

    recv_costs, recv_times = update_message['cost'], update_message['time']

    local_costs,local_times = global_table['cost'], global_table['time']
    
    change_count = 0

    for neighbor, recv_time in recv_times.items():
       
        # Skip if no update received from this neighbor
        if recv_time is None:
            continue

        # Check if received update is newer than the local timestamp for the neighbor
        if local_times[neighbor] is None or recv_time > local_times[neighbor]:
            
            if recv_costs[neighbor][node_id]!= local_costs[node_id][neighbor] and local_times[neighbor] is not None:
                print("only print after receive modify")
                local_costs[node_id][neighbor] = recv_costs[neighbor][node_id]
                local_times[node_id] = time.time()
                apply_changes(node_id,neighbor,recv_costs[neighbor][node_id],config_file_path)
                print("differences in changes nodes")
                change_count+=1

            
            if local_costs[neighbor] != recv_costs[neighbor] and local_times[neighbor] is not None:
        
                print(f"differences in {neighbor}")
                change_count += 1 

            local_times[neighbor] = recv_time
            local_costs[neighbor] = recv_costs[neighbor]
                
    format_print_for_dict(global_table)
    
    return change_count


def send_updates(global_state):
    while not shut_signal.is_set():
        if not global_state['active']:
            time.sleep(1)
            continue
    
        table = global_state['global_table']
        neighbors = global_state['neighbors']
        
        message =  {"sender":global_state['node_id'], "table":table }
        message = json.dumps(message)
        
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


def routing_calculation_thread(global_state, calculation_signal):
    while not shut_signal.is_set():
        calculation_signal.wait()  # Wait for a signal to start calculation
        calculation_signal.clear()  # Reset signal after waking up
        
        print("Performing routing calculations...")
    
        dijkstra(global_state)
        
        format_print_for_dict(global_state['global_table'])

def dijkstra(global_state):
    # Retrieve the cost table from the global state
    cost_table = global_state['global_table']['cost']
    node_id = global_state['node_id']
    
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
    for dest in cost_table.keys():
        if dest != node_id:
            if distances[dest] == float('inf'):
                print(f"Node {node_id} to node {dest}: Unreachable")
            else:
                path = reconstruct_path(node_id, dest, predecessors)
                print(f"Node {node_id} to node {dest}: Distance = {distances[dest]}, Path = {''.join(path)}")
    

def apply_changes(node_id,other_node,new_cost,config_file_path):
    # Read the contents of the file
    with open(config_file_path, 'r') as file:
        lines = file.readlines()

    # Update the cost for the specified neighbor
    with open(config_file_path, 'w') as file:
        for line in lines:
            parts = line.split()
            if parts[0] == other_node:
                # Replace the cost with the new cost, maintaining other data unchanged
                parts[1] = str(new_cost)
                updated_line = ' '.join(parts) + '\n'
                file.write(updated_line)
            else:
                file.write(line)

def update_link_cost(node_id, other_node, new_cost, global_state,config_file_path):
    cost_table = global_state['global_table']['cost']
    time_table = global_state['global_table']['time']
    
    cost_table[node_id][other_node] = new_cost
    time_table[node_id] = time.time()
    apply_changes(node_id,other_node,new_cost,config_file_path)


def monitor_convergence(global_state, calculation_signal):
    while not shut_signal.is_set():
        update = global_state['update']

        if update:
            print("Convergence waiting!")
            print(f"Update: Node {global_state['node_id']} is gathering information. Waiting for 20 seconds before executing the routing algorithm.")
            time.sleep(20)
            calculation_signal.set()  # Signal that convergence time has been reached
        
            global_state['update'] = False

        time.sleep(1)  # Check periodically, adjust as needed


def command_line_interface(global_state, config_file_path, server_socket):
    while not shut_signal.is_set():
        node_id = global_state['node_id']
        cmd = input()
        if cmd == "config":
            neighbors = load_config(config_file_path)
            for neighbor, info in neighbors.items():
                print(f"{neighbor} {info['distance']} {info['port_id']}")

        elif cmd == "routing table":
            print("from terminal")
            dijkstra(global_state)

        elif re.match(r"^change [A-J] [A-J] \d+(\.\d+)?$", cmd):
            print("change detected!")
            _, src, des, cost_str = cmd.split(" ")
            new_cost = float(cost_str)
            cost_table = global_state['global_table']['cost']
            
            # Check if either source or destination matches the current node ID
            if src != node_id and des != node_id:
                print(f"Node {node_id} cannot change the link {src}-{des} as it is not associated with either node.")
                return

            # Determine if the link exists and is not infinite
            other_node = src if src != node_id else des
            if cost_table[node_id][other_node] != float('inf'):
                print(f"Updating cost for link {src}-{des} from {cost_table[node_id][other_node]} to {new_cost}.")
                update_link_cost(node_id, other_node, new_cost, global_state,config_file_path)
            else:
                print(f"Link {src}-{des} does not exist.")
            
        elif cmd == "disable":
            global_state['active'] = False
            print(f"[{node_id}] is disabled")

        elif cmd == "enable":
            current_time = time.time()
            global_state['global_table']['time'][node_id] = current_time
            global_state['last_enable'] = current_time
            neighbors = global_state['neighbors']
            for neighbor_id, info in neighbors.items():
                global_state['neighbors'][neighbor_id]['last_received'] = current_time

            global_state['active'] = True
            print(f"[{node_id}] is enabled")

        
        else:
            print("Can't recognise your command, check Readme.txt, and make sure you type your command right.\n")


def check_neighbors_alive(global_state):
    while not shut_signal.is_set():

        if not global_state['active']:
            time.sleep(1)
            continue

        current_time = time.time()
        node_id = global_state['node_id']
        neighbors = global_state['neighbors']
        timeout_neighbors = [neighbour_id for neighbour_id, info in neighbors.items() if current_time - info['last_received'] > 15]
        print(f"timeout_neighbours: {timeout_neighbors}")
        for neighbor_id in timeout_neighbors:
            if neighbors[neighbor_id]['active']:
                neighbors[neighbor_id]['active'] = False
                print(f"Haven't received message from neighbor {neighbor_id}, consider it down.\n")
                global_state['global_table']['cost'][node_id][neighbor_id] = float('inf')

                for node in global_state['global_table']['cost'][neighbor_id].keys():
                    global_state['global_table']['cost'][neighbor_id][node] = float('inf')
                   
                global_state['global_table']['time'][node_id] = current_time
                global_state['global_table']['time'][neighbor_id] = current_time
        
        time.sleep(5)


def start_server(node_id, port_id, config_file_path):
    global_state = {}
    neighbors = load_config(config_file_path)
    global_table = init_routing_table(node_id, neighbors)
    global_state['node_id'] = node_id
    global_state['global_table'] = global_table
    global_state['neighbors'] = neighbors
    global_state['active'] = True
    global_state['last_enable'] = None
    global_state['update'] = False
    

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', port_id))
    server_socket.listen()

    listening_thread = threading.Thread(target=listening_to_neighbors, args=(port_id, server_socket, global_state, config_file_path,calculation_signal))
    sending_thread = threading.Thread(target= send_updates, args=(global_state,))
    routing_calc_thread = threading.Thread(target=routing_calculation_thread, args=(global_state, calculation_signal))
    cli_thread = threading.Thread(target=command_line_interface, args=(global_state, config_file_path, server_socket))
    convergence_thread = threading.Thread(target=monitor_convergence, args=(global_state,calculation_signal))
    check_thread = threading.Thread(target=check_neighbors_alive, args=(global_state,))

    listening_thread.start()
    sending_thread.start()
    routing_calc_thread.start()
    cli_thread.start()
    convergence_thread.start()

    # Wait for 60 seconds to gather sufficient information
    print(f"Initialise: Node {node_id} is gathering information. Waiting for 20 seconds before executing the routing algorithm.")
    time.sleep(60)
    print("executing routing algorithm")
    calculation_signal.set()  # Signal to calculate shortest path
    
    check_thread.start()
    cli_thread.join()


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("Usage: python3 COMP3221_A1_Routing.py <Node ID> <Port ID> <Config File Path>")
        sys.exit(1)

    node_id = sys.argv[1]
    port_id = int(sys.argv[2])
    config_file_path = sys.argv[3]

    start_server(node_id, port_id, config_file_path)
