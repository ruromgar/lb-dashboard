"""Simple file-based cache with TTL for scraped HTML pages."""

import logging
import os
import time
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = os.environ.get("LB_CACHE_DIR", "./cache")
DEFAULT_TTL = int(os.environ.get("LB_CACHE_TTL", "3600"))


def get_cached(
    cache_dir: str,
    cache_key: str,
    ttl: int = DEFAULT_TTL,
) -> Optional[str]:
    """Return cached content if it exists and is fresh, else None."""
    path = Path(cache_dir) / cache_key
    if not path.exists():
        return None
    age = time.time() - path.stat().st_mtime
    if age > ttl:
        logger.info("Cache expired for %s (age=%.0fs, ttl=%ds)", cache_key, age, ttl)
        return None
    logger.info("Cache hit for %s (age=%.0fs)", cache_key, age)
    return path.read_text(encoding="utf-8")


def get_stale_cached(cache_dir: str, cache_key: str) -> Optional[str]:
    """Return cached content regardless of TTL, or None if no cache exists."""
    path = Path(cache_dir) / cache_key
    if not path.exists():
        return None
    logger.info("Stale cache fallback for %s", cache_key)
    return path.read_text(encoding="utf-8")


def save_to_cache(cache_dir: str, cache_key: str, content: str) -> None:
    """Write content to the cache directory."""
    path = Path(cache_dir) / cache_key
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    logger.info("Cached %s (%d bytes)", cache_key, len(content))
