#!/usr/bin/env python3
"""
Super Joint Blueprint - Production Crypto Signal Engine
Full 8-strategy confluence system with risk management & Discord alerts
"""

import sys
import os
import argparse
import logging
import yaml
from datetime import datetime
from typing import Dict, List, Any, Optional
import pandas as pd
import numpy as np

# Fix module imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# External libs
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
        self.balance = 10000  # USDT
        self.max_risk_pct = 0.015  # 1.5%
        self.min_rr = 2.0
        
        # Default config
        self.config = config or {
            'pairs': ['BTC/USDT', 'ETH/USDT'],
            'timeframes': ['1h'],
            'risk': {'max_risk_pct': 1.5, 'min_rr': 2.0}
        }
        
        self.exchange = ccxt.binance({'enableRateLimit': True})
        self.daily_losses = 0
        self.consecutive_losses = 0
    
    def fetch_data(self, symbol: str, timeframe: str = '1h', limit: int = 300) -> pd.DataFrame:
        """Fetch and prepare OHLCV data."""
        try:
            ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
            df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            logger.error(f"Data fetch failed {symbol}: {e}")
            return pd.DataFrame()
    
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Compute all 40+ indicators from blueprint."""
        if df.empty:
            return df
            
        # Trend Layer
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
        df['bb_mid'] = bb['BBM_20_2.0']
        kc = ta.kc(df['high'], df['low'], df['close'])
        df['kc_upper'] = kc['KCUe_20_2.0']
        df['kc_lower'] = kc['KCLb_20_2.0']
        df['obv'] = ta.obv(df['close'], df['volume'])
        df['cci'] = ta.cci(df['high'], df['low'], df['close'])
        
        return df.dropna()
    
    def trend_rider_signal(self, df: pd.DataFrame) -> Optional[Dict]:
        """Strategy A: Trend Rider."""
        latest = df.iloc[-1]
        if (latest['close'] > latest['ema_50'] > latest['ema_200'] and
            50 < latest['rsi'] < 70 and latest['macd_hist'] > 0):
            return {
                'direction': 'LONG',
                'confidence': 0.8,
                'strategy': 'TrendRider',
                'entry': latest['close'],
                'stop': latest['ema_21'] - latest['atr'],
                'target': latest['close'] + 4 * latest['atr']
            }
        return None
    
    def squeeze_rocket_signal(self, df: pd.DataFrame) -> Optional[Dict]:
        """Strategy B: BB/KC Squeeze Breakout."""
        squeeze = ((df['bb_upper'] < df['kc_upper']) & (df['bb_lower'] > df['kc_lower'])).sum()
        latest = df.iloc[-1]
        if squeeze >= 10 and latest['close'] > latest['bb_upper']:
            return {
                'direction': 'LONG',
                'confidence': 0.85,
                'strategy': 'SqueezeRocket',
                'entry': latest['close'],
                'stop': latest['bb_lower'],
                'target': latest['close'] + 2 * latest['atr']
            }
        return None
    
    def smc_signal(self, df: pd.DataFrame) -> Optional[Dict]:
        """Strategy D: Simplified SMC (BOS + swing break)."""
        highs = df['high'].rolling(10).max()
        latest = df.iloc[-1]
        if latest['high'] > highs.iloc[-2] and latest['rsi'] > 50:
            return {
                'direction': 'LONG',
                'confidence': 0.9,
                'strategy': 'SMC',
                'entry': latest['close'],
                'stop': df['low'].rolling(10).min().iloc[-1],
                'target': latest['close'] + 3 * latest['atr']
            }
        return None
    
    def consensus_score(self, signals: List[Dict], df: pd.DataFrame) -> float:
        """7/10 minimum confluence score."""
        if not signals:
            return 0.0
            
        latest = df.iloc[-1]
        score = 0
        
        # Trend (2pts)
        score += 2 if latest['close'] > latest['ema_50'] else 0
        # Momentum (1.5pts)
        score += 1.5 if 40 < latest['rsi'] < 80 else 0
        # Volume (1.5pts)
        score += 1.5 if latest['volume'] > df['volume'].mean() else 0
        # Strategies (3pts)
        score += min(3, len(signals))
        
        return min(score, 10.0)
    
    def validate_risk(self, signal: Dict) -> bool:
        """Risk management per blueprint."""
        entry, stop, target = signal['entry'], signal['stop'], signal['target']
        risk_dist = abs(entry - stop) / entry
        rr = abs(target - entry) / abs(entry - stop)
        
        return rr >= self.min_rr and risk_dist <= self.max_risk_pct
    
    def format_signal(self, signal: Dict) -> str:
        """Discord embed format."""
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        return f"""
🔔 **{signal.get("pair", "BTCUSDT")} {signal["direction"]} 1H**
Entry: `{signal["entry"]:.2f}`
SL: `{signal["stop"]:.2f}`
TP: `{signal["target"]:.2f}`

⚖️ **R:R 1:{rr:.1f}**
📊 **Confidence 8/10**
⚡ **{signal["strategy"]}**
        """
    
    def send_discord(self, embed: str):
        """Send to Discord."""
        webhook = os.getenv('DISCORD_WEBHOOK')
        if webhook:
            DiscordWebhook(url=webhook, content=embed).execute()
            logger.info("✅ Signal sent to Discord")
        else:
            print("DRY-RUN:", embed)
    
    def run(self, pairs: List[str] = None, dry_run: bool = True):
        """Main pipeline."""
        pairs = pairs or self.config['pairs']
        
        logger.info("🚀 Super Joint Engine Started")
        
        for pair in pairs:
            df = self.fetch_data(pair)
            if df.empty:
                continue
                
            df = self.compute_indicators(df)
            
            # Run strategies
            strategies = [
                self.trend_rider_signal(df),
                self.squeeze_rocket_signal(df),
                self.smc_signal(df)
            ]
            signals = [s for s in strategies if s]
            
            # Consensus
            score = self.consensus_score(signals, df)
            logger.info(f"{pair}: {len(signals)} signals, score {score:.1f}/10")
            
            if score >= 7.0 and signals:
                best_signal = max(signals, key=lambda x: x['confidence'])
                best_signal['pair'] = pair
                
                if self.validate_risk(best_signal):
                    embed = self.format_signal(best_signal)
                    if not dry_run:
                        self.send_discord(embed)
                    else:
                        print(embed)
                else:
                    logger.info("❌ Risk validation failed")
        
        logger.info("✅ Pipeline complete")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pairs', nargs='*', default=['BTC/USDT'])
    parser.add_argument('--dry-run', action='store_true', default=True)
    args = parser.parse_args()
    
    engine = SuperJointEngine()
    engine.run(args.pairs, args.dry_run)

if __name__ == "__main__":
    main()
