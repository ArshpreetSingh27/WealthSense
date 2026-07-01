import pandas as pd
import lightgbm as lgb
from sklearn.metrics import precision_score, accuracy_score
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
csv_file = os.path.join(BASE_DIR, "data", "processed", "nifty50_features.csv")

df = pd.read_csv(csv_file)
df['Stock'] = df['Stock'].astype('category')

target = 'Target'
features = [col for col in df.columns if col not in [target, 'Date', 'Forward_Return_5d']]

split_idx = int(len(df) * 0.8)
df_train = df[:split_idx]
df_test = df[split_idx:]

model = lgb.LGBMClassifier(n_estimators=300, random_state=42)
model.fit(df_train[features], df_train[target])

probs = model.predict_proba(df_test[features])[:, 1]
preds = (probs > 0.5).astype(int)

print(f"Base Accuracy: {accuracy_score(df_test[target], preds):.4f}")

print("\n--- Precision by Conviction ---")
for t in [0.50, 0.52, 0.53, 0.54, 0.545, 0.55]:
    mask = probs > t
    if mask.any():
        p = precision_score(df_test[target][mask], [1]*mask.sum())
        count = mask.sum()
        print(f"Threshold {t}: Precision={p:.4f} (Count: {count})")
    else:
        print(f"Threshold {t}: No signals")
