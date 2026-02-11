"""
DEMO: See TF-IDF and Logistic Regression in Action!

Run this to see EXACTLY what happens inside the ML model.

Usage:
    python demo_ml_internals.py
"""

import joblib
from pathlib import Path

# Load the trained model
model_path = Path(__file__).parent / "training" / "symptom_classifier_v3.joblib"

print("="*70)
print("🔬 MACHINE LEARNING DEMO: TF-IDF + Logistic Regression")
print("="*70)

# Load model
print("\n📂 Loading trained model...")
model = joblib.load(model_path)

vectorizer = model["vectorizer"]
classifier = model["classifier"]
label_binarizer = model["label_binarizer"]

print(f"✅ Model loaded: {model['version']} ({model['train_samples']:,} samples)")

# Test input
test_input = "sepun ako grabe"
print(f"\n📝 Test input: '{test_input}'")

# STEP 1: TF-IDF
print("\n" + "="*70)
print("STEP 1: TF-IDF (Text → Numbers)")
print("="*70)

X = vectorizer.transform([test_input])
print(f"✅ Converted to: {X.shape[1]:,} numbers (sparse matrix)")

# Show top features
feature_names = vectorizer.get_feature_names_out()
dense = X.toarray()[0]
word_scores = [(feature_names[i], dense[i]) for i in range(len(dense)) if dense[i] > 0]
word_scores.sort(key=lambda x: x[1], reverse=True)

print(f"\n📊 Top TF-IDF scores (non-zero):")
for word, score in word_scores[:10]:
    print(f"   '{word}': {score:.4f}")

if len(word_scores) > 10:
    print(f"   ... and {len(word_scores) - 10} more")

# STEP 2: Logistic Regression
print("\n" + "="*70)
print("STEP 2: Logistic Regression (Numbers → Probabilities)")
print("="*70)

# Get probabilities for each symptom
probs = classifier.predict_proba(X)[0]
symptom_probs = [(label_binarizer.classes_[i], probs[i]) 
                 for i in range(len(probs))]
symptom_probs.sort(key=lambda x: x[1], reverse=True)

print(f"\n📊 Symptom Probabilities:")
threshold = model["threshold"]
for symptom, prob in symptom_probs:
    status = "✅" if prob >= threshold else "❌"
    bar_length = int(prob * 50)  # Scale to 50 chars
    bar = "█" * bar_length + "░" * (50 - bar_length)
    print(f"   {status} {symptom:20s} {prob:5.1%} {bar}")

# STEP 3: Final Prediction
print("\n" + "="*70)
print("STEP 3: Apply Threshold & Get Final Prediction")
print("="*70)
print(f"\nThreshold: {threshold:.0%}")

detected = [s for s, p in symptom_probs if p >= threshold]
print(f"\n🎯 Final Prediction: {detected}")

if not detected:
    print("   (No symptoms detected above threshold)")

# Show the actual weights for top symptom
print("\n" + "="*70)
print("BONUS: Inside the Logistic Regression Model")
print("="*70)

if detected:
    top_symptom = detected[0]
    symptom_idx = list(label_binarizer.classes_).index(top_symptom)
    
    # Get coefficients for this symptom
    coef = classifier.estimators_[symptom_idx].coef_[0]
    
    # Show which words contributed most
    word_contributions = []
    for i, score in enumerate(dense):
        if score > 0:  # Only non-zero TF-IDF scores
            contribution = score * coef[i]
            word_contributions.append((feature_names[i], score, coef[i], contribution))
    
    word_contributions.sort(key=lambda x: abs(x[3]), reverse=True)
    
    print(f"\n🔍 Why '{top_symptom}' was predicted:")
    print(f"\n   Top contributing words:")
    print(f"   {'Word':<15} {'TF-IDF':<10} {'Weight':<10} {'Contribution':<15}")
    print(f"   {'-'*50}")
    
    for word, tfidf, weight, contrib in word_contributions[:10]:
        sign = "+" if contrib > 0 else ""
        print(f"   {word:<15} {tfidf:<10.4f} {weight:<10.4f} {sign}{contrib:<15.4f}")
    
    print(f"\n   💡 Formula: Contribution = TF-IDF × Weight")
    print(f"   💡 Final Score = Sum of all contributions")

# Interactive mode
print("\n" + "="*70)
print("🎮 Try Your Own Input!")
print("="*70)

while True:
    try:
        user_input = input("\n📝 Enter symptom text (or 'quit' to exit): ").strip()
        
        if user_input.lower() in ['quit', 'exit', 'q']:
            print("👋 Goodbye!")
            break
        
        if not user_input:
            continue
        
        # Process
        X = vectorizer.transform([user_input])
        probs = classifier.predict_proba(X)[0]
        
        # Show results
        print(f"\n📊 Results for: '{user_input}'")
        detected = []
        for i, prob in enumerate(probs):
            symptom = label_binarizer.classes_[i]
            if prob >= threshold:
                status = "✅"
                detected.append(symptom)
            else:
                status = "❌"
            
            if prob >= 0.05:  # Only show >5% for readability
                print(f"   {status} {symptom:20s} {prob:5.1%}")
        
        print(f"\n🎯 Detected: {detected if detected else 'None'}")
        
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        break
    except Exception as e:
        print(f"❌ Error: {e}")
