"""
FILE: src/performance_tracker.py
DESCRIPTION: The 'Scorekeeper' - Tracks P&L, Win Rate, and Portfolio Growth.
Persists trade history to a local JSON file to survive system restarts.
"""

import json
import os
from datetime import datetime

class PerformanceTracker:
    def __init__(self, filename: str = "data/trade_history.json"):
        self.filename = filename
        self._ensure_file_exists()
        self.history = self._load_history()

    def _ensure_file_exists(self):
        if not os.path.exists('data'):
            os.makedirs('data')
        if not os.path.exists(self.filename):
            with open(self.filename, 'w') as f:
                json.dump([], f)

    def _load_history(self):
        with open(self.filename, 'r') as f:
            return json.load(f)

    def log_trade(self, ticker: str, action: str, price: float, shares: int, total_cost: float):
        """Records a new trade execution."""
        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "ticker": ticker,
            "action": action,
            "price": price,
            "shares": shares,
            "total_cost": total_cost
        }
        self.history.append(entry)
        with open(self.filename, 'w') as f:
            json.dump(self.history, f, indent=4)

    def get_metrics(self, current_balance: float, initial_balance: float = 1000000.0):
        """Calculates performance KPIs."""
        total_trades = len([t for t in self.history if t['action'] == 'BUY'])
        
        # Calculate growth
        growth_pct = ((current_balance - initial_balance) / initial_balance) * 100
        
        # In a real system, we'd match BUYs to SELLs to get win rate.
        # For now, we'll estimate based on account growth vs trade count.
        return {
            "total_trades": total_trades,
            "growth_pct": round(growth_pct, 4),
            "pnl_absolute": round(current_balance - initial_balance, 2)
        }
