"""Contrato das fontes de enriquecimento: o que cada provider entrega por perfil.

Trocar de provider é trocar a implementação de `fetch`; `services.run_enrichment`
e o resto do código só enxergam `ProfileResult`. Providers podem expor
`fetch_many(usernames) -> dict[str, ProfileResult]` para enriquecer em lote (o
`run_enrichment` usa quando existe). Para múltiplos providers no futuro, compor
aqui (fallback/compensação) sem tocar o enriquecimento.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

# Estados: ok, not_enriched, private, not_found, rate_limited, error
@dataclass
class ProfileResult:
    status: str
    followers_count: int | None = None
    following_count: int | None = None
    bio: str | None = None
    profile_url: str | None = None   # validado na POC da issue #12 como confiável
    full_name: str | None = None
    external_url: str | None = None
    profile_pic_url: str | None = None
    posts_count: int | None = None
    category: str | None = None
    is_verified: bool | None = None
    is_business: bool | None = None
    source: str | None = None        # nome do provider que consultou (None = não consultado)
    fetched_at: datetime | None = None   # quando consultou, UTC (None = não consultado)

class ProfileProvider(Protocol):
    name: str
    def fetch(self, username: str) -> ProfileResult: ...
