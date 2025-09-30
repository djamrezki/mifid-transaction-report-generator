# src/mifid_tx_gen/validator.py
from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable, Tuple, Optional, List

import xmlschema
from xmlschema.validators.exceptions import XMLSchemaValidationError, XMLSchemaException


# validator.py
HEAD003_NS = "urn:iso:std:iso:20022:tech:xsd:head.003.001.01"
HEAD001_NS = "urn:iso:std:iso:20022:tech:xsd:head.001.001.01"
AUTH016_NS = "urn:iso:std:iso:20022:tech:xsd:auth.016.001.01"



def _as_path(p) -> Path:
    return p if isinstance(p, Path) else Path(p)


def _scan_ns_locations(xsd_dir: Path) -> Dict[str, str]:
    """
    Build a namespace -> schema file map by scanning xsd_dir for common ISO20022 filenames.
    This helps xmlschema resolve strict xs:any payload/header schemas even if the instance's
    xsi:schemaLocation is absent/incomplete.
    """
    locations: Dict[str, str] = {}

    if not xsd_dir or not xsd_dir.exists():
        return locations

    # Best-effort: pick the *first* matching file we find for each namespace.
    candidates = list(xsd_dir.glob("*.xsd"))

    def pick(ns: str, *name_starts: str):
        if ns in locations:
            return
        for c in candidates:
            stem = c.stem  # e.g., "head.003.001.01" or "head.001.001.01_ESMAUG_1.0.0"
            if any(st in stem for st in name_starts):
                locations[ns] = c.resolve().as_uri()
                return

    pick(HEAD003_NS, "head.003")
    pick(HEAD001_NS, "head.001")
    pick(AUTH016_NS, "auth.016")

    return locations


def _load_schema_with_bases(main_xsd: Path,
                            base_urls: Iterable[str],
                            locations: Optional[Dict[str, str]] = None) -> xmlschema.XMLSchema:
    """
    Try to load the main XSD using a list of base URLs.
    Returns the first successfully built XMLSchema, otherwise raises the last error.
    """
    last_err: Optional[Exception] = None
    for base_url in base_urls:
        try:
            return xmlschema.XMLSchema(
                str(main_xsd),
                base_url=base_url,
                locations=locations or None,   # maps ns -> xsd url
            )
        except Exception as e:
            last_err = e
            continue
    assert last_err is not None  # for type-checkers
    raise last_err


def _assert_bizdata_declared(schema: xmlschema.XMLSchema, main_xsd: Path) -> None:
    """
    Guard to ensure the loaded schema actually declares the head.003 BizData element.
    Gives a helpful list of what *was* declared otherwise.
    """
    try:
        declared = schema.maps.elements  # xmlschema >= 1.3
    except AttributeError:
        # Fallback for older versions
        declared = getattr(schema, "elements", {})

    key = f"{{{HEAD003_NS}}}BizData"
    if key not in declared:
        # Provide a readable dump of declared element QNames
        declared_list = "\n  - ".join(sorted(declared.keys()))
        raise RuntimeError(
            "Main XSD loaded, but it does NOT declare the global element 'BizData' "
            f"in namespace {HEAD003_NS}.\n"
            f"Main XSD: {main_xsd}\n"
            "Declared global elements:\n"
            f"  - {declared_list or '(none)'}"
        )


def validate_xml(out_path, xsd_dir, main_xsd) -> None:
    """
    Validate the XML document at out_path against the provided main_xsd.
    The validator will:
      - Use main_xsd.parent, xsd_dir, and cwd as candidate base URLs.
      - Provide ns->xsd mapping from xsd_dir when available.
      - Fail fast if BizData isn't declared by the loaded schema.
    Raises:
      - RuntimeError on failure with helpful diagnostics.
    """
    out_path = _as_path(out_path)
    xsd_dir = _as_path(xsd_dir)
    main_xsd = _as_path(main_xsd)

    if not main_xsd.exists():
        raise RuntimeError(f"Main XSD not found: {main_xsd}")

    # Candidate bases to try (in this order)
    base_urls: List[str] = []
    try:
        base_urls.append(main_xsd.parent.resolve().as_uri())
    except Exception:
        pass
    if xsd_dir.exists():
        try:
            base_urls.append(xsd_dir.resolve().as_uri())
        except Exception:
            pass
    try:
        base_urls.append(Path.cwd().resolve().as_uri())
    except Exception:
        pass
    # Deduplicate while preserving order
    seen = set()
    base_urls = [b for b in base_urls if not (b in seen or seen.add(b))]

    # Optional ns->schema mapping from directory scan
    locations = _scan_ns_locations(xsd_dir)

    # Try loading the schema with the candidate base URLs
    try:
        schema = _load_schema_with_bases(main_xsd, base_urls, locations=locations)
        _assert_bizdata_declared(schema, main_xsd)
    except Exception as e:
        tried = ", ".join(base_urls) or "(none)"
        raise RuntimeError(
            "Failed to load/prepare XML Schema for validation.\n"
            f"Main XSD: {main_xsd}\n"
            f"Tried base URLs: [{tried}]\n"
            f"Namespace locations: {locations or '(none)'}\n"
            f"Error: {e}"
        ) from e

    # Now validate the instance
    try:
        schema.validate(str(out_path))
    except XMLSchemaValidationError as ve:
        # Include the path and a short excerpt of the instance element if available
        raise RuntimeError(
            "XML validation failed.\n"
            f"Main XSD: {main_xsd}\n"
            f"Base URLs tried: {base_urls}\n"
            f"Namespace locations: {locations or '(none)'}\n"
            f"Validation error: {ve}"
        ) from ve
    except XMLSchemaException as xe:
        raise RuntimeError(
            "XML validation encountered a schema processing error.\n"
            f"Main XSD: {main_xsd}\n"
            f"Base URLs tried: {base_urls}\n"
            f"Namespace locations: {locations or '(none)'}\n"
            f"Error: {xe}"
        ) from xe
