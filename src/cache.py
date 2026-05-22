"""Tiny in-process TTL cache.

One worker with multiple threads (our gunicorn config) shares this dict, so
expensive predictions only run once per TTL window.  Free-tier Render has
limited CPU, and the predictor's TF-IDF + festival cross-matching is the
single biggest cost (~3-8 sec on cold caches).
"""
from __future__ import annotations

import functools
import time
from typing import Callable


def ttl_cache(ttl_seconds: int) -> Callable:
    """Memoise a pure function for `ttl_seconds` based on its arguments."""
    def decorator(fn: Callable) -> Callable:
        store: dict = {}

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            now = time.time()
            if key in store:
                ts, value = store[key]
                if now - ts < ttl_seconds:
                    return value
            value = fn(*args, **kwargs)
            store[key] = (now, value)
            # Cheap eviction: when the cache grows large, drop the half oldest.
            if len(store) > 64:
                cutoff = sorted(v[0] for v in store.values())[len(store) // 2]
                for k in [k for k, v in store.items() if v[0] < cutoff]:
                    store.pop(k, None)
            return value

        wrapper.cache_clear = store.clear            # type: ignore[attr-defined]
        wrapper.cache_info  = lambda: {              # type: ignore[attr-defined]
            "size": len(store), "ttl": ttl_seconds,
        }
        return wrapper

    return decorator
