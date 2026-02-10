"""
Merge datasets for v2 model training.

Combines:
- Original: symptom_eval.whole.jsonl (2,170 samples)
- New Tagalog: symptom_eval.tagalog_500.jsonl (500 samples)  
- New Cebuano: symptom_eval.cebuano_500.jsonl (500 samples)
- New English: symptom_eval.english_500.jsonl (500 samples)

Output: symptom_eval.combined_v2.jsonl (3,670 samples total)
"""

import json
from pathlib import Path

def merge_datasets():
    base_path = Path(__file__).parent.parent / "data" / "datasets"
    
    datasets = [
        ("symptom_eval.whole.jsonl", "Original"),
        ("symptom_eval.tagalog_500.jsonl", "New Tagalog"),
        ("symptom_eval.cebuano_500.jsonl", "New Cebuano"),
        ("symptom_eval.english_500.jsonl", "New English"),
    ]
    
    combined = []
    stats = {}
    
    print("="*70)
    print("📦 MERGING DATASETS")
    print("="*70)
    
    for filename, label in datasets:
        filepath = base_path / filename
        if not filepath.exists():
            print(f"⚠️  {label:15s}: NOT FOUND - {filename}")
            continue
        
        count = 0
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    combined.append(json.loads(line))
                    count += 1
        
        stats[label] = count
        print(f"✅ {label:15s}: {count:,} samples")
    
    # Write combined
    output = base_path / "symptom_eval.combined_v2.jsonl"
    with open(output, "w", encoding="utf-8") as f:
        for entry in combined:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    
    print("="*70)
    print(f"📊 TOTAL: {len(combined):,} samples")
    print(f"✅ Saved to: {output.name}")
    print("="*70)
    
    return output, len(combined), stats

if __name__ == "__main__":
    output_path, total, stats = merge_datasets()
    print(f"\\n✅ Ready to train v2 model on {total:,} samples!")
