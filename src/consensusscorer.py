import pandas as pd
from typing import List, Dict, Any

class ConsensusScorer:
    def score_signal(self, strategy_signals: List[Dict[str, Any]], df: pd.DataFrame) -> float:
        """Score 0-10 across 8 dimensions per blueprint."""
        score = 0.0
        latest = df.iloc[-1]
        
        # 1. TREND ALIGNMENT (2 pts max)
        ema_bullish = (latest['ema_50'] > latest['ema_200'] and 
                      latest['close'] > latest['ema_50'])
        trend_healthy = (latest['close'] > latest['supertrend'] and 
                        latest['close'] > latest['ichimoku'])
        score += 2 if ema_bullish and trend_healthy else 1 if ema_bullish or trend_healthy else 0
        
        # 2. MOMENTUM (1.5 pts max)
        momentum_good = (40 < latest['rsi'] < 80 and 
                        latest['macd_hist'] > 0 and 
                        latest['cci'] > -100)
        score += 1.5 if momentum_good else 0.75 if latest['rsi'] > 40 else 0
        
        # 3. VOLUME CONFIRMATION (1.5 pts max)
        vol_confirm = (latest['volume'] > df['volume'].rolling(20).mean().iloc[-1] and
                      latest['obv'] > df['obv'].rolling(20).min().iloc[-1])
        score += 1.5 if vol_confirm else 0.75
        
        # 4. MARKET STRUCTURE SMC (2 pts max) - highest edge
        highs = df['high'].rolling(11, center=True).max()
        lows = df['low'].rolling(11, center=True).min()
        smc_bull = latest['high'] > highs.iloc[-2]  # BOS higher high
        score += 2 if smc_bull else 1
        
        # 5. VOLATILITY REGIME (1 pt max)
        squeeze_expanding = (latest['bb_upper'] > latest['kc_upper'] or 
                           latest['bb_lower'] < latest['kc_lower'])
        score += 1 if squeeze_expanding else 0.5
        
        # 6. MULTI-TF ALIGNMENT (0.5 pt) - simplified
        score += 0.5 if latest['rsi'] > 50 else 0
        
        # 7-8. ON-CHAIN/SENTIMENT - placeholders (add API data)
        score += 0.5  # Neutral default
        
        return min(score, 10.0)
