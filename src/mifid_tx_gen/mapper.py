# mapper.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List
from .domain import TradeRecord
from .config import GeneratorConfig, MappingRule, resolve_macros

@dataclass
class FieldMapper:
    cfg: GeneratorConfig

    def to_xml_fields(self, trade: TradeRecord) -> List[tuple[str, str]]:
        """
        - If MappingRule.from_field is a CSV column, take its value.
        - Otherwise treat it as a literal/macro and resolve it (ENV/NOW/plain strings).
        """
        pairs: list[tuple[str, str]] = []
        for rule in self.cfg.fields:
            src = rule.from_field
            if src in trade.data:
                val = trade.get(src, None)
            else:
                val = resolve_macros(src)  # handles {ENV:...}, {NOW_ISO}, or plain strings like "false", "NORE"

            if val is None or str(val) == "":
                continue

            pairs.append((rule.to_path, str(val)))
        return pairs
