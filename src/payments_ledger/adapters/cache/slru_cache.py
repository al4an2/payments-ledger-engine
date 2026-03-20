from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Literal
from payments_ledger.services.ports import BalanceCachedData, BalanceCacheWriteData
from payments_ledger.adapters.cache.shared_layer import build_balance_cache_key, to_cached_data

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
            return

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
        self._lock = asyncio.Lock()

        if self._protected_capacity < 1:
            raise ValueError("Minimal protected_capacity size = 1")
        if self._probation_capacity < 1:
            raise ValueError("Minimal probation_capacity size = 1")

    def _remove_node(self, node: _Node) -> None:
        goal_node = self._nodes.get(node.key)

        if goal_node is not node:
            raise RuntimeError("node is out of sync with cache segments")

        if node.segment == "probation":
            self._probation_cache.remove(node)
        else:
            self._protected_cache.remove(node)

        del self._nodes[node.key]

    def _touch(self, node: _Node) -> None:
        if node.segment == "probation":
            self._promote_to_protected(node)
        else:
            self._protected_cache.move_to_front(node)

    def _evict_probation_tail_if_needed(self) -> None:
        if len(self._probation_cache) > self._probation_capacity:
            tail_node = self._probation_cache.pop_tail()

            if tail_node is None:
                raise RuntimeError("probation overflow without eviction candidate")

            if tail_node.key not in self._nodes:
                raise RuntimeError("evicted probation node is missing from index")

            del self._nodes[tail_node.key]

    def _demote_to_probation_if_needed(self) -> None:
        if len(self._protected_cache) > self._protected_capacity:
            tail_node = self._protected_cache.pop_tail()

            if tail_node is None:
                raise RuntimeError("protected overflow had no tail")

            tail_node.segment = "probation"
            self._probation_cache.append_front(tail_node)
            self._evict_probation_tail_if_needed()

    def _promote_to_protected(self, node: _Node) -> None:
        self._probation_cache.remove(node)

        node.segment = "protected"
        self._protected_cache.append_front(node)
        self._demote_to_probation_if_needed()

    async def get_if_fresh(
        self, account_id: str, currency: str, expected_version: int
    ) -> BalanceCachedData | None:
        async with self._lock:
            key = build_balance_cache_key(account_id=account_id, currency=currency)

            cached = self._nodes.get(key)

            if cached is None:
                return None

            cached_version = cached.value.ledger_version

            if expected_version > cached_version:
                self._remove_node(cached)
                return None

            if expected_version < cached_version:
                return None

            self._touch(node=cached)
            return cached.value

    async def put(self, item: BalanceCacheWriteData) -> None:
        async with self._lock:
            new_key = build_balance_cache_key(account_id=item.account_id, currency=item.currency)
            cached = self._nodes.get(new_key)

            if cached and item.ledger_version < cached.value.ledger_version:
                return

            data = to_cached_data(item)
            if cached is None:
                new_node = _Node(key=new_key, value=data, segment="probation")
                self._probation_cache.append_front(new_node)
                self._nodes[new_key] = new_node
                self._evict_probation_tail_if_needed()

            else:
                cached.value = data
                self._touch(cached)

    async def invalidate(self, account_id: str, currency: str) -> None:
        async with self._lock:
            key = build_balance_cache_key(account_id=account_id, currency=currency)
            cached = self._nodes.get(key)
            if cached:
                self._remove_node(cached)
