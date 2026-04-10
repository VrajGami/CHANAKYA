"""
FILE: src/backtester.py
DESCRIPTION: Professional Historical Backtesting Engine.
Simulates life-like trading (including SHORTS and Fractional Shares) against 5 years of data.
Injects 'Event Narratives' (Pandemics/Wars) and calculates Institutional KPIs.
"""
import yfinance as yf
import pandas as pd
import sqlite3
import json
import numpy as np
import logging
from datetime import datetime, timedelta

logger = logging.getLogger("Backtester")

INITIAL_CAPITAL = 100.0
WATCHLIST = ["TD.TO", "SHOP.TO", "WELL.TO", "LSPD.TO"]

def _signal(row: pd.Series, df: pd.DataFrame, idx: int) -> int:
    """Deterministic signal generator."""
    rsi = row.get("RSI", 50)
    z   = row.get("Z_Score", 0)
    sma = row.get("SMA_50", row["Close"])

    bullish = (rsi < 45) and (row["Close"] > sma) and (z < 1.0)
    bearish = (rsi > 75) or (z > 2.5) or (row["Close"] < sma * 0.95)

    if bullish: return 1
    if bearish: return -1
    return 0

def calculate_metrics(snapshots):
    """Calculate CAGR, Max Drawdown, and Sharpe Ratio."""
    if len(snapshots) < 2:
        return {"cagr": 0, "drawdown": 0, "sharpe": 0}
    
    vals = [s[1] for s in snapshots]
    start_val = vals[0]
    end_val = vals[-1]
    
    # 1. CAGR
    days = len(vals)
    years = max(0.1, days / 252)
    cagr = ((end_val / start_val) ** (1 / years)) - 1
    
    # 2. Max Drawdown
    peak = vals[0]
    max_dd = 0
    for v in vals:
        if v > peak: peak = v
        dd = (peak - v) / peak
        if dd > max_dd: max_dd = dd
        
    # 3. Sharpe (approx)
    returns = pd.Series(vals).pct_change().dropna()
    sharpe = (returns.mean() / returns.std()) * (252 ** 0.5) if returns.std() != 0 else 0
    
    return {
        "cagr": round(cagr * 100, 2),
        "drawdown": round(max_dd * 100, 2),
        "sharpe": round(sharpe, 2)
    }

def run_backtest(db_path: str = "data/sovereign.db", years: int = 5):
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    logger.info("=== INITIALIZING PRO BACKTESTER ($100 Baseline) ===")

    end_date = datetime.today()
    start_date = end_date - timedelta(days=365 * years)
    raw = yf.download(WATCHLIST, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), group_by="ticker", auto_adjust=True, progress=False)

    ticker_dfs = {}
    for ticker in WATCHLIST:
        try:
            df = raw[ticker].copy()
            df.dropna(subset=["Close"], inplace=True)
            df["SMA_50"] = df["Close"].rolling(50).mean()
            delta = df["Close"].diff()
            gain = delta.where(delta > 0, 0).rolling(14).mean()
            loss = (-delta.where(delta < 0, 0)).rolling(14).mean()
            df["RSI"] = 100 - (100 / (1 + gain / loss))
            df["Z_Score"] = (df["Close"] - df["Close"].rolling(20).mean()) / df["Close"].rolling(20).std()
            ticker_dfs[ticker] = df
        except: continue

    all_dates = sorted(set.intersection(*[set(df.index) for df in ticker_dfs.values()]))
    
    capital = INITIAL_CAPITAL
    holdings = {t: 0.0 for t in WATCHLIST} # shares (float)
    snapshots = []

    for i, date in enumerate(all_dates):
        if i < 50:
            snapshots.append((date.isoformat(), INITIAL_CAPITAL, INITIAL_CAPITAL, ""))
            continue

        # Event Detection
        event = ""
        date_str = date.strftime("%Y-%m-%d")
        if "2020-02-20" <= date_str <= "2020-03-31": event = "Pandemic Strike"
        if "2022-02-24" <= date_str <= "2022-04-01": event = "Geopolitical Crisis"

        # Mark-to-Market
        holdings_value = 0
        for t, shares in holdings.items():
            price = ticker_dfs[t].loc[date, "Close"]
            holdings_value += shares * price
        
        net_liq = capital + holdings_value
        snapshots.append((date.isoformat(), net_liq, capital, event))

        # Rebalance
        for ticker in WATCHLIST:
            df = ticker_dfs[ticker]
            row = df.loc[date]
            sig = _signal(row, df, i)
            held = holdings[ticker]

            # Exit Logic
            if (sig == -1 and held > 0) or (sig == 1 and held < 0):
                capital += held * float(row["Close"])
                holdings[ticker] = 0.0
            
            # Entry Logic (Buy or Short)
            if sig != 0 and held == 0 and capital > 1.0:
                alloc = min(capital * 0.25, 50.0) # Risk 25% or max $50
                price = float(row["Close"])
                if price <= 0: continue
                
                shares = (alloc / price) * sig # + for Long, - for Short
                capital -= abs(shares * price)
                holdings[ticker] = shares

    # Save to DB
    metrics = calculate_metrics(snapshots)
    c.execute("DELETE FROM portfolio_snapshots")
    
    # Downsample
    step = max(1, len(snapshots) // 500)
    sampled = snapshots[::step]
    
    # We store event info in a custom format or separate column - let's reuse positions_json temporarily for metadata
    for ts, nl, af, ev in sampled:
        meta = json.dumps({"event": ev, "metrics": metrics})
        c.execute("INSERT INTO portfolio_snapshots (timestamp, net_liquidation, available_funds, positions_json) VALUES (?, ?, ?, ?)", (ts, nl, af, meta))
    
    conn.commit()
    conn.close()
    logger.info(f"=== PRO BACKTEST COMPLETE: $100 -> ${snapshots[-1][1]:.2f} (Sharpe: {metrics['sharpe']}) ===")
