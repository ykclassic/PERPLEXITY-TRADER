class RiskManager:
    def __init__(self, config):
        self.max_risk_pct = config['risk']['max_risk_pct'] / 100
        self.min_rr = config['risk']['min_rr']
        self.daily_losses = 0  # Track state
    
    def validate_trade(self, signal: dict, account_balance: float = 10000) -> bool:
        risk_distance = abs(signal['entry'] - signal['stop']) / signal['entry']
        rr = abs(signal['target'] - signal['entry']) / abs(signal['entry'] - signal['stop'])
        
        position_size = (account_balance * self.max_risk_pct) / risk_distance
        
        if rr >= self.min_rr and position_size > 0:
            signal['position_size'] = position_size
            return True
        return False
