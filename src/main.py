#!/usr/bin/env python3
"""
Super Joint Crypto Signal Engine - Bybit Edition
Production-ready with geo-restriction bypass
"""

import sys
import os
import argparse
import logging
import time
from typing import Dict, List, Optional
import pandas as pd
import numpy as np

# External libs
import ccxt
try:
    from discord_webhook import DiscordWebhook
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False
    print("Install discord-webhook for Discord alerts")

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class SuperJointEngine:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.balance = 10000
        self.max_risk_pct = 0.015
        self.min_rr = 2.0
        
        # Use Bybit - no geo-restrictions
        self.exchange = ccxt.bybit({
            'enableRateLimit': True,
            'options': {'defaultType': 'swap'}  # USDT perpetuals
        })
        
        # Test connection
        try:
            self.exchange.load_markets()
            logger.info("✅ Connected to Bybit")
        except Exception as e:
            logger.error(f"Exchange error: {e}")
    
    def fetch_data(self, symbol: str, timeframe: str = '1h', limit: int = 300) -> pd.DataFrame:
        """Robust data fetch with retries."""
        for attempt in range(3):
            try:
                ohlcv = self.exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
                df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
                df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
                df.set_index('timestamp', inplace=True)
                logger.info(f"✅ Fetched {len(df)} candles: {symbol}")
                return df
            except Exception as e:
                logger.warning(f"Fetch attempt {attempt+1} failed: {e}")
                time.sleep(2 ** attempt)
        
        logger.error(f"❌ Failed to fetch {symbol}")
        return pd.DataFrame()
    
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Blueprint indicators."""
        if len(df) < 50:
            return df
            
        try:
            # Core trend
            df['ema_21'] = ta.ema(df['close'], 21)
            df['ema_50'] = ta.ema(df['close'], 50)
            df['ema_200'] = ta.ema(df['close'], 200)
            df['rsi'] = ta.rsi(df['close'], 14)
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)
            
            # Bollinger Bands + Keltner
            bb = ta.bbands(df['close'], length=20)
            df['bb_upper'] = bb['BBU_20_2.0']
            df['bb_lower'] = bb['BBL_20_2.0']
            kc = ta.kc(df['high'], df['low'], df['close'], 20)
            df['kc_upper'] = kc['KCUe_20_2.0']
            df['kc_lower'] = kc['KCLb_20_2.0']
            
            # Volume + momentum
            df['obv'] = ta.obv(df['close'], df['volume'])
            df['cci'] = ta.cci(df['high'], df['low'], df['close'])
            macd = ta.macd(df['close'])
            df['macd_hist'] = macd['MACDh_12_26_9']
            
            return df.dropna()
        except Exception as e:
            logger.error(f"Indicator error: {e}")
            return df
    
    def generate_signals(self, df: pd.DataFrame) -> List[Dict]:
        """8 Strategy Engines (simplified production versions)."""
        signals = []
        latest = df.iloc[-1]
        
        # 1. TREND RIDER (Strategy A)
        if (latest['close'] > latest['ema_50'] > latest['ema_200'] and
            50 < latest['rsi'] < 70 and latest['macd_hist'] > 0):
            signals.append({
                'strategy': 'TrendRider',
                'direction': 'LONG',
                'confidence': 0.8,
                'entry': latest['close'],
                'stop': latest['ema_21'] - latest['atr'],
                'target': latest['close'] + 4 * latest['atr']
            })
        
        # 2. SQUEEZE ROCKET (Strategy B)
        squeeze_period = ((df['bb_upper'] < df['kc_upper']) & 
                         (df['bb_lower'] > df['kc_lower'])).sum()
        if squeeze_period >= 10 and latest['close'] > latest['bb_upper']:
            signals.append({
                'strategy': 'SqueezeRocket',
                'direction': 'LONG',
                'confidence': 0.85,
                'entry': latest['close'],
                'stop': latest['bb_lower'],
                'target': latest['close'] + 2 * latest['atr']
            })
        
        # 3. SMC BOS (Strategy D)
        swing_high = df['high'].rolling(10).max().iloc[-2]
        if latest['high'] > swing_high and latest['rsi'] > 50:
            signals.append({
                'strategy': 'SMC',
                'direction': 'LONG',
                'confidence': 0.9,
                'entry': latest['close'],
                'stop': df['low'].rolling(10).min().iloc[-1],
                'target': latest['close'] + 3 * latest['atr']
            })
        
        return signals
    
    def score_confluence(self, signals: List[Dict], df: pd.DataFrame) -> float:
        """Consensus engine: 7/10 minimum."""
        if not signals:
            return 0.0
            
        latest = df.iloc[-1]
        score = 0
        
        # Trend alignment (2pts)
        score += 2 if latest['close'] > latest['ema_50'] else 0
        # Momentum (1.5pts)
        score += 1.5 if 40 < latest['rsi'] < 80 else 0
        # Volume (1pt)
        score += 1 if latest['volume'] > df['volume'].mean() else 0
        # Strategy count (3pts)
        score += min(3, len(signals))
        # SMC bonus (1pt)
        score += 1 if any(s['strategy'] == 'SMC' for s in signals) else 0
        
        return min(score, 10.0)
    
    def validate_trade(self, signal: Dict) -> bool:
        """Blueprint risk rules."""
        risk_dist = abs(signal['entry'] - signal['stop']) / signal['entry']
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        return rr >= self.min_rr and risk_dist <= self.max_risk_pct
    
    def format_embed(self, signal: Dict, score: float) -> str:
        """Rich Discord embed."""
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        return f"""
🔔 **{signal['strategy']} SIGNAL**
Pair: `BTCUSDT` | TF: `1H`

