"""Bounded, per-process TTL/LRU result cache with same-key request coalescing."""
from collections import OrderedDict
from concurrent.futures import Future
from copy import deepcopy
import math
from threading import Lock
from time import monotonic


class ResultCache:
    def __init__(self, max_entries=256, ttl_seconds=300, clock=monotonic):
        self.max_entries = int(max_entries)
        self.ttl_seconds = float(ttl_seconds)
        if self.max_entries < 0 or not math.isfinite(self.ttl_seconds) or self.ttl_seconds < 0:
            raise ValueError('Cache size and TTL must be finite, nonnegative values')
        self.clock = clock
        self._lock = Lock()
        self._entries = OrderedDict()
        self._pending = {}
        self._generation = 0

    def clear(self):
        # Active requests may finish, but cannot repopulate a cleared cache.
        with self._lock:
            self._generation += 1
            self._entries.clear()
            self._pending.clear()

    def get_or_compute(self, key, compute):
        if self.max_entries == 0 or self.ttl_seconds == 0:
            return compute(), 'BYPASS'
        with self._lock:
            now = self.clock()
            expired = [k for k, (deadline, _) in self._entries.items() if deadline <= now]
            for old in expired:
                del self._entries[old]
            if key in self._entries:
                self._entries.move_to_end(key)
                return deepcopy(self._entries[key][1]), 'HIT'
            future = self._pending.get(key)
            owner = future is None
            if owner:
                future = Future()
                self._pending[key] = future
            generation = self._generation
        if not owner:
            return deepcopy(future.result()), 'COALESCED'
        try:
            value = compute()
            stored = deepcopy(value)
            with self._lock:
                if generation == self._generation:
                    self._entries[key] = (self.clock() + self.ttl_seconds, stored)
                    while len(self._entries) > self.max_entries:
                        self._entries.popitem(last=False)
            future.set_result(stored)
            return value, 'MISS'
        except BaseException as exc:
            # A failed request must release all waiters and never be cached.
            future.set_exception(exc)
            raise
        finally:
            with self._lock:
                if self._pending.get(key) is future:
                    del self._pending[key]
