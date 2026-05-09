#!/usr/bin/env python3
"""
Super Joint Crypto Signal Engine - PRODUCTION READY
Rich Discord alerts with Entry/SL/TP + Risk Management
"""

import sys
import os
import argparse
import logging
import requests
import pandas as pd
import numpy as np
import pandas_ta as ta
from datetime import datetime
from typing import Dict, List, Optional

try:
    from discord_webhook import DiscordWebhook
    DISCORD_AVAILABLE = True
except ImportError:
    DISCORD_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')
logger = logging.getLogger(__name__)

class SuperJointEngine:
    def __init__(self, dry_run: bool = True, balance: float = 10000):
        self.dry_run = dry_run
        self.balance = balance  # Account balance USD
        self.max_risk_pct = 0.015  # 1.5% max risk
    
    def fetch_coingecko(self, coin_id: str, days: int = 14) -> pd.DataFrame:
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {'vs_currency': 'usd', 'days': days, 'interval': 'hourly'}
        
        try:
            resp = requests.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            
            df = pd.DataFrame(data['prices'], columns=['timestamp', 'close'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['high'] = df['close'] * 1.002
            df['low'] = df['close'] * 0.998
            df['open'] = df['close'].shift(1).fillna(df['close'])
            df['volume'] = pd.Series([v[1] for v in data['total_volumes']])
            
            df.set_index('timestamp', inplace=True)
            logger.info(f"✅ {coin_id}: {len(df)} candles")
            return df
        except Exception as e:
            logger.error(f"❌ {coin_id}: {e}")
            return pd.DataFrame()
    
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < 30:
            return df
        
        try:
            # EMAs
            df['ema_21'] = ta.ema(df['close'], 21)
            df['ema_50'] = ta.ema(df['close'], 50)
            df['ema_200'] = ta.ema(df['close'], 200)
            df['rsi'] = ta.rsi(df['close'], 14)
            df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)
            
            # Bollinger Bands
            bb = ta.bbands(df['close'], length=20)
            if isinstance(bb, pd.DataFrame):
                bb_cols = bb.columns
                upper_col = next((col for col in bb_cols if 'BBU' in col), None)
                lower_col = next((col for col in bb_cols if 'BBL' in col), None)
                mid_col = next((col for col in bb_cols if 'BBM' in col), None)
                
                if upper_col:
                    df['bb_upper'] = bb[upper_col]
                if lower_col:
                    df['bb_lower'] = bb[lower_col]
                if mid_col:
                    df['bb_mid'] = bb[mid_col]
            
            # Keltner Channels
            kc = ta.kc(df['high'], df['low'], df['close'])
            kc_cols = kc.columns if isinstance(kc, pd.DataFrame) else []
            upper_kc = next((col for col in kc_cols if 'KCU' in col), None)
            lower_kc = next((col for col in kc_cols if 'KCL' in col), None)
            
            if upper_kc:
                df['kc_upper'] = kc[upper_kc]
            if lower_kc:
                df['kc_lower'] = kc[lower_kc]
            
            # Additional indicators
            macd = ta.macd(df['close'])
            if isinstance(macd, pd.DataFrame) and 'MACDh_12_26_9' in macd.columns:
                df['macd_hist'] = macd['MACDh_12_26_9']
            
            df['obv'] = ta.obv(df['close'], df['volume'])
            df['cci'] = ta.cci(df['high'], df['low'], df['close'])
            
            return df.dropna()
        except Exception as e:
            logger.warning(f"TA partial failure: {e}")
            return df
    
    def trend_rider(self, df: pd.DataFrame) -> Optional[Dict]:
        """Strategy A: Multi-EMA trend + momentum."""
        latest = df.iloc[-1]
        if (latest['close'] > latest['ema_50'] > latest['ema_200'] and
            50 < latest.get('rsi', 50) < 70 and
            latest.get('macd_hist', 0) > 0):
            atr = latest.get('atr', 100)
            return {
                'direction': 'LONG',
                'confidence': 0.82,
                'strategy': 'TrendRider',
                'entry': latest['close'],
                'stop': latest['ema_21'] - atr * 0.5,
                'target': latest['close'] + atr * 4
            }
        return None
    
    def squeeze_rocket(self, df: pd.DataFrame) -> Optional[Dict]:
        """Strategy B: Volatility squeeze breakout."""
        squeeze = ((df['bb_upper'] < df.get('kc_upper', df['close'] * 1.01)) & 
                   (df['bb_lower'] > df.get('kc_lower', df['close'] * 0.99))).sum()
        latest = df.iloc[-1]
        if squeeze >= 5 and latest['close'] > latest['bb_upper']:
            atr = latest.get('atr', 100)
            return {
                'direction': 'LONG',
                'confidence': 0.88,
                'strategy': 'SqueezeRocket',
                'entry': latest['close'],
                'stop': latest['bb_lower'],
                'target': latest['close'] + atr * 2.5
            }
        return None
    
    def mean_reversion(self, df: pd.DataFrame) -> Optional[Dict]:
        """Strategy C: Oversold bounce."""
        latest = df.iloc[-1]
        rsi = latest.get('rsi', 50)
        if rsi < 32 and latest['close'] <= latest['bb_lower']:
            return {
                'direction': 'LONG',
                'confidence': 0.76,
                'strategy': 'MeanReversion',
                'entry': latest.get('bb_mid', latest['close']),
                'stop': latest['low'] - latest.get('atr', 100),
                'target': latest.get('bb_mid', latest['close'] * 1.03)
            }
        return None
    
    def confluence_score(self, signals: List[Dict], df: pd.DataFrame) -> float:
        """Multi-strategy consensus (min 7.0 fires)."""
        if not signals:
            return 0.0
        
        latest = df.iloc[-1]
        score = len(signals) * 1.8  # Base points per strategy
        
        # Trend bonus
        score += 2.0 if latest['close'] > latest['ema_50'] else 0
        # Momentum bonus
        rsi = latest.get('rsi', 50)
        score += 1.5 if 45 < rsi < 75 else 0
        # Volume bonus
        score += 1.0 if latest['volume'] > df['volume'].tail(20).mean() else 0
        
        return min(score, 10.0)
    
    def calculate_position_size(self, signal: Dict) -> float:
        """ATR-based position sizing (1.5% risk max)."""
        risk_dist = abs(signal['entry'] - signal['stop']) / signal['entry']
        risk_amount = self.balance * self.max_risk_pct
        size = risk_amount / risk_dist if risk_dist > 0 else 0
        return round(size, 2)
    
    def risk_check(self, signal: Dict) -> bool:
        """Blueprint risk validation."""
        risk_dist = abs(signal['entry'] - signal['stop']) / signal['entry']
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        return rr >= 1.8 and risk_dist <= 0.025  # Conservative
    
    def format_discord_embed(self, signal: Dict, score: float, coin: str, pos_size: float) -> str:
        """Rich Discord alert with Entry/SL/TP."""
        entry, sl, tp = signal['entry'], signal['stop'], signal['target']
        risk_dist = abs(entry - sl) / entry * 100
        rr = abs(tp - entry) / abs(entry - sl)
        
        embed = f"""
🚨 **SUPER JOINT SIGNAL** 🚨
*{coin.upper()} {signal['direction']}*

💰 **ENTRY PRICE**: `{entry:,.0f} USD`
🛑 **STOP LOSS**: `{sl:,.0f} USD`
🎯 **TAKE PROFIT**: `{tp:,.0f} USD`

⚖️ **R:R**: `1:{rr:.1f}`
📊 **SCORE**: `{score:.1f}/10`
⭐ **STRATEGY**: `{signal['strategy']}`
💼 **POSITION SIZE**: `{pos_size:,.0f} USD` (1.5% risk)
📈 **RISK**: `{risk_dist:.1f}%`

---
*Super Joint Engine | Multi-Strategy Confluence*
        """
        return embed
    
    def send_discord_alert(self, embed: str):
        """Send rich Discord embed."""
        if self.dry_run or not DISCORD_AVAILABLE:
            print("\n" + "═" * 60)
            print(embed)
            print("═" * 60 + "\n")
            logger.info("🧪 DRY RUN - SIGNAL READY")
        else:
            webhook_url = os.getenv('DISCORD_WEBHOOK')
            if webhook_url:
                try:
                    webhook = DiscordWebhook(url=webhook_url, content=embed[:2000])
                    webhook.execute()
                    logger.info("✅ LIVE DISCORD ALERT SENT")
                except Exception as e:
                    logger.error(f"Discord send error: {e}")
    
    def analyze_coin(self, coin_id: str, coin_name: str):
        """Complete analysis pipeline."""
        logger.info(f"🔄 {coin_name}")
        
        df = self.fetch_coingecko(coin_id)
        if df.empty or len(df) < 40:
            logger.warning(f"❌ {coin_name}: insufficient data")
            return
        
        df = self.compute_indicators(df)
        
        # Generate signals from 3 core strategies
        signals = [
            self.trend_rider(df),
            self.squeeze_rocket(df),
            self.mean_reversion(df)
        ]
        signals = [s for s in signals if s]
        
        score = self.confluence_score(signals, df)
        logger.info(f"  → {len(signals)} signals | **{score:.1f}/10**")
        
        # FIRE SIGNAL if score >= 7.0
        if score >= 7.0 and signals:
            best_signal = max(signals, key=lambda x: x['confidence'])
            
            if self.risk_check(best_signal):
                pos_size = self.calculate_position_size(best_signal)
                embed = self.format_discord_embed(best_signal, score, coin_name, pos_size)
                self.send_discord_alert(embed)
                logger.info(f"✅ **{best_signal['strategy']}** TRADE SIGNAL")
            else:
                logger.info("❌ Risk validation failed")
    
    def run(self):
        """Full market scan."""
        logger.info("🚀 SUPER JOINT ENGINE v3.0")
        logger.info(f"Balance: ${self.balance:,.0f} | Mode: {'DRY' if self.dry_run else 'LIVE'}")
        
        coins = [
            ('bitcoin', 'BTC'),
            ('ethereum', 'ETH'), 
            ('solana', 'SOL')
        ]
        
        for coin_id, name in coins:
            self.analyze_coin(coin_id, name)

def main():
    parser = argparse.ArgumentParser(description="Super Joint Trading Signals")
    parser.add_argument('--live', action='store_true', help="Live Discord alerts")
    parser.add_argument('--balance', type=float, default=10000, help="Account balance USD")
    args = parser.parse_args()
    
    engine = SuperJointEngine(dry_run=not args.live, balance=args.balance)
    engine.run()

if __name__ == "__main__":
    main()
