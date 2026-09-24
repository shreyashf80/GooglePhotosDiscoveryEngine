import hashlib
from abc import ABC, abstractmethod
from datetime import datetime

from shared.models import RawRecord

class SourceBase(ABC):
    """Abstract base class for all pipeline sources (FR-1)."""
    
    @abstractmethod
    def fetch(self, since: datetime, cap: int) -> list[RawRecord]:
        """Fetch records from the source created after `since`, up to `cap` items."""
        pass

def hash_author(author_name: str | None) -> str | None:
    """Hash an author's name (SHA-256 first 12 chars) before storage (FR-4)."""
    if not author_name:
        return None
    return hashlib.sha256(author_name.encode('utf-8')).hexdigest()[:12]