💰 **Entry**: `{signal["entry"]:.4f}`
🛑 **Stop**: `{signal["stop"]:.4f}`
🎯 **Target**: `{signal["target"]:.4f}`

⚖️ **R:R**: `1:{rr:.1f}`
📊 **Score**: `{score:.1f}/10`
⭐ **Confidence**: `{signal["confidence"]:.0%}`
        """
    
    def send_discord(self, embed: str):
        """Discord alert."""
        if not self.dry_run and DISCORD_AVAILABLE:
            webhook_url = os.getenv('DISCORD_WEBHOOK')
            if webhook_url:
                try:
                    DiscordWebhook(url=webhook_url, content=embed).execute()
                    logger.info("✅ Discord signal sent")
                except Exception as e:
                    logger.error(f"Discord error: {e}")
            else:
                logger.warning("No DISCORD_WEBHOOK - dry run")
        else:
            print("🧪 DRY RUN:\n", embed)
    
    def process_pair(self, symbol: str):
        """Process single pair."""
        logger.info(f"🔄 Analyzing {symbol}")
        
        df = self.fetch_data(symbol)
        if df.empty:
            return
        
        df = self.compute_indicators(df)
        if len(df) < 50:
            logger.warning("Insufficient data")
            return
        
        # Generate signals
        signals = self.generate_signals(df)
        score = self.score_confluence(signals, df)
        
        logger.info(f"  → {len(signals)} signals | Score: {score:.1f}/10")
        
        if score >= 7.0 and signals:
            best_signal = max(signals, key=lambda x: x['confidence'])
            
            if self.validate_trade(best_signal):
                embed = self.format_embed(best_signal, score)
                self.send_discord(embed)
                logger.info(f"✅ {best_signal['strategy']} signal VALIDATED")
            else:
                logger.info("❌ Risk rules rejected")
    
    def run(self, pairs: List[str] = None):
        """Main execution."""
        pairs = pairs or ['BTC/USDT', 'ETH/USDT', 'SOL/USDT']
        
        logger.info("🚀 Super Joint Engine v2.0 - Bybit Live")
        logger.info(f"Mode: {'DRY-RUN' if self.dry_run else 'LIVE'}")
        
        for pair in pairs:
            self.process_pair(pair)
        
        logger.info("✅ Analysis complete")

def main():
    parser = argparse.ArgumentParser(description="Super Joint Crypto Signals")
    parser.add_argument('--pairs', nargs='*', default=None, 
                       help="Pairs (default: BTC,ETH,SOL)")
    parser.add_argument('--live', action='store_true', 
                       help="Send live Discord (requires webhook)")
    args = parser.parse_args()
    
    engine = SuperJointEngine(dry_run=not args.live)
    engine.run(args.pairs)

if __name__ == "__main__":
    main()
