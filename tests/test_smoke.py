
from pathlib import Path
from mifid_tx_gen.generator import ReportGenerator

def test_smoke(tmp_path: Path):
    csv_path = Path("samples/trades.csv")
    cfg_path = Path("config/mapping.json")
    out_path = tmp_path / "out.xml"
    gen = ReportGenerator.from_paths(csv_path, cfg_path, xsd_dir=None)
    gen.generate(out_path)
    assert out_path.exists()
    assert out_path.read_text().startswith("<")
