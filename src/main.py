#!/usr/bin/env python3
"""
Super Joint Crypto Signal Engine - FULLY SELF-CONTAINED
Auto-creates config.yaml + 9 pairs x 3 TFs + Dual Discord
"""

import sys
import os
import argparse
import logging
import yaml
import requests
import pandas as pd
import numpy as np
import pandas_ta_classic as ta
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
        
        # Auto-create config if missing
        if not os.path.exists(config_path):
            self.create_default_config(config_path)
        
        # Load config
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.balance = 25000
        self.max_risk_pct = self.config['risk']['max_risk_pct'] / 100
        self.min_rr = self.config['risk']['min_rr']
        
        # CoinGecko mapping for USDT pairs
        self.pair_map = {
            'BTCUSDT': 'bitcoin', 'ETHUSDT': 'ethereum', 'SOLUSDT': 'solana',
            'BNBUSDT': 'binancecoin', 'ADAUSDT': 'cardano', 'XRPUSDT': 'ripple',
            'MATICUSDT': 'matic-network', 'LINKUSDT': 'chainlink', 'TONUSDT': 'toncoin'
        }
        
        logger.info(f"✅ Loaded {len(self.config['pairs'])} pairs x {len(self.config['timeframes'])} TFs")
    
    def create_default_config(self, path: str):
        """Auto-generate your exact config."""
        config = {
            'discord': {
                'webhook_url': '${DISCORD_WEBHOOK}',
                'signals_channel': 'signals',
                'high_conviction_channel': 'high-conviction'
            },
            'pairs': ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'ADAUSDT', 
                     'XRPUSDT', 'MATICUSDT', 'LINKUSDT', 'TONUSDT'],
            'timeframes': ['15m', '1h', '4h'],
            'risk': {
                'max_risk_pct': 1.5, 'min_rr': 2.0, 'max_correlated_trades': 3,
                'weekly_dd_limit': 10.0, 'daily_loss_limit': 4.0, 'consecutive_losses_limit': 3
            },
            'apis': {'binance': True, 'coingecko': True, 'glassnode': 'demo'}
        }
        
        os.makedirs(os.path.dirname(path) if os.path.dirname(path) else '.', exist_ok=True)
        with open(path, 'w') as f:
            yaml.dump(config, f, default_flow_style=False)
        logger.info(f"✅ Created {path}")
    
    def fetch_data(self, pair: str, timeframe: str = '1h') -> pd.DataFrame:
        """CoinGecko data for exchange pairs."""
        coin_id = self.pair_map.get(pair, pair.lower().replace('usdt', ''))
        
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
            
            logger.info(f"✅ {pair}: {len(df)} candles")
            return df
        except Exception as e:
            logger.warning(f"❌ {pair}: {e}")
            return pd.DataFrame()
    
    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Core technical analysis."""
        if len(df) < 40:
            return df
        
        # EMAs
        for period in [8, 21, 50, 200]:
            df[f'ema_{period}'] = ta.ema(df['close'], period)
        
        df['rsi'] = ta.rsi(df['close'], 14)
        df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)
        
        # BB
        try:
            bb = ta.bbands(df['close'])
            if isinstance(bb, pd.DataFrame) and not bb.empty:
                bb_cols = bb.columns
                df['bb_upper'] = bb[bb_cols[0]]
                df['bb_lower'] = bb[bb_cols[2]]
                df['bb_mid'] = bb[bb_cols[1]]
        except:
            df['bb_upper'] = df['close'] * 1.02
            df['bb_lower'] = df['close'] * 0.98
            df['bb_mid'] = df['close']
        
        return df.dropna()
    
    def generate_signals(self, df: pd.DataFrame, timeframe: str) -> List[Dict]:
        """3 core strategies."""
        signals = []
        latest = df.iloc[-1]
        
        # Trend Rider
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
        
        # Squeeze Breakout
        squeeze = (df['close'].rolling(20).std() < df['atr'] * 0.5).sum()
        if squeeze >= 8 and latest['close'] > latest['bb_upper']:
            signals.append({
                'direction': 'LONG',
                'confidence': 0.88,
                'strategy': f'Squeeze-{timeframe}',
                'entry': latest['close'],
                'stop': latest['bb_lower'],
                'target': latest['close'] + latest['atr'] * 3
            })
        
        # Mean Reversion
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
        """Multi-strategy scoring."""
        if not signals:
            return 0.0
        
        latest = df.iloc[-1]
        score = len(signals) * 1.8
        score += 2.0 if latest['close'] > latest['ema_50'] else 0
        score += 1.5 if 45 < latest['rsi'] < 75 else 0
        score += 1.0 if latest['volume'] > df['volume'].mean() else 0
        return min(score, 10.0)
    
    def position_size(self, signal: Dict) -> float:
        risk_dist = abs(signal['entry'] - signal['stop']) / signal['entry']
        risk_amount = self.balance * self.max_risk_pct
        return round(risk_amount / risk_dist, 0)
    
    def validate_trade(self, signal: Dict) -> bool:
        risk_dist = abs(signal['entry'] - signal['stop']) / signal['entry']
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        return rr >= self.min_rr and risk_dist <= 0.03
    
    def format_embed(self, signal: Dict, score: float, pair: str, tf: str, size: float) -> str:
        entry, sl, tp = f"{signal['entry']:,.0f}", f"{signal['stop']:,.0f}", f"{signal['target']:,.0f}"
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        channel = "high-conviction" if score >= 8.5 else "signals"
        
        return f"""🚨 **{pair} {tf}** 🚨
`{signal['direction']} | {signal['strategy']}`

💰 **ENTRY**: `{entry}$`
🛑 **STOP**: `{sl}$`  
🎯 **TARGET**: `{tp}$`

⚖️ **R:R**: `1:{rr:.1f}`
📊 **SCORE**: `{score:.1f}/10`
💼 **SIZE**: `${size:,}`

---
#{channel} | {datetime.now().strftime('%H:%M UTC')}
"""
    
    def send_alert(self, embed: str):
        if self.dry_run:
            print("\n" + "="*70)
            print(embed)
            print("="*70 + "\n")
            return
        
        webhook = os.getenv('DISCORD_WEBHOOK')
        if webhook and DISCORD_AVAILABLE:
            try:
                DiscordWebhook(url=webhook, content=embed[:1900]).execute()
                logger.info("✅ Discord alert sent")
            except Exception as e:
                logger.error(f"Discord: {e}")
    
    def scan_pair(self, pair: str, timeframe: str):
        logger.info(f"🔄 {pair} {timeframe}")
        
        df = self.fetch_data(pair, timeframe)
        if df.empty or len(df) < 40:
            return
        
        df = self.compute_indicators(df)
        signals = self.generate_signals(df, timeframe)
        score = self.confluence_score(signals, df)
        
        logger.info(f"  → {len(signals)} signals | **{score:.1f}/10**")
        
        if score >= 7.0 and signals:
            best = max(signals, key=lambda x: x['confidence'])
            if self.validate_trade(best):
                size = self.position_size(best)
                embed = self.format_embed(best, score, pair, timeframe, size)
                self.send_alert(embed)
    
    def run(self):
        logger.info("🚀 SUPER JOINT ENGINE v6 - 9x3 SCAN")
        for pair in self.config['pairs']:
            for tf in self.config['timeframes']:
                self.scan_pair(pair, tf)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    args = parser.parse_args()
    
    engine = SuperJointEngine(dry_run=not args.live)
    engine.run()

if __name__ == "__main__":
    main()
