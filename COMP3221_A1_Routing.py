import socket
import threading
import sys
import time
import re
from threading import Timer

shut_signal = threading.Event()

def load_config(config_file_path):
    neighbors = {}
    current_time = time.time()
    with open(config_file_path, 'r') as file:
        num_neighbors = int(file.readline().strip())
        for _ in range(num_neighbors):
            line = file.readline().strip().split()
            node_id, distance, port_id = line[0], float(line[1]), int(line[2])
            neighbors[node_id] = {'distance': distance, 'port_id': port_id, 'last_received': current_time}
    return neighbors

def routing(node_id, message, global_state):
    lines = message.split('\n')
    fr = lines[0].strip()
    routing_table = global_state['routing_table']
    global_state['neighbors'][fr]['last_received'] = time.time()
    if_changed = False
    for line in lines[1:]:
        des, dis, path = line.split(' ')
        dis = float(dis)
        if des != node_id and node_id not in path:
            if des in routing_table.keys():
                if fr not in routing_table[des]['path']:
                    if dis + routing_table[fr]['distance'] < routing_table[des]['distance']:
                        routing_table[des]['distance'] = dis + routing_table[fr]['distance']
                        routing_table[des]['path'] = routing_table[fr]['path'] + path[1:]
                        if_changed = True
                elif fr in routing_table[des]['path']:
                    if routing_table[des]['distance'] != dis+routing_table[fr]['distance']:
                        routing_table[des]['distance'] = dis + routing_table[fr]['distance']
                        routing_table[des]['path'] = routing_table[fr]['path'] + path[1:]
                        if_changed = True
            else:
                routing_table[des] = {'distance':dis + routing_table[fr]['distance'],'path':routing_table[fr]['path'] + path[1:]}
                if_changed = True
    global_state['routing_table'] = routing_table
    
    #print(global_state['routing_print_allowed'])
    if if_changed and global_state['routing_print_allowed']:
        print("---- Routing Algorithm Completed ----")
        print(f"I am Node {node_id}")
        for des in routing_table.keys():
            dis = routing_table[des]['distance']
            path = routing_table[des]['path']
            print(f"Least cost path from {node_id} to {des}: {path}, link cost: {dis}")
        print("-------------------------------------")

def listening_to_neighbors(node_id, port_id, server_socket, global_state, config_file_path):
    print(f"[{node_id}] Node is listening on port {port_id}\n")

    while not shut_signal.is_set():
        try:
            conn, addr = server_socket.accept()
            print(f"[{node_id}] Connection from {addr} established.\n")
            data = conn.recv(4096)
            if data:
                message = data.decode('utf-8')
                #print(f"[{node_id}] received message:\n{message}")
                if message.startswith('change'):
                    temp_split = message.split(' ')
                    des = temp_split[1]
                    new_cost = temp_split[2]
                    change_link_cost(des,  new_cost, global_state, config_file_path)
                else:
                    routing(node_id, message, global_state)
            conn.close()
        except socket.error:
            break

    print(f"[{node_id}] Node has stopped listening on port {port_id}\n")

def command_line_interface(node_id, global_state, config_file_path, server_socket):
    while not shut_signal.is_set():
        cmd = input()
        if cmd == "config":
            neighbors = global_state["neighbors"]
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
        elif cmd == "routing table":
            routing_table = global_state['routing_table']
            for node_id, info in routing_table.items():
                print(f"{node_id} {info['distance']} {info['path']}")
        elif re.match(r"^change [a-zA-Z] \d+(\.\d+)?$", cmd):
            temp_split = cmd.split(" ")
            target_id = temp_split[1]
            new_dis = temp_split[2]
            routing_table = global_state['routing_table']
            neighbors = global_state['neighbors']
            if target_id in neighbors.keys():
                target_port = neighbors[target_id]['port_id']
                message = f"change {node_id} {new_dis}"
                try:
                    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                        s.connect(('localhost', target_port))
                        s.sendall(message.encode('utf-8'))
                except socket.error as e:
                    print(f"Error sending message to neighbor {target_id}: {e}")
                    print(f"Please make sure {target_id} is active, so it can update its own config file")
                    print(f"The link cost change unsucceed because {target_id} is not active\n")
                    continue
                change_link_cost(target_id, float(new_dis), global_state, config_file_path)
            else:
                print(f"{target_id} is not {node_id}'s neighbor\n")
        elif cmd == "disable":

            print(f"[{node_id}] is disabled")
        elif cmd == "enable":

            print(f"[{node_id}] is enabled again")
        else:
            print("Can't recognise your command, check Readme.txt, and make sure you type your command right.\n")

