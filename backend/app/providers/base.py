from dataclasses import dataclass
from typing import Protocol

# Estados: ok, not_enriched, private, not_found, rate_limited, error
@dataclass
class ProfileResult:
    status: str
    followers_count: int | None = None
    following_count: int | None = None
    bio: str | None = None

class ProfileProvider(Protocol):
    name: str
    def fetch(self, username: str) -> ProfileResult: ...
