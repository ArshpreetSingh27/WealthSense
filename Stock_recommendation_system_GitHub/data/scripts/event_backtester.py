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
# 3. SLOW-ALPHA BACKTESTER
# -----------------------------
def run_event_backtest(df, holding_period=7, friction=0.0012):
    print(f"Running Event-Driven Backtest (Holding: {holding_period} days, Friction: {friction*100}%)")
    
    dates = df.index.unique().sort_values()
    history = []
    
    # Portfolio is split into 'holding_period' slots, each rebalanced every 'holding_period' days
    slots = [None] * holding_period
    
    for i, date in enumerate(dates):
        slot_idx = i % holding_period
        day_data = df.loc[date]
        
        # Signal Generation (Top 5 / Bottom 5)
        day_data = day_data.sort_values("Pred_Neutral_Return", ascending=False)
        longs = day_data.head(5)["Stock"].tolist()
        shorts = day_data.tail(5)["Stock"].tolist()
        
        # Update current slot
        slots[slot_idx] = {"longs": longs, "shorts": shorts, "cost": friction}
        
        # Calculate daily P&L across all slots
        if i + 1 < len(dates):
            next_date = dates[i+1]
            next_day_data = df.loc[next_date].set_index("Stock")
            
            daily_pnl = 0
            active_slots = 0
            for sp in slots:
                if sp is None: continue
                active_slots += 1
                sp_ret = 0
                for s in sp["longs"]:
                    if s in next_day_data.index:
                        r = next_day_data.loc[s, "Return"]
                        if isinstance(r, pd.Series): r = r.iloc[0]
                        sp_ret += (1/10) * r # 5 longs + 5 shorts = 10 stocks
                for s in sp["shorts"]:
                    if s in next_day_data.index:
                        r = next_day_data.loc[s, "Return"]
                        if isinstance(r, pd.Series): r = r.iloc[0]
                        sp_ret -= (1/10) * r
                
                # Apply cost only on rebalance day for that slot
                daily_pnl += (1/holding_period) * (sp_ret - (sp["cost"] if slot_idx == slots.index(sp) else 0))
            
            history.append({"Date": next_date, "Return": daily_pnl})

    perf_df = pd.DataFrame(history).set_index("Date")
    cagr = ( (1 + perf_df["Return"]).prod() ** (252/len(perf_df)) ) - 1
    vol = perf_df["Return"].std() * np.sqrt(252)
    sharpe = (cagr - 0.05) / vol if vol > 0 else 0
    
    print(f"\n================================")
    print(f" EVENT-DRIVEN PERSISTENCE PERFORMANCE")
    print(f"================================")
    print(f"CAGR:         {cagr:.2%}")
    print(f"Sharpe Ratio: {sharpe:.2f}")
    print(f"Volatility:   {vol:.2%}")
    print(f"Max Drawdown: {((perf_df['Return'].cumsum() - perf_df['Return'].cumsum().cummax()).min()*100):.2f}%")
    print(f"================================\n")
    
    perf_df["Equity"] = (1 + perf_df["Return"]).cumprod()
    plt.figure(figsize=(10, 6))
    plt.plot(perf_df["Equity"], color='darkred')
    plt.title("Event-Driven Persistence Alpha (7-Day Holding)")
    plt.savefig(os.path.join(REPORTS_DIR, "event_validation.png"))

if __name__ == "__main__":
    run_event_backtest(df)
