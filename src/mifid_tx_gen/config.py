
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Any, Optional
import json
import xml.etree.ElementTree as ET

def _rename_xmlns_keys(obj):
    if isinstance(obj, dict):
        new = {}
        for k, v in obj.items():
            nk = "xmlns" if k == "_xmlns" else k
            new[nk] = _rename_xmlns_keys(v)
        return new
    if isinstance(obj, list):
        return [_rename_xmlns_keys(x) for x in obj]
    return obj

@dataclass
class MappingRule:
    from_field: str
    to_path: str  # QName path relative to record element

@dataclass
class RootSpec:
    qname: str
    attributes: Dict[str, str] = field(default_factory=dict)
    children: Dict[str, Any] = field(default_factory=dict)
    # NEW: allow default namespace on this node
    xmlns: Optional[str] = None

from dataclasses import dataclass, field

@dataclass
class GeneratorConfig:
    namespaces: dict[str, str]
    root: RootSpec
    # legacy direct-child record element (batch style); optional now
    record_element: str | None = None
    fields: list[MappingRule] = field(default_factory=list)
    # ISO style:
    record_container_qname: str | None = None
    record_element_qname: str | None = None

    @classmethod
    def load(cls, path: Path) -> "GeneratorConfig":
        data = json.loads(Path(path).read_text())
        data = _rename_xmlns_keys(data)  # <— handle _xmlns
        fields = [MappingRule(r["from"], r["to"]) for r in data["fields"]]
        root = RootSpec(**data["root"])
        return cls(
            namespaces=data["namespaces"],
            root=root,
            record_element=data.get("record_element"),
            fields=fields,
            record_container_qname=data.get("record_container_qname"),
            record_element_qname=data.get("record_element_qname"),
        )

    def augment_namespaces_from_xsd(self, xsd_dir: Path | None) -> None:
        if not xsd_dir or not Path(xsd_dir).exists():
            return
        # Attempt to read targetNamespace from any XSDs present and add to map if missing
        for xsd in Path(xsd_dir).glob("*.xsd"):
            try:
                tree = ET.parse(xsd)
                ns = tree.getroot().attrib.get("targetNamespace")
                if not ns:
                    continue
                # if file name contains a hint for the prefix, try to infer
                hint = xsd.stem.split("_")[0]  # e.g., auth.016.001.01
                if "auth.016" in hint and "rep" not in self.namespaces.values():
                    # only add if not present under any prefix
                    if ns not in self.namespaces.values():
                        self.namespaces["rep_inferred"] = ns
                if "head.001" in hint and ns not in self.namespaces.values():
                    self.namespaces["hdr_inferred"] = ns
            except Exception:
                continue

def resolve_macros(value: str) -> str:
    if not isinstance(value, str):
        return value

    # {ENV:VAR} or {ENV:VAR:default}
    if value.startswith("{ENV:") and value.endswith("}"):
        parts = value.strip("{}").split(":")  # ["ENV", "VAR"] or ["ENV","VAR","default"]
        # Defensive: pad missing default with empty string
        _, var, *rest = parts
        default = rest[0] if rest else ""
        import os
        return os.getenv(var, default)

    if value == "{NOW_ISO}":
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")

    return value

