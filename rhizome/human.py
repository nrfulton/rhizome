from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class HumanInput:
    content: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
