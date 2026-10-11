"""All runtime numeric assumptions are versioned configuration."""
from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
SIM = yaml.safe_load((ROOT / "data/config/sim.yaml").read_text())
MODEL = yaml.safe_load((ROOT / "data/config/model.yaml").read_text())
SCENARIOS = {p.stem: yaml.safe_load(p.read_text()) for p in (ROOT / "data/scenarios").glob("*.yaml")}
