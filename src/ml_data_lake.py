import yfinance as yf
import pandas as pd
from rich.console import Console
from rich.progress import Progress
import os

console = Console()

class MLDataLake:
    """
    Historical Data Engine using Yahoo Finance for instant, 
    permission-free, deep historical data (up to 20+ years).
    """
    
    def __init__(self):
        # Canadian Tickers use .TO suffix for Yahoo Finance
        self.tickers = ["SHOP.TO", "RY.TO", "TD.TO", "ENB.TO", "ATD.TO", 
                        "CNR.TO", "BNS.TO", "CP.TO", "BN.TO", "TRI.TO"]

    def download_deep_history(self, period: str = "max"):
        """
        Downloads max historical data for the watchlist and saves to CSV.
        """
        if not os.path.exists('data'):
            os.makedirs('data')

        with Progress() as progress:
            task = progress.add_task("[cyan]Downloading Deep History...", total=len(self.tickers))
            
            for symbol in self.tickers:
                progress.console.print(f"[*] Fetching deep history for {symbol}...")
                
                try:
                    ticker_obj = yf.Ticker(symbol)
                    # Fetch maximum available history
                    df = ticker_obj.history(period=period)
                    
                    if not df.empty:
                        # Standardize column names to lowercase
                        df.columns = [str(col).lower() for col in df.columns]
                        
                        filename = f"data/{symbol.replace('.TO', '')}_DEEP_HISTORY.csv"
                        df.to_csv(filename)
                        progress.console.print(f"[green]Saved {len(df)} rows to {filename}[/green]")
                    else:
                        progress.console.print(f"[red]Warning: No data found for {symbol}[/red]")
                        
                except Exception as e:
                    progress.console.print(f"[red]Error downloading {symbol}: {e}[/red]")
                
                progress.advance(task)

if __name__ == "__main__":
    lake = MLDataLake()
    # Pulling EVERYTHING back to the 90s/2000s
    lake.download_deep_history(period="max")
