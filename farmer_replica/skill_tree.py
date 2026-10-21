"""
Skill tree sederhana pakai pygame.
Install: pip install pygame
Kontrol: drag mouse kiri = geser kamera, klik node = beli/level up.
"""
import pygame

NODE_W, NODE_H = 96, 90
GAP_X, GAP_Y = 54, 50

BG = (120, 143, 158)
NODE_BG = (34, 34, 34)
GOLD = (240, 200, 110)
LOCKED = (110, 100, 80)
MAXED = (255, 225, 140)


# ---------- DATA ----------
class Node:
    def __init__(self, name, max_level=1, cost=10, children=None):
        self.name = name
        self.max_level = max_level
        self.cost = cost
        self.level = 0
        self.children = children or []
        self.parent = None
        self.x = self.y = 0
        for c in self.children:
            c.parent = self

    @property
    def available(self):
        # node kebuka kalau parent sudah level max
        return self.parent is None or self.parent.level >= self.parent.max_level

    @property
    def maxed(self):
        return self.level >= self.max_level

    def rect(self, ox, oy):
        return pygame.Rect(self.x + ox, self.y + oy, NODE_W, NODE_H)


# ---------- LAYOUT ----------
def layout(node, depth=0, cursor=None):
    """Daun dapat slot x berurutan, parent ditaruh di tengah anak-anaknya."""
    if cursor is None:
        cursor = [0]
    node.y = depth * (NODE_H + GAP_Y)
    if not node.children:
        node.x = cursor[0]
        cursor[0] += NODE_W + GAP_X
    else:
        for c in node.children:
            layout(c, depth + 1, cursor)
        node.x = (node.children[0].x + node.children[-1].x) / 2


def walk(node):
    yield node
    for c in node.children:
        yield from walk(c)


# ---------- DRAW ----------
def draw_edges(surf, node, ox, oy):
    if not node.children:
        return
    px = node.x + NODE_W / 2 + ox
    py = node.y + NODE_H + oy
    mid = py + GAP_Y / 2
    xs = [c.x + NODE_W / 2 + ox for c in node.children]
    pygame.draw.line(surf, GOLD, (px, py), (px, mid), 3)             # turun dari parent
    pygame.draw.line(surf, GOLD, (min(xs + [px]), mid), (max(xs + [px]), mid), 3)  # garis horizontal
    for c, cx in zip(node.children, xs):
        pygame.draw.line(surf, GOLD, (cx, mid), (cx, c.y + oy), 3)   # turun ke anak
        draw_edges(surf, c, ox, oy)


def draw_node(surf, font, n, ox, oy):
    r = n.rect(ox, oy)
    border = MAXED if n.maxed else (GOLD if n.available else LOCKED)
    pygame.draw.rect(surf, border, r.inflate(8, 8), border_radius=3)
    pygame.draw.rect(surf, NODE_BG, r)
    label = font.render(n.name, True, border)
    surf.blit(label, label.get_rect(center=(r.centerx, r.centery - 8)))
    if n.max_level > 1:
        lv = font.render(f"{n.level} / {n.max_level}", True, (230, 230, 230))
        surf.blit(lv, lv.get_rect(center=(r.centerx, r.bottom - 12)))


# ---------- MAIN ----------
def build_tree():
    return Node("while", 1, 0, [
        Node("loop", 5, 10, [
            Node("wheat", 9, 20),
            Node("bush", 1, 50, [
                Node("carrot", 10, 30),
                Node("print()", 1, 40, [Node("set_speed()"), Node("get_time()", children=[Node("simulate()")])]),
                Node("1 + 1", 1, 40, [Node("(x,y)"), Node("a = 2")]),
            ]),
        ]),
        Node("hay", 10, 15),
    ])


def main():
    pygame.init()
    screen = pygame.display.set_mode((1280, 800))
    pygame.display.set_caption("Skill Tree")
    font = pygame.font.SysFont("consolas", 13, bold=True)
    hud = pygame.font.SysFont("consolas", 20, bold=True)
    clock = pygame.time.Clock()

    root = build_tree()
    layout(root)
    nodes = list(walk(root))
    gold = 500
    ox, oy = 100, 40
    dragging, moved = False, 0

    running = True
    while running:
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                dragging, moved = True, 0
            elif e.type == pygame.MOUSEMOTION and dragging:
                ox += e.rel[0]
                oy += e.rel[1]
                moved += abs(e.rel[0]) + abs(e.rel[1])
            elif e.type == pygame.MOUSEBUTTONUP and e.button == 1:
                dragging = False
                if moved < 5:  # klik, bukan drag
                    for n in nodes:
                        if n.rect(ox, oy).collidepoint(e.pos):
                            if n.available and not n.maxed and gold >= n.cost:
                                gold -= n.cost
                                n.level += 1
                            break

        screen.fill(BG)
        draw_edges(screen, root, ox, oy)
        for n in nodes:
            draw_node(screen, font, n, ox, oy)
        screen.blit(hud.render(f"Gold: {gold}", True, (255, 255, 255)), (16, 12))
        pygame.display.flip()
        clock.tick(60)

    pygame.quit()


if __name__ == "__main__":
    main()
