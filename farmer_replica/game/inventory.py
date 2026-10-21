"""Item dan hasil panen."""


class Inventory:
    def __init__(self, items=None):
        self._items = dict(items or {})

    def count(self, item):
        return self._items.get(item, 0)

    def add(self, item, n=1):
        self._items[item] = self.count(item) + n

    def can_afford(self, cost):
        return all(self.count(i) >= n for i, n in cost.items())

    def pay(self, cost):
        if not self.can_afford(cost):
            return False
        for item, n in cost.items():
            self._items[item] -= n
        return True

    def as_dict(self):
        return dict(self._items)

    def replace(self, items):
        self._items = dict(items)
