def format_discord_embed(signal: dict) -> str:
    """Build rich Discord embed payload."""
    return f"""
**{signal['pair']} {signal['direction']} {signal['timeframe']}**
Entry: {signal['entry']:.2f}
SL: {signal['stop']:.2f}
TP1: {signal['target']:.2f} (1R)

**Confidence**: {signal['confidence']:.1f}/10
**Strategies**: {', '.join(signal['strategies'])}
**R:R**: 1:{signal['rr']:.1f}
"""
