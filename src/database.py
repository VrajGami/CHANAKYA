"""
FILE: src/database.py
DESCRIPTION: SQLite Database Manager for persistent trade logging and portfolio state.
"""
import sqlite3
import os
import json
import logging
from datetime import datetime
from typing import Dict, Any, List

logger = logging.getLogger("Database")

class DatabaseManager:
    def __init__(self, db_path: str = "data/sovereign.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize_schema()

    def _get_connection(self):
        return sqlite3.connect(self.db_path)

    def _initialize_schema(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            
            # Trades Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    ticker TEXT,
                    action TEXT,
                    quantity REAL,
                    price REAL,
                    total_value REAL,
                    rationale TEXT,
                    market_regime TEXT
                )
            ''')
            
            # Portfolio Snapshots Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    net_liquidation REAL,
                    available_funds REAL,
                    positions_json TEXT
                )
            ''')
            
            # Agent Logs Table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS agent_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME,
                    ticker TEXT,
                    agent_name TEXT,
                    log_content TEXT
                )
            ''')
            
            # MIGRATION: Ensure positions_json exists (Safe for existing DBs)
            try:
                cursor.execute("ALTER TABLE portfolio_snapshots ADD COLUMN positions_json TEXT")
            except sqlite3.OperationalError:
                pass # Already exists
            
            conn.commit()

    def log_trade(self, ticker: str, action: str, quantity: int, price: float, rationale: str = "", market_regime: str = ""):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO trades (timestamp, ticker, action, quantity, price, total_value, rationale, market_regime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (datetime.now().isoformat(), ticker, action, quantity, price, quantity * price, rationale, market_regime))
            conn.commit()

    def record_portfolio_snapshot(self, net_liquidation: float, available_funds: float, positions: list, metrics: dict = None):
        """Saves a point-in-time snapshot of the portfolio state."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            meta = {"positions": positions, "metrics": metrics or {}}
            cursor.execute('''
                INSERT INTO portfolio_snapshots (timestamp, net_liquidation, available_funds, positions_json)
                VALUES (?, ?, ?, ?)
            ''', (datetime.now().isoformat(), net_liquidation, available_funds, json.dumps(meta)))
            conn.commit()

    def add_agent_log(self, ticker: str, agent_name: str, log_content: str):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO agent_logs (timestamp, ticker, agent_name, log_content)
                VALUES (?, ?, ?, ?)
            ''', (datetime.now().isoformat(), ticker, agent_name, log_content))
            conn.commit()

    def get_recent_trades(self, limit: int = 50) -> List[Dict]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, ticker, action, quantity, price, rationale, market_regime
                FROM trades ORDER BY timestamp DESC LIMIT ?
            ''', (limit,))
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

    def get_portfolio_history(self, limit: int = 500) -> List[Dict]:
        """Returns chronological portfolio snapshots for trajectory chart reconstruction."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT timestamp, net_liquidation, available_funds, positions_json
                FROM portfolio_snapshots ORDER BY timestamp ASC LIMIT ?
            ''', (limit,))
            columns = [col[0] for col in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]
    
    def get_session_start_time(self) -> str:
        """Returns the timestamp of the very first portfolio snapshot (session start)."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT MIN(timestamp) FROM portfolio_snapshots')
            row = cursor.fetchone()
            return row[0] if row and row[0] else None
    def get_latest_metrics(self) -> dict:
        """Fetch the latest KPIs from the most recent historical snapshot."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT positions_json FROM portfolio_snapshots WHERE positions_json LIKE '%metrics%' ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                try:
                    data = json.loads(row[0])
                    return data.get("metrics", {})
                except: return {}
            return {}
    def clear_all_data(self):
        """Wipes all trades, snapshots, and logs for a clean simulation mission."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades")
            cursor.execute("DELETE FROM portfolio_snapshots")
            cursor.execute("DELETE FROM agent_logs")
            conn.commit()
        logger.info("Database cleared for new simulation mission.")
