#!/usr/bin/env python3
import argparse
import yaml
from datafetcher import DataFetcher
from indicators import compute_all_indicators
from strategies.trend_rider import TrendRider  # + all others
from consensusscorer import ConsensusScorer
from riskmanager import RiskManager
from signalformatter import format_discord_embed
from discordnotifier import send_signal
import logging

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--pairs', nargs='+', default=['BTCUSDT'])
    parser.add_argument('--tf', default='1h')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    
    fetcher = DataFetcher()
    scorer = ConsensusScorer()
    rm = RiskManager(fetcher.config)
    
    for pair in args.pairs:
        df = fetcher.fetch_ohlcv(pair, args.tf)
        df = compute_all_indicators(df)
        
        # Run all 8 strategies
        strategies = [TrendRider()]  # +7 more
        signals = [s.generate_signal(df) for s in strategies]
        valid_signals = [s for s in signals if s]
        
        if valid_signals:
            consensus_score = scorer.score_signal(valid_signals, df)
            if consensus_score >= 7.0:
                best_signal = max(valid_signals, key=lambda x: x['confidence'])
                if rm.validate_trade(best_signal):
                    embed = format_discord_embed(best_signal)
                    if not args.dry_run:
                        send_signal(embed)
                    else:
                        print(embed)

if __name__ == "__main__":
    main()
