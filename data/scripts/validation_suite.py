import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_PATH = os.path.join(BASE_DIR, "data", "processed", "midcap_wf_results.csv")
REPORTS_DIR = os.path.join(BASE_DIR, "data", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# -----------------------------
# 2. LOAD DATA
# -----------------------------
df = pd.read_csv(RESULTS_PATH, parse_dates=["Date"])
df = df.set_index("Date").sort_index()

# -----------------------------
# 3. MIDCAP VALIDATION
# -----------------------------
def run_midcap_validation(df, lag=1, friction=0.0012):
    print(f"Running Fixed Midcap Validation (Lag: T+{lag}, Friction: {friction*100}%)")
    
    dates = df.index.unique().sort_values()
    history = []
    
    positions = None
    
    for i in range(len(dates) - lag):
        date_t = dates[i]
        date_exec = dates[i + lag]
        
        # Rebalance every 5 days
        if i % 5 == 0:
            day_data = df.loc[date_t]
            day_data = day_data.sort_values("Pred_Neutral_Return", ascending=False)
            longs = day_data.head(10)["Stock"].tolist()
            shorts = day_data.tail(10)["Stock"].tolist()
            positions = {"longs": longs, "shorts": shorts}
            cost = friction
        else:
            cost = 0
            
        if positions:
            exec_data = df.loc[date_exec].set_index("Stock")
            daily_ret = 0
            for s in positions["longs"]:
                if s in exec_data.index:
                    r = exec_data.loc[s, "Return"]
                    if isinstance(r, pd.Series): r = r.iloc[0]
                    daily_ret += (1/20) * r
            for s in positions["shorts"]:
                if s in exec_data.index:
                    r = exec_data.loc[s, "Return"]
                    if isinstance(r, pd.Series): r = r.iloc[0]
                    daily_ret -= (1/20) * r
            
            history.append({"Date": date_exec, "Return": daily_ret - cost})

    perf_df = pd.DataFrame(history).set_index("Date")
    # CAGR
    total_ret = (1 + perf_df["Return"]).prod()
    cagr = (total_ret ** (252/len(perf_df))) - 1 if len(perf_df) > 0 else 0
    vol = perf_df["Return"].std() * np.sqrt(252)
    sharpe = (cagr - 0.05) / vol if vol > 0 else 0
    
    print(f"\n================================")
    print(f" MIDCAP POST-COST PERFORMANCE")
    print(f"================================")
    print(f"CAGR:         {cagr:.2%}")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Volatility:   {vol:.2%}")
    print(f"================================\n")
    
    perf_df["Equity"] = (1 + perf_df["Return"]).cumprod()
    plt.figure(figsize=(10, 6))
    plt.plot(perf_df["Equity"], color='purple')
    plt.title("Midcap Inefficiency Alpha (Post-Costs)")
    plt.savefig(os.path.join(REPORTS_DIR, "midcap_validation.png"))

if __name__ == "__main__":
    run_midcap_validation(df)
