import json
from typing import Dict, Any
from datetime import datetime, timedelta

class RiskManager:
    def __init__(self, config: Dict):
        self.config = config['risk']
        self.max_risk_pct = self.config['max_risk_pct'] / 100
        self.min_rr = self.config['min_rr']
        self.balance = 10000  # Default - make dynamic
    
    def validate_trade(self, signal: Dict[str, Any]) -> bool:
        """Validate risk rules per blueprint."""
        entry = signal['entry']
        stop = signal['stop']
        target = signal['target']
        
        # Calculate risk/reward
        risk_distance = abs(entry - stop) / entry
        reward_distance = abs(target - entry) / entry
        rr_ratio = reward_distance / risk_distance if risk_distance > 0 else 0
        
        # 1. Min R:R 1:2
        if rr_ratio < self.min_rr:
            print(f"Rejected: R:R {rr_ratio:.2f} < {self.min_rr}")
            return False
        
        # 2. Max 1.5% risk
        risk_amount = self.balance * self.max_risk_pct
        position_size = risk_amount / risk_distance if risk_distance > 0 else 0
        
        if position_size <= 0:
            return False
        
        # Update signal
        signal['risk_distance'] = risk_distance
        signal['rr_ratio'] = rr_ratio
        signal['position_size'] = position_size
        
        print(f"Risk OK: {risk_distance:.1%} risk, {rr_ratio:.1f}:1 R:R, size ${position_size:.0f}")
        return True
