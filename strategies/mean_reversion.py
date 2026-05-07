import pandas as pd
from typing import Optional, Dict, Any

class MeanReversion:
    def generate_signal(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Strategy C: Mean Reversion Engine.
        Trigger: RSI 30/70 + BB touch + CCI extreme."""
        
        latest = df.iloc[-1]
        
        oversold = latest['rsi'] < 30 and latest['close'] <= latest['bb_lower']
        overbought = latest['rsi'] > 70 and latest['close'] >= latest['bb_upper']
        
        cci_oversold = latest['cci'] < -100
        cci_overbought = latest['cci'] > 100
        
        mfi_turn = latest['mfi'] > df['mfi'].rolling(14).min().iloc[-1]  # MFI bottoming
        stoch_cross = latest['stochrsi'] > df['stochrsi'].shift(1).iloc[-1]  # StochRSI turning up
        
        if oversold and cci_oversold and (mfi_turn or stoch_cross):
            return {
                'direction': 'LONG',
                'confidence': 0.75,
                'entry': latest['bb_mid'],  # Mean reversion target
                'stop': latest['low'] - latest['atr'],
                'target': latest['bb_mid'],
                'strategies': ['MeanReversion']
            }
        elif overbought and cci_overbought and (mfi_turn or stoch_cross):
            return {
                'direction': 'SHORT',
                'confidence': 0.75,
                'entry': latest['bb_mid'],
                'stop': latest['high'] + latest['atr'],
                'target': latest['bb_mid'],
                'strategies': ['MeanReversion']
            }
        return None
