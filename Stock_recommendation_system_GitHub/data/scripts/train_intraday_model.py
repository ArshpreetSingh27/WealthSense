import os
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import accuracy_score
import warnings
warnings.filterwarnings('ignore')

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PROCESSED_DIR = os.path.join(BASE_DIR, "data", "processed")
csv_file = os.path.join(PROCESSED_DIR, "intraday_features.csv")

if not os.path.exists(csv_file):
    print("Intraday features file not found!")
    exit(1)

print(f"Loading intraday data from {csv_file}...")
df = pd.read_csv(csv_file)
df['Datetime'] = pd.to_datetime(df['Datetime'])
df = df.sort_values(by=['Datetime', 'Stock'])

target = "Target"
df['Stock'] = df['Stock'].astype('category')
features = ['RSI', 'Volatility', 'SMA_20_Ratio', 'Volume_Ratio'] # Simplified for intraday

# =========================
# RIGOROUS TIME-BASED TRAIN / TEST SPLIT
# =========================
# To prevent "cheating", we ensure the test set is strictly in the future relative to train.
unique_times = sorted(df['Datetime'].unique())
split_idx = int(len(unique_times) * 0.8)
split_date = unique_times[split_idx]

print(f"Splitting intraday data at {split_date} (80/20 temporal split)")

train_df = df[df['Datetime'] < split_date]
test_df = df[df['Datetime'] >= split_date]

X_train, y_train = train_df[features], train_df[target]
X_test, y_test = test_df[features], test_df[target]

model = lgb.LGBMClassifier(
    n_estimators=500,
    learning_rate=0.02,
    max_depth=5,
    num_leaves=31,
    random_state=42
)
model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    categorical_feature=['Stock'],
    callbacks=[lgb.early_stopping(stopping_rounds=50, verbose=False)]
)

df["Prob_Up"] = model.predict_proba(df[features])[:, 1]
df["Recommendation"] = df["Prob_Up"].apply(
    lambda x: "BUY" if x > 0.52 else "SELL" if x < 0.48 else "HOLD"
)

latest_date = df['Datetime'].max()
latest_recommendations = df[df['Datetime'] == latest_date].copy()
cols_to_save = ['Stock', 'Datetime', 'Prob_Up', 'Recommendation', 'RSI', 'Volatility']
latest_recommendations = latest_recommendations[cols_to_save]
latest_recommendations.rename(columns={'Datetime': 'Date'}, inplace=True)

output_file = os.path.join(PROCESSED_DIR, "latest_recommendations_intraday.json")
latest_recommendations.to_json(output_file, orient="records", date_format="iso")

print(f"Saved intraday recommendations to: {output_file}")
