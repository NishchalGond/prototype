"""Distil the property export into the index committed with the code.

    python scripts/build_property_index.py

The Property Finder export is ~23MB across several CSVs and is gitignored, so a
clean clone enriches no Property Type at all. Only the distilled lookups are
needed at runtime -- a few thousand building and community entries, not 90,807
listings -- and those are small enough to commit.

Run after refreshing the export. The result is deterministic: same input, same
file, so a no-op run leaves the working tree clean.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.property_reference import load_property_reference  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "propertyfiinder"
OUT = ROOT / "engine" / "resources" / "property_index.json"


def main() -> int:
    if not SOURCE.exists():
        print(f"No export at {SOURCE}; nothing to build.")
        return 1

    ref = load_property_reference(SOURCE)
    if not len(ref):
        print("Export produced an empty index; refusing to overwrite.")
        return 1

    # sort_keys so an unchanged export produces a byte-identical file and does
    # not show up as a diff.
    OUT.write_text(json.dumps(ref.to_index(), sort_keys=True), encoding="utf-8")
    print(f"{ref.stats()}\n-> {OUT.relative_to(ROOT)} ({OUT.stat().st_size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
