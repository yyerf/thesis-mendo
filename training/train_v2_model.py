"""
Train symptom_classifier_v2.joblib on expanded dataset (3,670 samples).

This is the v2 model with:
- Original 2,170 samples
- New 500 Tagalog samples (typos, slang, natural expressions)
- New 500 Cebuano samples (regional variations)
- New 500 English samples (colloquial patterns)

Expected improvements:
- Better typo handling ("sepun", "ubu", "hedache")
- Better multilingual support (Tagalog, Cebuano, English mix)
- Better slang/colloquial detection
"""

import json
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.multiclass import OneVsRestClassifier
from sklearn.preprocessing import MultiLabelBinarizer
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, f1_score
import joblib

def load_dataset(filepath):
    """Load JSONL dataset."""
    data = []
    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    return data

def train_v2_model():
    base_path = Path(__file__).parent
    dataset_path = base_path.parent / "data" / "datasets" / "symptom_eval.combined_v2.jsonl"
    
    print("="*70)
    print("🏋️  TRAINING SYMPTOM CLASSIFIER V2")
    print("="*70)
    
    # Load combined dataset
    print(f"\n📂 Loading dataset from: {dataset_path.name}")
    data = load_dataset(dataset_path)
    print(f"✅ Loaded {len(data):,} samples")
    
    # Extract texts and labels
    texts = [item["text"] for item in data]
    labels = [item["labels"] for item in data]
    
    # Binarize labels
    print("\n🔢 Binarizing labels...")
    mlb = MultiLabelBinarizer()
    y = mlb.fit_transform(labels)
    print(f"✅ Found {len(mlb.classes_)} unique symptom classes:")
    print(f"   {sorted(mlb.classes_)}")
    
    # Split data
    X_train, X_test, y_train, y_test = train_test_split(
        texts, y, test_size=0.15, random_state=42
    )
    print(f"\n📊 Dataset split:")
    print(f"   Training: {len(X_train):,} samples")
    print(f"   Testing:  {len(X_test):,} samples")
    
    # Vectorize
    print("\n🔤 Creating TF-IDF features...")
    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=(1, 3),
        min_df=2,
        sublinear_tf=True
    )
    X_train_vec = vectorizer.fit_transform(X_train)
    X_test_vec = vectorizer.transform(X_test)
    print(f"✅ Feature matrix shape: {X_train_vec.shape}")
    
    # Train classifier
    print("\n🤖 Training OneVsRestClassifier (LogisticRegression)...")
    classifier = OneVsRestClassifier(
        LogisticRegression(max_iter=1000, C=1.0, random_state=42),
        n_jobs=-1
    )
    classifier.fit(X_train_vec, y_train)
    print("✅ Training complete!")
    
    # Evaluate
    print("\n📈 Evaluating on test set...")
    y_pred = classifier.predict(X_test_vec)
    
    micro_f1 = f1_score(y_test, y_pred, average="micro")
    macro_f1 = f1_score(y_test, y_pred, average="macro")
    
    print(f"\n📊 PERFORMANCE METRICS:")
    print(f"   Micro F1: {micro_f1:.1%}")
    print(f"   Macro F1: {macro_f1:.1%}")
    
    # Save model
    model_path = base_path / "symptom_classifier_v2.joblib"
    metrics_path = base_path / "symptom_classifier_v2_metrics.json"
    
    print(f"\n💾 Saving model...")
    joblib.dump({
        "vectorizer": vectorizer,
        "classifier": classifier,
        "label_binarizer": mlb,
        "threshold": 0.20,  # Balanced threshold for good typo/dialect detection
        "version": "v2",
        "train_samples": len(data),
    }, model_path)
    print(f"✅ Model saved to: {model_path.name}")
    
    # Save metrics
    metrics = {
        "version": "v2",
        "train_samples": len(data),
        "test_samples": len(X_test),
        "micro_f1": float(micro_f1),
        "macro_f1": float(macro_f1),
        "classes": sorted(mlb.classes_.tolist()),
        "dataset_composition": {
            "original": 2170,
            "tagalog": 500,
            "cebuano": 500,
            "english": 500
        }
    }
    
    with open(metrics_path, "w") as f:
        json.dump(metrics, f, indent=2)
    print(f"✅ Metrics saved to: {metrics_path.name}")
    
    print("\n" + "="*70)
    print("✅ V2 MODEL TRAINING COMPLETE!")
    print("="*70)
    print(f"\n📊 Summary:")
    print(f"   Total samples: {len(data):,}")
    print(f"   Micro F1: {micro_f1:.1%}")
    print(f"   Macro F1: {macro_f1:.1%}")
    print(f"   Model file: {model_path.name}")
    
    return model_path, metrics

if __name__ == "__main__":
    train_v2_model()
