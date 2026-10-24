import os
import joblib
import pandas as pd
import matplotlib.pyplot as plt

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
MODEL_DIR = os.path.join(BASE_DIR, "data", "models")

# Load model and features
model = joblib.load(os.path.join(MODEL_DIR, "lgb_ranking.pkl"))
features = joblib.load(os.path.join(MODEL_DIR, "ranking_features.pkl"))

# Get importance
importance = pd.DataFrame({
    'feature': features,
    'importance': model.feature_importances_
}).sort_values(by='importance', ascending=False)

print("\n================================")
print(" FEATURE IMPORTANCE ANALYSIS")
print("================================")
print(importance)
print("================================\n")

# Identify bottom 5 features
bottom_5 = importance.tail(5)['feature'].tolist()
print(f"Suggested for pruning (Noise): {bottom_5}")
