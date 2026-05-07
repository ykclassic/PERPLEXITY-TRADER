import ccxt
import pandas as pd
import yaml
import os
from typing import List, Dict, Optional

class DataFetcher:
    def __init__(self, config_path: str = "config/config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.exchange = ccxt.binance({'enableRateLimit': True})
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        """Fetch OHLCV data from Binance."""
        ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        df.set_index('timestamp', inplace=True)
        return df
    
    def fetch_all(self) -> Dict[str, Dict[str, pd.DataFrame]]:
        """Fetch data for all pairs/timeframes."""
        data = {}
        for pair in self.config['pairs']:
            data[pair] = {}
            for tf in self.config['timeframes']:
                data[pair][tf] = self.fetch_ohlcv(pair, tf)
        return data
