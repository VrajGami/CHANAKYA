"""
FILE: src/analytics.py
DESCRIPTION: Institutional-Grade Performance Analytics for the Sovereign Alpha Engine.
Calculates CAGR, Sharpe Ratio, Win Rate, and Volatility in real-time.
"""
import pandas as pd
import numpy as np

class PerformanceAnalyst:
    @staticmethod
    def calculate_kpis(values: list, benchmark_values: list = None) -> dict:
        """
        Calculates CAGR, Max Drawdown, Sharpe Ratio, Win Rate, and Volatility.
        Assumes daily frequency (252 trading days per year).
        """
        if not values or len(values) < 2:
            return {
                "cagr": 0.0, "drawdown": 0.0, "sharpe": 0.0, 
                "win_rate": 0.0, "volatility": 0.0, "profit_factor": 0.0
            }
        
        start_val = values[0]
        end_val = values[-1]
        
        # 1. CAGR (Compound Annual Growth Rate)
        days = len(values)
        years = max(0.01, days / 252) # Scaled for long sims
        try:
            cagr = ((end_val / start_val) ** (1 / years)) - 1
        except: cagr = 0.0
        
        # 2. Max Drawdown
        peak = values[0]
        max_dd = 0.0
        for v in values:
            if v > peak: peak = v
            dd = (peak - v) / peak if peak != 0 else 0
            if dd > max_dd: max_dd = dd
            
        # 3. Sharpe & Volatility
        returns = pd.Series(values).pct_change().dropna()
        vol = 0.0
        sharpe = 0.0
        win_rate = 0.0
        profit_factor = 1.0

        if len(returns) >= 2:
            vol = returns.std() * (252 ** 0.5)
            if vol != 0:
                sharpe = (returns.mean() * 252) / vol
            
            # 4. Win Rate (Days with positive returns)
            wins = returns[returns > 0]
            losses = returns[returns < 0]
            win_rate = len(wins) / len(returns) if len(returns) > 0 else 0.0
            
            # 5. Profit Factor (Gross Gains / Gross Losses)
            sum_wins = wins.sum()
            sum_losses = abs(losses.sum())
            profit_factor = sum_wins / sum_losses if sum_losses > 0 else 1.0
            
        return {
            "cagr": round(float(cagr) * 100, 2),
            "drawdown": round(float(max_dd) * 100, 2),
            "sharpe": round(float(sharpe), 2),
            "win_rate": round(float(win_rate) * 100, 1),
            "volatility": round(float(vol) * 100, 2),
            "profit_factor": round(float(profit_factor), 2)
        }
