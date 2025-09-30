
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any

@dataclass
class TradeRecord:
    data: dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)
