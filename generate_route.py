import random

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np

# Configuration constants
SEED = 42
NUM_MAIN = 3
NUM_MOBILE = 15
MAX_NEIGHBORS = 4
ROAD_SPEED = 1.0
AIR_SPEED = 3.0
ROAD_COST_UNIT = 1.0
AIR_COST_UNIT = 3.0
MAIN_COORDS = np.array([[0, 0], [10, 0], [5, 8]])


def build_supply_graph(selected_mobile_idx=11, priority=1):
    """
    Builds and returns:
      - G: the MultiDiGraph with road/air edges
      - pos: node→(x,y) dict for plotting
      - paths: dict main_index→list of node indices (composite-optimal)
      - metrics: dict main_index→(t_road, c_road, t_air, c_air)
      - edge_mode: dict main_index→list of (u, v, mode_sel)
      - best_bal: index of the main with lowest composite sum
    """
    if not (0 <= selected_mobile_idx < NUM_MOBILE):
        raise ValueError(f"selected_mobile_idx must be between 0 and {NUM_MOBILE-1}, got {selected_mobile_idx}")
    
    random.seed(SEED)
    np.random.seed(SEED)

    total_nodes = NUM_MAIN + NUM_MOBILE
    mobile_coords = np.random.rand(NUM_MOBILE, 2) * 20
    coords = np.vstack([MAIN_COORDS, mobile_coords])

    dest_index = NUM_MAIN + selected_mobile_idx
    main_indices = list(range(NUM_MAIN))
    mobile_indices = list(range(NUM_MAIN, total_nodes))

    neighbor_sets = {i: set() for i in range(total_nodes)}
    def can_add(i, j):
        if i == j: return False
        if (i in main_indices and j in main_indices) or \
           (i in main_indices and j == dest_index) or \
           (j in main_indices and i == dest_index):
            return False
        if len(neighbor_sets[i]) >= MAX_NEIGHBORS or len(neighbor_sets[j]) >= MAX_NEIGHBORS:
            return False
        return True

    def add_edge(i, j, G):
        if not can_add(i, j): return
        neighbor_sets[i].add(j); neighbor_sets[j].add(i)
        dist = np.linalg.norm(coords[i] - coords[j])
        t_r = dist/ROAD_SPEED * random.uniform(1.0,1.5)
        c_r = dist*ROAD_COST_UNIT * random.uniform(0.5,1.0)
        t_a = dist/AIR_SPEED * random.uniform(0.5,1.0)
        c_a = dist*AIR_COST_UNIT * random.uniform(1.0,1.5)
        for mode, t, c in [("road",t_r,c_r),("air",t_a,c_a)]:
            G.add_edge(i, j, mode=mode, time=t, cost=c, comp=t+c)
            G.add_edge(j, i, mode=mode, time=t, cost=c, comp=t+c)

    G = nx.MultiDiGraph()
    for idx in range(total_nodes):
        G.add_node(idx, pos=tuple(coords[idx]))

    # build network
    for m in main_indices:
        add_edge(m, random.choice(mobile_indices), G)
    order = mobile_indices.copy(); random.shuffle(order)
    for u, v in zip(order[:-1], order[1:]):
        add_edge(u, v, G)
    for i in range(total_nodes):
        possible = [j for j in range(total_nodes) if can_add(i, j)]
        extras = random.randint(0, MAX_NEIGHBORS - len(neighbor_sets[i]))
        for j in random.sample(possible, min(extras, len(possible))):
            add_edge(i, j, G)

    paths, comp_sums, metrics, edge_mode = {}, {}, {}, {}
    for m in main_indices:
        H = G.copy()
        for om in main_indices:
            if om != m: H.remove_node(om)
        try:
            path = nx.dijkstra_path(H, source=m, target=dest_index, weight='comp')
        except nx.NetworkXNoPath:
            path = []
        paths[m] = path
        
        if path:
            comp_sums[m] = sum(min(e['comp'] for e in G[u][v].values()) for u,v in zip(path, path[1:]))
            t_r = c_r = t_a = c_a = 0.0
            modes = []
            for u,v in zip(path, path[1:]):
                er = min((e for e in G[u][v].values() if e['mode']=='road'), key=lambda e: e['cost'])
                ea = min((e for e in G[u][v].values() if e['mode']=='air'), key=lambda e: e['time'])
                t_r += er['time']; c_r += er['cost']
                t_a += ea['time']; c_a += ea['cost']
                sel = 'A' if priority == 1 else 'R'
                modes.append((u, v, sel))
            metrics[m] = (t_r, c_r, t_a, c_a)
            edge_mode[m] = modes
        else:
            comp_sums[m] = float('inf')
            metrics[m] = (0.0, 0.0, 0.0, 0.0)
            edge_mode[m] = []
    
    if all(comp == float('inf') for comp in comp_sums.values()):
        best_bal = main_indices[0]
    else:
        best_bal = min(comp_sums, key=lambda m: comp_sums[m])
    pos = {i: tuple(coords[i]) for i in range(total_nodes)}
    return G, pos, paths, metrics, edge_mode, best_bal


