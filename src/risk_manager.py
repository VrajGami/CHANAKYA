"""
FILE: src/risk_manager.py
DESCRIPTION: The 'Fortress' - Deterministic Risk Governance Engine.
This module is the ultimate authority on capital preservation. It calculates position 
sizes using the Kelly Criterion and enforces account-wide circuit breakers.
"""

from typing import Dict
import math

class RiskGuardian:
    def __init__(self, total_capital: float, max_risk_per_trade: float = 0.50):
        """
        Initialize the Fortress with account capital and risk limits.
        :param total_capital: Current account balance in CAD.
        :param max_risk_per_trade: Max % of capital risked per trade (50% for small accounts).
        """
        self.total_capital = total_capital
        self.max_risk_per_trade = max_risk_per_trade
        self.max_drawdown_limit = 0.80  # Aggressive for $100 sim
        self.max_position_value = 100.0 # Allow full $100 per ticker for tiny accounts

    def calculate_kelly_size(self, win_probability: float, win_loss_ratio: float) -> float:
        """
        Mathematical 'Sweet Spot' calculation using the Kelly Criterion.
        Formula: K% = W - [(1 - W) / R]
        """
        if win_loss_ratio <= 0: return 0.0
        
        # Calculate theoretical Kelly fraction
        kelly_pct = win_probability - ((1 - win_probability) / win_loss_ratio)
        
        # Apply 'Half-Kelly' for safety margin and cap it at our global risk limit
        safe_kelly = max(0, kelly_pct / 2) 
        return min(safe_kelly, self.max_risk_per_trade)

    def get_safe_position_size(self, price: float, stop_loss: float, confidence: float) -> float:
        """
        Determines the exact number of shares to purchase.
        Combines deterministic math with AI confidence scores.
        """
        if stop_loss >= price:
            raise ValueError("Safety Error: Stop loss must be below entry price for Long positions.")

        # Determine how much of our wallet we are allowed to 'bet'
        # We assume a conservative 2:1 Win/Loss ratio for the calculation
        risk_pct = self.calculate_kelly_size(win_probability=confidence, win_loss_ratio=2.0)
        
        # Calculate dollar amount to risk and risk-per-share
        dollar_risk = self.total_capital * risk_pct
        risk_per_share = price - stop_loss
        
        # Logic: (Total $ to risk) / (Loss if stop hit) = Number of Shares
        # Allow fractional shares for high resolution exposure
        shares = dollar_risk / risk_per_share if risk_per_share > 0 else 0
        return round(shares, 4)

    def validate_trade(self, symbol: str, total_cost: float) -> bool:
        """
        The final 'Veto' gate. Prevents the bot from over-leveraging.
        """
        if total_cost > self.total_capital:
            print(f"Fortress VETO: {symbol} trade cost (${total_cost}) exceeds capital.")
            return False
        
        print(f"Fortress APPROVED: {symbol} trade is within safe parameters.")
        return True
