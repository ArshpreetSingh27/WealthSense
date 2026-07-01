import pandas as pd
import numpy as np

class RiskManager:
    def __init__(self, capital=1000000, max_single_stock=0.05, max_sector=0.25, drawdown_kill=0.10):
        self.capital = capital
        self.max_single_stock = max_single_stock # 5% per stock
        self.max_sector = max_sector # 25% per sector
        self.drawdown_kill = drawdown_kill # 10% de-risk
        
    def apply_constraints(self, signals, current_drawdown=0.0):
        """
        Input: List of dicts with {ticker, sector, weight, price, adv_30}
        Output: Adjusted signals
        """
        # 1. Drawdown De-risking
        de_risk_factor = 1.0
        if current_drawdown > 0.03:
            # Linear de-risking: reduce exposure by 20% for every 1% DD past 3%
            de_risk_factor = max(0, 1.0 - (current_drawdown - 0.03) * 20)
            
        if current_drawdown >= self.drawdown_kill:
            print("CRITICAL: DRAWDOWN KILL-SWITCH TRIGGERED. LIQUIDATING.")
            return []

        # 2. Sector Exposure Caps
        sector_totals = {}
        for s in signals:
            sector = s.get('sector', 'OTHER')
            sector_totals[sector] = sector_totals.get(sector, 0) + abs(s['weight'])
            
        # 3. Adjust weights for Sector and Single-Stock limits
        adjusted_signals = []
        for s in signals:
            sector = s.get('sector', 'OTHER')
            
            # Single stock cap
            adj_weight = min(abs(s['weight']), self.max_single_stock)
            
            # Sector cap (pro-rata reduction if sector exceeds limit)
            if sector_totals[sector] > self.max_sector:
                adj_weight *= (self.max_sector / sector_totals[sector])
            
            # Liquidity Cap: Max 10% of 30-day ADV
            # Allocation = adj_weight * capital
            # Quantity = Allocation / Price
            # Quantity <= 0.1 * ADV
            max_qty = s.get('adv_30', 0) * 0.1
            target_qty = (adj_weight * self.capital) / s['price']
            
            final_qty = min(target_qty, max_qty)
            final_weight = (final_qty * s['price']) / self.capital
            
            # Apply de-risk factor
            final_weight *= de_risk_factor
            final_qty = int(final_weight * self.capital / s['price'])
            
            if final_qty > 0:
                s['weight'] = final_weight if s['weight'] > 0 else -final_weight
                s['quantity'] = final_qty
                s['allocation'] = final_weight * self.capital
                adjusted_signals.append(s)
                
        return adjusted_signals

    def get_risk_metrics(self, signals):
        # Calculate Net and Gross exposure
        gross = sum(abs(s['weight']) for s in signals)
        net = sum(s['weight'] for s in signals)
        return {"gross_exposure": gross, "net_exposure": net}
