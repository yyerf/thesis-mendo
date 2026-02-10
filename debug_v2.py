"""Debug V2 model - why is it performing worse?"""
import joblib
from pathlib import Path

# Load both models
v1 = joblib.load("training/symptom_classifier_v1.joblib")
v2 = joblib.load("training/symptom_classifier_v2.joblib")

print("="*70)
print("🔍 DEBUGGING V2 MODEL")
print("="*70)

# Compare model structures
print("\n📊 MODEL COMPARISON:")
print(f"V1 Training samples: {v1.get('train_samples', 'unknown')}")
print(f"V2 Training samples: {v2.get('train_samples', 'unknown')}")

print(f"\nV1 Threshold: {v1.get('threshold', 'not set')}")
print(f"V2 Threshold: {v2.get('threshold', 'not set')}")

print(f"\nV1 Vectorizer features: {len(v1['vectorizer'].get_feature_names_out())}")
print(f"V2 Vectorizer features: {len(v2['vectorizer'].get_feature_names_out())}")

# Test on "sepun ako"
test_text = "sepun ako"
print(f"\n🧪 TEST: '{test_text}'")

# V1 prediction
X_v1 = v1['vectorizer'].transform([test_text])
if hasattr(v1['classifier'], 'predict_proba'):
    probs_v1 = v1['classifier'].predict_proba(X_v1)[0]
    print(f"\nV1 Probabilities:")
    for i, prob in enumerate(probs_v1):
        if prob > 0.1:  # Show anything > 10%
            print(f"  {v1['label_binarizer'].classes_[i]:20s}: {prob:.3f}")

# V2 prediction
X_v2 = v2['vectorizer'].transform([test_text])
if hasattr(v2['classifier'], 'predict_proba'):
    probs_v2 = v2['classifier'].predict_proba(X_v2)[0]
    print(f"\nV2 Probabilities:")
    for i, prob in enumerate(probs_v2):
        if prob > 0.1:  # Show anything > 10%
            print(f"  {v2['label_binarizer'].classes_[i]:20s}: {prob:.3f}")

# Check threshold
threshold_v1 = v1.get('threshold', 0.5)
threshold_v2 = v2.get('threshold', 0.5)

print(f"\n🎯 PREDICTIONS (with threshold):")
v1_pred = [v1['label_binarizer'].classes_[i] for i, p in enumerate(probs_v1) if p >= threshold_v1]
v2_pred = [v2['label_binarizer'].classes_[i] for i, p in enumerate(probs_v2) if p >= threshold_v2]

print(f"V1 (threshold={threshold_v1}): {v1_pred}")
print(f"V2 (threshold={threshold_v2}): {v2_pred}")

print("\n" + "="*70)
print("💡 DIAGNOSIS:")
print("="*70)

if threshold_v2 > threshold_v1:
    print(f"⚠️  V2 has HIGHER threshold ({threshold_v2} vs {threshold_v1})")
    print("   This makes it MORE strict, detecting FEWER symptoms")
elif max(probs_v2) < threshold_v2:
    print(f"⚠️  V2's probabilities are too LOW for threshold {threshold_v2}")
    print("   Model might need lower threshold or better training")

print("\n🔧 SOLUTION:")
print("   1. Check if V2 threshold should be lower (try 0.3)")
print("   2. Review training data quality")
print("   3. Check if features are being extracted correctly")
