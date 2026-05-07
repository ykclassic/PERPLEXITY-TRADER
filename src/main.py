#!/usr/bin/env python3
"""
Super Joint Blueprint - Production Crypto Signal Engine
Enhanced with Multi-Exchange Failover and Source Tracking
"""

import sys
import os
import argparse
import logging
from typing import Dict, List, Any, Optional, Tuple
import pandas as pd
import ccxt
import pandas_ta_classic as ta
from discord_webhook import DiscordWebhook

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('signals.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class SuperJointEngine:
    def __init__(self, config: Dict = None):
        self.config = config or {
            'pairs': ['BTC/USDT', 'ETH/USDT'],
            'timeframes': ['1h'],
            'risk': {'max_risk_pct': 1.5, 'min_rr': 2.0}
        }
        
        self.max_risk_pct = self.config['risk']['max_risk_pct'] / 100
        self.min_rr = self.config['risk']['min_rr']
        
        # Initialize Exchange Pool for Failover
        self.exchange_pool = [
            {'name': 'Binance', 'client': ccxt.binance({'enableRateLimit': True})},
            {'name': 'Bybit', 'client': ccxt.bybit({'enableRateLimit': True})},
            {'name': 'Kraken', 'client': ccxt.kraken({'enableRateLimit': True})}
        ]
    
    def fetch_data(self, symbol: str, timeframe: str = '1h', limit: int = 300) -> Tuple[pd.DataFrame, Optional[str]]:
        """
        Scans through multiple exchanges until data is successfully retrieved.
        Returns (DataFrame, Exchange_Name)
        """
        for exchange in self.exchange_pool:
            try:
                name = exchange['name']
                client = exchange['client']
                
                logger.info(f"Attempting to fetch {symbol} from {name}...")
                ohlcv = client.fetch_ohlcv(symbol, timeframe, limit=limit)
                
                if not ohlcv or len(ohlcv) < limit * 0.8:
                    logger.warning(f"Insufficient data from {name}, trying next...")
                    continue

                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                
                logger.info(f"Successfully retrieved data from {name}")
                return df, name

            except Exception as e:
                logger.error(f"Exchange {exchange['name']} failed for {symbol}: {str(e)}")
                continue
        
        logger.critical(f"All exchanges failed for {symbol}")
        return pd.DataFrame(), None
    
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty: return df
        
        df['ema_8'] = ta.ema(df['close'], 8)
        df['ema_21'] = ta.ema(df['close'], 21)
        df['ema_50'] = ta.ema(df['close'], 50)
        df['ema_200'] = ta.ema(df['close'], 200)
        df['rsi'] = ta.rsi(df['close'], 14)
        
        macd = ta.macd(df['close'])
        df['macd_hist'] = macd['MACDh_12_26_9']
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)
        
        bb = ta.bbands(df['close'], length=20)
        df['bb_upper'] = bb['BBU_20_2.0']
        df['bb_lower'] = bb['BBL_20_2.0']
        
        kc = ta.kc(df['high'], df['low'], df['close'])
        df['kc_upper'] = kc['KCUe_20_2.0']
        df['kc_lower'] = kc['KCLb_20_2.0']
        
        return df.dropna()

    # --- Strategy Logic (Condensed) ---
    def trend_rider_signal(self, df: pd.DataFrame) -> Optional[Dict]:
        latest = df.iloc[-1]
        if (latest['close'] > latest['ema_50'] > latest['ema_200'] and 50 < latest['rsi'] < 70):
            return {
                'direction': 'LONG', 'confidence': 0.8, 'strategy': 'TrendRider',
                'entry': latest['close'], 'stop': latest['ema_21'] - latest['atr'],
                'target': latest['close'] + (latest['atr'] * 3)
            }
        return None

    def squeeze_rocket_signal(self, df: pd.DataFrame) -> Optional[Dict]:
        squeeze = ((df['bb_upper'] < df['kc_upper']) & (df['bb_lower'] > df['kc_lower'])).tail(10).sum()
        latest = df.iloc[-1]
        if squeeze >= 5 and latest['close'] > latest['bb_upper']:
            return {
                'direction': 'LONG', 'confidence': 0.85, 'strategy': 'SqueezeRocket',
                'entry': latest['close'], 'stop': latest['bb_lower'],
                'target': latest['close'] + (latest['atr'] * 2)
            }
        return None

    def validate_risk(self, signal: Dict) -> bool:
        entry, stop, target = signal['entry'], signal['stop'], signal['target']
        risk_dist = abs(entry - stop) / entry
        rr = abs(target - entry) / abs(entry - stop)
        return rr >= self.min_rr and risk_dist <= self.max_risk_pct

    def format_signal(self, signal: Dict, exchange_name: str) -> str:
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        return f"""
🔔 **{signal["pair"]} {signal["direction"]} 1H**
Entry: `{signal["entry"]:.2f}`
SL: `{signal["stop"]:.2f}`
TP: `{signal["target"]:.2f}`

⚖️ **R:R 1:{rr:.1f}**
🏛️ **Source: {exchange_name}**
⚡ **Strategy: {signal["strategy"]}**
        """

    def send_discord(self, embed: str):
        webhook = os.getenv('DISCORD_WEBHOOK')
        if webhook:
            DiscordWebhook(url=webhook, content=embed).execute()
            logger.info("✅ Signal sent to Discord")
        else:
            print("\n--- SIGNAL (DRY RUN) ---\n", embed)

    def run(self, pairs: List[str] = None, dry_run: bool = True):
        pairs = pairs or self.config['pairs']
        logger.info(f"🚀 Engine Started. Failover Order: Binance -> Bybit -> Kraken")
        
        for pair in pairs:
            # Multi-exchange scan
            df, source_name = self.fetch_data(pair)
            
            if df.empty or not source_name:
                continue
                
            df = self.compute_indicators(df)
            
            strategies = [
                self.trend_rider_signal(df),
                self.squeeze_rocket_signal(df)
            ]
            signals = [s for s in strategies if s]
            
            if signals:
                best_signal = max(signals, key=lambda x: x['confidence'])
                best_signal['pair'] = pair
                
                if self.validate_risk(best_signal):
                    embed = self.format_signal(best_signal, source_name)
                    if not dry_run:
                        self.send_discord(embed)
                    else:
                        print(embed)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pairs', nargs='*', default=['BTC/USDT', 'ETH/USDT'])
    parser.add_argument('--live', action='store_true', help="Send to Discord (default is dry-run)")
    args = parser.parse_args()
    
    engine = SuperJointEngine()
    engine.run(args.pairs, dry_run=not args.live)

if __name__ == "__main__":
    main()
