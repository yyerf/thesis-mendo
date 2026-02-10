"""
Setup for 3-way model comparison:
1. Baseline (no ML) 
2. ML v1 (2,171 samples)
3. ML v2 (3,671 samples - will train)

This script:
- Merges datasets
- Trains v2 model
- Creates comparison framework
"""

import json
from pathlib import Path

def check_current_setup():
    """Verify all files are in place."""
    
    base = Path(__file__).parent
    datasets_path = base.parent / "data" / "datasets"
    
    print("="*70)
    print("📋 CURRENT SETUP CHECK")
    print("="*70)
    
    # Check models
    v1_model = base / "symptom_classifier_v1.joblib"
    current_model = base / "symptom_classifier.joblib"
    metrics = base / "symptom_classifier_metrics.json"
    
    print("\n🔬 MODELS:")
    print(f"  {'✅' if v1_model.exists() else '❌'} symptom_classifier_v1.joblib (backup)")
    print(f"  {'✅' if current_model.exists() else '❌'} symptom_classifier.joblib (current)")
    
    if metrics.exists():
        data = json.load(open(metrics))
        print(f"\n📊 V1 MODEL STATS:")
        print(f"  Training samples: {data.get('train_samples', 'unknown')}")
        print(f"  Micro F1: {data.get('micro_f1', 0):.1%}")
        print(f"  Macro F1: {data.get('macro_f1', 0):.1%}")
    
    # Check datasets
    datasets = [
        ("symptom_eval.whole.jsonl", "Original dataset"),
        ("symptom_eval.tagalog_500.jsonl", "New Tagalog (500)"),
        ("symptom_eval.cebuano_500.jsonl", "New Cebuano (500)"),
        ("symptom_eval.english_500.jsonl", "New English (500)"),
    ]
    
    print(f"\n📁 DATASETS:")
    total = 0
    for filename, desc in datasets:
        filepath = datasets_path / filename
        if filepath.exists():
            count = sum(1 for line in open(filepath, encoding="utf-8") if line.strip())
            total += count
            print(f"  ✅ {desc:25s}: {count:,} samples")
        else:
            print(f"  ❌ {desc:25s}: NOT FOUND")
    
    print(f"\n  📊 TOTAL AVAILABLE: {total:,} samples")
    
    # Check step3_hybrid
    step3 = base.parent / "mendo_core" / "step3_hybrid.py"
    has_ml = False
    if step3.exists():
        content = step3.read_text()
        has_ml = "_predict_ml_classifier" in content
    
    print(f"\n🔧 INTEGRATION:")
    print(f"  {'✅' if has_ml else '❌'} ML classifier integrated in step3_hybrid.py")
    
    print("\n" + "="*70)
    
    if not has_ml:
        print("⚠️  WARNING: ML classifier not integrated in step3_hybrid.py")
        print("   Need to re-add ML classifier code that was reverted.")
    
    return {
        "v1_exists": v1_model.exists(),
        "current_exists": current_model.exists(),
        "total_samples": total,
        "ml_integrated": has_ml
    }

if __name__ == "__main__":
    status = check_current_setup()
    
    if not status["ml_integrated"]:
        print("\n🔧 NEXT STEP: Re-integrate ML classifier into step3_hybrid.py")
    elif status["total_samples"] < 3600:
        print("\n📦 NEXT STEP: Merge datasets")
    else:
        print("\n🏋️ NEXT STEP: Train v2 model on combined dataset")
