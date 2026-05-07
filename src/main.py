#!/usr/bin/env python3
"""
Super Joint Crypto Signal Engine - Geo-Restriction Proof
Uses CoinGecko (free, no blocks) + Technical Analysis
"""

import sys
import os
import argparse
import logging
import requests
import pandas as pd
import numpy as np
import pandas_ta_classic as ta
from datetime import datetime, timedelta
from typing import Dict, List, Optional

try:
    from discord_webhook import DiscordWebhook
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

# Logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class SuperJointEngine:
    def __init__(self, dry_run: bool = True):
        self.dry_run = dry_run
        self.pairs = ['bitcoin', 'ethereum', 'solana']  # CoinGecko IDs
    
    def fetch_coingecko(self, coin_id: str, days: int = 14) -> pd.DataFrame:
        """Fetch from CoinGecko - works globally, no restrictions."""
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {'vs_currency': 'usd', 'days': days, 'interval': 'hourly'}
        
        try:
            resp = requests.get(url, params=params, timeout=10)
            data = resp.json()
            
            df = pd.DataFrame(data['prices'], columns=['timestamp', 'close'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['high'] = df['close'] * 1.005  # Proxy
            df['low'] = df['close'] * 0.995
            df['open'] = df['close'].shift(1).fillna(df['close'])
            df['volume'] = data['total_volumes']
            
            df.set_index('timestamp', inplace=True)
            logger.info(f"✅ CoinGecko: {coin_id} ({len(df)} candles)")
            return df
        except Exception as e:
            logger.error(f"CoinGecko error {coin_id}: {e}")
            return pd.DataFrame()
    
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Full blueprint indicators."""
        if len(df) < 50:
            return df
            
        # Trend
        df['ema_21'] = ta.ema(df['close'], 21)
        df['ema_50'] = ta.ema(df['close'], 50)
        df['ema_200'] = ta.ema(df['close'], 200)
        df['rsi'] = ta.rsi(df['close'], 14)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)
        
        # Volatility
        bb = ta.bbands(df['close'])
        df['bb_upper'] = bb['BBU_20_2.0']
        df['bb_lower'] = bb['BBL_20_2.0']
        kc = ta.kc(df['high'], df['low'], df['close'])
        df['kc_upper'] = kc['KCUe_20_2.0']
        df['kc_lower'] = kc['KCLb_20_2.0']
        
        # Momentum/Volume
        df['macd_hist'] = ta.macd(df['close'])['MACDh_12_26_9']
        df['obv'] = ta.obv(df['close'], df['volume'])
        df['cci'] = ta.cci(df['high'], df['low'], df['close'])
        
        return df.dropna()
    
    def trend_rider(self, df: pd.DataFrame) -> Optional[Dict]:
        """Strategy A: EMA trend + RSI + MACD."""
        latest = df.iloc[-1]
        if (latest['close'] > latest['ema_50'] > latest['ema_200'] and
            50 < latest['rsi'] < 70 and latest['macd_hist'] > 0):
            return {
                'direction': 'LONG',
                'confidence': 0.8,
                'strategy': 'TrendRider',
                'entry': latest['close'],
                'stop': latest['ema_21'] - latest['atr'] * 0.5,
                'target': latest['close'] + latest['atr'] * 4
            }
        return None
    
    def squeeze_rocket(self, df: pd.DataFrame) -> Optional[Dict]:
        """Strategy B: BB squeeze breakout."""
        squeeze = ((df['bb_upper'] < df['kc_upper']) & 
                  (df['bb_lower'] > df['kc_lower'])).sum()
        latest = df.iloc[-1]
        if squeeze >= 8 and latest['close'] > latest['bb_upper']:
            return {
                'direction': 'LONG',
                'confidence': 0.85,
                'strategy': 'SqueezeRocket',
                'entry': latest['close'],
                'stop': latest['bb_lower'],
                'target': latest['close'] + latest['atr'] * 2
            }
        return None
    
    def mean_reversion(self, df: pd.DataFrame) -> Optional[Dict]:
        """Strategy C: RSI oversold + BB lower."""
        latest = df.iloc[-1]
        if latest['rsi'] < 30 and latest['close'] <= latest['bb_lower']:
            return {
                'direction': 'LONG',
                'confidence': 0.75,
                'strategy': 'MeanReversion',
                'entry': latest['bb_mid'],
                'stop': latest['low'] - latest['atr'],
                'target': latest['bb_mid']
            }
        return None
    
    def confluence_score(self, signals: List[Dict], df: pd.DataFrame) -> float:
        """Score 0-10 (min 7 fires)."""
        if not signals:
            return 0.0
            
        latest = df.iloc[-1]
        score = 0
        
        # Trend (2pts)
        score += 2 if latest['close'] > latest['ema_50'] else 0
        # Momentum (1.5pts)
        score += 1.5 if 40 < latest['rsi'] < 80 else 0
        # Volume (1pt)
        score += 1 if latest['volume'] > df['volume'].mean() else 0
        # Strategy diversity (3pts)
        score += min(3, len(signals))
        
        return min(score, 10.0)
    
    def risk_check(self, signal: Dict) -> bool:
        """1.5% max risk, 1:2 RR min."""
        risk_dist = abs(signal['entry'] - signal['stop']) / signal['entry']
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        return rr >= 2.0 and risk_dist <= 0.015
    
    def format_embed(self, signal: Dict, score: float, coin: str) -> str:
        """Discord embed."""
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        return f"""
🔔 **{coin.upper()} {signal['direction']}**
Confidence: `{score:.1f}/10`
Strategy: `{signal['strategy']}`

💰 Entry: `{signal["entry"]:.2f} USD`
🛑 Stop: `{signal["stop"]:.2f}`
🎯 Target: `{signal["target"]:.2f}`

⚖️ R:R `1:{rr:.1f}`
⭐ Edge: Multi-confluence
        """
    
    def send_alert(self, embed: str):
        """Discord or console."""
        if self.dry_run or not DISCORD_AVAILABLE:
            print("🧪 DRY RUN:\n" + embed)
        else:
            webhook = os.getenv('DISCORD_WEBHOOK')
            if webhook:
                DiscordWebhook(url=webhook, content=embed).execute()
    
    def analyze_coin(self, coin_id: str, coin_name: str):
        """Full analysis pipeline."""
        logger.info(f"🔄 {coin_name} ({coin_id})")
        
        df = self.fetch_coingecko(coin_id)
        if df.empty:
            return
        
        df = self.compute_indicators(df)
        if len(df) < 50:
            logger.warning("Insufficient data")
            return
        
        # Run strategies
        strategies = [
            self.trend_rider(df),
            self.squeeze_rocket(df),
            self.mean_reversion(df)
        ]
        signals = [s for s in strategies if s]
        
        score = self.confluence_score(signals, df)
        logger.info(f"  → {len(signals)} signals | {score:.1f}/10")
        
        if score >= 7.0 and signals:
            best = max(signals, key=lambda x: x['confidence'])
            if self.risk_check(best):
                embed = self.format_embed(best, score, coin_name)
                self.send_alert(embed)
                logger.info(f"✅ {best['strategy']} SIGNAL")
    
    def run(self):
        """Execute full scan."""
        logger.info("🚀 Super Joint Engine - CoinGecko Live")
        logger.info(f"Mode: {'DRY' if self.dry_run else 'LIVE'}")
        
        coins = [
            ('bitcoin', 'BTC'),
            ('ethereum', 'ETH'),
            ('solana', 'SOL')
        ]
        
        for coin_id, coin_name in coins:
            self.analyze_coin(coin_id, coin_name)
        
        logger.info("✅ Scan complete")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help="Live Discord alerts")
    args = parser.parse_args()
    
    engine = SuperJointEngine(dry_run=not args.live)
    engine.run()

if __name__ == "__main__":
    main()
