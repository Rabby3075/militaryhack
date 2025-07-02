from generate_route import draw_supply_graph

try:
    # Use a valid mobile index (0-14 since NUM_MOBILE=15)
    fig = draw_supply_graph(selected_mobile_idx=10, priority=1)
    fig.savefig('my_supply_graph.png', dpi=300)
    print("Supply graph saved successfully as 'my_supply_graph.png'")
except Exception as e:
    print(f"Error generating supply graph: {e}")
