import pandas_ta_classic as ta
import numpy as np
import pandas as pd

def compute_all_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Compute 40+ indicators from blueprint."""
    # Trend
    df['ema_8'] = ta.ema(df['close'], 8)
    df['ema_13'] = ta.ema(df['close'], 13)
    df['ema_21'] = ta.ema(df['close'], 21)
    df['ema_50'] = ta.ema(df['close'], 50)
    df['ema_100'] = ta.ema(df['close'], 100)
    df['ema_200'] = ta.ema(df['close'], 200)
    df['sma_50'] = ta.sma(df['close'], 50)
    df['sma_200'] = ta.sma(df['close'], 200)
    supertrend = ta.supertrend(df['high'], df['low'], df['close'], length=10, multiplier=3)
    df['supertrend'] = supertrend['SUPERT_10_3.0']
    df['ichimoku'] = ta.ichimoku(df['high'], df['low'], df['close'])['ISA_9']
    df['psar'] = ta.psar(df['high'], df['low'], df['close'])['PSARl_0.02_0.2']
    
    # Momentum
    df['rsi'] = ta.rsi(df['close'], 14)
    macd = ta.macd(df['close'])
    df['macd'] = macd['MACD_12_26_9']
    df['macd_hist'] = macd['MACDh_12_26_9']
    df['stochrsi'] = ta.stochrsi(df['close'])['STOCHRSIk_14_14_3_3']
    df['cci'] = ta.cci(df['high'], df['low'], df['close'], 20)
    df['mfi'] = ta.mfi(df['high'], df['low'], df['close'], df['volume'], 14)
    df['willr'] = ta.willr(df['high'], df['low'], df['close'], 14)
    df['roc'] = ta.roc(df['close'], 10)
    
    # Volatility
    bb = ta.bbands(df['close'], 20, 2)
    df['bb_upper'] = bb['BBU_20_2.0']
    df['bb_lower'] = bb['BBL_20_2.0']
    df['bb_mid'] = bb['BBM_20_2.0']
    kc = ta.kc(df['high'], df['low'], df['close'], 20, 1.5)
    df['kc_upper'] = kc['KCUe_20_1.5']
    df['kc_lower'] = kc['KCL_20_1.5']
    df['atr'] = ta.atr(df['high'], df['low'], df['close'], 14)
    
    # Volume
    df['obv'] = ta.obv(df['close'], df['volume'])
    df['vwap'] = ta.vwap(df['high'], df['low'], df['close'], df['volume'])
    
    return df.dropna()
