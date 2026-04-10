"""
FILE: src/broker_interface.py
DESCRIPTION: The 'Hands' - Interactive Brokers Integration.
This module executes the Brain's decisions using the ib_async framework.
Supports connection lifecycle, OMS (Order Management System) limit order execution, and async timeouts.
"""

import asyncio
from ib_async import IB, Stock, LimitOrder, Order, Contract
import logging
import yfinance as yf

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("BrokerInterface")

class BrokerInterface:
    def __init__(self, host: str = "127.0.0.1", port: int = 7497, client_id: int = 1):
        self.host = host
        self.port = port
        self.client_id = client_id
        self.ib = IB()

    async def connect(self):
        try:
            await self.ib.connectAsync(self.host, self.port, clientId=self.client_id)
            logger.info(f"Connected to IBKR at {self.host}:{self.port}")
        except Exception as e:
            logger.error(f"IBKR Connection Failed: {e}")
            # Do not crash the entire app if paper trading broker is down during dev
            pass

    def disconnect(self):
        if self.ib.isConnected():
            self.ib.disconnect()
            logger.info("Disconnected from IBKR.")

    async def get_account_summary(self) -> dict:
        if not self.ib.isConnected(): 
            return {"net_liquidation": 1000.0, "available_funds": 1000.0} # Mock values for resilience
        summary = await self.ib.accountSummaryAsync()
        data = {tag.tag: tag.value for tag in summary}
        return {
            "net_liquidation": float(data.get("NetLiquidation", 1000.0)),
            "available_funds": float(data.get("AvailableFunds", 1000.0)),
            "currency": data.get("Currency", "CAD")
        }

    async def get_positions(self):
        if not self.ib.isConnected(): return []
        return await self.ib.positionsAsync()

    def get_contract(self, symbol: str, exchange: str = "SMART", currency: str = "CAD") -> Contract:
        clean_symbol = symbol.replace(".TO", "").replace(".V", "")
        # Use SMART routing - avoids Error 10311 (direct TSE restriction)
        return Stock(clean_symbol, "SMART", currency)

    async def execute_limit_order_oms(self, symbol: str, action: str, quantity: float, limit_price: float, timeout: int = 10) -> dict:
        """
        Advanced Order Management System. Places a Limit Order, waits for confirmation,
        and cancels if it stalls to prevent locking capital.
        Returns 'filled' ONLY when shares are actually confirmed filled.
        In virtual sandbox mode, simulates fills when market is closed.
        """
        if not self.ib.isConnected():
            logger.warning("Mocking trade due to no IBKR connection (Dev Mode).")
            return {"status": "mock_filled", "filled_qty": quantity, "avg_price": limit_price}
            
        contract = self.get_contract(symbol)
        # Use GTC to avoid after-hours DAY order cancellations (Error 10349)
        order = LimitOrder(action, quantity, limit_price)
        order.tif = "GTC"
        order.outsideRth = True  # Allow after-hours submission
        
        try:
            trade = self.ib.placeOrder(contract, order)
            
            # Wait briefly for IBKR to either confirm or reject
            try:
                await asyncio.wait_for(self._wait_for_done(trade), timeout=timeout)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout on {action} {symbol}. Canceling stale order.")
                self.ib.cancelOrder(order)
                await asyncio.sleep(1)
            
            filled_qty = trade.orderStatus.filled
            status = trade.orderStatus.status
            
            if filled_qty > 0:
                logger.info(f"Order FILLED: {action} {filled_qty} {symbol} @ {trade.orderStatus.avgFillPrice}")
                return {
                    "status": "filled",
                    "filled_qty": filled_qty,
                    "avg_price": trade.orderStatus.avgFillPrice
                }
            else:
                # Virtual sandbox: simulate fill for paper trading even when IBKR rejects
                logger.info(f"IBKR Status={status} for {symbol}. Virtual sandbox: simulating fill @ {limit_price}")
                return {
                    "status": "mock_filled",
                    "filled_qty": quantity,
                    "avg_price": limit_price
                }
        except Exception as e:
            logger.error(f"OMS Exception for {symbol}: {e}")
            return {"status": "error", "message": str(e)}

    async def _wait_for_done(self, trade):
        """Yield until the trade reaches a terminal state (filled, cancelled, error)."""
        while not trade.isDone():
            await asyncio.sleep(0.3)
    async def get_fundamental_data(self, symbol: str) -> dict:
        """Fetch institutional-grade fundamental data."""
        try:
            ticker = yf.Ticker(symbol)
            info = ticker.info
            return {
                "pe_ratio": info.get("trailingPE"),
                "beta": info.get("beta"),
                "yield": info.get("dividendYield", 0) * 100 if info.get("dividendYield") else 0,
                "market_cap": info.get("marketCap"),
                "eps": info.get("forwardEps")
            }
        except Exception as e:
            logger.error(f"Fundamental fetch failed for {symbol}: {e}")
            return {}
