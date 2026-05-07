import pandas as pd
import numpy as np
from typing import Optional, Dict, Any, List

class SMCEngine:
    def __init__(self):
        self.min_ob_size = 0.01  # 1% body for order block
        self.fvg_threshold = 0.5  # ATR % for FVG
    
    def detect_swing_highs_lows(self, df: pd.DataFrame, window: int = 5) -> tuple:
        """Detect swing highs/lows for BOS/CHOCH."""
        highs = df['high'].rolling(window*2+1, center=True).apply(
            lambda x: x.iloc[window] if x.iloc[window] == x.max() else np.nan
        )
        lows = df['low'].rolling(window*2+1, center=True).apply(
            lambda x: x.iloc[window] if x.iloc[window] == x.min() else np.nan
        )
        return highs, lows
    
    def detect_order_blocks(self, df: pd.DataFrame) -> List[Dict]:
        """Detect Order Blocks (strong candles before reversal)."""
        order_blocks = []
        for i in range(1, len(df)-1):
            candle_body = abs(df['close'].iloc[i] - df['open'].iloc[i]) / df['close'].iloc[i]
            if candle_body > self.min_ob_size:
                # Bullish OB: strong green before bearish move
                if (df['close'].iloc[i] > df['open'].iloc[i] and 
                    df['low'].iloc[i+1:i+6].min() < df['low'].iloc[i]):
                    order_blocks.append({
                        'type': 'bullish',
                        'high': df['high'].iloc[i],
                        'low': df['low'].iloc[i],
                        'index': i
                    })
        return order_blocks
    
    def detect_fvg(self, df: pd.DataFrame, atr: pd.Series) -> List[Dict]:
        """Fair Value Gap: gap between candles > 0.5 ATR."""
        fvgs = []
        for i in range(2, len(df)):
            gap_up = (df['low'].iloc[i] > df['high'].iloc[i-2]) 
            gap_size_up = (df['low'].iloc[i] - df['high'].iloc[i-2]) / atr.iloc[i]
            
            gap_down = (df['high'].iloc[i] < df['low'].iloc[i-2])
            gap_size_down = (df['low'].iloc[i-2] - df['high'].iloc[i]) / atr.iloc[i]
            
            if gap_up and gap_size_up > self.fvg_threshold:
                fvgs.append({'type': 'bullish', 'top': df['low'].iloc[i], 'bottom': df['high'].iloc[i-2]})
            elif gap_down and gap_size_down > self.fvg_threshold:
                fvgs.append({'type': 'bearish', 'top': df['low'].iloc[i-2], 'bottom': df['high'].iloc[i]})
        return fvgs
    
    def detect_bos_choch(self, df: pd.DataFrame) -> Dict[str, bool]:
        """Break of Structure (BOS) vs Change of Character (CHOCH)."""
        highs, lows = self.detect_swing_highs_lows(df)
        latest_high = highs.dropna().iloc[-1] if not highs.dropna().empty else 0
        latest_low = lows.dropna().iloc[-1] if not lows.dropna().empty else float('inf')
        prev_high = highs.dropna().iloc[-2] if len(highs.dropna()) > 1 else 0
        prev_low = lows.dropna().iloc[-2] if len(lows.dropna()) > 1 else float('inf')
        
        latest = df.iloc[-1]
        bos_bull = latest['high'] > prev_high  # New higher high
        bos_bear = latest['low'] < prev_low    # New lower low
        choch_bull = latest['high'] > prev_high and latest['close'] < prev_low  # Structure break + rejection
        
        return {'bos_bull': bos_bull, 'bos_bear': bos_bear, 'choch_bull': choch_bull}
    
    def generate_signal(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Strategy D: Smart Money Concepts.
        Trigger: BOS/CHOCH + OB/FVG + liquidity sweep."""
        
        atr = df['atr'].iloc[-1]
        latest = df.iloc[-1]
        
        # Detect structures
        structure = self.detect_bos_choch(df)
        obs = self.detect_order_blocks(df)
        fvgs = self.detect_fvg(df, df['atr'])
        
        # Recent OB or FVG within range
        recent_ob = any(ob['index'] > len(df)-20 for ob in obs)
        recent_fvg = any(abs(latest['close'] - (fvg['top'] + fvg['bottom'])/2) < atr 
                        for fvg in fvgs[-3:])
        
        # Liquidity sweep: recent high/low swept then reversed
        highs, lows = self.detect_swing_highs_lows(df)
        liquidity_sweep = (
            (latest['low'] < lows.iloc[-2] and latest['close'] > df['open'].iloc[-1]) or  # Sweep low, close green
            (latest['high'] > highs.iloc[-2] and latest['close'] < df['open'].iloc[-1])   # Sweep high, close red
        )
        
        if (structure['bos_bull'] or structure['choch_bull']) and recent_ob and recent_fvg and liquidity_sweep:
            return {
                'direction': 'LONG',
                'confidence': 0.9,  # Highest edge per blueprint
                'entry': latest['close'],
                'stop': min([ob['low'] for ob in obs[-2:]] + [latest['low'] - atr]),
                'target': latest['close'] + 3 * atr,
                'strategies': ['SMC']
            }
        return None
