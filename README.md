# Super Joint Blueprint - Unified Crypto Signal Engine

Production-grade crypto trading signal generator based on convergence across 40+ indicators, 8 strategies, SMC, on-chain, and derivatives data. Delivers Discord signals with 7/10+ confidence score.

## Features
- Multi-timeframe analysis (15m-4h)
- 8 parallel strategies with consensus scoring
- Strict risk management (1.5% risk, 1:2 RR min)
- Free APIs only (CCXT, CoinGecko, Glassnode free)
- GitHub Actions deployment (zero cost)
- Backtesting + drawdown protection

## Quick Start
1. `pip install -r requirements.txt`
2. Copy `config/config.yaml.example` to `config.yaml` and set Discord webhook
3. `python src/main.py` (local test)
4. Enable GitHub Actions for scheduled runs

## Architecture
See [GUIDE.md](GUIDE.md) for full blueprint implementation.

## Deployment Options
- **Free**: GitHub Actions (1h signals)
- **24/7**: Oracle VPS Free Tier + cron
- **Pro**: Railway/Render ($5/mo)

**Disclaimer**: For educational purposes. Backtest thoroughly. No financial advice.
