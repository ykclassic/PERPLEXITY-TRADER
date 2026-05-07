class OnChainMacro:
    def generate_signal(self, df: pd.DataFrame, mvrv_z: float = 0, puell: float = 1.0, netflow: float = 0) -> Optional[Dict[str, Any]]:
        """Strategy H: On-Chain Alpha Macro Timing.
        Long: MVRV Z<0, Puell<0.5, netflow negative."""
        
        # Macro bias only - slow moving
        long_bias = mvrv_z < 0 and puell < 0.5 and netflow < 0
        short_bias = mvrv_z > 5 and puell > 3 and netflow > 0
        
        latest = df.iloc[-1]
        if long_bias:
            return {
                'direction': 'LONG',
                'confidence': 0.6,  # Position sizing guide
                'entry': latest['close'],
                'stop': latest['ema_200'],
                'target': latest['close'] + 10 * latest['atr'],  # Swing
                'strategies': ['OnChainMacro']
            }
        elif short_bias:
            return {
                'direction': 'SHORT',
                'confidence': 0.6,
                'entry': latest['close'],
                'stop': latest['ema_200'],
                'target': latest['close'] - 10 * latest['atr'],
                'strategies': ['OnChainMacro']
            }
        return None
