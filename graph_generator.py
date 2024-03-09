import random
import networkx as nx
import matplotlib.pyplot as plt
import sys

if len(sys.argv) != 2:
    print("Usage: python3 graph_generator.py <dir_path>")
dir = sys.argv[1]

# Generate a graph with 10 nodes
G = nx.Graph()
nodes = [chr(i) for i in range(65, 75)]  # ASCII codes for A to J
G.add_nodes_from(nodes)

# Add 15-20 random edges with random weights between 0 to 10
num_edges = random.randint(15, 20)
for _ in range(num_edges):
    # Select two different nodes
    u = random.choice(list(G.nodes))
    v = random.choice(list(G.nodes))
    while u == v or G.has_edge(u, v):
        u = random.choice(list(G.nodes))
        v = random.choice(list(G.nodes))
    # Generate a random weight
    weight = round(random.uniform(0, 10),1)
    # Add the edge with the weight
    G.add_edge(u, v, weight=weight)

# Draw the graph
pos = nx.spring_layout(G)  # positions for all nodes
edges = G.edges(data=True)


nx.draw(G, pos, with_labels=True, node_size=700, node_color="skyblue", alpha=0.6)
nx.draw_networkx_edge_labels(G, pos, edge_labels={(u, v): d['weight'] for u, v, d in edges})
plt.title(f"Graph with 10 Nodes and {num_edges} Edges")
plt.axis('off')
plt.savefig(f"{dir}/graph.png", format="PNG")

node_info = {}

for node in G.nodes():
    neighbors = G[node] 
    node_info[node] = {neighbor: data['weight'] for neighbor, data in neighbors.items()}

for label in nodes:
    f = open(f"{dir}/{label}config.txt", "w")
    f.write(f"{len(node_info[label])}\n")
    neighbours = node_info[label]
    for neighbour in neighbours:
        f.write(f"{neighbour} {neighbours[neighbour]} {ord(neighbour)-65+6000}\n")