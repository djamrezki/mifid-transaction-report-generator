
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from .config import GeneratorConfig
from .csv_reader import CsvReader
from .domain import TradeRecord
from .mapper import FieldMapper
from .xml_builder import XmlBuilder


try:
    from .xml_builder_iso import IsoXmlBuilder as PreferredBuilder
    _HAS_LXML = True
except Exception:
    from .xml_builder import XmlBuilder as PreferredBuilder
    _HAS_LXML = False

@dataclass
class ReportGenerator:
    cfg: GeneratorConfig
    csv_path: Path

    @classmethod
    def from_paths(cls, csv_path: Path, cfg_path: Path, xsd_dir: str | None) -> "ReportGenerator":
        cfg = GeneratorConfig.load(cfg_path)
        cfg.augment_namespaces_from_xsd(Path(xsd_dir) if xsd_dir else None)
        return cls(cfg=cfg, csv_path=csv_path)

    def generate(self, out_path: Path) -> Path:
        builder = PreferredBuilder(self.cfg)
        if _HAS_LXML and hasattr(builder, "build_root"):
            root, container = builder.build_root()  # lxml path
            mapper = FieldMapper(self.cfg)
            for row in CsvReader(self.csv_path).rows():
                fields = mapper.to_xml_fields(TradeRecord(row))
                builder.append_tx(container, fields)  # lxml method
            builder.write(root, out_path)
        else:
            # stdlib fallback
            b = XmlBuilder(self.cfg)
            root = b.build_root()
            mapper = FieldMapper(self.cfg)
            for row in CsvReader(self.csv_path).rows():
                fields = mapper.to_xml_fields(TradeRecord(row))
                b.append_record(root, fields)
            b.write(root, out_path, pretty=True)
        return out_path

