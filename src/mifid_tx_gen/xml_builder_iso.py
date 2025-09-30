from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from lxml import etree as LET
from .config import GeneratorConfig, resolve_macros

@dataclass
class IsoXmlBuilder:
    cfg: GeneratorConfig

    def _uri(self, prefix: str) -> str:
        uri = self.cfg.namespaces.get(prefix)
        if not uri:
            raise KeyError(f"Unknown ns prefix: {prefix}")
        return uri

    def build_root(self) -> tuple[LET._Element, LET._Element]:
        for needed in ("head003", "head001", "msg", "xsi"):
            if needed not in self.cfg.namespaces:
                raise ValueError(f"Missing '{needed}' in mapping.json -> namespaces")

        head003 = self._uri("head003")
        head001 = self._uri("head001")
        msg     = self._uri("msg")
        xsi     = self._uri("xsi")

        # <BizData xmlns="head003" xmlns:xsi="...">
        root = LET.Element(LET.QName(head003, "BizData"), nsmap={None: head003, "xsi": xsi})

        # schemaLocation
        sl = (self.cfg.root.attributes or {}).get("xsi:schemaLocation")
        if sl:
            root.set(LET.QName(xsi, "schemaLocation"), resolve_macros(sl))

        # <Hdr>
        hdr = LET.SubElement(root, LET.QName(head003, "Hdr"))

        # <AppHdr xmlns="head001">
        apphdr = LET.SubElement(hdr, LET.QName(head001, "AppHdr"), nsmap={None: head001})
        fr = LET.SubElement(apphdr, LET.QName(head001, "Fr"))

        # OrgId -> Id -> OrgId -> Othr -> Id + SchmeNm/Prtry("LEI")  ✅ ESMAUG-compliant
        fr_org = LET.SubElement(fr, LET.QName(head001, "OrgId"))
        fr_org_id = LET.SubElement(fr_org, LET.QName(head001, "Id"))
        fr_org_id_org = LET.SubElement(fr_org_id, LET.QName(head001, "OrgId"))

        othr = LET.SubElement(fr_org_id_org, LET.QName(head001, "Othr"))
        LET.SubElement(othr, LET.QName(head001, "Id")).text = resolve_macros("{ENV:FIRM_LEI:UNKNOWN}")
        schme = LET.SubElement(othr, LET.QName(head001, "SchmeNm"))
        LET.SubElement(schme, LET.QName(head001, "Prtry")).text = "LEI"


        # --- To ---
        to = LET.SubElement(apphdr, LET.QName(head001, "To"))
        to_org = LET.SubElement(to, LET.QName(head001, "OrgId"))
        to_org_id = LET.SubElement(to_org, LET.QName(head001, "Id"))
        to_org_id_org = LET.SubElement(to_org_id, LET.QName(head001, "OrgId"))

        to_othr = LET.SubElement(to_org_id_org, LET.QName(head001, "Othr"))
        LET.SubElement(to_othr, LET.QName(head001, "Id")).text = resolve_macros("{ENV:TO_LEI:UNKNOWN}")
        to_schme = LET.SubElement(to_othr, LET.QName(head001, "SchmeNm"))
        LET.SubElement(to_schme, LET.QName(head001, "Prtry")).text = "LEI"

        # --- BizMsgIdr (unique id) ---
        import uuid, datetime
        LET.SubElement(apphdr, LET.QName(head001, "BizMsgIdr")).text = "mf-" + uuid.uuid4().hex[:33]


        # --- MsgDefIdr (must match the business message definition) ---
        LET.SubElement(apphdr, LET.QName(head001, "MsgDefIdr")).text = "auth.016.001.01"

        # --- CreDt (after MsgDefIdr) ---
        LET.SubElement(apphdr, LET.QName(head001, "CreDt")).text = datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


        # <Pyld><Document xmlns="auth.016">
        pyld = LET.SubElement(root, LET.QName(head003, "Pyld"))
        doc  = LET.SubElement(pyld, LET.QName(msg, "Document"), nsmap={None: msg})

        # <FinInstrmRptgTxRpt>
        container = LET.SubElement(doc, LET.QName(msg, "FinInstrmRptgTxRpt"))

        return root, container


    # xml_builder_iso.py
    import lxml.etree as LET

    def append_tx(self, container, fields):
        # Always bind children to the auth.016 namespace so lookups work.
        msg_ns = self._uri("msg")  # => "urn:iso:std:iso:20022:tech:xsd:auth.016.001.01"

        tx = LET.SubElement(container, LET.QName(msg_ns, "Tx"))
        # ensure a single <New> exists under this Tx
        new_el = tx.find(f"./{{{msg_ns}}}New")
        if new_el is None:
            new_el = LET.SubElement(tx, LET.QName(msg_ns, "New"))

        # Fill content according to mapping rules
        for path, value in fields:
            self._ensure_path(tx, path, value)




    def _ensure_path(self, root, path, value):
        """
        Create missing elements along /-separated path.
        If the last segment contains '@attr', set that attribute on the element.
        Supports nested paths like: New/Tx/Pric/Pric/MntryVal/Amt@Ccy.
        Ensures inner Tx children are inserted in schema order.
        """
        NS_AUTH = "urn:iso:std:iso:20022:tech:xsd:auth.016.001.01"
        NS_HEAD = "urn:iso:std:iso:20022:tech:xsd:head.001.001.01"

        INNER_TX_ORDER = ["TradDt", "TradgCpcty", "Qty", "Pric", "TradVn"]

        def get_ns(elem):
            # return the namespace of an element tag {ns}local or None
            t = elem.tag
            if isinstance(t, str) and t.startswith("{"):
                return t[1:].split("}")[0]
            return None

        def qname(ns, tag):
            return LET.QName(ns, tag)

        def is_inner_tx(parent):
            """
            True if parent is the *inner* Tx (child of New), not the outer wrapper Tx.
            We identify it as:
              - localname == 'Tx' AND
              - namespace == auth016 AND
              - it does NOT have 'New' or 'Cxl' among its direct children.
            """
            tag = parent.tag
            if not (tag.endswith("}Tx") or tag == "Tx"):
                return False
            ns = get_ns(parent)
            if ns != NS_AUTH:
                return False
            for child in parent:
                ln = child.tag.split("}", 1)[-1]
                if ln in ("New", "Cxl"):
                    return False  # that's the OUTER Tx
            return True

        def insert_child_in_order(parent, new_child):
            """
            Insert new_child into parent respecting INNER_TX_ORDER if parent is inner Tx.
            Otherwise, append at the end.
            """
            if not is_inner_tx(parent):
                parent.append(new_child)
                return

            new_ln = new_child.tag.split("}", 1)[-1]
            try:
                new_idx = INNER_TX_ORDER.index(new_ln)
            except ValueError:
                parent.append(new_child)
                return

            # Insert before the first sibling that should come AFTER new_child.
            for after_ln in INNER_TX_ORDER[new_idx + 1:]:
                for i, sib in enumerate(list(parent)):
                    sib_ln = sib.tag.split("}", 1)[-1]
                    if sib_ln == after_ln:
                        parent.insert(i, new_child)
                        return

            parent.append(new_child)

        # --- actual path creation logic (fixed indentation) ---
        current = root
        parts = [p for p in path.split("/") if p]
        default_ns = get_ns(root) or NS_AUTH
        set_text_at_end = True

        for i, part in enumerate(parts):
            # Attribute segment on the current element to create/find
            if "@" in part:
                elem_tag, attr_name = part.split("@", 1)
                if elem_tag:
                    ns = get_ns(current) or default_ns
                    child = current.find(f"./{{{ns}}}{elem_tag}")
                    if child is None:
                        new_child = LET.Element(qname(ns, elem_tag))
                        insert_child_in_order(current, new_child)
                        child = new_child
                    current = child
                if value is not None:
                    current.set(attr_name, str(value))
                # since terminal is attribute, don't set text later
                set_text_at_end = False
                return

            # Normal element segment (this MUST be inside the loop)
            ns = get_ns(current) or default_ns
            child = current.find(f"./{{{ns}}}{part}")
            if child is None:
                new_child = LET.Element(qname(ns, part))
                insert_child_in_order(current, new_child)
                child = new_child
            current = child

        # After walking all segments, set text if appropriate
        if set_text_at_end and value is not None:
            current.text = str(value)



    def write(self, root: LET._Element, out_path: Path, pretty: bool = True) -> None:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        xml_bytes = LET.tostring(root, xml_declaration=True, encoding="utf-8", pretty_print=pretty)
        out_path.write_bytes(xml_bytes)
