import json
import os
import random
import tempfile
import pandas as pd
from datetime import date, datetime
from risk_harden import RiskHarden

class PaperTrader:
    def __init__(self, portfolio_path="data/paper_portfolio.json", log_path=None):
        self.portfolio_path = portfolio_path
        self.log_path = log_path or os.path.join(os.path.dirname(portfolio_path), "trades_log.csv")
        self.load_portfolio()
        
    def load_portfolio(self):
        if os.path.exists(self.portfolio_path):
            with open(self.portfolio_path, "r") as f:
                self.data = json.load(f)
        else:
            self.data = {
                "capital": 1000000, # Initial Capital
                "cash": 1000000,
                "positions": {},    # {Ticker: {qty, entry_price, date, side, reason}}
                "pending_signals": [],
                "equity_history": [],
                "trades": []
            }
        # Ensure cash is initialized if loading old schema
        if "cash" not in self.data:
            self.data["cash"] = self.data.get("capital", 1000000)

    def save_portfolio(self):
        directory = os.path.dirname(os.path.abspath(self.portfolio_path))
        os.makedirs(directory, exist_ok=True)
        temporary_path = None
        try:
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=directory, delete=False) as output:
                temporary_path = output.name
                json.dump(self.data, output, indent=4)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_path, self.portfolio_path)
        finally:
            if temporary_path and os.path.exists(temporary_path):
                os.unlink(temporary_path)

    def log_trade_csv(self, trade_data):
        """
        Logs a trade to a CSV file for long-term tracking.
        """
        df = pd.DataFrame([trade_data])
        if not os.path.exists(self.log_path):
            df.to_csv(self.log_path, index=False)
        else:
            df.to_csv(self.log_path, mode='a', header=False, index=False)

    def execute_pending_trades(self, current_prices, current_market_date=None):
        """
        Executes signals that were queued from the previous day (T+1 Execution).
        """
        rh = RiskHarden()
        execution_count = 0
        
        # Signals are stored in pending_signals
        signals_to_exec = self.data.get("pending_signals", [])
        remaining_signals = []
        market_day = date.fromisoformat(current_market_date) if current_market_date else date.today()
        try:
            signal_day = date.fromisoformat(self.data.get("pending_market_date", ""))
        except (TypeError, ValueError):
            signal_day = None
        if signals_to_exec and (signal_day is None or not 0 < (market_day - signal_day).days <= 4):
            print("[WARNING] Discarding undated or stale pending signals.")
            self.data["pending_signals"] = []
            self.data["pending_market_date"] = None
            self.save_portfolio()
            return 0

        for s in signals_to_exec:
            ticker = s["ticker"]
            if ticker not in current_prices:
                print(f"[WARNING] No price data for {ticker}, skipping execution.")
                remaining_signals.append(s)
                continue
            
            if ticker in self.data["positions"]:
                print(f"[INFO] Already have a position in {ticker}, skipping.")
                continue

            price = current_prices[ticker]
            if price <= 0:
                print(f"[WARNING] Invalid price for {ticker}, skipping execution.")
                remaining_signals.append(s)
                continue
            
            # 1. Realistic Slippage
            vol = s.get("vol_20", 0.02)
            adv = s.get("adv_30", 1e8)
            trade_size = s.get("allocation", 50000)
            slippage = rh.calculate_dynamic_slippage(vol, trade_size, adv)
            
            # 2. Execution Price (Buy at Price + Slippage, Sell at Price - Slippage)
            side = s.get("signal", "LONG")
            exec_price = price * (1 + slippage if side == "LONG" else 1 - slippage)
            
            # 3. Partial Fill Simulation (Randomly fill 80-100% for realism)
            fill_pct = random.uniform(0.8, 1.0) if adv < 1e7 else 1.0
            qty = int(s.get("quantity", trade_size / exec_price) * fill_pct)
            if qty <= 0:
                print(f"[WARNING] Non-positive quantity for {ticker}, skipping execution.")
                continue
            
            cost = qty * exec_price
            if self.data["cash"] >= cost:
                self.data["cash"] -= cost
                self.data["positions"][ticker] = {
                    "qty": qty,
                    "entry_price": exec_price,
                    "date": datetime.now().strftime("%Y-%m-%d"),
                    "side": side,
                    "reason": s.get("reason", "SIGNAL")
                }
                
                trade_log = {
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "ticker": ticker,
                    "type": "BUY" if side == "LONG" else "SHORT",
                    "qty": qty,
                    "price": round(exec_price, 2),
                    "expected_return": s.get("pred_return", 0),
                    "reason": s.get("reason", "SIGNAL"),
                    "slippage": round(slippage, 4),
                    "cash_remaining": round(self.data["cash"], 2)
                }
                self.data["trades"].append(trade_log)
                self.log_trade_csv(trade_log)
                execution_count += 1
            else:
                print(f"[WARNING] Insufficient cash for {ticker}")

        self.data["pending_signals"] = remaining_signals
        if not remaining_signals:
            self.data["pending_market_date"] = None
        self.save_portfolio()
        print(f"[SUCCESS] Executed {execution_count} pending trades.")
        return execution_count

    def update_and_monitor(self, current_prices):
        """
        Updates portfolio valuation and checks for exit triggers (Stops/Alpha Decay).
        """
        rh = RiskHarden()
        exits = []
        
        for ticker, pos in list(self.data["positions"].items()):
            if ticker in current_prices:
                current_val = current_prices[ticker]
                days_held = (datetime.now() - datetime.strptime(pos["date"], "%Y-%m-%d")).days
                
                # Side-aware PnL calculation
                if pos["side"] == "LONG":
                    pnl_pct = (current_val - pos["entry_price"]) / pos["entry_price"]
                else: # SHORT
                    pnl_pct = (pos["entry_price"] - current_val) / pos["entry_price"]
                
                # Check Exit Conditions
                reason = None
                if rh.check_alpha_decay(days_held, pnl_pct):
                    reason = "ALPHA DECAY"
                elif pnl_pct < -0.05: # 5% Hard Stop
                    reason = "STOP LOSS"
                elif pnl_pct > 0.15: # 15% Take Profit
                    reason = "TAKE PROFIT"
                
                if reason:
                    self.close_position(ticker, current_val, reason)
                    exits.append(ticker)

        # Update Equity History
        total_equity = self.calculate_total_equity(current_prices)
        self.data["equity_history"].append({
            "date": datetime.now().strftime("%Y-%m-%d"),
            "equity": round(total_equity, 2),
            "cash": round(self.data["cash"], 2)
        })
        self.save_portfolio()
        return exits

    def calculate_total_equity(self, current_prices):
        equity = self.data["cash"]
        for ticker, pos in self.data["positions"].items():
            price = current_prices.get(ticker, pos["entry_price"])
            if pos["side"] == "LONG":
                equity += pos["qty"] * price
            else: # SHORT
                # Entry notional was reserved from cash when the short opened.
                equity += pos["entry_price"] * pos["qty"]
                equity += (pos["entry_price"] - price) * pos["qty"]
        return equity

    def close_position(self, ticker, price, reason):
        pos = self.data["positions"].pop(ticker)
        
        if pos["side"] == "LONG":
            pnl = (price - pos["entry_price"]) * pos["qty"]
            realized_val = pos["qty"] * price
            self.data["cash"] += realized_val # Get cash back + profit/loss
        else: # SHORT
            pnl = (pos["entry_price"] - price) * pos["qty"]
            # Return the reserved entry notional, then apply the short P&L.
            self.data["cash"] += pos["entry_price"] * pos["qty"] + pnl

        trade_log = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ticker": ticker,
            "type": "SELL" if pos["side"] == "LONG" else "COVER",
            "qty": pos["qty"],
            "price": round(price, 2),
            "pnl": round(pnl, 2),
            "reason": reason,
            "cash_remaining": round(self.data["cash"], 2)
        }
        self.data["trades"].append(trade_log)
        self.log_trade_csv(trade_log)

    def queue_signals(self, signals, market_date):
        """
        Stores signals for T+1 execution.
        """
        self.data["pending_signals"] = signals
        self.data["pending_market_date"] = market_date
        self.save_portfolio()
        print(f"[INFO] Queued {len(signals)} signals for T+1 execution.")

if __name__ == "__main__":
    import random
    pt = PaperTrader()
    print(f"Paper Portfolio Loaded. Cash: {pt.data['cash']}")
