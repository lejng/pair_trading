import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from src.connectors.common_connector import CommonConnector
from src.connectors.swap.bybit_swap_connector import BybitSwapConnector
from src.helpers.spread_helper import get_execution_price

TITLE = "Stat Arbitrage Position Info"

# query param names
EXCHANGE_PARAM_KEY = "exchange"
TICKER_A_PARAM_KEY = "ticker_a"
TICKER_B_PARAM_KEY = "ticker_b"
ENTRY_A_PARAM_KEY = "entry_a"
ENTRY_B_PARAM_KEY = "entry_b"
TAKE_PARAM_KEY = "take"
STOP_PARAM_KEY = "stop"
AMOUNT_SIZE_USD_PARAM_KEY = "amount_size_usd"

st.set_page_config(page_title=TITLE, layout="wide")

bybit_swap = BybitSwapConnector(False)
exchanges = {
    bybit_swap.get_exchange_name(): bybit_swap
}

def find_live_spread(_exchange: CommonConnector, _ticker_a: str, _ticker_b: str, _amount_size_usd):
    orderbook_a = _exchange.get_order_book(_ticker_a)
    orderbook_b = _exchange.get_order_book(_ticker_b)

    price_a_buy = get_execution_price(orderbook_a, _amount_size_usd, 'buy')
    price_a_sell = get_execution_price(orderbook_a, _amount_size_usd, 'sell')
    price_b_buy = get_execution_price(orderbook_b, _amount_size_usd, 'buy')
    price_b_sell = get_execution_price(orderbook_b, _amount_size_usd, 'sell')

    slippage_a_pct = (price_a_buy - price_a_sell) / price_a_sell * 100
    slippage_b_pct = (price_b_buy - price_b_sell) / price_b_sell * 100

    live_short_spread = price_b_sell / price_a_buy

    live_buy_spread = price_b_buy / price_a_sell

    return {
        "live_short_spread": live_short_spread,
        "live_long_spread": live_buy_spread,
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
        ENTRY_A_PARAM_KEY: st.session_state[ENTRY_A_PARAM_KEY],
        ENTRY_B_PARAM_KEY: st.session_state[ENTRY_B_PARAM_KEY],
        TAKE_PARAM_KEY: st.session_state[TAKE_PARAM_KEY],
        STOP_PARAM_KEY: st.session_state[STOP_PARAM_KEY],
        AMOUNT_SIZE_USD_PARAM_KEY: st.session_state[AMOUNT_SIZE_USD_PARAM_KEY]
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
def show_live_spread_component(_selected_exchange, _ticker_a, _ticker_b, _amount_size_usd):
    # live spread
    live_spread = find_live_spread(_selected_exchange, _ticker_a, _ticker_b, _amount_size_usd)
    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Current slippage A", f"{live_spread['slippage_a_pct']:.8f} %")
        st.metric("Current slippage B", f"{live_spread['slippage_b_pct']:.8f} %")
    with c2:
        st.metric("Current Short Spread", f"{live_spread['live_short_spread']:.8f}")
        st.metric("Current Long Spread", f"{live_spread['live_long_spread']:.8f}")

st.title(f"⚡ {TITLE}")

ex_list = list(exchanges.keys())
selected_exchange_name = st.selectbox(
    "Exchange",
    ex_list,
    index=get_index_by_query_param(ex_list, EXCHANGE_PARAM_KEY),
    key=EXCHANGE_PARAM_KEY, on_change=update_url
)
amount_size_usd = st.number_input("Trading amount (for one leg)", min_value=1.0, max_value=100000.0, value=get_float_value_from_url(AMOUNT_SIZE_USD_PARAM_KEY, 100.0), key=AMOUNT_SIZE_USD_PARAM_KEY, on_change=update_url)

# columns on page
col1, col2 = st.columns(2)


with col1:
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
    timeframe = st.selectbox("Timeframe", ["1m", "5m", "15m", "1h", "4h", "1d"], index=0)
    candle_limit = st.number_input("Candle limit", min_value=1, max_value=1000, value=500)
with col2:
    entry_a = st.number_input("Entry A", min_value=0.000000000, max_value=100000000.0,
                            value=get_float_value_from_url(ENTRY_A_PARAM_KEY), format="%.8f",
                            key=ENTRY_A_PARAM_KEY, on_change=update_url
                            )
    entry_b = st.number_input("Entry B", min_value=0.000000000, max_value=100000000.0,
                            value=get_float_value_from_url(ENTRY_B_PARAM_KEY), format="%.8f",
                            key=ENTRY_B_PARAM_KEY, on_change=update_url
                            )
    take_profit = st.number_input("Take (take profit)", min_value=0.000000000, max_value=100000000.0,
                                  value=get_float_value_from_url(TAKE_PARAM_KEY), format="%.8f",
                                  key=TAKE_PARAM_KEY, on_change=update_url
                                  )
    stop_loss = st.number_input("Stop (stop loss)", min_value=0.000000000, max_value=100000000.0,
                                value=get_float_value_from_url(STOP_PARAM_KEY), format="%.8f",
                                key = STOP_PARAM_KEY, on_change = update_url
                                )

st.divider()

if st.button("Load", use_container_width=True):
    try:
        entry = entry_b / entry_a
        coins_a = amount_size_usd / entry_a
        coins_b = amount_size_usd / entry_b

        st.info(f"Recommended coins size for position {amount_size_usd} USDT is {ticker_a}: {coins_a:.8f} coins and {ticker_b}: {coins_b:.8f} coins")
        code_open_position = f"""
            OpenPositionInfo(
                ticker_a='{ticker_a}',
                ticker_b='{ticker_b}',
                coins_a={coins_a},
                coins_b={coins_b},
                #open_direction=Direction.SHORT,
                #open_direction=Direction.LONG,
            )
            """
        st.code(code_open_position, language='python')
        code_monitor_position = f"""
    PositionInfo(
        ticker_a='{ticker_a}',
        ticker_b='{ticker_b}',
        coins_a={coins_a},
        coins_b={coins_b},
        stop_loss_price={stop_loss},
        take_profit_price={take_profit},
        # close_direction=Direction.LONG,
        # close_direction=Direction.SHORT,
        is_closed=False
    )
                    """
        st.code(code_monitor_position, language='python')
        # Load data
        a_ohlcv = selected_exchange.get_ohlcv(ticker_a, timeframe, candle_limit)
        b_ohlcv = selected_exchange.get_ohlcv(ticker_b, timeframe, candle_limit)

        a_ohlcv_key = f"{selected_exchange_name}_{ticker_a}"
        b_ohlcv_key = f"{selected_exchange_name}_{ticker_b}"

        df = pd.DataFrame({
            a_ohlcv_key: a_ohlcv['close'],
            b_ohlcv_key: b_ohlcv['close']
        }).dropna()


        df['spread'] = df[b_ohlcv_key] / df[a_ohlcv_key]
        df = df.dropna()

        # live spread
        show_live_spread_component(selected_exchange, ticker_a, ticker_b, amount_size_usd)

        loss_when_trigger_stop = abs((stop_loss - entry) / entry * amount_size_usd)
        earn_when_trigger_take = abs((take_profit - entry) / entry * amount_size_usd)
        st.info(f"Loss when trigger stop: {loss_when_trigger_stop:.8f} USDT")
        st.info(f"Earn when trigger take: {earn_when_trigger_take:.8f} USDT")

        # example how to print dataframe
        #st.dataframe(df)

        # chart
        figure = go.Figure()
        figure.add_trace(go.Scatter(x=df.index, y=df['spread'], name='Spread', line=dict(color='blue')))
        figure.add_hline(y=entry, line_width=2, line_dash="dash", line_color="orange", annotation_text="entry point")
        figure.add_hline(y=stop_loss, line_width=2, line_dash="dash", line_color="red", annotation_text="stop loss")
        figure.add_hline(y=take_profit, line_width=2, line_dash="dash", line_color="green", annotation_text="take profit")

        figure.update_layout(
            title="Spread Chart B/A",
            xaxis_title="Time",
            yaxis_title="Value",
            height=600,
            template="plotly_white",
            hovermode="x unified",
            yaxis=dict(
                tickformat=".8f"  # 8 знаков после запятой
            )
        )
        st.plotly_chart(figure, use_container_width=True)

    except Exception as e:
        st.error(f"Error fetching data: {e}")