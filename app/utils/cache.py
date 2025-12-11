"""
Caching utilities using Redis
"""

import redis
import json
import pickle
from functools import wraps
from flask import current_app
import logging
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class Cache:
    """Redis cache wrapper"""

    def __init__(self, redis_url: str = None):
        """Initialize cache with Redis connection"""
        self.redis_client = None
        if redis_url:
            try:
                self.redis_client = redis.from_url(redis_url)
                self.redis_client.ping()
                logger.info("Cache connected to Redis")
            except Exception as e:
                logger.error(f"Failed to connect to Redis: {e}")

    def get(self, key: str, deserialize=True) -> Optional[Any]:
        """
        Get value from cache

        Args:
            key: Cache key
            deserialize: Whether to deserialize the value

        Returns:
            Cached value or None
        """
        if not self.redis_client:
            return None

        try:
            value = self.redis_client.get(key)
            if value is None:
                return None

            if deserialize:
                try:
                    return json.loads(value)
                except json.JSONDecodeError:
                    return pickle.loads(value)

            return value
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return None

    def set(self, key: str, value: Any, ttl: int = 3600, serialize=True):
        """
        Set value in cache

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time to live in seconds
            serialize: Whether to serialize the value
        """
        if not self.redis_client:
            return False

        try:
            if serialize:
                try:
                    serialized = json.dumps(value)
                except (TypeError, ValueError):
                    serialized = pickle.dumps(value)
            else:
                serialized = value

            self.redis_client.setex(key, ttl, serialized)
            return True
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
            return False

    def delete(self, key: str):
        """Delete key from cache"""
        if not self.redis_client:
            return False

        try:
            self.redis_client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
            return False

    def delete_pattern(self, pattern: str):
        """Delete all keys matching pattern"""
        if not self.redis_client:
            return False

        try:
            keys = self.redis_client.keys(pattern)
            if keys:
                self.redis_client.delete(*keys)
            return True
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
            return False

    def exists(self, key: str) -> bool:
        """Check if key exists in cache"""
        if not self.redis_client:
            return False

        try:
            return bool(self.redis_client.exists(key))
        except Exception as e:
            logger.error(f"Cache exists error for key {key}: {e}")
            return False

    def increment(self, key: str, amount: int = 1) -> Optional[int]:
        """Increment a counter"""
        if not self.redis_client:
            return None

        try:
            return self.redis_client.incrby(key, amount)
        except Exception as e:
            logger.error(f"Cache increment error for key {key}: {e}")
            return None

    def get_many(self, keys: list) -> dict:
        """Get multiple keys at once"""
        if not self.redis_client:
            return {}

        try:
            values = self.redis_client.mget(keys)
            result = {}
            for key, value in zip(keys, values):
                if value is not None:
                    try:
                        result[key] = json.loads(value)
                    except json.JSONDecodeError:
                        result[key] = pickle.loads(value)
            return result
        except Exception as e:
            logger.error(f"Cache get_many error: {e}")
            return {}


def cached(ttl: int = 3600, key_prefix: str = "", key_func: Optional[Callable] = None):
    """
    Decorator to cache function results

    Args:
        ttl: Time to live in seconds
        key_prefix: Prefix for cache key
        key_func: Function to generate cache key from arguments
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                from flask import current_app

                # Get cache instance
                if not hasattr(current_app, "cache"):
                    redis_url = current_app.config.get("REDIS_URL")
                    current_app.cache = Cache(redis_url)

                cache = current_app.cache

                # Generate cache key
                if key_func:
                    cache_key = f"{key_prefix}:{key_func(*args, **kwargs)}"
                else:
                    # Default key from function name and arguments
                    args_str = str(args) + str(sorted(kwargs.items()))
                    cache_key = f"{key_prefix}:{f.__name__}:{hash(args_str)}"

                # Try to get from cache
                cached_value = cache.get(cache_key)
                if cached_value is not None:
                    logger.debug(f"Cache hit for {cache_key}")
                    return cached_value

                # Execute function
                result = f(*args, **kwargs)

                # Cache result
                cache.set(cache_key, result, ttl)
                logger.debug(f"Cached result for {cache_key}")

                return result

            except Exception as e:
                logger.error(f"Caching error: {e}", exc_info=True)
                # If caching fails, just execute the function
                return f(*args, **kwargs)

        return decorated_function

    return decorator


def invalidate_cache(pattern: str):
    """
    Invalidate cache entries matching pattern

    Args:
        pattern: Redis key pattern (e.g., "bugs:*")
    """
    try:
        from flask import current_app

        if hasattr(current_app, "cache"):
            current_app.cache.delete_pattern(pattern)
            logger.info(f"Invalidated cache pattern: {pattern}")
    except Exception as e:
        logger.error(f"Cache invalidation error: {e}")
