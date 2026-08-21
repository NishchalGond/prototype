"""Export the UAE builders XLSX to a lightweight JSON for deployment."""
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.reference import load_reference

ref = load_reference(str(Path(__file__).resolve().parents[1] / "Builders data" / "UAE_Development_Builders.xlsx"))
data = []
for d in ref.developments:
    entry = {"name": d.name, "emirate": d.emirate}
    if d.region:
        entry["region"] = d.region
    if d.developer:
        entry["developer"] = d.developer
    if d.dev_type:
        entry["dev_type"] = d.dev_type
    if d.confidence:
        entry["confidence"] = d.confidence
    data.append(entry)

out = Path(__file__).resolve().parents[1] / "engine" / "resources" / "uae_developers.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=1)

has_dev = sum(1 for d in data if "developer" in d)
print(f"Exported {len(data)} developments ({has_dev} with named developer) -> {out}")
