import ccxt
import pandas as pd  # Ensure present
import yaml
from typing import Dict, List
import os

class DataFetcher:
    def __init__(self, config_path: str = "config/config.yaml"):
        if not os.path.exists(config_path):
            # Create minimal config if missing
            default_config = {
                'pairs': ['BTCUSDT'],
                'timeframes': ['1h'],
                'risk': {'max_risk_pct': 1.5, 'min_rr': 2.0}
            }
            with open(config_path, 'w') as f:
                yaml.dump(default_config, f)
            print(f"Created {config_path}")
        
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        self.exchange = ccxt.binance({'enableRateLimit': True})
    
    def fetch_ohlcv(self, symbol: str, timeframe: str, limit: int = 500) -> pd.DataFrame:
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            print(f"Fetch error {symbol}: {e}")
            return pd.DataFrame()
