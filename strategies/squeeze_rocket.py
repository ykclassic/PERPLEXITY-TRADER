import pandas as pd
import numpy as np
from typing import Optional, Dict, Any

class SqueezeRocket:
    def __init__(self):
        self.squeeze_bars = 15  # BB inside KC for 15 bars
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Strategy B: Breakout Engine Squeeze Rocket.
        Trigger: BB inside Keltner 15 bars, then break above upper BB.
        Confirmation: Volume 1.5x avg, OBV new high."""
        
        # Check squeeze condition (BB inside KC)
        squeeze_condition = (
            (df['bb_upper'] < df['kc_upper']) & 
            (df['bb_lower'] > df['kc_lower'])
        ).rolling(self.squeeze_bars).sum() == self.squeeze_bars
        
        squeeze_ended = squeeze_condition.shift(1).iloc[-1] and not squeeze_condition.iloc[-1]
        
        latest = df.iloc[-1]
        prev = df.iloc[-2]
        
        # Breakout above upper BB with volume confirmation
        volume_spike = latest['volume'] > 1.5 * df['volume'].rolling(20).mean().iloc[-1]
        obv_new_high = latest['obv'] > df['obv'].rolling(20).max().iloc[-2]
        bb_breakout = latest['close'] > latest['bb_upper']
        
        if squeeze_ended and bb_breakout and volume_spike and obv_new_high:
            atr = latest['atr']
            return {
                'direction': 'LONG',
                'confidence': 0.85,
                'entry': latest['close'],
                'stop': latest['bb_lower'] - atr,  # Below squeeze low
                'target': latest['close'] + 2 * atr,
                'strategies': ['SqueezeRocket']
            }
        return None
