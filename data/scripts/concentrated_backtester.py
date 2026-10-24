import os
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

# -----------------------------
# 1. PATH SETUP
# -----------------------------
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
RESULTS_PATH = os.path.join(BASE_DIR, "data", "processed", "event_wf_results.csv")
REPORTS_DIR = os.path.join(BASE_DIR, "data", "reports")
os.makedirs(REPORTS_DIR, exist_ok=True)

# -----------------------------
# 2. LOAD DATA
# -----------------------------
df = pd.read_csv(RESULTS_PATH, parse_dates=["Date"])
df = df.set_index("Date").sort_index()

# -----------------------------
# 3. CONCENTRATED BACKTESTER
# -----------------------------
def run_concentrated_backtest(df, holding_period=7, friction=0.0012, top_n=3, hurdle=0.005):
    print(f"Running Alpha Concentration (Top {top_n}, Hurdle: {hurdle*100}%)")
    
    dates = df.index.unique().sort_values()
    history = []
    slots = [None] * holding_period
    
    for i, date in enumerate(dates):
        slot_idx = i % holding_period
        day_data = df.loc[date]
        
        # 1. Filter by Hurdle
        valid_longs = day_data[day_data["Pred_Neutral_Return"] > hurdle]
        valid_shorts = day_data[day_data["Pred_Neutral_Return"] < -hurdle]
        
        # 2. Select Top N
        longs_df = valid_longs.sort_values("Pred_Neutral_Return", ascending=False).head(top_n)
        shorts_df = valid_shorts.sort_values("Pred_Neutral_Return", ascending=True).head(top_n)
        
        if len(longs_df) > 0 or len(shorts_df) > 0:
            longs_df = longs_df.set_index("Stock")
            shorts_df = shorts_df.set_index("Stock")
            
            # Conviction Sizing
            longs_df["Conf_Mult"] = 1.0 + (longs_df["PEAD_Signal"] * 0.5) + (longs_df["Block_Deal_Signal"] * 0.5)
            longs_df["Conf_Mult"] += (longs_df["Sentiment_Score"] > 0.2).astype(int) * 0.5
            
            shorts_df["Conf_Mult"] = 1.0 + (shorts_df["PEAD_Signal"] * 0.5) + (shorts_df["Block_Deal_Signal"] * 0.5)
            shorts_df["Conf_Mult"] += (shorts_df["Sentiment_Score"] < -0.2).astype(int) * 0.5
            
            l_weights = (longs_df["Conf_Mult"] / longs_df["ATR_Ratio"])
            s_weights = (shorts_df["Conf_Mult"] / shorts_df["ATR_Ratio"])
            
            total_w = l_weights.sum() + s_weights.sum()
            if total_w > 0:
                slots[slot_idx] = {
                    "longs": {s: l_weights[s]/total_w for s in longs_df.index},
                    "shorts": {s: s_weights[s]/total_w for s in shorts_df.index},
                    "cost": friction
                }
            else:
                slots[slot_idx] = None
        else:
            slots[slot_idx] = None
            
        # 3. Daily P&L calculation
        if i + 1 < len(dates):
            next_date = dates[i+1]
            next_day_data = df.loc[next_date].set_index("Stock")
            
            daily_pnl = 0
            for sp in slots:
                if sp is None: continue
                sp_ret = 0
                for s, w in sp["longs"].items():
                    if s in next_day_data.index:
                        r = next_day_data.loc[s, "Return"]
                        if isinstance(r, pd.Series): r = r.iloc[0]
                        sp_ret += w * r
                for s, w in sp["shorts"].items():
                    if s in next_day_data.index:
                        r = next_day_data.loc[s, "Return"]
                        if isinstance(r, pd.Series): r = r.iloc[0]
                        sp_ret -= w * r
                
                daily_pnl += (1/holding_period) * (sp_ret - (sp["cost"] if slot_idx == slots.index(sp) else 0))
            
            history.append({"Date": next_date, "Return": daily_pnl})

    perf_df = pd.DataFrame(history).set_index("Date")
    cagr = ( (1 + perf_df["Return"]).prod() ** (252/len(perf_df)) ) - 1
    vol = perf_df["Return"].std() * np.sqrt(252)
    sharpe = (cagr - 0.05) / vol if vol > 0 else 0
    
    print(f"\n================================")
    print(f" CONCENTRATED ALPHA PERFORMANCE")
    print(f"================================")
    print(f"CAGR:         {cagr:.2%}")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Volatility:   {vol:.2%}")
    print(f"================================\n")
    
    perf_df["Equity"] = (1 + perf_df["Return"]).cumprod()
    plt.figure(figsize=(10, 6))
    plt.plot(perf_df["Equity"], color='blue')
    plt.title("Concentrated Alpha Performance")
    plt.savefig(os.path.join(REPORTS_DIR, "concentrated_alpha.png"))

if __name__ == "__main__":
    run_concentrated_backtest(df, top_n=5, hurdle=0.01)
