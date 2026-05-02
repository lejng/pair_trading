import streamlit as st
import ccxt
import pandas as pd
from ccxt import Exchange
from statsmodels.tsa.stattools import coint, adfuller

from src.connectors.swap.bybit_swap_connector import BybitSwapConnector
from src.helpers.logger import logger_instance

# --- Configuration ---
DEFAULT_SYMBOLS_FILTER = ['/USDT:USDT', '/USDC:USDC']  # Linear perpetuals
DEFAULT_MIN_DAILY_VOLUME = 1000000  # Minimum 24h volume in USDT
DEFAULT_LOOKBACK_PERIOD = 500  # Number of candles to analyze
DEFAULT_EMA_WINDOW = 120  # EMA period for the spread
DEFAULT_CROSSING_THRESHOLD = 20  # Minimum zero-crossings to consider the pair active
DEFAULT_MAX_SPREAD_PERCENT = 0.1
DEFAULT_Z_SCORE_OPEN_POSITION = 2.0

def fetch_eligible_tickers(exchange: Exchange, symbol_filters, min_volume_threshold, max_spread_threshold):
    """Fetch and filter symbols by volume and spread criteria."""
    st.info("Fetching tickers and filtering by volume...")
    exchange.load_markets()
    all_tickers = exchange.fetch_tickers()

    filtered_symbols = []
    for symbol, ticker_data in all_tickers.items():
        for symbol_suffix in symbol_filters:
            if symbol.endswith(symbol_suffix):
                daily_volume = ticker_data.get('quoteVolume', 0)
                if daily_volume >= min_volume_threshold:
                    bid_price = ticker_data.get('bid', 0)
                    ask_price = ticker_data.get('ask', 0)
                    if bid_price and ask_price:
                        spread_percentage = ((ask_price - bid_price) / ask_price) * 100
                        if spread_percentage <= max_spread_threshold:
                            filtered_symbols.append(symbol)

    st.success(f"Found {len(filtered_symbols)} symbols meeting criteria.")
    return filtered_symbols


