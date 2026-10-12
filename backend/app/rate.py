"""Rate limiting em janela fixa, com contagem em memória.

Single-instance: os limites zeram no restart e não são compartilhados entre
réplicas. Para escalar ou ter durabilidade, troque o armazenamento por Redis
mantendo a assinatura de `hit` — único ponto usado por `main.py` e `auth.py`.
(A versão com Redis fazia `INCR` + `EXPIRE` em `rl:<key>`.)
"""
import threading
import time

_lock = threading.Lock()
_buckets: dict[str, tuple[int, float]] = {}   # key -> (contagem, expira em monotonic)
_calls = 0                                     # chamadas desde a última varredura

SWEEP_EVERY = 10_000

def _sweep(now: float) -> None:
    """Remove entradas vencidas para o dict não crescer sem limite."""
    for key in [k for k, (_, exp) in _buckets.items() if exp <= now]:
        del _buckets[key]

def hit(key: str, limit: int, window_seconds: int) -> bool:
    """Conta uma tentativa. True = dentro do limite; False = bloquear."""
    global _calls
    now = time.monotonic()
    with _lock:
        count, exp = _buckets.get(key, (0, 0.0))
        if exp <= now:                       # chave nova ou janela vencida
            count, exp = 0, now + window_seconds
        count += 1
        _buckets[key] = (count, exp)
        _calls += 1
        if _calls >= SWEEP_EVERY:
            _calls = 0
            _sweep(now)
        return count <= limit
