
from __future__ import annotations
from dataclasses import dataclass
import xml.etree.ElementTree as ET
from pathlib import Path
from .config import GeneratorConfig, resolve_macros
import xml.dom.minidom

@dataclass
class XmlBuilder:
    cfg: GeneratorConfig

    def _register_namespaces(self) -> None:
        for prefix, uri in self.cfg.namespaces.items():
            ET.register_namespace(prefix if prefix != "default" else "", uri)

    def _qname(self, qname: str) -> str:
        if ":" in qname:
            prefix, local = qname.split(":", 1)
            uri = self.cfg.namespaces.get(prefix)
            if not uri:
                raise KeyError(f"Unknown namespace prefix '{prefix}' in qname '{qname}'")
            return f"{{{uri}}}{local}"
        return qname  # no namespace

    def build_root(self) -> ET.Element:
        self._register_namespaces()
        root = ET.Element(self._qname(self.cfg.root.qname))
        # set attributes (macro-aware)
        for k, v in (self.cfg.root.attributes or {}).items():
            root.set(self._qname(k), resolve_macros(v))
        # static children under root (simple key→value map or nested objects)
        for child_qname, obj in (self.cfg.root.children or {}).items():
            self._append_child_object(root, child_qname, obj)
        return root

    def _append_child_object(self, parent: ET.Element, child_qname: str, obj) -> None:
        el = ET.SubElement(parent, self._qname(child_qname))
        if isinstance(obj, dict):
            for k, v in obj.items():
                if isinstance(v, dict):
                    self._append_child_object(el, k, v)
                else:
                    child = ET.SubElement(el, self._qname(k))
                    child.text = resolve_macros(v)
        else:
            el.text = resolve_macros(str(obj))

    def append_record(self, parent: ET.Element, fields: list[tuple[str, str]]) -> None:
        if self.cfg.record_container_qname and self.cfg.record_element_qname:
            container = self.ensure_container(parent, self.cfg.record_container_qname)
            self.append_record_into(container, self.cfg.record_element_qname, fields)
            return
        # legacy fallback
        tag = self._qname(self.cfg.record_element or "Record")
        rec_el = ET.SubElement(parent, tag)
        for path, value in fields:
            self._ensure_path(rec_el, path, value)


    def _ensure_path(self, base: ET.Element, path: str, value: str) -> None:
        # path like "rep:Instrument/rep:ISIN"
        current = base
        parts = path.split("/")
        for i, part in enumerate(parts):
            tag = self._qname(part)
            found = current.find(tag)
            if found is None:
                found = ET.SubElement(current, tag)
            current = found
            if i == len(parts) - 1:
                current.text = value

    def write(self, root: ET.Element, out_path: Path) -> None:
        tree = ET.ElementTree(root)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        tree.write(out_path, encoding="utf-8", xml_declaration=True)

    def write(self, root: ET.Element, out_path: Path, pretty: bool = True) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if pretty:
            # Serialize, parse with minidom, then re-serialize with indent
            rough_string = ET.tostring(root, encoding="utf-8", xml_declaration=True)
            parsed = xml.dom.minidom.parseString(rough_string)
            pretty_xml = parsed.toprettyxml(indent="  ", encoding="utf-8")
            out_path.write_bytes(pretty_xml)
        else:
            tree = ET.ElementTree(root)
            tree.write(out_path, encoding="utf-8", xml_declaration=True)
