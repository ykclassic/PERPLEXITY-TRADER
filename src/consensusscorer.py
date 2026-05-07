class ConsensusScorer:
    def score_signal(self, strategy_signals: list, df: pd.DataFrame) -> float:
        """Score 0-10 across 8 dimensions."""
        score = 0.0
        
        # 1. Trend Alignment (2 pts)
        latest = df.iloc[-1]
        if (latest['ema_50'] > latest['ema_200'] and 
            latest['close'] > latest['supertrend']):
            score += 2
        
        # 2. Momentum (1.5 pts)
        if 40 < latest['rsi'] < 80 and latest['macd_hist'] > 0:
            score += 1.5
        
        # ... Add other 6 dimensions (volume=1.5, SMC=2, on-chain=1, etc.)
        
        return min(score, 10.0)
