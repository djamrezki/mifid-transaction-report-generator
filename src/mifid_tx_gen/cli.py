from __future__ import annotations
import argparse
from pathlib import Path
from .generator import ReportGenerator

def main() -> None:
    p = argparse.ArgumentParser(description="MiFID TR XML Generator (ESMA 1.1.0)")
    p.add_argument("--csv", required=True, type=Path, help="Input trades CSV")
    p.add_argument("--config", required=True, type=Path, help="Mapping JSON")
    p.add_argument("--out", required=True, type=Path, help="Output XML path")
    p.add_argument("--xsd-dir", required=False, type=Path, help="XSD directory")
    p.add_argument("--validate", action="store_true", help="Validate output against XSDs")
    p.add_argument("--xsd-main", type=Path, help="Main XSD file (optional; otherwise auto-chosen)")

    args = p.parse_args()

    gen = ReportGenerator.from_paths(args.csv, args.config, args.xsd_dir)
    out = gen.generate(args.out)
    print(f"Generated XML: {out}")

    if args.validate:
        if not args.xsd_dir:
            raise SystemExit("--validate requires --xsd-dir")
        from .validator import validate_xml
        validate_xml(out, args.xsd_dir, args.xsd_main)
        print("Validation: OK")
