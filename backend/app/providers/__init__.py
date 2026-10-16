import os
from .null_provider import NullProvider
from .apify_provider import ApifyProvider

def get_provider():
    """Escolhe a fonte de enriquecimento (`PROVIDER=null|apify`).

    Registrar o próximo provider aqui (ex.: `official`, `http`) e documentar
    as variáveis no `.env.example`. Para múltiplos no futuro, compor neste
    ponto (fallback) sem tocar `services.run_enrichment`.
    """
    name = os.getenv("PROVIDER", "null")
    if name == "null":
        return NullProvider()
    if name == "apify":
        return ApifyProvider()
    raise ValueError(f"Provedor desconhecido: {name}")
