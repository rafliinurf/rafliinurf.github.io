"""Compact top-down layout for a tree/forest with secondary cross-links."""

RESEARCH_ROWS = (
    ("Loops",),
    ("Speed", "Grass"),
    ("Expand", "Plant"),
    ("Carrots", "Debug", "Operators", "Expand_2"),
    ("Watering", "Trees", "Debug_2", "Timing", "Senses", "Variables"),
    ("Fertilizer", "Sunflowers", "Pumpkins", "Simulation", "Lists", "Functions"),
    ("Cactus", "Dinosaurs", "Mazes", "Leaderboard", "Dictionaries", "Import", "Utilities", "Megafarm"),
    ("Polyculture", "Costs", "The_Farmers_Remains"),
    ("Auto_Unlock", "Hats"),
    ("Top_Hat",),
)


def layout_tree(
    nodes,
    node_width=190,
    node_height=72,
    gap_x=54,
    gap_y=50,
    ordered_rows=None,
):
    if ordered_rows is not None:
        listed_nodes = [name for row in ordered_rows for name in row]
        if len(listed_nodes) != len(set(listed_nodes)):
            raise ValueError("ordered layout contains duplicate nodes")
        if set(listed_nodes) != set(nodes):
            raise ValueError("ordered layout must include every node exactly once")

        max_row_width = max(map(len, ordered_rows), default=0)
        positions = {}
        for depth, row in enumerate(ordered_rows):
            start_x = (max_row_width - len(row)) * (node_width + gap_x) / 2
            for slot, name in enumerate(row):
                positions[name] = (
                    start_x + slot * (node_width + gap_x),
                    depth * (node_height + gap_y),
                )
        return positions

    names = list(nodes)
    order = {name: index for index, name in enumerate(names)}
    children = {name: [] for name in names}
    primary_parent = {}

    for name, data in nodes.items():
        parents = [parent for parent in data.get("visual_parents", ()) if parent in nodes]
        if parents:
            primary_parent[name] = parents[0]
            children[parents[0]].append(name)

    for child_names in children.values():
        child_names.sort(
            key=lambda name: (nodes[name].get("visual_order", order[name]), order[name])
        )

    roots = [name for name in names if name not in primary_parent]
    levels = []
    current_level = roots
    visited = set()
    while current_level:
        levels.append(current_level)
        visited.update(current_level)
        current_level = [
            child
            for parent in current_level
            for child in children[parent]
        ]

    if len(visited) != len(names):
        cycle_node = next(name for name in names if name not in visited)
        raise ValueError(f"visual parent cycle includes {cycle_node}")

    max_level_width = max(map(len, levels), default=0)
    positions = {}
    for depth, level in enumerate(levels):
        start_x = (max_level_width - len(level)) * (node_width + gap_x) / 2
        for slot, name in enumerate(level):
            positions[name] = (
                start_x + slot * (node_width + gap_x),
                depth * (node_height + gap_y),
            )

    return positions
