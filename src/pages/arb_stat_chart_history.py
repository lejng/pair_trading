import pandas as pd
import streamlit as st
import plotly.graph_objects as go
from statsmodels.tsa.stattools import adfuller

from src.connectors.common_connector import CommonConnector
from src.connectors.swap.bybit_swap_connector import BybitSwapConnector
from src.helpers.spread_helper import get_execution_price

TITLE = "Stat Arbitrage Chart History"

# query param names
EXCHANGE_PARAM_KEY = "exchange"
TICKER_A_PARAM_KEY = "ticker_a"
TICKER_B_PARAM_KEY = "ticker_b"
TIMEFRAME_PARAM_KEY = "timeframe"
ENTRY_Z_PARAM_KEY = "entry_z"
TAKE_PROFIT_Z_PARAM_KEY = "take_profit_z"
STOP_LOSS_Z_PARAM_KEY = "stop_loss_z"

st.set_page_config(page_title=TITLE, layout="wide")

bybit_swap = BybitSwapConnector(False)
exchanges = {
    bybit_swap.get_exchange_name(): bybit_swap
}

def calculate_atr_percent(symbol_ohlcv, period=24):
    # 1. Расчет True Range (Истинный диапазон)
    # TR = max(High-Low, |High-PrevClose|, |Low-PrevClose|)
    symbol_ohlcv['h_l'] = symbol_ohlcv['high'] - symbol_ohlcv['low']
    symbol_ohlcv['h_pc'] = (symbol_ohlcv['high'] - symbol_ohlcv['close'].shift(1)).abs()
    symbol_ohlcv['l_pc'] = (symbol_ohlcv['low'] - symbol_ohlcv['close'].shift(1)).abs()

    symbol_ohlcv['tr'] = symbol_ohlcv[['h_l', 'h_pc', 'l_pc']].max(axis=1)

    # 2. Расчет ATR (как простое скользящее среднее от TR)
    # Можно использовать Wilder's MA, но обычное SMA для фильтрации нам за глаза
    symbol_ohlcv['atr'] = symbol_ohlcv['tr'].rolling(window=period).mean()

    # 3. Перевод в проценты
    last_atr = symbol_ohlcv['atr'].iloc[-1]
    last_close = symbol_ohlcv['close'].iloc[-1]

    if last_close == 0: return None

    atr_percent = (last_atr / last_close) * 100
    return round(atr_percent, 3)

def find_live_spread(_exchange: CommonConnector, _ticker_a: str, _ticker_b: str, mean, std, _amount_size_usd):
    orderbook_a = _exchange.get_order_book(_ticker_a)
    orderbook_b = _exchange.get_order_book(_ticker_b)

    price_a_buy = get_execution_price(orderbook_a, _amount_size_usd, 'buy')
    price_a_sell = get_execution_price(orderbook_a, _amount_size_usd, 'sell')
    price_b_buy = get_execution_price(orderbook_b, _amount_size_usd, 'buy')
    price_b_sell = get_execution_price(orderbook_b, _amount_size_usd, 'sell')

    slippage_a_pct = (price_a_buy - price_a_sell) / price_a_sell * 100
    slippage_b_pct = (price_b_buy - price_b_sell) / price_b_sell * 100

    live_short_spread = price_b_sell / price_a_buy
    live_short_z_score = (live_short_spread - mean) / std

    live_buy_spread = price_b_buy / price_a_sell
    live_buy_z_score = (live_buy_spread - mean) / std

    return {
        "live_short_spread": live_short_spread,
        "live_short_z_score": live_short_z_score,
        "live_long_spread": live_buy_spread,
        "live_long_z_score": live_buy_z_score,
        "slippage_a_pct": slippage_a_pct,
        "slippage_b_pct": slippage_b_pct
    }

# 3. Функция синхронизации URL
def update_url():
    """Записывает все значения из session_state в параметры URL"""
    st.query_params.update({
        EXCHANGE_PARAM_KEY: st.session_state[EXCHANGE_PARAM_KEY],
        TICKER_A_PARAM_KEY: st.session_state[TICKER_A_PARAM_KEY],
        TICKER_B_PARAM_KEY: st.session_state[TICKER_B_PARAM_KEY],
        TIMEFRAME_PARAM_KEY: st.session_state[TIMEFRAME_PARAM_KEY],
        ENTRY_Z_PARAM_KEY: st.session_state[ENTRY_Z_PARAM_KEY],
        TAKE_PROFIT_Z_PARAM_KEY: st.session_state[TAKE_PROFIT_Z_PARAM_KEY],
        STOP_LOSS_Z_PARAM_KEY: st.session_state[STOP_LOSS_Z_PARAM_KEY]
    })

# 4. Вспомогательная функция для получения индексов
def get_index_by_query_param(list_options, query_key, default=0):
    target = st.query_params.get(query_key)
    if target is None:
        return default
    try:
        return list_options.index(target)
    except (ValueError, KeyError):
        return default

