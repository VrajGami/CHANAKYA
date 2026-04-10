"""
FILE: main.py
DESCRIPTION: Application Entry Point.
Starts the FastAPI+WebSocket server and background trading orchestrator.
"""
import asyncio
import logging
import warnings
from dotenv import load_dotenv
load_dotenv()
warnings.filterwarnings("ignore")
import uvicorn
from contextlib import asynccontextmanager
from src.api import app, ws_manager
import src.api as api_module
from src.orchestrator import Orchestrator
from src.backtester import run_backtest

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("Main")

bot = Orchestrator(ws_manager)
api_module._db = bot.db  # Wire DB into REST endpoints for history

@asynccontextmanager
async def lifespan(app):
    # Startup
    logger.info("Starting Sovereign Alpha Multi-Agent System...")
    # The Mission: Re-live history from Jan 2020 sequentially
    asyncio.create_task(bot.start_historical_simulator(start_date="2020-01-01"))
    yield
    # Shutdown
    logger.info("Shutting down system...")
    bot.shutdown()

app.router.lifespan_context = lifespan

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