def change_link_cost(des, cost, global_state, config_file_path):
    # change the cost to the des, delete all related routes in routing table
    update_cost_in_file(config_file_path, des, cost)
    global_state["neighbors"][des]["distance"] = cost
    
    nodes_to_delete = []
    for node in global_state["routing_table"].keys():
        if node == des:
            global_state["routing_table"][node]['distance'] = cost
        else:
            if des in global_state["routing_table"][node]['path']:
                nodes_to_delete.append(node)
    
    for node in nodes_to_delete:
        del global_state["routing_table"][node]

def update_cost_in_file(file_path, target, new_cost):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    updated_lines = []
    for line in lines:
        parts = line.split()
        if parts[0] == target:
            parts[1] = str(new_cost)
            updated_line = ' '.join(parts)
            updated_lines.append(updated_line + '\n')
        else:
            updated_lines.append(line)
    
    with open(file_path, 'w') as file:
        file.writelines(updated_lines)

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

def sending_routing_table(node_id, global_state):
    while not shut_signal.is_set():
        routing_table = global_state['routing_table']
        neighbors = global_state['neighbors']
        routing_table_str = format_routing_table_for_sending(routing_table)
        message = f"{node_id}\n{routing_table_str}"

        for neighbor_id, info in neighbors.items():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.connect(('localhost', info['port_id']))
                    s.sendall(message.encode('utf-8'))
            except socket.error as e:
                #print(f"Error sending routing table to neighbor {neighbor_id}: {e}")
                pass
        time.sleep(10)

def allow_routing_print(global_state):
    global_state['routing_print_allowed'] = True
    #print(f"global_state's routing_print_allowed = True now: {global_state['routing_print_allowed']}")

def check_neighbors_alive(global_state):
    while not shut_signal.is_set():
        current_time = time.time()
        timeout_neighbors = [node_id for node_id, info in global_state['neighbors'].items() if current_time - info['last_received'] > 15]
        for node_id in timeout_neighbors:
            print(f"Haven't received message from neighbor {node_id}, consider it down.\n")
            for dest, route in global_state['routing_table'].items():
                if node_id in route['path']:
                    global_state['routing_table'][dest]['distance'] = float('inf')
        time.sleep(5)

def start_server(node_id, port_id, config_file_path):
    global_state = {}
    neighbors = load_config(config_file_path)
    routing_table = init_routing_table(node_id, neighbors)
    global_state['routing_table'] = routing_table
    global_state['neighbors'] = neighbors
    global_state['routing_print_allowed'] = False

    Timer(2, allow_routing_print, args=(global_state,)).start()

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('localhost', port_id))
    server_socket.listen()

    listening_thread = threading.Thread(target=listening_to_neighbors, args=(node_id, port_id, server_socket, global_state, config_file_path))
    cli_thread = threading.Thread(target=command_line_interface, args=(node_id, global_state, config_file_path, server_socket))
    sending_thread = threading.Thread(target=sending_routing_table, args=(node_id, global_state))
    check_thread = threading.Thread(target=check_neighbors_alive, args=(global_state,))

    listening_thread.start()
    cli_thread.start()
    sending_thread.start()
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
