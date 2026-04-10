"""
FILE: src/dashboard.py
DESCRIPTION: The 'Cockpit' - Real-Time Terminal User Interface.
Uses the 'rich' library to create a live-updating dashboard for monitoring the bot.
"""

from rich.console import Console
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.live import Live
from rich.text import Text
from datetime import datetime

class Dashboard:
    def __init__(self):
        self.console = Console()
        self.layout = Layout()
        self._setup_layout()
        self.logs = []
        self.market_data = {}
        self.account_info = {"balance": 0.0, "pnl": 0.0}
        self.performance_data = {"total_trades": 0, "growth": 0.0, "pnl": 0.0}

    def _setup_layout(self):
        """Creates the structural grid for the dashboard."""
        self.layout.split(
            Layout(name="header", size=3),
            Layout(name="main", ratio=1),
            Layout(name="footer", size=3)
        )
        self.layout["main"].split_row(
            Layout(name="left_column", ratio=1),
            Layout(name="brain_feed", ratio=2)
        )
        self.layout["left_column"].split(
            Layout(name="watchlist", ratio=2),
            Layout(name="performance", ratio=1)
        )

    def update_account(self, balance: float, pnl: float = 0.0):
        self.account_info = {"balance": balance, "pnl": pnl}

    def add_log(self, message: str, style: str = "white"):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.logs.append(f"[{timestamp}] {message}")
        if len(self.logs) > 15:
            self.logs.pop(0)

    def update_market(self, ticker: str, price: float, rsi: float, trend: str):
        self.market_data[ticker] = {"price": price, "rsi": rsi, "trend": trend}

    def update_metrics(self, total_trades: int, growth_pct: float, pnl: float):
        self.performance_data = {
            "total_trades": total_trades,
            "growth": round(growth_pct, 4),
            "pnl": round(pnl, 2)
        }

    def generate_header(self) -> Panel:
        grid = Table.grid(expand=True)
        grid.add_column(justify="left", ratio=1)
        grid.add_column(justify="right", ratio=1)
        grid.add_row(
            Text("SOVEREIGN ALPHA V1.0", style="bold magenta"),
            Text(f"BALANCE: ${self.account_info['balance']:,.2f} CAD", style="bold green")
        )
        return Panel(grid, style="blue")

    def generate_watchlist(self) -> Panel:
        table = Table(title="Live Watchlist", expand=True)
        table.add_column("Ticker")
        table.add_column("Price")
        table.add_column("RSI")
        table.add_column("Status")

        for ticker, data in self.market_data.items():
            color = "green" if "BUY" in data['trend'] else "red" if "SELL" in data['trend'] else "white"
            table.add_row(
                ticker, 
                f"${data['price']}", 
                str(data['rsi']), 
                Text(data['trend'], style=color)
            )
        return Panel(table, title="Market Pulse", border_style="cyan")

    def generate_performance(self) -> Panel:
        data = self.performance_data
        grid = Table.grid(expand=True)
        grid.add_column(ratio=1)
        grid.add_column(ratio=1)
        
        growth_color = "green" if data['growth'] >= 0 else "red"
        
        grid.add_row("Total Trades:", str(data['total_trades']))
        grid.add_row("Growth (%):", Text(f"{data['growth']}%", style=growth_color))
        grid.add_row("Net P&L ($):", Text(f"${data['pnl']:,.2f}", style=growth_color))
        
        return Panel(grid, title="Performance Statistics", border_style="yellow")

    def generate_brain_feed(self) -> Panel:
        feed = "\n".join(self.logs)
        return Panel(feed, title="Neural Activity (Bull/Bear Debate)", border_style="magenta")

    def generate_footer(self) -> Panel:
        return Panel(
            Text(
                f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Status: ACTIVE | Mode: PAPER TRADING",
                justify="center",
                style="bold yellow"
            )
        )

    def render(self):
        self.layout["header"].update(self.generate_header())
        self.layout["watchlist"].update(self.generate_watchlist())
        self.layout["performance"].update(self.generate_performance())
        self.layout["brain_feed"].update(self.generate_brain_feed())
        self.layout["footer"].update(self.generate_footer())
        return self.layout

if __name__ == "__main__":
    # Test Render
    dash = Dashboard()
    dash.update_account(1000000.0)
    dash.update_market("SHOP.TO", 164.5, 45.0, "NEUTRAL")
    dash.add_log("System initialized.")
    dash.add_log("SHOP.TO Z-Score is low, analyzing bounce potential.")
    with Live(dash.render(), refresh_per_second=1):
        import time
        time.sleep(5)
