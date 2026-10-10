from .base import ProfileResult

class NullProvider:
    """Sem enriquecimento: nada é inventado. Bio e contadores ficam NULL."""
    name = "null"

    def fetch(self, username: str) -> ProfileResult:
        return ProfileResult(status="not_enriched")
