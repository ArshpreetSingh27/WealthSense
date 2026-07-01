import os
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import accuracy_score, confusion_matrix, classification_report
import warnings
warnings.filterwarnings('ignore')

# =========================
# PATH SETUP
# =========================
FILE_PATH = os.path.abspath(__file__)
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))

DATA_DIR = os.path.join(BASE_DIR, "data")
PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
csv_file = os.path.join(PROCESSED_DIR, "nifty50_features.csv")

assert os.path.exists(csv_file), "CSV file not found! Run process_all_stocks.py first."

# =========================
# LOAD DATA
# =========================
print(f"Loading data from {csv_file}...")
df = pd.read_csv(csv_file)

# Parse Dates properly
df['Date'] = pd.to_datetime(df['Date'])
df = df.sort_values(by=['Date', 'Stock']).reset_index(drop=True)

# Define Target
target = "Target"

# =========================
# PREPARE CATEGORICALS
# =========================
# Convert Stock ticker to categorical for LightGBM
df['Stock'] = df['Stock'].astype('category')

# Define features (Exclude Target, Date, and analytical columns used for backtesting)
features = [col for col in df.columns if col not in [target, 'Date', 'Forward_Return_5d', 'High_Low', 'High_CP', 'Low_CP', 'TR', 'ATR', '52W_High', '52W_Low', 'MACD', 'MACD_signal']]

print(f"Using {len(features)} features: {features}")

# =========================
# RIGOROUS TIME-BASED TRAIN / TEST SPLIT
# =========================
# To prevent "cheating" (look-ahead bias), we must ensure that the test set
# comes strictly AFTER the training set in time.
unique_dates = sorted(df['Date'].unique())
split_idx = int(len(unique_dates) * 0.8)
split_date = unique_dates[split_idx]

print(f"Splitting data at {split_date.date()} (80/20 temporal split)")

train_df = df[df['Date'] < split_date]
test_df = df[df['Date'] >= split_date]

X_train = train_df[features]
y_train = train_df[target]

X_test = test_df[features]
y_test = test_df[target]

print(f"Train shapes: X={X_train.shape}, y={y_train.shape}")
print(f"Test shapes: X={X_test.shape}, y={y_test.shape}")

# =========================
# LIGHTGBM MODEL
# =========================
# Added class_weight='balanced' to handle any market drift bias
model = lgb.LGBMClassifier(
    objective='binary',
    n_estimators=1000,
    learning_rate=0.02,
    max_depth=7,
    num_leaves=63,
    feature_fraction=0.8,
    bagging_fraction=0.8,
    bagging_freq=5,
    random_state=42,
    n_jobs=-1
)

print("Training boosted model...")
model.fit(
    X_train, y_train,
    eval_set=[(X_test, y_test)],
    categorical_feature=['Stock'],
    callbacks=[lgb.early_stopping(stopping_rounds=100, verbose=True)]
)

# =========================
# EVALUATION (ON OUT OF SAMPLE TEST DATA)
# =========================
print("\n--- TEST SET EVALUATION ---")
y_pred = model.predict(X_test)

print("\nAccuracy:", accuracy_score(y_test, y_pred))
print("\nConfusion Matrix:\n", confusion_matrix(y_test, y_pred))
print("\nClassification Report:\n", classification_report(y_test, y_pred))

# =========================
# FULL DATA PREDICTIONS & RECOMMENDATION LOGIC
# =========================
# Get probabilities for the entire dataset to save for the frontend
df["Prob_Up"] = model.predict_proba(df[features])[:, 1]

# Adjust thresholds to be stricter since class_weight='balanced' centers predictions near 0.5
df["Recommendation"] = df["Prob_Up"].apply(
    lambda x: "BUY" if x > 0.55 else "SELL" if x < 0.45 else "HOLD"
)

# =========================
# SAVE LATEST RECOMMENDATIONS (FOR FRONTEND)
# =========================
# The frontend only cares about the latest available date for each stock
latest_date = df['Date'].max()
latest_recommendations = df[df['Date'] == latest_date].copy()

# Select columns useful for the UI
cols_to_save = ['Stock', 'Date', 'Prob_Up', 'Recommendation', 'Return', 'RSI', 'Volatility']
latest_recommendations = latest_recommendations[cols_to_save]

# Sort by strongest BUY signals
latest_recommendations = latest_recommendations.sort_values(by="Prob_Up", ascending=False)

output_file = os.path.join(PROCESSED_DIR, "latest_recommendations.json")
latest_recommendations.to_json(output_file, orient="records", date_format="iso")

print(f"\nSaved {len(latest_recommendations)} latest recommendations to: {output_file}")
print("\nTop 5 BUY Signals for tomorrow:")
print(latest_recommendations.head(5)[['Stock', 'Recommendation', 'Prob_Up']])
