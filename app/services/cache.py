"""
cache.py  (production rewrite)
─────────────────────────────────────────────────────────────────────────────
Multi-tier caching system.

L1  │ OrderedDict LRU  │ In-process, ~256 entries, sub-millisecond
L2  │ Redis            │ Shared across workers, configurable TTL
L3  │ Semantic (Redis) │ Embedding similarity — uses Gemini text-embedding-004
                         (replaces sentence-transformers + torch, saves ~2.5 GB)
─────────────────────────────────────────────────────────────────────────────
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import redis

logger = logging.getLogger(__name__)


# ─── Gemini embedding helper ──────────────────────────────────────────────────

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    """Pure-numpy cosine similarity between two 1-D vectors."""
    denom = np.linalg.norm(a) * np.linalg.norm(b)
    if denom == 0:
        return 0.0
    return float(np.dot(a, b) / denom)


def _get_gemini_embedding(text: str) -> np.ndarray:
 
    try:
        import google.generativeai as genai
        from app.core.config import settings
        genai.configure(api_key=settings.GEMINI_API_KEY)
        result = genai.embed_content(
            model="models/text-embedding-004",
            content=text,
            task_type="SEMANTIC_SIMILARITY",
        )
        return np.array(result["embedding"], dtype=np.float32)
    except Exception as exc:
        logger.warning("Gemini embedding failed: %s", exc)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Semantic Cache  (L3 — Redis-backed embeddings)
# ─────────────────────────────────────────────────────────────────────────────

class SemanticCache:
   

    EMBED_PREFIX = "sem:emb:"
    TEXT_PREFIX  = "sem:txt:"
    INDEX_KEY    = "sem:idx"
    EMBED_TTL    = 86400 * 7     

    def __init__(
        self,
        redis_client: redis.Redis,
        similarity_threshold: float = 0.85,
    ):
        self.r = redis_client
        self.threshold = similarity_threshold

    def _embed_key(self, qhash: str) -> str:
        return f"{self.EMBED_PREFIX}{qhash}"

    def _text_key(self, qhash: str) -> str:
        return f"{self.TEXT_PREFIX}{qhash}"

    def _hash_query(self, query: str) -> str:
        return hashlib.sha256(query.encode()).hexdigest()[:32]

    def add(self, cache_key: str, query: str) -> None:
        """Store Gemini embedding for query in Redis."""
        try:
            qhash = self._hash_query(query)
            embedding = _get_gemini_embedding(query)

            pipe = self.r.pipeline()
            pipe.setex(self._embed_key(qhash), self.EMBED_TTL,
                       json.dumps(embedding.tolist()))
            pipe.setex(self._text_key(qhash), self.EMBED_TTL, query)
            pipe.setex(f"sem:map:{qhash}", self.EMBED_TTL, cache_key)
            pipe.sadd(self.INDEX_KEY, qhash)
            pipe.execute()
        except Exception as exc:
            logger.warning("SemanticCache.add failed: %s", exc)

    def find_similar(
        self, query: str, max_results: int = 3
    ) -> List[Tuple[str, float]]:
        """Return [(cache_key, similarity_score), …] above threshold."""
        try:
            query_vec = _get_gemini_embedding(query)
            qhashes = self.r.smembers(self.INDEX_KEY)
            if not qhashes:
                return []

            pipe = self.r.pipeline()
            ordered_hashes = list(qhashes)
            for qh in ordered_hashes:
                pipe.get(self._embed_key(qh))
            raw_embeds = pipe.execute()

            results: List[Tuple[str, float]] = []
            for qh, raw in zip(ordered_hashes, raw_embeds):
                if raw is None:
                    continue
                try:
                    vec = np.array(json.loads(raw), dtype=np.float32)
                    sim = _cosine_similarity(query_vec, vec)
                    if sim >= self.threshold:
                        cache_key = self.r.get(f"sem:map:{qh}")
                        if cache_key:
                            results.append((cache_key, sim))
                except Exception:
                    continue

            results.sort(key=lambda x: x[1], reverse=True)
            return results[:max_results]

        except Exception as exc:
            logger.warning("SemanticCache.find_similar failed: %s", exc)
            return []

    def remove(self, cache_key: str) -> None:
        """Remove entries whose map points to cache_key."""
        try:
            qhashes = self.r.smembers(self.INDEX_KEY)
            pipe = self.r.pipeline()
            for qh in qhashes:
                mapped = self.r.get(f"sem:map:{qh}")
                if mapped == cache_key:
                    pipe.delete(self._embed_key(qh))
                    pipe.delete(self._text_key(qh))
                    pipe.delete(f"sem:map:{qh}")
                    pipe.srem(self.INDEX_KEY, qh)
            pipe.execute()
        except Exception as exc:
            logger.warning("SemanticCache.remove failed: %s", exc)


# ─────────────────────────────────────────────────────────────────────────────
# Advanced Cache Manager  (L1 + L2 + L3)
# ─────────────────────────────────────────────────────────────────────────────

class AdvancedCacheManager:
    """
    Thread-safe, multi-tier cache manager.

    L1: OrderedDict LRU  (in-process)
    L2: Redis            (shared, durable)
    L3: SemanticCache    (Gemini embeddings, similarity search)
    """

    L2_PREFIX = "cache:v2:"

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        l1_max_size: int = 256,
        enable_semantic: bool = True,
        similarity_threshold: float = 0.85,
    ):
        # ── L1 ───────────────────────────────────────────────────────────────
        self._l1: OrderedDict[str, dict] = OrderedDict()
        self._l1_max = l1_max_size
        self._l1_lock = threading.Lock()

        # ── L2 ───────────────────────────────────────────────────────────────
        self._redis = redis.Redis(
            host=redis_host,
            port=redis_port,
            password=redis_password,
            decode_responses=True,
            socket_connect_timeout=2,
            socket_timeout=2,
            retry_on_timeout=True,
            health_check_interval=30,
        )

        # ── L3 ───────────────────────────────────────────────────────────────
        self._semantic: Optional[SemanticCache] = (
            SemanticCache(self._redis, similarity_threshold)
            if enable_semantic
            else None
        )

        # ── Stats ─────────────────────────────────────────────────────────────
        self._stats_lock = threading.Lock()
        self._stats: Dict[str, int] = {
            "l1_hits": 0, "l1_misses": 0,
            "l2_hits": 0, "l2_misses": 0,
            "semantic_hits": 0, "total": 0,
        }

    # ── Key helpers ───────────────────────────────────────────────────────────

    def _make_key(self, query: str, context: Optional[Dict] = None) -> str:
        content = query + (json.dumps(context, sort_keys=True) if context else "")
        return hashlib.sha256(content.encode()).hexdigest()

    def _l2_key(self, key: str) -> str:
        return f"{self.L2_PREFIX}{key}"

    # ── L1 helpers ────────────────────────────────────────────────────────────

    def _l1_get(self, key: str) -> Optional[dict]:
        with self._l1_lock:
            entry = self._l1.get(key)
            if entry is None:
                return None
            if time.time() > entry["expires_at"]:
                del self._l1[key]
                return None
            self._l1.move_to_end(key)
            entry["access_count"] += 1
            return entry

    def _l1_set(self, key: str, value: Any, ttl: int, metadata: Dict) -> None:
        with self._l1_lock:
            if len(self._l1) >= self._l1_max:
                self._l1.popitem(last=False)   # evict LRU — O(1)
            self._l1[key] = {
                "value": value,
                "expires_at": time.time() + ttl,
                "access_count": 1,
                "cached_at": time.time(),
                "metadata": metadata,
            }
            self._l1.move_to_end(key)

    def _l1_delete(self, key: str) -> None:
        with self._l1_lock:
            self._l1.pop(key, None)

    # ── Stats helpers ─────────────────────────────────────────────────────────

    def _hit(self, tier: str) -> None:
        with self._stats_lock:
            self._stats[f"{tier}_hits"] += 1
            self._stats["total"] += 1

    def _miss(self, tier: str) -> None:
        with self._stats_lock:
            self._stats[f"{tier}_misses"] += 1

    # ── Public: get ───────────────────────────────────────────────────────────

    def get(self, query: str, context: Optional[Dict] = None) -> Optional[Dict]:
        """Lookup order: L1 → L2 → L3 (semantic)."""
        key = self._make_key(query, context)

        # L1
        entry = self._l1_get(key)
        if entry:
            self._hit("l1")
            return {"response": entry["value"], "cache_level": "L1",
                    "metadata": entry["metadata"]}
        self._miss("l1")

        # L2
        try:
            raw = self._redis.get(self._l2_key(key))
            if raw:
                entry_dict = json.loads(raw)
                ttl_remaining = max(1, int(entry_dict.get("expires_at", 0) - time.time()))
                self._l1_set(key, entry_dict["value"], ttl_remaining,
                             entry_dict.get("metadata", {}))
                self._hit("l2")
                return {"response": entry_dict["value"], "cache_level": "L2",
                        "metadata": entry_dict.get("metadata", {})}
        except Exception as exc:
            logger.warning("L2 get error: %s", exc)
        self._miss("l2")

        # L3 — Semantic (Gemini)
        if self._semantic:
            try:
                similar = self._semantic.find_similar(query, max_results=1)
                if similar:
                    sim_key, score = similar[0]
                    result = self.get_by_key(sim_key)
                    if result:
                        result["cache_level"] = "L3_SEMANTIC"
                        result["similarity_score"] = round(score, 4)
                        self._hit("semantic")
                        return result
            except Exception as exc:
                logger.warning("L3 semantic lookup error: %s", exc)

        return None

    def get_by_key(self, key: str) -> Optional[Dict]:
        """Direct lookup by raw cache key (skips L3)."""
        entry = self._l1_get(key)
        if entry:
            return {"response": entry["value"], "cache_level": "L1",
                    "metadata": entry["metadata"]}
        try:
            raw = self._redis.get(self._l2_key(key))
            if raw:
                d = json.loads(raw)
                return {"response": d["value"], "cache_level": "L2",
                        "metadata": d.get("metadata", {})}
        except Exception as exc:
            logger.warning("get_by_key L2 error: %s", exc)
        return None

    # ── Public: set ───────────────────────────────────────────────────────────

    def set(
        self,
        query: str,
        response: Any,
        ttl: int = 3600,
        context: Optional[Dict] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        metadata = metadata or {}
        key = self._make_key(query, context)

        self._l1_set(key, response, ttl, metadata)

        try:
            payload = json.dumps({
                "value": response,
                "expires_at": time.time() + ttl,
                "metadata": metadata,
            })
            self._redis.setex(self._l2_key(key), ttl, payload)
        except Exception as exc:
            logger.warning("L2 set error: %s", exc)

        if self._semantic:
            try:
                self._semantic.add(key, query)
            except Exception as exc:
                logger.warning("Semantic add error: %s", exc)

        return key

    # ── Public: invalidate ────────────────────────────────────────────────────

    def invalidate(
        self,
        key: Optional[str] = None,
        pattern: Optional[str] = None,
    ) -> int:
        removed = 0

        if key:
            self._l1_delete(key)
            try:
                removed += self._redis.delete(self._l2_key(key))
            except Exception:
                pass
            if self._semantic:
                self._semantic.remove(key)

        elif pattern:
            glob = f"{self.L2_PREFIX}*{pattern}*"
            try:
                l2_keys = self._redis.keys(glob)
                if l2_keys:
                    removed += self._redis.delete(*l2_keys)
            except Exception as exc:
                logger.warning("Pattern invalidation error: %s", exc)

            with self._l1_lock:
                to_delete = [k for k in self._l1 if pattern in k]
                for k in to_delete:
                    del self._l1[k]
                    removed += 1
                    if self._semantic:
                        self._semantic.remove(k)

        return removed

    # ── Public: warm-up ───────────────────────────────────────────────────────

    def warm(self, entries: List[Tuple[str, Any]], ttl: int = 86400) -> int:
        count = 0
        for query, response in entries:
            try:
                self.set(query, response, ttl=ttl, metadata={"warmed": True})
                count += 1
            except Exception as exc:
                logger.warning("Warm entry failed: %s", exc)
        return count

    # ── Public: stats ─────────────────────────────────────────────────────────

    def get_stats(self) -> Dict:
        with self._stats_lock:
            stats = dict(self._stats)
        total = stats["total"] or 1
        hits  = stats["l1_hits"] + stats["l2_hits"] + stats["semantic_hits"]
        with self._l1_lock:
            l1_size = len(self._l1)
        return {
            **stats,
            "l1_size": l1_size,
            "l1_hit_rate":       round(stats["l1_hits"] / total, 4),
            "l2_hit_rate":       round(stats["l2_hits"] / total, 4),
            "semantic_hit_rate": round(stats["semantic_hits"] / total, 4),
            "overall_hit_rate":  round(hits / total, 4),
        }

    def get_hot_entries(self, limit: int = 10) -> List[Dict]:
        with self._l1_lock:
            items = sorted(
                self._l1.items(),
                key=lambda kv: kv[1]["access_count"],
                reverse=True,
            )[:limit]
        return [
            {"key": k[:12] + "…", "access_count": v["access_count"],
             "cached_at": v["cached_at"], "metadata": v["metadata"]}
            for k, v in items
        ]

    def health(self) -> Dict:
        try:
            self._redis.ping()
            redis_ok = True
        except Exception:
            redis_ok = False
        with self._l1_lock:
            l1_size = len(self._l1)
        return {"l1_size": l1_size, "redis_ok": redis_ok}


# ─── Singleton ────────────────────────────────────────────────────────────────

_manager_lock = threading.Lock()
_cache_manager_instance: Optional[AdvancedCacheManager] = None


def get_cache_manager(
    redis_host: str = "localhost",
    redis_port: int = 6379,
    redis_password: Optional[str] = None,
    l1_max_size: int = 256,
    enable_semantic: bool = True,
) -> AdvancedCacheManager:
    global _cache_manager_instance
    if _cache_manager_instance is None:
        with _manager_lock:
            if _cache_manager_instance is None:
                _cache_manager_instance = AdvancedCacheManager(
                    redis_host=redis_host,
                    redis_port=redis_port,
                    redis_password=redis_password,
                    l1_max_size=l1_max_size,
                    enable_semantic=enable_semantic,
                )
    return _cache_manager_instance