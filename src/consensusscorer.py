import pandas as pd  # ← THIS WAS MISSING!
from typing import List, Dict, Any

class ConsensusScorer:
    def score_signal(self, strategy_signals: List[Dict[str, Any]], df: pd.DataFrame) -> float:
        """Score 0-10 across 8 dimensions per blueprint."""
        if df.empty or len(df) < 20:
            return 0.0
            
        score = 0.0
        latest = df.iloc[-1]
        
        # 1. TREND ALIGNMENT (2 pts max): EMA ribbon + Supertrend + Ichimoku
        ema_bullish = (latest['ema_50'] > latest['ema_200'] and latest['close'] > latest['ema_50'])
        trend_healthy = (latest['close'] > latest.get('supertrend', latest['close']) and 
                        latest['close'] > latest.get('ichimoku', latest['close']))
        score += 2 if ema_bullish and trend_healthy else 1 if ema_bullish or trend_healthy else 0
        
        # 2. MOMENTUM (1.5 pts): RSI + MACD + CCI
        momentum_good = (40 < latest['rsi'] < 80 and 
                        latest['macd_hist'] > 0 and 
                        latest['cci'] > -100)
        score += 1.5 if momentum_good else 0.75 if latest['rsi'] > 40 else 0
        
        # 3. VOLUME CONFIRMATION (1.5 pts): Volume + OBV
        vol_avg = df['volume'].rolling(20).mean().iloc[-1]
        obv_trend = latest['obv'] > df['obv'].rolling(20).min().iloc[-1]
        vol_confirm = (latest['volume'] > 1.5 * vol_avg) and obv_trend
        score += 1.5 if vol_confirm else 0.75 if latest['volume'] > vol_avg else 0
        
        # 4. MARKET STRUCTURE SMC (2 pts): BOS proxy via swing breaks
        highs = df['high'].rolling(11, center=True).max()
        lows = df['low'].rolling(11, center=True).min()
        smc_bull = latest['high'] > highs.iloc[-2]
        smc_bear = latest['low'] < lows.iloc[-2]
        score += 2 if smc_bull or smc_bear else 1
        
        # 5. VOLATILITY REGIME (1 pt): BB/KC squeeze expansion
        squeeze_expanding = (latest['bb_upper'] > latest['kc_upper'] or 
                           latest['bb_lower'] < latest['kc_lower'])
        score += 1 if squeeze_expanding else 0.5
        
        # 6. SENTIMENT EXTREME (0.5 pt): RSI extremes
        score += 0.5 if latest['rsi'] > 70 or latest['rsi'] < 30 else 0
        
        # 7. STRATEGY AGREEMENT (1 pt): Multiple strategies align
        num_strategies = len(strategy_signals)
        score += min(1.0, num_strategies * 0.3)
        
        # 8. MULTI-TF ALIGNMENT (0.5 pt): Simplified momentum
        score += 0.5 if latest['rsi'] > 50 else 0
        
        return min(max(score, 0), 10.0)  # Clamp 0-10
