"""
FILE: src/orchestrator.py
DESCRIPTION: The Central Nervous System.
Loops over tickers, dispatches parallel LangGraph subagents, validates with MCP, and executes via OMS.
"""
import asyncio
import json
import logging
import os
import pandas as pd
from src.data_fetcher import MarketEyes
from src.ai_engine import MultiAgentEngine
from src.rag_memory import RAGMemory
from src.database import DatabaseManager
from src.broker_interface import BrokerInterface
from src.mcp_server import MCPRiskServer
from src.analytics import PerformanceAnalyst

logger = logging.getLogger("Orchestrator")

class Orchestrator:
    def __init__(self, ws_manager):
        self.ws = ws_manager
        # Expanded watchlist for diverse simulation: Financials, Tech, Health, Energy, Crypto-Proxies
        self.watchlist = [
            "TD.TO", "SHOP.TO", "WELL.TO", "LSPD.TO", # Original
            "ENB.TO", "RY.TO", "BNS.TO", "CNR.TO", # Heavyweights
            "WEED.TO", "HIVE.TO", "BITF.TO", "CP.TO" # Volatile / Lower Price
        ]
        self.db = DatabaseManager()
        self.rag = RAGMemory()
        self.ai = MultiAgentEngine(self.rag)
        self.broker = BrokerInterface(port=7497) # Paper trading port
        self.virtual_capital = 100.0 # Virtual Sandbox Baseline
        self.mcp = MCPRiskServer(initial_capital=self.virtual_capital)
        self.trade_lock = asyncio.Lock()
        self.running = False
        self.sim_mode = False
        self.current_sim_date = None
        self.perf_analyst = PerformanceAnalyst()
        self.history_values = [100.0]
        self.sim_metrics = {"cagr": 0.0, "drawdown": 0.0, "sharpe": 0.0}
        self.holdings = {t: {"shares": 0.0, "avg_cost": 0.0} for t in self.watchlist}

    async def verify_system_health(self):
        """Pre-flight checks to ensure the system doesn't crash during execution."""
        logger.info("Initializing Pre-Flight System Diagnostics...")
        health = {"database": True, "broker": False, "groq_api": False, "sandbox_mode": True}

        # Check DB
        try:
            self.db.get_recent_trades(1)
        except Exception as e:
            logger.error(f"CRITICAL: Database Offline. {e}")
            health["database"] = False
            return False, health

        # Check API Key
        if os.environ.get("GROQ_API_KEY") is not None:
             health["groq_api"] = True

        # Check Broker
        if self.broker.ib.isConnected():
             health["broker"] = True
             
        await self.ws.broadcast("system_health", health)
        logger.info(f"Diagnostics Complete: {health}")
        return True, health

    async def start_historical_simulator(self, start_date="2020-01-01"):
        """
        The Mission: Re-live history.
        Sequentially iterations from start_date to today using the AI Multi-Agent Brain.
        """
        self.running = True
        self.sim_mode = True
        logger.info(f"=== LAUNCHING TIME-MACHINE: {start_date} -> PRESENT ===")
        
        # 1. Clear previous session data for a clean mission
        self.db.clear_all_data()
        self.virtual_capital = 100.0
        
        # 2. Pre-fetch ALL data to ensure zero-latency playback
        import yfinance as yf
        data_cache = {}
        for ticker in self.watchlist:
            logger.info(f"Pre-loading 5Y history for {ticker}...")
            data_cache[ticker] = yf.download(ticker, start="2019-01-01", progress=False)

        # 3. Generate date range
        all_dates = pd.date_range(start=start_date, end=pd.Timestamp.now()).strftime('%Y-%m-%d').tolist()
        
        self.sim_speed = 0.05
        self.paused = False

        for date_str in all_dates:
            # Check for control commands
            cmd_msg = self.ws.cache.get("last_command")
            if cmd_msg:
                cmd = cmd_msg.get("command")
                val = cmd_msg.get("value")
                if cmd == "pause": self.paused = True
                elif cmd == "play": self.paused = False
                elif cmd == "speed": self.sim_speed = val
                # Clear command after consumption
                self.ws.cache["last_command"] = None

            while self.paused:
                await asyncio.sleep(0.5)
                # Check if unpaused
                cmd_msg = self.ws.cache.get("last_command")
                if cmd_msg and cmd_msg.get("command") == "play":
                    self.paused = False
                    self.ws.cache["last_command"] = None

            if not self.running: break
            
            # Warp Drive: Check if day is worth processing
            # We skip weekends/holidays (where data is static)
            ts = pd.to_datetime(date_str)
            if ts.weekday() >= 5: continue # Skip Sat/Sun

            self.current_sim_date = date_str
            
            # Update UI Clock
            await self.ws.broadcast("system_time_update", {"date": date_str})

            # Warp Drive: Intelligent Pacing
            is_critical = False
            
            # Peek at metrics to decide speed
            sample_metrics = {}
            for t in self.watchlist:
                eyes = MarketEyes(t, full_df=data_cache.get(t))
                m = eyes.fetch_historical_intelligence(date_str)
                if m.get("status") != "WAITING_FOR_DATA":
                    # Critical if Price Move > 2% or RSI Extreme or Z-Score Extreme
                    price = m.get("price", 0)
                    rsi = m.get("rsi", 50)
                    z = m.get("z_score", 0)
                    if abs(z) > 2.0 or rsi > 70 or rsi < 30:
                        is_critical = True
                sample_metrics[t] = m

            if is_critical or "2020-03" in date_str or "2022-02" in date_str:
                logger.info(f"--- [DEEP FOCUS] MISSION DAY: {date_str} ---")
                await self.run_cycle(sim_date=date_str, cache=data_cache)
                await asyncio.sleep(max(0.1, self.sim_speed * 10)) # Focus mode is slower but scaled
            else:
                # WARP SPEED: Background account update only
                # logger.info(f"--- [WARP DRIVE] MISSION DAY: {date_str} ---")
                await self.run_cycle(sim_date=date_str, cache=data_cache, fast_mode=True)
                await asyncio.sleep(self.sim_speed) # Warp speed

    def shutdown(self):
        self.running = False
        self.broker.disconnect()

    async def _process_ticker(self, ticker: str, current_position: int, balance: float, sim_date: str = None, cache: dict = None):
        try:
            if sim_date and cache:
                eyes = MarketEyes(ticker, full_df=cache.get(ticker))
                metrics = eyes.fetch_historical_intelligence(sim_date)
            else:
                eyes = MarketEyes(ticker)
                metrics = eyes.fetch_intelligence()
            
            if metrics.get("status") == "WAITING_FOR_DATA":
                return None

            # Fundamentals - in sim mode we use cached/approx fundamentals to avoid API noise
            if not sim_date:
                fundamentals = await self.broker.get_fundamental_data(ticker)
                metrics.update(fundamentals)
            
            logger.info(f"Initiating LangGraph Debate for {ticker} (Sim Date: {sim_date})...")
            
            decision = await asyncio.to_thread(
                self.ai.run_trading_cycle, ticker, metrics, balance, current_position
            )
            
            await self.ws.broadcast("agent_log", {"ticker": ticker, "decision": decision})
            
            return {
                "ticker": ticker,
                "metrics": metrics,
                "decision": decision
            }
        except Exception as e:
            logger.error(f"Pipeline error for {ticker}: {e}")
            return None

    async def run_cycle(self, sim_date: str = None, cache: dict = None, fast_mode: bool = False):
        if not sim_date: await self.verify_system_health()

        memory_count = self.rag.get_memory_count()
        await self.ws.broadcast("learning_metrics", {"total_memories": memory_count, "target_memories": 1000})

        # Pre-calculate holdings and capital once per cycle
        try:
            recent_trades = self.db.get_recent_trades(limit=1000)
            self.holdings = {}
            derived_capital = 100.0
            for t in reversed(recent_trades):
                ticker = t['ticker']
                if ticker not in self.holdings: self.holdings[ticker] = {'shares': 0.0, 'avg_cost': 0.0}
                if t['action'] == "BUY":
                    new_shares = self.holdings[ticker]['shares'] + t['quantity']
                    total_cost = (self.holdings[ticker]['shares'] * self.holdings[ticker]['avg_cost']) + (t['quantity'] * t['price'])
                    self.holdings[ticker]['avg_cost'] = total_cost / new_shares if new_shares > 0 else 0
                    self.holdings[ticker]['shares'] = new_shares
                    derived_capital -= t['quantity'] * t['price']
                elif t['action'] == "SELL":
                    self.holdings[ticker]['shares'] = max(0, self.holdings[ticker]['shares'] - t['quantity'])
                    if self.holdings[ticker]['shares'] == 0: self.holdings[ticker]['avg_cost'] = 0.0
                    derived_capital += t['quantity'] * t['price']
            self.virtual_capital = max(0.0, derived_capital)
            self.mcp.update_capital(self.virtual_capital)
        except Exception: pass

        # PARALLEL PROCESSING: Process all tickers at once
        tasks = []
        for ticker in self.watchlist:
            current_pos = self.holdings.get(ticker, {}).get('shares', 0)
            tasks.append(self._process_ticker(ticker, current_pos, self.virtual_capital, sim_date, cache, fast_mode))
        
        results = await asyncio.gather(*tasks)
        results = [r for r in results if r is not None]

        # Sync Market Pulse for all tickers at once to reduce WS overhead
        pulse_data = {}
        current_holdings_value = 0.0
        for r in results:
            ticker = r["ticker"]
            m = r["metrics"]
            # Inject holdings into metrics
            h = self.holdings.get(ticker, {'shares': 0, 'avg_cost': 0.0})
            m["shares"] = h["shares"]
            m["avg_cost"] = h["avg_cost"]
            m["conviction"] = r["decision"].get("conviction", 0) if not fast_mode else 0
            pulse_data[ticker] = m
            current_holdings_value += h["shares"] * m.get("price", 0.0)
        
        await self.ws.broadcast("market_pulse", pulse_data)
        
        true_net_liq = self.virtual_capital + current_holdings_value
        await self.ws.broadcast("portfolio_update", {
            "net_liquidation": true_net_liq,
            "available_funds": self.virtual_capital,
            "positions": self.holdings
        })

        if fast_mode: return

        # EXECUTION PHASE (Deterministic logic remains sequential for capital safety)
        # 1. Handle Liquidations
        for r in results:
            ticker = r["ticker"]
            held = self.holdings.get(ticker, {}).get('shares', 0)
            score = r["decision"].get("conviction", 0)
            if held > 0 and score < -20:
                await self._execute_trade(ticker, "SELL", held, r["metrics"]["price"], r["decision"], r["metrics"])

        # 2. Handle Accumulation (Sort by conviction)
        results.sort(key=lambda x: x["decision"].get("conviction", 0), reverse=True)
        for r in results:
            score = r["decision"].get("conviction", 0)
            if score > 50: # Lowered from 70 to encourage more active training
                ticker = r["ticker"]
                m = r["metrics"]
                d = r["decision"]
                # MCP Sizing logic...
                pseudo_confidence = min(score / 100.0, 0.99)
                mcp_resp = json.loads(self.mcp.execute_tool("get_position_size", {
                    "price": m["price"], "stop_loss": m["price"] * (1 - d.get("stop_loss_pct", 0.05)), "confidence": pseudo_confidence
                }))
                shares = mcp_resp.get("recommended_shares", 0)

                # SMALL ACCOUNT OVERRIDE: If Kelly says 0.01 but we can afford 1 full share, buy 1.
                if shares < 1.0 and self.virtual_capital >= m["price"] and score > 60:
                    shares = 1.0
                    logger.info(f"Small Account Override: Boosting {ticker} to 1.0 shares.")

                if shares > 0:
                    total_cost = shares * m["price"]
                    if total_cost <= self.virtual_capital:
                        await self._execute_trade(ticker, "BUY", shares, m["price"], d, m)
                    elif self.virtual_capital >= m["price"]:
                        # Buy as many as we can afford if the recommendation is too high
                        affordable = int(self.virtual_capital / m["price"])
                        if affordable > 0:
                            await self._execute_trade(ticker, "BUY", affordable, m["price"], d, m)
        # Performance Snapshot
        self.history_values.append(true_net_liq)
        self.sim_metrics = PerformanceAnalyst.calculate_kpis(self.history_values)
        await self.ws.broadcast("portfolio_update", {
            "net_liquidation": true_net_liq, "available_funds": self.virtual_capital, "metrics": self.sim_metrics, "positions": self.holdings
        })
        self.db.record_portfolio_snapshot(true_net_liq, self.virtual_capital, [{"ticker": k, "shares": v["shares"]} for k, v in self.holdings.items()], self.sim_metrics)

    async def _execute_trade(self, ticker, action, shares, price, decision, metrics):
        """Helper to unify trade execution and RAG logging."""
        await self.ws.broadcast("trade_alert", {"ticker": ticker, "action": action, "shares": shares})
        oms_result = await self.broker.execute_limit_order_oms(ticker, action, shares, price)
        if oms_result.get('status') in ('filled', 'mock_filled'):
            self.db.log_trade(ticker, action, shares, price, decision.get("rationale", ""), metrics.get("market_regime", ""))
            # Update virtual capital immediately
            cost = shares * price
            if action == "BUY": self.virtual_capital -= cost
            else: self.virtual_capital += cost
            self.mcp.update_capital(self.virtual_capital)
            # Reflection
            lesson = await asyncio.to_thread(self.ai.run_post_trade_reflection, ticker, action, 0.0, decision.get("rationale", ""))
            self.rag.store_trade_memory(ticker, action, 0.0, lesson, metrics.get("market_regime", ""))

    async def _process_ticker(self, ticker: str, current_position: int, balance: float, sim_date: str = None, cache: dict = None, fast_mode: bool = False):
        try:
            if sim_date and cache:
                eyes = MarketEyes(ticker, full_df=cache.get(ticker))
                metrics = eyes.fetch_historical_intelligence(sim_date)
            else:
                eyes = MarketEyes(ticker)
                metrics = eyes.fetch_intelligence()
            
            if metrics.get("status") == "WAITING_FOR_DATA": return {"ticker": ticker, "metrics": {"price": 0}, "decision": {}}

            if fast_mode:
                return {"ticker": ticker, "metrics": metrics, "decision": {}}
            
            decision = await asyncio.to_thread(self.ai.run_trading_cycle, ticker, metrics, balance, current_position)
            await self.ws.broadcast("agent_log", {"ticker": ticker, "decision": decision})
            return {"ticker": ticker, "metrics": metrics, "decision": decision}
        except Exception as e:
            logger.error(f"Pipeline error for {ticker}: {e}")
            return None
