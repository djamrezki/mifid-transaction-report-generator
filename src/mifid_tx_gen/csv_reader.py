
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import csv
from typing import Iterator

@dataclass
class CsvReader:
    path: Path
    delimiter: str = ","

    def rows(self) -> Iterator[dict[str, str]]:
        with self.path.open(newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f, delimiter=self.delimiter)
            for row in reader:
                yield {k.strip(): (v.strip() if isinstance(v, str) else v) for k, v in row.items()}
