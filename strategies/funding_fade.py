# Note: Requires external API call to Coinglass for funding/OI
# Placeholder - integrate in onchainengine.py
class FundingFade:
    def generate_signal(self, df: pd.DataFrame, funding_rate: float = 0, long_short_ratio: float = 1.0, oi_change: float = 0) -> Optional[Dict[str, Any]]:
        """Strategy F: Funding Rate OI Divergence.
        Signal: Funding <-0.1% AND L/S >3 (short) OR price up + OI declining."""
        
        latest = df.iloc[-1]
        
        # Extreme funding + crowd positioning
        short_signal = funding_rate < -0.001 and long_short_ratio > 3.0
        long_signal = funding_rate > 0.001 and long_short_ratio < 0.33
        
        # Weak trend: price up but OI declining
        price_up_oi_down = (latest['close'] > df['close'].iloc[-5] and oi_change < 0)
        
        if short_signal or (price_up_oi_down and funding_rate > 0):
            return {
                'direction': 'SHORT' if short_signal else 'LONG',
                'confidence': 0.8,
                'entry': latest['close'],
                'stop': latest['high'] + latest['atr'],
                'target': latest['close'] - 1.5 * latest['atr'],
                'strategies': ['FundingFade']
            }
        return None
