from __future__ import annotations
from payments_ledger.services.ports import BalanceCachedData, BalanceCacheWriteData
from dataclasses import dataclass
from typing import Literal
# from payments_ledger.adapters.cache.shared_layer import build_balance_cache_key


@dataclass(eq=False, slots=True)
class _Node:
    key: str
    value: BalanceCachedData
    segment: Literal["probation", "protected"]
    prev: _Node | None = None
    next: _Node | None = None


class _RecencyList:
    def __init__(self) -> None:
        self._head: _Node | None = None
        self._tail: _Node | None = None
        self._size = 0

    def __len__(self) -> int:
        return self._size

    def append_front(self, node: _Node) -> None:
        old_head = self._head
        node.prev = None

        if old_head is None:
            if self._tail is not None:
                raise RuntimeError("invalid list state: tail exists while head is None")

            node.next = None
            self._head = node
            self._tail = node
            self._size = 1
            return

        node.next = old_head
        old_head.prev = node
        self._head = node
        self._size += 1

    def remove(self, node: _Node) -> None:
        if self._head is None or self._tail is None:
            raise ValueError("cannot remove from an empty list")

        if self._head is node and self._tail is node:
            self._head = None
            self._tail = None

        elif self._head is node:
            new_head = node.next
            if new_head is None:
                raise RuntimeError("head.next must exist when removing head from multi-node list")
            new_head.prev = None
            self._head = new_head

        elif self._tail is node:
            new_tail = node.prev
            if new_tail is None:
                raise RuntimeError("tail.prev must exist when removing tail from multi-node list")
            new_tail.next = None
            self._tail = new_tail

        else:
            prev_node = node.prev
            next_node = node.next
            if prev_node is None or next_node is None:
                raise RuntimeError("middle node must have both prev and next")
            prev_node.next = next_node
            next_node.prev = prev_node

        node.prev = None
        node.next = None
        self._size -= 1

    def move_to_front(self, node: _Node) -> None:
        if node is self._head:
            return None

        self.remove(node)
        self.append_front(node)

    def pop_tail(self) -> _Node | None:
        if self._tail is None:
            return None

        node = self._tail

        if self._head is self._tail:
            self._head = None
            self._tail = None
        else:
            new_tail = node.prev

            if new_tail is None:
                raise RuntimeError("tail.prev must exist for a multi-node list")

            new_tail.next = None
            self._tail = new_tail

        node.prev = None
        node.next = None
        self._size -= 1
        return node


class SLRUBalanceCacheL1:
    def __init__(self, capacity: int, protected_ratio: float = 0.8) -> None:
        if capacity < 2:
            raise ValueError("Minimal capacity size = 2")
        if not 0 < protected_ratio < 1:
            raise ValueError("Protected ratio must be between 0 and 1")

        self._capacity = capacity
        self._protected_capacity = int(capacity * protected_ratio)
        self._probation_capacity = capacity - self._protected_capacity
        self._nodes: dict[str, _Node] = {}
        self._protected_cache = _RecencyList()
        self._probation_cache = _RecencyList()

    async def get_if_fresh(
        self, account_id: str, currency: str, expected_version: int
    ) -> BalanceCachedData | None:
        pass

    async def put(self, item: BalanceCacheWriteData) -> None:
        pass

    async def invalidate(self, account_id: str, currency: str) -> None:
        pass
