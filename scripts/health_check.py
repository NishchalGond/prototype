"""Full system health check."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

print("=== 1. Reference Data (Developer Enrichment) ===")
from engine.reference import load_reference, enrich, _JSON_FALLBACK

print(f"  JSON fallback path: {_JSON_FALLBACK}")
print(f"  JSON exists: {_JSON_FALLBACK.exists()}")

ROOT = Path(__file__).resolve().parents[1]
ref = load_reference(str(ROOT / "Builders data" / "UAE_Development_Builders.xlsx"))
print(f"  Developments loaded: {len(ref)}")

# Test enrichment
fields = {"Community": "Dubai Hills - Park", "Sub-Community": "MULBERRY at PARK HEIGHTS",
          "Project": "MULBERRY at PARK HEIGHTS", "Developer": "", "Property Type": ""}
enriched = enrich(fields, ref)
dev = fields.get("Developer", "")
print(f"  Test: Dubai Hills -> Developer: {dev}")
print(f"  Enriched fields: {enriched}")
assert dev, "FAIL: Developer enrichment did not work!"

print()
print("=== 2. JSON Fallback Test (simulating Railway) ===")
from engine.reference import _load_from_json
ref2 = _load_from_json(_JSON_FALLBACK)
print(f"  JSON fallback loaded: {len(ref2)} developments")
fields2 = {"Community": "Arabian Ranches", "Developer": "", "Property Type": ""}
e2 = enrich(fields2, ref2)
dev2 = fields2.get("Developer", "")
print(f"  Arabian Ranches -> Developer: {dev2}")
assert dev2, "FAIL: JSON fallback enrichment did not work!"

print()
print("=== 3. Engine Processor ===")
from engine.processor import Processor
p = Processor(batch_size=1000, enable_enrichment=True,
              reference_path=ROOT / "Builders data" / "UAE_Development_Builders.xlsx")
print(f"  Processor initialized, ref={len(p.ref)} developments")

print()
print("=== 4. Outreach Validation Logic ===")
from engine import validation as V

def _has_contact(row: dict) -> bool:
    return bool(row.get("mobile_1") or row.get("mobile_2") or row.get("mobile_3") or row.get("email_address"))

# Record with name + phone -> VALID
fields3 = {"Name": "John Doe", "Mobile 1": "+971551234567", "Community": "Dubai Hills"}
row3, _ = V.transform(fields3, {})
has_name3 = bool(row3.get("name") and str(row3.get("name")).strip())
has_contact3 = _has_contact(row3)
print(f"  Name+Phone: has_name={has_name3}, has_contact={has_contact3} -> should be VALID")
assert has_name3 and has_contact3, "FAIL"

# Record with name + secondary mobile only -> VALID
fields3b = {"Name": "Ali Hassan", "Mobile 2": "+971509876543", "Community": "Downtown Dubai"}
row3b, _ = V.transform(fields3b, {})
has_name3b = bool(row3b.get("name") and str(row3b.get("name")).strip())
has_contact3b = _has_contact(row3b)
print(f"  Name+Mobile 2: has_name={has_name3b}, has_contact={has_contact3b} -> should be VALID")
assert has_name3b and has_contact3b, "FAIL"

# Record with name only -> INCOMPLETE
fields4 = {"Name": "Jane Doe", "Community": "Dubai Hills"}
row4, _ = V.transform(fields4, {})
has_name4 = bool(row4.get("name") and str(row4.get("name")).strip())
has_contact4 = _has_contact(row4)
print(f"  Name only:  has_name={has_name4}, has_contact={has_contact4} -> should be INCOMPLETE")
assert has_name4 and not has_contact4, "FAIL"

# Record with no name -> INCOMPLETE
fields5 = {"Mobile 1": "+971551234567"}
row5, _ = V.transform(fields5, {})
has_name5 = bool(row5.get("name") and str(row5.get("name")).strip())
has_contact5 = _has_contact(row5)
print(f"  Phone only: has_name={has_name5}, has_contact={has_contact5} -> should be INCOMPLETE")
assert not has_name5 and has_contact5, "FAIL"

print()
print("=== 5. Git Status ===")
import subprocess
result = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, cwd=str(ROOT))
changed = result.stdout.strip().split("\n") if result.stdout.strip() else []
print(f"  Uncommitted changes: {len(changed)} files")
for c in changed[:15]:
    print(f"    {c}")
if len(changed) > 15:
    print(f"    ... and {len(changed) - 15} more")

# Check JSON is tracked
result2 = subprocess.run(["git", "check-ignore", "engine/resources/uae_developers.json"],
                         capture_output=True, text=True, cwd=str(ROOT))
json_ignored = result2.returncode == 0
print(f"  uae_developers.json gitignored: {json_ignored}")
if json_ignored:
    print("  WARNING: JSON reference file is gitignored and won't deploy to Railway!")
else:
    print("  OK: JSON reference file will deploy to Railway")

print()
print("=== ALL CHECKS PASSED ===")