def get_float_value_from_url(key: str, default: float = 0.0) -> float:
    url_value = st.query_params.get(key)
    if url_value is None:
        return default
    try:
        return float(url_value)
    except (ValueError, TypeError):
        return default

@st.fragment(run_every=5) # Обновление каждые 5 секунд
def show_live_spread_component(_selected_exchange, _ticker_a, _ticker_b, mean, std, _amount_size_usd, _entry_z):
    # live spread
    live_spread = find_live_spread(_selected_exchange, _ticker_a, _ticker_b, mean, std, _amount_size_usd)
    st.metric("Current Mean", f"{mean:.8f}")
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Current slippage A", f"{live_spread["slippage_a_pct"]:.8f} %")
        st.metric("Current slippage B", f"{live_spread["slippage_b_pct"]:.8f} %")
    with c2:
        st.metric("Current Short Z-Score", f"{live_spread["live_short_z_score"]:.8f}")
        st.metric("Current Short Spread", f"{live_spread["live_short_spread"]:.8f}")
    with c3:
        st.metric("Current Long Z-Score", f"{live_spread["live_long_z_score"]:.8f}")
        st.metric("Current Long Spread", f"{live_spread["live_long_spread"]:.8f}")

    if live_spread["live_short_z_score"] >= entry_z:
        st.write(f"Short spread (sell {ticker_b} and buy {ticker_a})")
        # here we can send notification or market orders
    if live_spread["live_long_z_score"] <= -entry_z:
        st.write(f"Buy spread (sell {ticker_a} and buy {ticker_b})")
        # here we can send notification or market orders

def show_stop_loss_and_take(mean, std, _stop_loss_z, _take_profit_z):
    for_open_long_stop = mean - _stop_loss_z * std
    for_open_long_take = mean - _take_profit_z * std
    st.write(f"For long spread, take {for_open_long_take:.8f}, stop {for_open_long_stop:.8f}")

    for_open_short_stop = mean + _stop_loss_z * std
    for_open_short_take = mean + _take_profit_z * std
    st.write(f"For short spread, take {for_open_short_take:.8f}, stop {for_open_short_stop:.8f}")

st.title(f"⚡ {TITLE}")

# columns on page
col1, col2, col3 = st.columns(3)
ex_list = list(exchanges.keys())

with col1:
    selected_exchange_name = st.selectbox(
        "Exchange",
        ex_list,
        index=get_index_by_query_param(ex_list, EXCHANGE_PARAM_KEY),
        key=EXCHANGE_PARAM_KEY, on_change=update_url
    )
    selected_exchange = exchanges[selected_exchange_name]
    all_symbols = selected_exchange.get_symbols()
    ticker_a = st.selectbox(
        "Ticker A",
        all_symbols, index=get_index_by_query_param(all_symbols, TICKER_A_PARAM_KEY, 0),
        key=TICKER_A_PARAM_KEY, on_change=update_url
    )
    ticker_b = st.selectbox(
        "Ticker B",
        all_symbols,
        index=get_index_by_query_param(all_symbols, TICKER_B_PARAM_KEY, 1),
        key=TICKER_B_PARAM_KEY, on_change=update_url
    )

with col2:
    tf_options = ["1m", "5m", "15m", "1h", "4h", "1d"]
    timeframe = st.selectbox("Timeframe", tf_options, index=get_index_by_query_param(tf_options, TIMEFRAME_PARAM_KEY, 3),
                             key=TIMEFRAME_PARAM_KEY, on_change=update_url)
    candle_limit = st.number_input("Candle limit", min_value=1, max_value=1000, value=500)
    ema_length = st.number_input("EMA length", min_value=1, max_value=1000, value=120)
with col3:
    entry_z = st.number_input("Entry Z", min_value=0.0, max_value=10.0, value=get_float_value_from_url(ENTRY_Z_PARAM_KEY, 2.0), key=ENTRY_Z_PARAM_KEY, on_change=update_url)
    take_profit_z = st.number_input("Exit Z (take profit)", min_value=0.0, max_value=10.0, value=get_float_value_from_url(TAKE_PROFIT_Z_PARAM_KEY, 0.5), key=TAKE_PROFIT_Z_PARAM_KEY, on_change=update_url)
    stop_loss_z = st.number_input("Stop Z (stop loss)", min_value=0.0, max_value=10.0, value=get_float_value_from_url(STOP_LOSS_Z_PARAM_KEY, 3.5), key=STOP_LOSS_Z_PARAM_KEY, on_change=update_url)

amount_size_usd = st.number_input("Trading amount", min_value=1, max_value=100000, value=500)

st.divider()

st.write(f"Short spread (sell {ticker_b} and buy {ticker_a}) when z-score >= {entry_z}")
st.write(f"Buy spread (sell {ticker_a} and buy {ticker_b}) when z-score < -{entry_z}")

