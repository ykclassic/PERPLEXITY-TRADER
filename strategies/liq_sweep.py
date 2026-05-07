class LiqSweep:
    def generate_signal(self, df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """Strategy G: Liquidation Sweep Reversal.
        Trigger: Price sweeps recent swing then reverses sharply."""
        
        latest = df.iloc[-1]
        prev_candle = df.iloc[-2]
        
        # Detect swing high/low sweep
        swing_high = df['high'].rolling(10).max().iloc[-2]
        swing_low = df['low'].rolling(10).min().iloc[-2]
        
        swept_high = latest['high'] > swing_high and latest['close'] < prev_candle['open']
        swept_low = latest['low'] < swing_low and latest['close'] > prev_candle['open']
        
        # Sharp reversal candle + volume
        reversal_strength = abs(latest['close'] - prev_candle['close']) / latest['atr'] > 1.5
        volume_spike = latest['volume'] > 2 * df['volume'].rolling(20).mean().iloc[-1]
        
        if (swept_high or swept_low) and reversal_strength and volume_spike:
            direction = 'LONG' if swept_low else 'SHORT'
            stop = swing_low - latest['atr'] if direction == 'LONG' else swing_high + latest['atr']
            
            return {
                'direction': direction,
                'confidence': 0.85,
                'entry': latest['close'],
                'stop': stop,
                'target': latest['close'] + 2 * latest['atr'] * (-1 if direction == 'SHORT' else 1),
                'strategies': ['LiqSweep']
            }
        return None