def fetch_historical_prices(exchange: Exchange, symbol_list, time_frame, candle_limit):
    """Fetch historical price data for multiple symbols."""
    price_data = {}
    progress_bar = st.progress(0)
    
    for index, trading_symbol in enumerate(symbol_list):
        try:
            ohlcv_data = exchange.fetch_ohlcv(trading_symbol, timeframe=time_frame, limit=candle_limit)
            price_df = pd.DataFrame(ohlcv_data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
            price_data[trading_symbol] = price_df['close']
        except Exception as error:
            st.error(f"Error fetching {trading_symbol}: {error}")
        progress_bar.progress((index + 1) / len(symbol_list))
    
    return pd.DataFrame(price_data)


def analyze_cointegrated_pairs(price_dataframe, ema_period, min_crossings):
    """Analyze pairs for cointegration and mean reversion."""
    analysis_results = []
    available_symbols = price_dataframe.columns
    total_pairs = len(available_symbols)
    total_combinations = total_pairs * (total_pairs - 1) // 2
    
    st.info(f"Analyzing {total_combinations} possible combinations...")
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    pairs_analyzed = 0

    for first_index in range(total_pairs):
        for second_index in range(first_index + 1, total_pairs):
            first_symbol = available_symbols[first_index]
            second_symbol = available_symbols[second_index]
            
            pairs_analyzed += 1
            status_text.text(f"Analyzing pair {pairs_analyzed}/{total_combinations}: {first_symbol} - {second_symbol}")
            progress_bar.progress(pairs_analyzed / total_combinations)

            first_price_series = price_dataframe[first_symbol]
            second_price_series = price_dataframe[second_symbol]

            # Cointegration Test
            cointegration_score, cointegration_p_value, _ = coint(first_price_series, second_price_series)

            if cointegration_p_value < 0.05:  # Pair is cointegrated
                price_spread = first_price_series / second_price_series

                # Stationarity Test (ADF)
                adf_test_result = adfuller(price_spread)
                if adf_test_result[1] < 0.05:

                    # Mean reversion analysis via EMA
                    ema_spread_values = price_spread.ewm(span=ema_period).mean()
                    spread_deviation = price_spread - ema_spread_values
                    zero_crossings = ((spread_deviation.shift(1) * spread_deviation) < 0).sum()

                    if zero_crossings >= min_crossings:
                        # Z-Score calculation
                        rolling_mean_spread = price_spread.rolling(window=ema_period).mean()
                        rolling_std_spread = price_spread.rolling(window=ema_period).std()
                        z_score_values = (price_spread - rolling_mean_spread) / rolling_std_spread
                        latest_z_score = z_score_values.iloc[-1]

                        analysis_results.append({
                            'pair': f"{first_symbol} - {second_symbol}",
                            'p_value': round(cointegration_p_value, 4),
                            'adf_stat': round(adf_test_result[0], 2),
                            'crossings': zero_crossings,
                            'z_score': round(latest_z_score, 2)
                        })
    return analysis_results


def verify_pair_cointegration(exchange: Exchange, symbol_a, symbol_b, time_frame, candle_count):
    """Verify cointegration of a pair on a different exchange."""
    try:
        # Fetch historical data
        symbol_a_ohlcv = exchange.fetch_ohlcv(symbol_a, timeframe=time_frame, limit=candle_count)
        symbol_b_ohlcv = exchange.fetch_ohlcv(symbol_b, timeframe=time_frame, limit=candle_count)

        symbol_a_prices = pd.Series([candle[4] for candle in symbol_a_ohlcv])
        symbol_b_prices = pd.Series([candle[4] for candle in symbol_b_ohlcv])

        # Cointegration test
        cointegration_score, cointegration_p_value, _ = coint(symbol_a_prices, symbol_b_prices)

        return round(cointegration_p_value, 4)
    except Exception as error:
        logger_instance.error(f"Error verifying cointegration: {error}")
        return None

def calculate_pair_z_score(exchange: Exchange, symbol_a, symbol_b, time_frame, candle_count, window_size):
    """Calculate Z-score for a pair spread on specified exchange."""
    try:
        # Fetch price data
        symbol_a_ohlcv = exchange.fetch_ohlcv(symbol_a, timeframe=time_frame, limit=candle_count)
        symbol_b_ohlcv = exchange.fetch_ohlcv(symbol_b, timeframe=time_frame, limit=candle_count)

        symbol_a_close_prices = pd.Series([candle[4] for candle in symbol_a_ohlcv])
        symbol_b_close_prices = pd.Series([candle[4] for candle in symbol_b_ohlcv])

        price_spread = symbol_a_close_prices / symbol_b_close_prices
        spread_mean = price_spread.rolling(window=window_size).mean()
        spread_std = price_spread.rolling(window=window_size).std()
        z_score_values = (price_spread - spread_mean) / spread_std

        return round(z_score_values.iloc[-1], 2)
    except Exception as error:
        logger_instance.error(f"Error calculating Z-score: {error}")
        return f"Error: {error}"

# Streamlit page configuration
st.set_page_config(
    page_title="Arbitrage Statistical Screener",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Arbitrage Pair Screener")
st.markdown("Tool for finding cointegrated cryptocurrency pairs")

def perform_long_timeframe_analysis(exchange, symbol_list, time_frame, candle_limit, ema_period, min_crossings):
    """Perform analysis on long timeframe to find globally cointegrated pairs."""
    st.info(f"Step 2: Analyzing {time_frame} for global cointegration...")
    
    long_term_price_data = fetch_historical_prices(exchange, symbol_list, time_frame, candle_limit)
    long_term_price_data = long_term_price_data.dropna(axis=1)
    
    if long_term_price_data.empty:
        st.error("No historical data available for long timeframe.")
        st.stop()
    
    long_term_pairs = analyze_cointegrated_pairs(long_term_price_data, ema_period, min_crossings)
    
    if not long_term_pairs:
        st.warning("No cointegrated pairs found on long timeframe.")
        st.stop()
    
    st.success(f"Found {len(long_term_pairs)} cointegrated pairs on {time_frame}")
    return long_term_pairs

def perform_short_timeframe_validation(exchange, long_term_pairs, time_frame, candle_limit, ema_period, min_crossings):
    """Validate long-term pairs on short timeframe."""
    st.info(f"Step 3: Validating {len(long_term_pairs)} pairs on {time_frame}...")
    
    # Extract symbols needed for short timeframe analysis
    validation_symbols = set()
    for pair_data in long_term_pairs:
        symbol_a, symbol_b = pair_data['pair'].split(' - ')
        validation_symbols.update([symbol_a, symbol_b])
    
    short_term_price_data = fetch_historical_prices(exchange, list(validation_symbols), time_frame, candle_limit)
    short_term_price_data = short_term_price_data.dropna(axis=1)
    
    if short_term_price_data.empty:
        st.error("No historical data available for short timeframe.")
        st.stop()
    
    short_term_pairs = analyze_cointegrated_pairs(short_term_price_data, ema_period, min_crossings)
    return short_term_pairs

def compile_final_candidates(long_term_pairs, short_term_pairs):
    """Compile final candidate pairs from both timeframe analyses."""
    st.info("Step 4: Compiling final results...")
    
    final_candidates = []
    short_term_lookup = {pair['pair']: pair for pair in short_term_pairs}
    
    for long_term_pair in long_term_pairs:
        pair_identifier = long_term_pair['pair']
        if pair_identifier in short_term_lookup:
            short_term_pair = short_term_lookup[pair_identifier]
            
            final_candidates.append({
                'pair': pair_identifier,
                'p_val_long': long_term_pair['p_value'],
                'p_val_short': short_term_pair['p_value'],
                'crosses_long': long_term_pair['crossings'],
                'crosses_short': short_term_pair['crossings'],
                'z_short': short_term_pair['z_score'],
                'z_long': long_term_pair['z_score']
            })
    
    # Sort by combined p-value and crossings
    final_candidates.sort(key=lambda x: (x['p_val_long'] + x['p_val_short'], -x['crosses_short']))
    
    st.success(f"✅ Analysis complete! Found {len(final_candidates)} candidate pairs.")
    return final_candidates

def run_pair_analysis(symbol_filters,
                      min_volume_threshold,
                      candle_limit,
                      ema_period,
                      min_crossings,
                      short_timeframe,
                      long_timeframe):
    """Main analysis workflow for finding arbitrage pairs."""
    
    # Initialize exchanges
    bybit_exchange = BybitSwapConnector(False).get_exchange()
    
    # Step 1: Fetch eligible symbols
    st.info("Step 1: Fetching eligible symbols...")
    eligible_symbols = fetch_eligible_tickers(bybit_exchange, symbol_filters, min_volume_threshold, DEFAULT_MAX_SPREAD_PERCENT)
    
    if not eligible_symbols:
        st.error("No eligible symbols found.")
        st.stop()
    
    # Step 2: Long timeframe analysis
    long_term_pairs = perform_long_timeframe_analysis(
        bybit_exchange, eligible_symbols, long_timeframe, candle_limit, ema_period, min_crossings
    )

    short_term_pairs = long_term_pairs
    if not long_timeframe == short_timeframe:
        # Step 3: Short timeframe validation
        short_term_pairs = perform_short_timeframe_validation(
            bybit_exchange, long_term_pairs, short_timeframe, candle_limit, ema_period, min_crossings
        )
    
    # Step 4: Compile final results
    final_candidates = compile_final_candidates(long_term_pairs, short_term_pairs)
    
    return final_candidates

def calculate_summary_metrics(candidates_list, z_score_threshold):
    """Calculate summary statistics for analysis results."""
    total_pairs = len(candidates_list)
    trading_ready_pairs = sum(1 for pair in candidates_list 
                             if abs(pair['z_short']) >= z_score_threshold or 
                                abs(pair['z_long']) >= z_score_threshold)
    avg_p_value = None
    avg_crossings = None
    if total_pairs > 0:
        avg_p_value = sum(pair['p_val_long'] + pair['p_val_short'] for pair in candidates_list) / (2 * total_pairs)
        avg_crossings = sum(pair['crosses_short'] for pair in candidates_list) / total_pairs
    
    return total_pairs, trading_ready_pairs, avg_p_value, avg_crossings

def display_analysis_results(candidates_list, z_score_threshold):
    """Display comprehensive analysis results with metrics and tables."""
    st.header("📈 Analysis Results")
    
    # Calculate and display summary metrics
    total_pairs, trading_ready, avg_p_val, avg_cross = calculate_summary_metrics(candidates_list, z_score_threshold)
    
    metrics_col1, metrics_col2, metrics_col3, metrics_col4 = st.columns(4)
    with metrics_col1:
        st.metric("Total Pairs", total_pairs)
    with metrics_col2:
        st.metric("Trading Ready", trading_ready)
    with metrics_col3:
        st.metric("Avg P-Value", f"{avg_p_val:.4f}")
    with metrics_col4:
        st.metric("Avg Crossings", f"{avg_cross:.1f}")
    
    # Display all candidates with styling
    st.subheader("All Candidates")
    candidates_df = pd.DataFrame(candidates_list)
    
    def highlight_trading_opportunities(row):
        if (abs(row['z_short']) >= z_score_threshold or 
            abs(row['z_long']) >= z_score_threshold):
            return ['background-color: #ffcccc'] * len(row)
        return [''] * len(row)
    
    styled_candidates_df = candidates_df.style.apply(highlight_trading_opportunities, axis=1)
    st.dataframe(styled_candidates_df, use_container_width=True)

    st.subheader("Links for chart history")
    def make_link(row):
        symbols = row['pair'].split(' - ')
        url = f"/arb_stat_chart_history?ticker_a={symbols[1]}&ticker_b={symbols[0]}"
        return f'<a href="{url}" target="_blank">Open</a>'

    with_links = candidates_df.copy()
    with_links['Chart'] = with_links.apply(make_link, axis=1)
    st.markdown(
        with_links.to_html(escape=False, index=False),
        unsafe_allow_html=True
    )
    
    # Display trading ready pairs
    st.subheader("🎯 Trading Ready Pairs")
    ready_pairs = [pair for pair in candidates_list 
                  if abs(pair['z_short']) >= z_score_threshold or 
                     abs(pair['z_long']) >= z_score_threshold]
    
    if ready_pairs:
        ready_pairs_df = pd.DataFrame(ready_pairs)
        st.dataframe(ready_pairs_df, use_container_width=True)
    else:
        st.info("No pairs currently meet the Z-score threshold for trading.")
    
    return ready_pairs

def perform_binance_verification(candidates_list, exchange_connection, time_frame, candle_limit, window_size, z_score_threshold):
    """Verify analysis results against Binance exchange."""
    st.subheader("🔄 Binance Verification")
    
    with st.spinner("Verifying pairs with Binance..."):
        try:
            verification_data = []
            progress_tracker = st.progress(0)

            for index, candidate_pair in enumerate(candidates_list):
                bybit_z_score = candidate_pair['z_short']
                symbol_a, symbol_b = candidate_pair['pair'].split(' - ')

                binance_z_score = calculate_pair_z_score(
                    exchange_connection, symbol_a, symbol_b,
                    time_frame, candle_limit, window_size
                )
                
                binance_p_value = verify_pair_cointegration(
                    exchange_connection, symbol_a, symbol_b,
                    time_frame, candle_limit
                )
                
                bybit_p_value = candidate_pair['p_val_short']

                # Determine verification status
                verification_status = "WAIT"
                if isinstance(binance_z_score, float):
                    if abs(bybit_z_score) >= z_score_threshold and abs(binance_z_score) >= z_score_threshold and (bybit_z_score * binance_z_score > 0):
                        verification_status = "🔥 CONFIRMED"

                verification_data.append({
                    'pair': candidate_pair['pair'],
                    'z_bybit': bybit_z_score,
                    'z_binance': binance_z_score,
                    'p_val_bybit_short': bybit_p_value,
                    'p_val_binance_short': binance_p_value,
                    'status': verification_status
                })

                progress_tracker.progress((index + 1) / len(candidates_list))

            # Display verification results
            verification_df = pd.DataFrame(verification_data)

            def highlight_verified_pairs(row):
                if row['status'] == '🔥 CONFIRMED':
                    return ['background-color: #ccffcc'] * len(row)
                return [''] * len(row)

            styled_verification_df = verification_df.style.apply(highlight_verified_pairs, axis=1)
            st.dataframe(styled_verification_df, use_container_width=True)

            # Summary
            confirmed_pairs_count = sum(1 for result in verification_data if result['status'] == '🔥 CONFIRMED')
            st.success(f"✅ {confirmed_pairs_count} pairs confirmed by Binance!")

        except Exception as verification_error:
            st.error(f"❌ Error during Binance verification: {verification_error}")


# UI Parameters Section
#st.sidebar.header("Analysis Parameters")

# Symbol filters
symbol_filters_input = st.text_input(
    "Symbol Filters (comma-separated)",
    value=", ".join(DEFAULT_SYMBOLS_FILTER),
    help="Symbol suffixes to filter (e.g., /USDT:USDT, /USDC:USDC)"
)

# Numeric parameters
min_volume_input = st.number_input(
    "Min Daily Volume (USDT)",
    value=DEFAULT_MIN_DAILY_VOLUME,
    min_value=0,
    step=100000,
    help="Minimum 24h trading volume"
)

candle_limit_input = st.number_input(
    "Lookback Period (candles)",
    value=DEFAULT_LOOKBACK_PERIOD,
    min_value=50,
    max_value=2000,
    step=50,
    help="Number of historical candles to analyze"
)

ema_period_input = st.number_input(
    "EMA Window",
    value=DEFAULT_EMA_WINDOW,
    min_value=10,
    max_value=200,
    step=5,
    help="EMA period for spread calculation"
)

min_crossings_input = st.number_input(
    "Min Zero Crossings",
    value=DEFAULT_CROSSING_THRESHOLD,
    min_value=5,
    max_value=100,
    step=5,
    help="Minimum zero-crossings for active pairs"
)

z_score_threshold_input = st.number_input(
    "Z-Score Open Threshold",
    value=DEFAULT_Z_SCORE_OPEN_POSITION,
    min_value=0.5,
    max_value=5.0,
    step=0.1,
    help="Z-score threshold for opening positions"
)

# Timeframe selection
short_timeframe_input = st.selectbox(
    "Short Timeframe",
    options=["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "3d", "1w"],
    index=4,  # Default to "1h"
    help="Timeframe for short-term analysis"
)

long_timeframe_input = st.selectbox(
    "Long Timeframe",
    options=["1m", "5m", "15m", "30m", "1h", "2h", "4h", "1d", "3d", "1w"],
    index=7,  # Default to "1d"
    help="Timeframe for long-term analysis"
)

# Parse symbol filters
symbol_filters = [s.strip() for s in symbol_filters_input.split(",") if s.strip()]

# Simple search button
if st.button("🔍 Search Pairs", type="primary"):
    analysis_results = run_pair_analysis(
        symbol_filters=symbol_filters,
        min_volume_threshold=min_volume_input,
        candle_limit=candle_limit_input,
        ema_period=ema_period_input,
        min_crossings=min_crossings_input,
        short_timeframe=short_timeframe_input,
        long_timeframe=long_timeframe_input
    )
    
    # Display results immediately
    ready_trading_pairs = display_analysis_results(analysis_results, z_score_threshold_input)


    # Binance verification section
    #binance_connection = ccxt.binance({'options': {'defaultType': 'future'}})
    #perform_binance_verification(analysis_results, binance_connection, short_timeframe_input, candle_limit_input, ema_period_input, z_score_threshold_input)


