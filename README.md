# MiFID Transaction Generator (ESMA TR 1.1.0)

Config-driven CSV → XML generator that produces ESMA Transaction Reporting files.
- Python **3.12+**
- No external dependencies by default (pure stdlib)
- Flexible field mapping via `config/mapping.json`
- OOP design with clear separation of concerns
- Optional XSD awareness: can read target namespaces from your local XSDs

> ⚠️ You must supply accurate XML element names and namespaces in the mapping. The sample mapping is **illustrative**. Adjust it to your reporting schema pack (ESMA TR 1.1.0).

## Quick start

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e .
```

### Generate XML

```bash
mifid-tx-gen \
  --csv ./samples/trades.csv \
  --config ./config/mapping.json \
  --out ./samples/out.xml \
  --xsd-dir ./config/xsd
```

### Run with validation

To validate against ESMA XSDs you need `lxml`:

```bash
pip install -e '.[envelope]'
```

Then run:

```bash
# Set your Legal Entity Identifiers (LEIs)
export FIRM_LEI=5493001KJTIIGC8Y1R12
export TO_LEI=724500PMK2A2M1S1W168

mifid-tx-gen \
  --csv ./samples/trades.csv \
  --config ./config/mapping.json \
  --out ./samples/out.xml \
  --xsd-dir ./config/xsd \
  --xsd-main ./config/xsd/head.003.001.01.xsd \
  --validate
```

This will:
- Generate `samples/out.xml`
- Validate it against the ESMA 1.1.0 schema set
- Fail fast if `FIRM_LEI` or `TO_LEI` are missing or invalid

## Project structure

```
mifid_tx_gen/
  config.py         # Load & validate config
  csv_reader.py     # Read CSV rows
  domain.py         # Domain objects (TradeRecord)
  mapper.py         # Map CSV rows → domain → XML model
  xml_builder.py    # Build XML with namespaces
  xml_builder_iso.py# lxml-based builder (schema-aware)
  generator.py      # High-level ReportGenerator
  validator.py      # XML schema validation
  cli.py            # CLI entrypoint
config/
  mapping.json      # Field & XML mapping
  xsd/              # Put your ESMA XSDs here
samples/
  trades.csv        # Example CSV
tests/
  test_smoke.py
```

## Mapping file (config/mapping.json)

- `namespaces`: prefix → URI
- `root`: root element `{prefix}:{localName}` and optional attributes (e.g., `xsi:schemaLocation`)
- `record_element`: element name for each transaction record
- `fields`: CSV field mapping. Each entry maps a CSV column `from` to an XML path `to` (QName path under the record element). Simple transforms supported.

See `config/mapping.json` for a full example.
