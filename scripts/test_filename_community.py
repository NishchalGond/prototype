import sys
sys.path.insert(0, '.')
from pathlib import Path
from engine.processor import Processor

p = Processor(batch_size=100, enable_enrichment=True, reference_path=Path("engine/resources/uae_developers.json"))

test_files = [
    Path(r"C:\Users\USER\Downloads\Prototype\Dubai Hills Raw Work\Raw Batches\Batch 01 (5 files - Club Villas, DHE)\Club Villas.xlsx"),
    Path(r"C:\Users\USER\Downloads\Prototype\Dubai Hills Raw Work\Raw Batches\Batch 04 (5 files - Emerald Hills, Fairway, Golf Grove)\Fairway Vistas.xlsx"),
    Path(r"C:\Users\USER\Downloads\Prototype\Dubai Hills Raw Work\Raw Batches\Batch 11 (5 files - Parkway Vistas, Sidra)\Sidra 1 (c) 2022 June.xlsx"),
]

for tf in test_files:
    if not tf.exists():
        continue
    print(f"\n--- Testing: {tf.name} ---")
    rows = []
    def on_batch(b):
        rows.extend(b)
        return len(b)
    
    p.process(tf, source_name=tf.name, on_batch=on_batch)
    print(f"  Rows count: {len(rows)}")
    for r in rows[:3]:
        print(f"  -> Name: {r.get('name')} | Community: {r.get('community')} | Sub-Comm: {r.get('sub_community')} | Dev: {r.get('developer')}")
