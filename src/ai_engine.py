"""
FILE: src/ai_engine.py
DESCRIPTION: LangGraph Multi-Agent Trading Architecture.
Coordinates the Analyst Team, the Bear/Bull debate, the Head Trader, and the Reflection capabilities.
"""
from typing import TypedDict, Dict, Any, List
from langgraph.graph import StateGraph, END
import json
from src.llm_manager import LLMManager
from src.rag_memory import RAGMemory
import asyncio

class AgentState(TypedDict):
    ticker: str
    current_metrics: dict
    account_balance: float
    current_position: int
    market_regime: str
    
    # Intelligence Gathered
    rag_context: List[Dict]
    
    # Debate Arguments
    bull_analysis: dict
    bear_analysis: dict
    
    # Execution
    trader_decision: dict

class MultiAgentEngine:
    def __init__(self, rag_memory: RAGMemory):
        self.llm = LLMManager()
        self.rag = rag_memory
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(AgentState)
        
        # Add Nodes
        workflow.add_node("sentiment_rag_analyst", self.node_sentiment_rag_analyst)
        workflow.add_node("bull_agent", self.node_bull_agent)
        workflow.add_node("bear_agent", self.node_bear_agent)
        workflow.add_node("head_trader", self.node_head_trader)
        
        # Direct Edges (Sequential Flow for Simplicity)
        workflow.add_edge("sentiment_rag_analyst", "bull_agent")
        workflow.add_edge("sentiment_rag_analyst", "bear_agent")
        workflow.add_edge("bull_agent", "head_trader")
        workflow.add_edge("bear_agent", "head_trader")
        workflow.add_edge("head_trader", END)
        
        workflow.set_entry_point("sentiment_rag_analyst")
        return workflow.compile()

    def node_sentiment_rag_analyst(self, state: AgentState) -> dict:
        """Retrieves past trading context from ChromaDB based on the current regime."""
        memories = self.rag.retrieve_similar_scenarios(
            state['market_regime'], 
            f"Price: {state['current_metrics'].get('price')}, RSI: {state['current_metrics'].get('rsi')}"
        )
        return {"rag_context": memories}

    def node_bull_agent(self, state: AgentState) -> dict:
        """Formulates the aggressive bullish case using historical data."""
        m = state['current_metrics']
        sys = (
            "You are the BULL Analyst. Analyze the 30-day historical OHLCV candles to find bullish patterns. "
            "Look for: higher lows, volume surges, price above SMA50, strong weekly momentum. "
            "Use the RAG context to see if past similar setups succeeded. "
            "Format strictly as JSON: {\"arguments\": [\"detail1\", \"detail2\"]}"
        )
        user = (
            f"Ticker: {state['ticker']}\n"
            f"Trend: {m.get('trend_direction')} | 1W Change: {m.get('price_change_1w_pct')}% | 1M Change: {m.get('price_change_1m_pct')}%\n"
            f"52W High: {m.get('high_52w')} | 52W Low: {m.get('low_52w')} | RSI: {m.get('rsi')} | Z-Score: {m.get('z_score')}\n"
            f"Last 30 Candles: {m.get('recent_candles', [])}\n"
            f"RAG Memory: {state['rag_context']}"
        )
        res = self.llm.execute_micro_task(sys, user)
        try:
            parsed = json.loads(res)
        except:
            parsed = {"arguments": [f"Bull: {m.get('trend_direction')} trend, 1M change {m.get('price_change_1m_pct')}%"]}
        return {"bull_analysis": parsed}

    def node_bear_agent(self, state: AgentState) -> dict:
        """Formulates the bearish risk case using historical data."""
        m = state['current_metrics']
        sys = (
            "You are the BEAR Analyst. Analyze the 30-day historical OHLCV candles for warning signs. "
            "Look for: lower highs, declining volume, price below SMA50, negative momentum, proximity to 52W high (resistance). "
            "Use RAG to identify past failures in similar regimes. "
            "Format strictly as JSON: {\"arguments\": [\"risk1\", \"risk2\"]}"
        )
        user = (
            f"Ticker: {state['ticker']}\n"
            f"Trend: {m.get('trend_direction')} | 1W Change: {m.get('price_change_1w_pct')}% | 1M Change: {m.get('price_change_1m_pct')}%\n"
            f"52W High: {m.get('high_52w')} | 52W Low: {m.get('low_52w')} | RSI: {m.get('rsi')} | Z-Score: {m.get('z_score')}\n"
            f"Last 30 Candles: {m.get('recent_candles', [])}\n"
            f"RAG Memory: {state['rag_context']}"
        )
        res = self.llm.execute_micro_task(sys, user)
        try:
            parsed = json.loads(res)
        except:
            parsed = {"arguments": [f"Bear: RSI={m.get('rsi')}, regime={m.get('market_regime')}"]}
        return {"bear_analysis": parsed}

    def node_head_trader(self, state: AgentState) -> dict:
        """Synthesizes Bull/Bear debate + historical data into a final conviction score."""
        m = state['current_metrics']
        sys = (
            "You are the CIO & Head Trader. Synthesize the Bull and Bear arguments with the historical data. "
            "Generate a 'Conviction Score' from -100 to +100. "
            " -100 = Dump immediately (strong downtrend, sell signal). "
            " 0 = Neutral, do nothing. "
            " +100 = Maximum upside conviction, accumulate heavily. "
            "Weight historical trend direction and 30-day candle pattern heavily. "
            "Provide quantitative 'Factor Scores' (0-100) for your reasoning. "
            "ONLY respond with this exact JSON: { \"conviction\": 90, \"rationale\": \"one sentence reason\", \"stop_loss_pct\": 0.05, \"factor_scores\": {\"technical\": 80, \"momentum\": 70, \"sentiment\": 50, \"risk\": 90} }"
        )
        user = (
            f"Ticker: {state['ticker']}\n"
            f"Historical: Trend={m.get('trend_direction')}, 1M={m.get('price_change_1m_pct')}%, 1W={m.get('price_change_1w_pct')}%, 52W-High={m.get('high_52w')}, 52W-Low={m.get('low_52w')}\n"
            f"Bull Case: {state.get('bull_analysis')}\n"
            f"Bear Case: {state.get('bear_analysis')}\n"
            f"RAG Past Lessons: {state.get('rag_context')}"
        )
        res = self.llm.execute_micro_task(sys, user)
        try:
            parsed = json.loads(res)
            if "conviction" not in parsed:
                parsed["conviction"] = 0
            if "factor_scores" not in parsed:
                parsed["factor_scores"] = {"technical": 50, "momentum": 50, "sentiment": 50, "risk": 50}
        except:
            # Derive a basic score from trend even on parser fail
            trend = m.get('trend_direction', 'DOWNTREND')
            pct_1m = m.get('price_change_1m_pct', 0)
            fallback_score = 30 if trend == 'UPTREND' and pct_1m > 0 else -20
            parsed = {
                "conviction": fallback_score, 
                "rationale": f"Auto: {trend}, 1M={pct_1m}%", 
                "stop_loss_pct": 0.05,
                "factor_scores": {"technical": 40, "momentum": 40, "sentiment": 50, "risk": 60}
            }
        return {"trader_decision": parsed}

    def run_trading_cycle(self, ticker: str, metrics: dict, balance: float, current_position: int) -> dict:
        """Kicks off the LangGraph pipeline for a specific asset."""
        initial_state = {
            "ticker": ticker,
            "current_metrics": metrics,
            "account_balance": balance,
            "current_position": current_position,
            "market_regime": metrics.get('market_regime', 'NORMAL'),
            "rag_context": [],
            "bull_analysis": {},
            "bear_analysis": {},
            "trader_decision": {}
        }
        
        # Run graph
        final_state = self.graph.invoke(initial_state)
        return final_state['trader_decision']

    def run_post_trade_reflection(self, ticker: str, action: str, pnl: float, rationale: str):
        """Micro-Task: the Reflection Agent evaluates trade performance locally."""
        sys = "You are a Post-Trade Analysis Agent. Summarize the trade lesson in 1 sentence. JSON format: {'lesson': 'string'}"
        user = f"Trade: {action} {ticker}. PnL: ${pnl}. Rationale: {rationale}."
        
        # Use cheap local model to avoid wasting Groq credits
        res = self.llm.execute_micro_task(sys, user)
        try:
            lesson = json.loads(res).get("lesson", "Standard execution.")
        except:
            lesson = f"Executed {action} resulting in {'profit' if pnl > 0 else 'loss'} of {pnl}."
            
        return lesson
