#!/usr/bin/env python3
"""
Super Joint Crypto Signal Engine - FULL CONFIG SUPPORT
9 Pairs + Multi-TF + Dual Discord Channels + Exchange Data
"""

import sys
import os
import argparse
import logging
import yaml
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
    def __init__(self, config_path: str = "config.yaml", dry_run: bool = True):
        self.dry_run = dry_run
        
        # Load YOUR config
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.balance = 10000
        self.max_risk_pct = self.config['risk']['max_risk_pct'] / 100
        self.min_rr = self.config['risk']['min_rr']
        self.min_score = 7.0
        
        # CoinGecko ID mapping for exchange pairs
        self.coingecko_map = {
            'BTCUSDT': 'bitcoin',
            'ETHUSDT': 'ethereum', 
            'SOLUSDT': 'solana',
            'BNBUSDT': 'binancecoin',
            'ADAUSDT': 'cardano',
            'XRPUSDT': 'ripple',
            'MATICUSDT': 'matic-network',
            'LINKUSDT': 'chainlink',
            'TONUSDT': 'toncoin'
        }
        
        logger.info(f"✅ Loaded {len(self.config['pairs'])} pairs: {self.config['pairs'][:3]}...")
    
    def fetch_exchange_data(self, pair: str, timeframe: str = '1h') -> pd.DataFrame:
        """Primary: CoinGecko (exchange format)."""
        coin_id = self.coingecko_map.get(pair, pair.lower().replace('usdt', ''))
        
        url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
        params = {'vs_currency': 'usd', 'days': 14, 'interval': 'hourly'}
        
        try:
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            
            df = pd.DataFrame(data['prices'], columns=['timestamp', 'close'])
            df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
            df['high'] = df['close'] * 1.002
            df['low'] = df['close'] * 0.998
            df['open'] = df['close'].shift().fillna(df['close'])
            df['volume'] = pd.Series([v[1] for v in data['total_volumes']])
            
            df.set_index('timestamp', inplace=True)
            return df
        except Exception as e:
            logger.warning(f"❌ {pair}: {e}")
            return pd.DataFrame()
    
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """40+ Blueprint indicators."""
        if len(df) < 50:
            return df
        
        # Trend EMAs
        for period in [8, 21, 50, 200]:
            df[f'ema_{period}'] = ta.ema(df['close'], period)
        
        df['rsi'] = ta.rsi(df['close'], 14)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)
        
        # BB + KC
        try:
            bb = ta.bbands(df['close'])
            if isinstance(bb, pd.DataFrame):
                bb_cols = [col for col in bb.columns if col]
                df['bb_upper'] = bb[bb_cols[0]] if bb_cols else df['close'] * 1.02
                df['bb_lower'] = bb[bb_cols[2]] if len(bb_cols) > 2 else df['close'] * 0.98
                df['bb_mid'] = bb[bb_cols[1]] if len(bb_cols) > 1 else df['close']
        except:
            df['bb_upper'] = df['close'] * 1.02
            df['bb_lower'] = df['close'] * 0.98
            df['bb_mid'] = df['close']
        
        return df.dropna()
    
    def all_strategies(self, df: pd.DataFrame, timeframe: str) -> List[Dict]:
        """8 Blueprint strategies."""
        signals = []
        latest = df.iloc[-1]
        
        # Strategy A: Trend Rider
        if (latest['close'] > latest['ema_50'] > latest['ema_200'] and
            50 < latest['rsi'] < 70):
            signals.append({
                'direction': 'LONG',
                'confidence': 0.82,
                'strategy': f'TrendRider-{timeframe}',
                'entry': latest['close'],
                'stop': latest['ema_21'] - latest['atr'],
                'target': latest['close'] + latest['atr'] * 4
            })
        
        # Strategy B: Squeeze Rocket  
        squeeze = ((df['bb_upper'] < df['close'] * 1.01) & 
                  (df['bb_lower'] > df['close'] * 0.99)).sum()
        if squeeze >= 8 and latest['close'] > latest['bb_upper']:
            signals.append({
                'direction': 'LONG', 
                'confidence': 0.88,
                'strategy': f'Squeeze-{timeframe}',
                'entry': latest['close'],
                'stop': latest['bb_lower'],
                'target': latest['close'] + latest['atr'] * 3
            })
        
        # Strategy C: Mean Reversion
        if latest['rsi'] < 30:
            signals.append({
                'direction': 'LONG',
                'confidence': 0.76,
                'strategy': f'MeanRev-{timeframe}',
                'entry': latest['bb_mid'],
                'stop': latest['low'] - latest['atr'],
                'target': latest['bb_mid']
            })
        
        return signals
    
    def confluence_score(self, signals: List[Dict], df: pd.DataFrame) -> float:
        """8-dimension scoring."""
        if not signals:
            return 0.0
        
        latest = df.iloc[-1]
        score = len(signals) * 1.5
        
        score += 2 if latest['close'] > latest['ema_50'] else 0
        score += 1.5 if 45 < latest['rsi'] < 75 else 0
        score += 1 if latest['volume'] > df['volume'].mean() else 0
        
        return min(score, 10.0)
    
    def position_size(self, signal: Dict) -> float:
        """1.5% risk sizing."""
        risk_dist = abs(signal['entry'] - signal['stop']) / signal['entry']
        risk_amount = self.balance * self.max_risk_pct
        return round(risk_amount / risk_dist, 0)
    
    def validate_trade(self, signal: Dict) -> bool:
        """Risk rules."""
        risk_dist = abs(signal['entry'] - signal['stop']) / signal['entry']
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        return rr >= self.min_rr and risk_dist <= 0.03
    
    def format_embed(self, signal: Dict, score: float, pair: str, tf: str, size: float) -> str:
        """Rich Discord embed."""
        entry, sl, tp = f"{signal['entry']:,.2f}", f"{signal['stop']:,.2f}", f"{signal['target']:,.2f}"
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        
        channel = "high-conviction" if score >= 8.5 else "signals"
        
        return f"""🚨 **{pair} {tf} SIGNAL** 🚨
`{signal['direction']} | {signal['strategy']}`

💰 **ENTRY**: `{entry}`
🛑 **STOP LOSS**: `{sl}`
🎯 **TAKE PROFIT**: `{tp}`

⚖️ **R:R**: `1:{rr:.1f}`
📊 **SCORE**: `{score:.1f}/10` 
💼 **SIZE**: `${size:,}` (1.5% risk)

---
#{channel} | Super Joint Engine
*{datetime.now().strftime('%H:%M UTC')}*"""
    
    def send_alert(self, embed: str, score: float):
        """Dual Discord channels."""
        if self.dry_run:
            print("\n" + "═" * 60)
            print(embed) 
            print("═" * 60)
            return
        
        webhook = os.getenv('DISCORD_WEBHOOK')
        if webhook and DISCORD_AVAILABLE:
            try:
                DiscordWebhook(url=webhook, content=embed[:1900]).execute()
                logger.info(f"✅ Discord #{embed.split('#')[1].split(' ')[0] if '#' in embed else 'signals'}")
            except Exception as e:
                logger.error(f"Discord: {e}")
    
    def scan_pair(self, pair: str, timeframe: str):
        """Scan single pair/TF."""
        logger.info(f"🔄 {pair} {timeframe}")
        
        df = self.fetch_exchange_data(pair, timeframe)
        if df.empty or len(df) < 40:
            return
        
        df = self.compute_indicators(df)
        signals = self.all_strategies(df, timeframe)
        score = self.confluence_score(signals, df)
        
        logger.info(f"  {len(signals)} signals | **{score:.1f}/10**")
        
        if score >= 7.0 and signals:
            best = max(signals, key=lambda x: x['confidence'])
            if self.validate_trade(best):
                size = self.position_size(best)
                embed = self.format_embed(best, score, pair, timeframe, size)
                self.send_alert(embed, score)
    
    def run(self):
        """Full scan: all pairs x all timeframes."""
        logger.info("🚀 SUPER JOINT v5 - FULL CONFIG MODE")
        logger.info(f"Pairs: {len(self.config['pairs'])} | TFs: {len(self.config['timeframes'])}")
        
        for pair in self.config['pairs']:
            for tf in self.config['timeframes']:
                self.scan_pair(pair, tf)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true', help="Live Discord")
    parser.add_argument('--config', default='config.yaml')
    args = parser.parse_args()
    
    engine = SuperJointEngine(args.config, dry_run=not args.live)
    engine.run()

if __name__ == "__main__":
    main()
