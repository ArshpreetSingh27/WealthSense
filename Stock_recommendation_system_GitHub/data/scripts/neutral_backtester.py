import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_PATH = os.path.join(BASE_DIR, "data", "processed", "neutral_wf_results.csv")
REPORTS_DIR = os.path.join(BASE_DIR, "data", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# -----------------------------
# 2. LOAD DATA
# -----------------------------
df = pd.read_csv(RESULTS_PATH, index_col=0, parse_dates=True)
df = df.sort_index()

# -----------------------------
# 3. SECTOR-NEUTRAL BACKTESTER
# -----------------------------
def run_neutral_backtest(df, stocks_per_sector=1, slippage=0.0005):
    print(f"Running Sector-Neutral Backtest (Top/Bottom {stocks_per_sector} per Sector)...")
    
    dates = df.index.unique().sort_values()
    history = []
    
    positions = None
    
    for i, date in enumerate(dates):
        # 1. Rebalance every 5 days
        if i % 5 == 0:
            day_data = df.loc[date]
            day_data["Sector_Rank"] = day_data.groupby("Sector")["Pred_Neutral_Return"].rank(ascending=False)
            day_data["Sector_Rank_Inv"] = day_data.groupby("Sector")["Pred_Neutral_Return"].rank(ascending=True)
            
            longs = day_data[day_data["Sector_Rank"] <= stocks_per_sector]
            shorts = day_data[day_data["Sector_Rank_Inv"] <= stocks_per_sector]
            
            longs_w = 1 / longs["ATR_Ratio"]
            shorts_w = 1 / shorts["ATR_Ratio"]
            total_w = longs_w.sum() + shorts_w.sum()
            
            positions = {
                "longs": {s: longs_w[s]/total_w for s in longs.index},
                "shorts": {s: shorts_w[s]/total_w for s in shorts.index}
            }
            cost = slippage # Apply slippage only on rebalance
        else:
            cost = 0
            
        # 2. Calculate Today's Return (at date_t+1)
        if positions and i + 1 < len(dates):
            next_date = dates[i+1]
            next_day_data = df.loc[next_date]
            
            daily_ret = 0
            for s, w in positions["longs"].items():
                if s in next_day_data.index: daily_ret += w * next_day_data.loc[s, "Return"]
            for s, w in positions["shorts"].items():
                if s in next_day_data.index: daily_ret -= w * next_day_data.loc[s, "Return"]
            
            history.append({"Date": next_date, "Return": daily_ret - cost})

    perf_df = pd.DataFrame(history).set_index("Date")
    perf_df["Equity"] = (1 + perf_df["Return"]).cumprod()
    
    # Metrics
    cagr = (perf_df["Equity"].iloc[-1] ** (252 / len(perf_df))) - 1
    vol = perf_df["Return"].std() * np.sqrt(252)
    sharpe = (cagr - 0.05) / vol if vol != 0 else 0
    
    print(f"\n================================")
    print(f" STAT-ARB NEUTRAL PERFORMANCE")
    print(f"================================")
    print(f"CAGR:         {cagr:.2%}")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Volatility:   {vol:.2%}")
    print(f"Max Drawdown: {((perf_df['Equity'] - perf_df['Equity'].cummax()) / perf_df['Equity'].cummax()).min():.2%}")
    print(f"================================\n")
    
    perf_df.to_csv(os.path.join(REPORTS_DIR, "stat_arb_equity.csv"))

if __name__ == "__main__":
    run_neutral_backtest(df)
