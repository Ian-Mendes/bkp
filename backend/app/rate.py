import os
import redis

_client = None

def _r():
    global _client
    if _client is None:
        _client = redis.Redis.from_url(os.environ["REDIS_URL"])
    return _client

def hit(key: str, limit: int, window_seconds: int) -> bool:
    """Conta uma tentativa. True = dentro do limite; False = bloquear."""
    k = f"rl:{key}"
    n = _r().incr(k)
    if n == 1:
        _r().expire(k, window_seconds)
    return n <= limit
