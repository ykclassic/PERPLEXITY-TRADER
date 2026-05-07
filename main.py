#!/usr/bin/env python3
"""
Super Joint Blueprint - Main Orchestrator
Runs full pipeline: data → indicators → strategies → consensus → risk → Discord
"""

import argparse
import logging
import os
import sys
import yaml
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
import pandas as pd

# Core modules
from datafetcher import DataFetcher
from indicators import compute_all_indicators
from consensusscorer import ConsensusScorer
from riskmanager import RiskManager
from signalformatter import format_discord_embed
from discordnotifier import send_signal

# All 8 Strategies
from strategies.trend_rider import TrendRider
from strategies.squeeze_rocket import SqueezeRocket
from strategies.mean_reversion import MeanReversion
from strategies.smc_engine import SMCEngine
from strategies.vwap_reversion import VWAPReversion
from strategies.funding_fade import FundingFade
from strategies.liq_sweep import LiqSweep
from strategies.onchain_macro import OnChainMacro

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('signals.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SignalEngine:
    def __init__(self, config_path: str = "config/config.yaml"):
        """Initialize full engine with config."""
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.fetcher = DataFetcher(config_path)
        self.scorer = ConsensusScorer()
        self.risk_mgr = RiskManager(self.config)
        
        # Initialize all 8 strategies
        self.strategies = [
            TrendRider(),
            SqueezeRocket(),
            MeanReversion(),
            SMCEngine(),
            VWAPReversion(),
            FundingFade(),
            LiqSweep(),
            OnChainMacro()
        ]
        
        # Risk state (persisted)
        self.daily_losses = self.load_risk_state().get('daily_losses', 0)
        self.consecutive_losses = self.load_risk_state().get('consecutive_losses', 0)
    
    def load_risk_state(self) -> Dict:
        """Load persisted risk state."""
        try:
            with open('risk_state.json', 'r') as f:
                import json
                return json.load(f)
        except FileNotFoundError:
            return {}
    
    def save_risk_state(self):
        """Save risk state."""
        state = {
            'daily_losses': self.daily_losses,
            'consecutive_losses': self.consecutive_losses,
            'last_run': datetime.now().isoformat()
        }
        import json
        with open('risk_state.json', 'w') as f:
            json.dump(state, f)
    
    def check_circuit_breakers(self) -> bool:
        """Check all risk circuit breakers."""
        config_risk = self.config['risk']
        
        # Daily loss limit
        if self.daily_losses >= config_risk['daily_loss_limit']:
            logger.warning("Daily loss limit hit. Pausing 24h.")
            return False
        
        # Consecutive losses kill switch
        if self.consecutive_losses >= config_risk['consecutive_losses_limit']:
            logger.error("Kill switch: 3+ consecutive losses. Manual review required.")
            return False
        
        # Weekly drawdown (simplified - implement full P&L tracking)
        return True
    
    def run_pipeline(self, pair: str, timeframe: str) -> List[Dict[str, Any]]:
        """Full pipeline for one pair/timeframe."""
        signals = []
        
        try:
            logger.info(f"Processing {pair} {timeframe}")
            
            # 1. Fetch & prepare data
            df = self.fetcher.fetch_ohlcv(pair, timeframe, limit=500)
            df = compute_all_indicators(df)
            
            if len(df) < 50:  # Need history
                logger.warning(f"Insufficient data for {pair} {timeframe}")
                return signals
            
            # 2. Run all 8 strategies
            raw_signals = []
            for strategy in self.strategies:
                signal = strategy.generate_signal(df)
                if signal:
                    signal['pair'] = pair
                    signal['timeframe'] = timeframe
                    raw_signals.append(signal)
            
            # 3. Consensus scoring
            if raw_signals:
                score = self.scorer.score_signal(raw_signals, df)
                logger.info(f"Consensus score: {score:.1f}/10 for {len(raw_signals)} strategies")
                
                if score >= 7.0:
                    # Pick best signal
                    best_signal = max(raw_signals, key=lambda x: x.get('confidence', 0))
                    best_signal['confidence_score'] = score
                    best_signal['strategies'] = list(set(s['strategies'][0] for s in raw_signals))
                    
                    # 4. Risk validation
                    if self.risk_mgr.validate_trade(best_signal):
                        signals.append(best_signal)
                        logger.info(f"VALID SIGNAL: {best_signal['direction']} {pair}")
                    else:
                        logger.info("Signal rejected by risk manager")
            
            return signals
            
        except Exception as e:
            logger.error(f"Pipeline error {pair} {timeframe}: {e}")
            return signals
    
    def process_all_pairs(self) -> List[Dict[str, Any]]:
        """Run pipeline for all configured pairs/timeframes."""
        if not self.check_circuit_breakers():
            return []
        
        all_signals = []
        pairs = self.args.pairs if hasattr(self, 'args') else self.config['pairs']
        timeframes = [self.args.tf] if hasattr(self, 'args') and self.args.tf else self.config['timeframes']
        
        for pair in pairs:
            for tf in timeframes:
                signals = self.run_pipeline(pair, tf)
                all_signals.extend(signals)
        
        return all_signals
    
    def send_signals(self, signals: List[Dict[str, Any]]):
        """Send valid signals to Discord."""
        for signal in signals:
            embed = format_discord_embed(signal)
            if not self.args.dry_run:
                response = send_signal(embed)
                logger.info(f"Signal sent: {response.status_code}")
            else:
                print("DRY RUN:\n", embed)
    
    def update_risk_state(self, signals: List):
        """Update risk tracking (simplified)."""
        if not signals:
            self.consecutive_losses += 1
        else:
            self.consecutive_losses = 0  # Reset on win
        self.save_risk_state()

def main():
    parser = argparse.ArgumentParser(description="Super Joint Crypto Signal Engine")
    parser.add_argument('--pairs', nargs='+', default=None, help="Pairs to process")
    parser.add_argument('--tf', default='1h', help="Timeframe")
    parser.add_argument('--dry-run', action='store_true', help="Don't send to Discord")
    parser.add_argument('--config', default='config/config.yaml', help="Config file")
    args = parser.parse_args()
    
    engine = SignalEngine(args.config)
    engine.args = args  # Pass args to engine
    
    logger.info("=== Super Joint Signal Engine Started ===")
    logger.info(f"Mode: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    
    # Run pipeline
    signals = engine.process_all_pairs()
    
    # Send signals
    if signals:
        logger.info(f"Found {len(signals)} valid signals (score >=7/10)")
        engine.send_signals(signals)
        engine.update_risk_state(signals)
    else:
        logger.info("No qualifying signals found")
        engine.update_risk_state([])
    
    logger.info("Pipeline complete")

if __name__ == "__main__":
    main()
