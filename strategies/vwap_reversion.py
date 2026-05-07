import pandas as pd
from typing import Optional, Dict, Any
import numpy as np

class VWAPReversion:
    def generate_signal(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Strategy E: VWAP Reversion.
        Entry: Price >1.5 SD from VWAP + RSI divergence."""
        
        latest = df.iloc[-1]
        vwap_dev = abs(latest['close'] - latest['vwap']) / latest['atr']
        
        # 1.5 ATR deviation from VWAP (proxy for SD)
        extreme_dev = vwap_dev > 1.5
        
        # RSI divergence: price makes new extreme but RSI doesn't
        price_new_high = latest['close'] > df['close'].rolling(20).max().iloc[-2]
        rsi_not_new_high = latest['rsi'] < df['rsi'].rolling(20).max().iloc[-2]
        
        volume_declining = latest['volume'] < df['volume'].rolling(10).mean().iloc[-1]
        
        if extreme_dev and price_new_high and rsi_not_new_high and volume_declining:
            direction = 'SHORT'  # Fade extension
        elif extreme_dev and (latest['close'] < df['close'].rolling(20).min().iloc[-2]) and volume_declining:
            direction = 'LONG'
        else:
            return None
        
        return {
            'direction': direction,
            'confidence': 0.7,
            'entry': latest['close'],
            'stop': latest['close'] + 1.5 * latest['atr'] if direction == 'SHORT' else latest['close'] - 1.5 * latest['atr'],
            'target': latest['vwap'],
            'strategies': ['VWAPReversion']
        }
