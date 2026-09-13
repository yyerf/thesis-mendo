#!/usr/bin/env python3
"""Test elliptical/abbreviated list structure."""

import sys
sys.path.insert(0, ".")

from mendo_core.prediction_pipeline import predict_symptoms

# Test case from user
user_text = "sakit akong ulo, tiyan, ngipon, pero naa koy sipon"

print(f"Testing: {user_text}")
print("=" * 80)

report = predict_symptoms(user_text)
symptoms = report["final"]["symptoms"]

print(f"\nFinal symptoms: {symptoms}")

print("\n" + "=" * 80)
print("ANALYSIS:")
print("=" * 80)

print("\nSentence structure (elliptical/abbreviated list):")
print("  'sakit akong ulo,' → HEADACHE")
print("  'tiyan,' → should be understood as 'sakit akong tiyan' (STOMACH_ACHE)")
print("  'ngipon,' → should be understood as 'sakit akong ngipon' (TOOTHACHE)")
print("  'pero naa koy sipon' → RUNNY_NOSE (contrast word cancels negation)")

print("\nThis is an ELLIPSIS: the prefix 'sakit akong' is implied for later items")
print("Common in natural language: 'I have a headache, stomach ache, toothache'")
print("                          = 'I have a headache, a stomach ache, a toothache'")

print("\n" + "=" * 80)
print("EXPECTED vs ACTUAL:")
print("=" * 80)
print(f"Expected: ['HEADACHE', 'STOMACH_ACHE', 'TOOTHACHE', 'RUNNY_NOSE']")
print(f"Actual:   {symptoms}")

if set(symptoms) == {"HEADACHE", "STOMACH_ACHE", "TOOTHACHE", "RUNNY_NOSE"}:
    print("\n✅ CORRECT - All symptoms detected from elliptical list")
else:
    missing = set(["HEADACHE", "STOMACH_ACHE", "TOOTHACHE", "RUNNY_NOSE"]) - set(symptoms)
    extra = set(symptoms) - {"HEADACHE", "STOMACH_ACHE", "TOOTHACHE", "RUNNY_NOSE"}
    if missing:
        print(f"\n❌ MISSING: {missing}")
    if extra:
        print(f"\n❌ EXTRA: {extra}")

print("\n" + "=" * 80)
print("NEGATION TEST:")
print("=" * 80)

# Test with negation
neg_text = "wala koy sakit sa ulo, tiyan, ngipon, pero naa koy sipon"
print(f"\nNegated version: {neg_text}")

neg_report = predict_symptoms(neg_text)
neg_symptoms = neg_report["final"]["symptoms"]

print(f"Final symptoms: {neg_symptoms}")
print(f"\nExpected: ['RUNNY_NOSE'] only (ulo, tiyan, ngipon all negated)")
print(f"Actual:   {neg_symptoms}")

if neg_symptoms == ["RUNNY_NOSE"]:
    print("\n✅ CORRECT - Elliptical list items all negated")
else:
    print("\n❌ WRONG - Some elliptical items not negated")