def draw_supply_graph(selected_mobile_idx=11, priority=1):
    """
    Builds the supply graph, draws it, and returns the Matplotlib Figure object.
    """
    if not (0 <= selected_mobile_idx < NUM_MOBILE):
        raise ValueError(f"selected_mobile_idx must be between 0 and {NUM_MOBILE-1}, got {selected_mobile_idx}")
    
    G, pos, paths, metrics, edge_mode, best_bal = build_supply_graph(selected_mobile_idx, priority)
    fig, ax = plt.subplots(figsize=(12,10))

    # Draw all edges
    for u, v in G.edges():
        x0,y0 = pos[u]; x1,y1 = pos[v]
        ax.plot([x0,x1],[y0,y1], color='lightgrey', linewidth=1, alpha=0.4)
    # Draw nodes
    total_nodes = G.number_of_nodes()
    mobile_indices = list(range(NUM_MAIN, total_nodes))
    main_indices = list(range(NUM_MAIN))
    dest = NUM_MAIN + selected_mobile_idx
    nx.draw_networkx_nodes(G, pos, nodelist=mobile_indices, node_size=200, node_color='lightgrey')
    nx.draw_networkx_nodes(G, pos, nodelist=main_indices, node_size=500, node_color='white', edgecolors='black')
    nx.draw_networkx_nodes(G, pos, nodelist=[dest], node_size=600, node_color='yellow')
    # Labels
    node_names = [f"Main{i+1}" for i in range(NUM_MAIN)] + [f"M{i+1}" for i in range(total_nodes-NUM_MAIN)]
    labels = {i: node_names[i] for i in range(total_nodes)}
    nx.draw_networkx_labels(G, pos, labels=labels, font_size=8)
    # Path drawing
    colors = ['red','green','blue']
    for idx, m in enumerate(main_indices):
        path = paths[m]; col = colors[idx]
        for u,v in zip(path, path[1:]):
            x0,y0 = pos[u]; x1,y1 = pos[v]
            ax.plot([x0,x1],[y0,y1], color=col, linewidth=3)
    # Highlight best path
    best_path = paths[best_bal]
    for u,v in zip(best_path, best_path[1:]):
        x0,y0 = pos[u]; x1,y1 = pos[v]
        ax.plot([x0,x1],[y0,y1], color='black', linewidth=4, linestyle='--')
    # Edge mode labels on best path
    for u,v,sel in edge_mode[best_bal]:
        x0,y0 = pos[u]; x1,y1 = pos[v]
        xm,ym = (x0+x1)/2, (y0+y1)/2
        ax.text(xm, ym, sel, color='black', fontsize=14, fontweight='bold', ha='center', va='center')
    # Metrics annotation
    for idx, m in enumerate(main_indices):
        t_r,c_r,t_a,c_a = metrics[m]
        ax.text(0.02, 0.95-idx*0.04,
                f"Main{m+1} - Road: T={t_r:.1f}, C={c_r:.1f} | Air: T={t_a:.1f}, C={c_a:.1f}",
                transform=ax.transAxes, color=colors[idx], fontsize=12, fontweight='bold', va='top')
    ax.set_title(f"Supply Graph (Priority={'Air' if priority==1 else 'Road'})", fontsize=16)
    ax.axis('off')
    fig.tight_layout()
    return fig
