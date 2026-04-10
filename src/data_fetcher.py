"""
FILE: src/data_fetcher.py
DESCRIPTION: The 'Eyes' - Real-Time Market Intelligence Ingestion.
Pulls OHLCV data from Yahoo Finance and calculates professional technical indicators.
Includes Z-Score for Mean Reversion and RSI for Momentum analysis.
"""

import yfinance as yf
import pandas as pd
from typing import Optional

class MarketEyes:
    def __init__(self, ticker: str, full_df: pd.DataFrame = None):
        """
        Initializes the data engine.
        :param ticker: TSX ticker symbol.
        :param full_df: Optional pre-fetched dataframe for high-speed simulation.
        """
        self.ticker = ticker
        self.data: Optional[pd.DataFrame] = full_df

    def fetch_intelligence(self, period: str = "1y") -> dict:
        """
        Fetches historical data, technical indicators, and latest news.
        :return: A dictionary of the latest metrics for the AI Brain.
        """
        stock = yf.Ticker(self.ticker)
        news = stock.news
        df = stock.history(period=period)
        
        if df.empty:
            raise ValueError(f"Failed to ingest data for {self.ticker}")

        self.data = df.ffill().fillna(0)

        # 1. Trend Analysis (Moving Averages)
        self.data['SMA_50'] = self.data['Close'].rolling(window=50).mean()
        
        # 2. Momentum Analysis (RSI)
        delta = self.data['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        self.data['RSI'] = 100 - (100 / (1 + (gain / loss)))

        # 3. Mean Reversion Analysis (Z-Score)
        sma_20 = self.data['Close'].rolling(window=20).mean()
        std_20 = self.data['Close'].rolling(window=20).std()
        self.data['Z_Score'] = (self.data['Close'] - sma_20) / std_20

        # 4. Volatility Regime Detection (using standard deviation)
        # Compare current 10-day volatility to 100-day historical volatility
        std_10 = self.data['Close'].rolling(window=10).std()
        std_100 = self.data['Close'].rolling(window=100).std()
        
        latest = self.data.iloc[-1]
        
        current_vol = std_10.iloc[-1]
        hist_vol = std_100.iloc[-1]
        
        if pd.isna(current_vol) or pd.isna(hist_vol):
            regime = "NORMAL"
        elif current_vol > hist_vol * 1.5:
            regime = "HIGH_VOLATILITY (CRASH/SPIKE)"
        elif current_vol < hist_vol * 0.5:
            regime = "LOW_VOLATILITY (CHOPPY/RANGING)"
        else:
            regime = "NORMAL_TRENDING"

        import random
        base_price = latest['Close']
        noise = base_price * random.uniform(-0.002, 0.002) if not pd.isna(base_price) else 0

        def sanitize(val):
            return 0.0 if pd.isna(val) else round(float(val), 2)

        # Format recent candles for AI training (last 30 days)
        recent_30 = self.data.tail(30)
        candles_summary = []
        for _, row in recent_30.iterrows():
            candles_summary.append({
                "date": str(_.date()),
                "open": round(float(row['Open']), 2),
                "high": round(float(row['High']), 2),
                "low": round(float(row['Low']), 2),
                "close": round(float(row['Close']), 2),
                "volume": int(row['Volume'])
            })

        # Price change analysis
        price_30d_ago = self.data['Close'].iloc[-30] if len(self.data) >= 30 else self.data['Close'].iloc[0]
        price_7d_ago = self.data['Close'].iloc[-7] if len(self.data) >= 7 else self.data['Close'].iloc[0]
        current_close = self.data['Close'].iloc[-1]

        pct_change_1m = round(((current_close - price_30d_ago) / price_30d_ago) * 100, 2)
        pct_change_1w = round(((current_close - price_7d_ago) / price_7d_ago) * 100, 2)

        # Support / Resistance from 52-week high/low
        high_52w = round(float(self.data['High'].max()), 2)
        low_52w = round(float(self.data['Low'].min()), 2)

        # Trend direction from SMA
        trend_direction = "UPTREND" if current_close > sanitize(latest['SMA_50']) else "DOWNTREND"

        # Format news for the LLM
        headlines = [n.get('title', 'Market Update') for n in news[:5]] if news else ["No recent news found."]

        return {
            "price": sanitize(base_price + noise),
            "rsi": sanitize(latest['RSI'] + random.uniform(-1, 1) if not pd.isna(latest['RSI']) else 0),
            "z_score": sanitize(latest['Z_Score']),
            "sma_50": sanitize(latest['SMA_50']),
            "volume": int(latest['Volume']) if not pd.isna(latest['Volume']) else 0,
            "market_regime": regime,
            "recent_news": headlines,
            # Historical training context
            "price_change_1w_pct": pct_change_1w,
            "price_change_1m_pct": pct_change_1m,
            "trend_direction": trend_direction,
            "high_52w": high_52w,
            "low_52w": low_52w,
            "recent_candles": candles_summary  # Full 30-day OHLCV for deep AI analysis
        }

    def fetch_historical_intelligence(self, target_date: str) -> dict:
        """
        Simulates the intelligence available on a specific PAST date.
        Strictly slices data to prevent look-ahead bias (Glitch Proof).
        """
        if self.data is None:
            self.data = yf.download(self.ticker, start="2019-01-01", progress=False)
            
        # 1. Blind Slicing
        ts = pd.to_datetime(target_date)
        df_blind = self.data[self.data.index <= ts].copy()
        
        if len(df_blind) < 50:
            # Not enough data for indicators yet
            return {"price": 0.0, "status": "WAITING_FOR_DATA"}
            
        # 2. Re-calculate indicators as they were ON THAT DAY
        df_blind['SMA_50'] = df_blind['Close'].rolling(window=50).mean()
        delta = df_blind['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        df_blind['RSI'] = 100 - (100 / (1 + (gain / loss)))
        
        sma_20 = df_blind['Close'].rolling(window=20).mean()
        std_20 = df_blind['Close'].rolling(window=20).std()
        df_blind['Z_Score'] = (df_blind['Close'] - sma_20) / std_20

        latest = df_blind.iloc[-1]
        
        def to_float(val):
            if isinstance(val, pd.Series):
                val = val.iloc[0]
            return round(float(val), 2) if not pd.isna(val) else 0.0

        return {
            "price": to_float(latest['Close']),
            "rsi": to_float(latest['RSI']) if 'RSI' in latest else 50.0,
            "z_score": to_float(latest['Z_Score']) if 'Z_Score' in latest else 0.0,
            "sma_50": to_float(latest['SMA_50']) if 'SMA_50' in latest else 0.0,
            "volume": int(latest['Volume'].iloc[0]) if isinstance(latest['Volume'], pd.Series) else int(latest['Volume']),
            "market_regime": "HISTORICAL_SIMULATION",
            "recent_news": ["Simulated historical news context..."]
        }
