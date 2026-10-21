"""Contoh urutan node persis kayak screenshot + tes layout.

Nama id di bawah cuma placeholder dari ikon di screenshot. Yang penting adalah
`visual_parents` dan `visual_order` (urutan kiri -> kanan antar saudara).
Jalanin:  python tree_order_example.py
"""
from tree_layout import layout_tree


def n(parent=None, order=0):
    return {"visual_parents": [parent] if parent else [], "visual_order": order}


NODES = {
    "while":     n(),
    # level 1
    "drone":     n("while", 0),      # 5/5
    "wheat":     n("while", 1),      # 10/10
    # level 2
    "hay_crate": n("drone", 0),      # 9/9
    "bush":      n("drone", 1),
    # level 3 (cabang dari bush: tanaman | print | operator)
    "carrots":   n("bush", 0),       # 10/10
    "print":     n("bush", 1),
    "ops":       n("bush", 2),       # 1 + 1
    # cabang tanaman
    "barrel":    n("carrots", 0),    # 9/9
    "tree":      n("carrots", 1),    # 10/10
    "pouch":     n("barrel", 0),     # 4/4
    "sunflower": n("barrel", 1),
    "dark_box":  n("pouch", 0),      # 6/6
    "crab":      n("dark_box", 0),   # 5/5
    "pumpkin":   n("tree", 0),       # 10/10
    "cactus":    n("pumpkin", 0),    # 6/6
    "grass_4_5": n("pumpkin", 1),    # 4/5
    "bones":     n("cactus", 0),     # 6/6
    # cabang print()
    "set_speed": n("print", 0),
    "get_time":  n("print", 1),
    "simulate":  n("get_time", 0),
    "trophy":    n("simulate", 0),
    # cabang 1 + 1
    "tuple":     n("ops", 0),        # (x,y)
    "assign":    n("ops", 1),        # a = 2
    "list":      n("assign", 0),     # [1,2,3]
    "func":      n("assign", 1),     # def f():
    "dict":      n("list", 0),       # {1:2}
    "get_cost":  n("dict", 0),
    "import":    n("func", 0),
    "random":    n("func", 1),
}

# kolom (dalam setengah slot) di screenshot, dihitung dari node paling kiri
EXPECTED = {
    "while": 7, "drone": 6, "wheat": 8, "hay_crate": 5, "bush": 7,
    "carrots": 3, "print": 7, "ops": 11,
    "barrel": 1, "tree": 4, "set_speed": 6, "get_time": 8, "tuple": 10, "assign": 12,
    "pouch": 0, "sunflower": 2, "pumpkin": 4, "simulate": 8, "list": 10, "func": 13,
    "dark_box": 0, "cactus": 3, "grass_4_5": 5, "trophy": 8, "dict": 10, "import": 12, "random": 14,
    "crab": 0, "bones": 3, "get_cost": 10,
}

if __name__ == "__main__":
    # ukuran kotak di screenshot: 96 x 90, jarak 56 / 50
    pos = layout_tree(NODES, node_width=96, node_height=90, gap_x=56, gap_y=50)
    unit = (96 + 56) / 2
    min_x = min(x for x, _ in pos.values())
    bad = 0
    for name, (x, y) in pos.items():
        col = (x - min_x) / unit
        ok = abs(col - EXPECTED[name]) < 1e-9
        bad += not ok
        print(f"{name:10s} kolom={col:5.1f} (screenshot {EXPECTED[name]:2d}) y={y:4.0f} {'OK' if ok else 'BEDA'}")
    print("SEMUA COCOK" if not bad else f"{bad} node beda")