st.divider()

if st.button("Load", use_container_width=True):
    try:
        # Load data
        a_ohlcv = selected_exchange.get_ohlcv(ticker_a, timeframe, candle_limit)
        b_ohlcv = selected_exchange.get_ohlcv(ticker_b, timeframe, candle_limit)

        atr_a = calculate_atr_percent(a_ohlcv)
        atr_b = calculate_atr_percent(b_ohlcv)

        a_ohlcv_key = f"{selected_exchange_name}_{ticker_a}"
        b_ohlcv_key = f"{selected_exchange_name}_{ticker_b}"

        df = pd.DataFrame({
            a_ohlcv_key: a_ohlcv['close'],
            b_ohlcv_key: b_ohlcv['close']
        }).dropna()

        # check if we have some trouble with synchronization candles
        loss_long = 1 - len(df) / len(a_ohlcv)
        loss_short = 1 - len(df) / len(b_ohlcv)
        max_loss = max(loss_long, loss_short)
        if max_loss > 0.1:
            st.warning(f"⚠️ Lost candles: {max_loss:.1%}")
            st.write("Long candles:", len(a_ohlcv))
            st.write("Short candles:", len(b_ohlcv))
            st.write("Merged candles:", len(df))
        # ---

        df['spread'] = df[b_ohlcv_key] / df[a_ohlcv_key]
        df['mean'] = df['spread'].ewm(span=ema_length, adjust=False).mean()
        # standard deviation
        df['std'] = df['spread'].ewm(span=ema_length, adjust=False).std()
        df['zscore'] = (df['spread'] - df['mean']) / df['std']
        df['upper_z'] = df['mean'] + entry_z * df['std']
        df['lower_z'] = df['mean'] - entry_z * df['std']
        df = df.dropna()

        # potential profit
        move_percent = (df['upper_z'].iloc[-1] / df['mean'].iloc[-1] - 1) * 100
        st.info(f"Spread movement potential (for Z-score coefficient {entry_z}): {move_percent:.2f}%")
        # current price
        st.info(f"price {ticker_a}: {df[a_ohlcv_key].iloc[-1]:.8f} | price {ticker_b}: {df[b_ohlcv_key].iloc[-1]:.8f}")

        # ATR info
        st.info(f"ATR for {ticker_a} is {atr_a}, ATR for {ticker_b} is {atr_b}")
        if atr_a and atr_b:
            atr_ratio = max(atr_a, atr_b) / min(atr_a, atr_b)
            if atr_ratio > 1.5:
                st.warning(f"Skip! Volatility gap is {atr_ratio:.2f} (exceeds 1.5 limit)")
            else:
                st.success(f"Clear! Volatility ratio is {atr_ratio:.2f}. Safe for 50/50 entry")

        adf_result = adfuller(df['spread'])
        t_statistic = adf_result[0]
        critical_values = adf_result[4]
        is_t_statistic_ok = t_statistic < critical_values['5%']
        p_value = adf_result[1]
        is_p_value_ok = p_value < 0.05
        p_value_message = f"P-value {p_value}, is ok: {is_p_value_ok}"
        if is_p_value_ok:
            st.success(p_value_message)
        else:
            st.warning(p_value_message)

        t_statistic_message = f"T-statistic {t_statistic:.4f}, critical (5%): {critical_values['5%']:.4f}, is ok: {is_t_statistic_ok}"
        if is_t_statistic_ok:
            st.success(t_statistic_message)
        else:
            st.warning(t_statistic_message)
        show_stop_loss_and_take(df['mean'].iloc[-1], df['std'].iloc[-1], stop_loss_z, take_profit_z)
        # live spread
        show_live_spread_component(selected_exchange, ticker_a, ticker_b, df['mean'].iloc[-1], df['std'].iloc[-1], amount_size_usd, entry_z)

        # example how to print dataframe
        #st.dataframe(df)

        # chart
        figure = go.Figure()
        figure.add_trace(go.Scatter(x=df.index, y=df['spread'], name='Spread', line=dict(color='blue')))
        figure.add_trace(go.Scatter(x=df.index, y=df['mean'], name='Mean', line=dict(color='orange')))
        figure.add_trace(go.Scatter(x=df.index, y=df['upper_z'], name='Upper Z', line=dict(color='green', dash='dash')))
        figure.add_trace(go.Scatter(x=df.index, y=df['lower_z'], name='Lower Z', line=dict(color='red', dash='dash')))
        figure.update_layout(
            title="Z-Score Deviation Chart B/A",
            xaxis_title="Time",
            yaxis_title="Value",
            height=600,
            template="plotly_white",
            hovermode="x unified"
        )
        st.plotly_chart(figure, use_container_width=True)

    except Exception as e:
        st.error(f"Error fetching data: {e}")