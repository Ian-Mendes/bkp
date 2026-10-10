import os
from .null_provider import NullProvider

def get_provider():
    name = os.getenv("PROVIDER", "null")
    if name == "null":
        return NullProvider()
    raise ValueError(f"Provedor desconhecido: {name}")
