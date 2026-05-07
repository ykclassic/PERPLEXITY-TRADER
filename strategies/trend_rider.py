import pandas as pd
from typing import Optional, Dict, Any

class TrendRider:
    def __init__(self):
        pass
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Strategy A: Trend Rider Momentum Continuation."""
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        conditions = (
            latest['close'] > latest['ema_50'] > latest['ema_200'] and
            latest['rsi'] > 50 and latest['rsi'] < 70 and
            latest['macd_hist'] > 0 and prev['macd_hist'] < latest['macd_hist'] and
            latest['volume'] > df['volume'].rolling(20).mean().iloc[-1]
        )
        
        if conditions:
            return {
                'direction': 'LONG',
                'confidence': 0.8,
                'entry': latest['close'],
                'stop': latest['supertrend'],
                'target': latest['close'] + 4 * latest['atr']
            }
        return None
